"""Run from starter: .\\.venv\\Scripts\\python.exe scripts/run_cp5.py --split dev"""
import argparse, csv, json, os, sys
from pathlib import Path
from dotenv import load_dotenv
STARTER = Path(__file__).resolve().parents[1]
ROOT = STARTER.parent
sys.path.insert(0, str(STARTER))
from src.embeddings import MyEmbedder
from src.store import PgVectorStore
from src.evaluation import evaluate_query, summarize

parser = argparse.ArgumentParser()
parser.add_argument('--split', choices=['dev','test','all'], default='dev')
args = parser.parse_args()
load_dotenv(STARTER / '.env')
questions_path = STARTER / 'benchmark' / 'questions.jsonl'
if not questions_path.exists():
    raise SystemExit(f'Missing benchmark: {questions_path}')
questions = [json.loads(line) for line in questions_path.read_text(encoding='utf-8').splitlines() if line.strip()]
# Validate all benchmark filters before selecting the split.
allowed_filters = {'section', 'document_id', 'source', 'page'}
for q in questions:
    flt = q.get('filter')
    if flt is not None:
        if not isinstance(flt, dict) or not flt or set(flt) - allowed_filters:
            raise ValueError(f'Invalid metadata filter in {q["question_id"]}: {flt}')
        if 'section' in flt and flt['section'] not in ('Chapter 1', 'Chapter 2'):
            raise ValueError(f'Unexpected section filter in {q["question_id"]}')
        if 'section' in flt:
            expected_section = 'Chapter 1' if q['physical_page'] <= 23 else 'Chapter 2'
            if flt['section'] != expected_section:
                raise ValueError(f'Filter conflicts with documented source page in {q["question_id"]}')
questions = [q for q in questions if args.split == 'all' or q['split'] == args.split]
if not questions:
    raise SystemExit('No questions in selected split')
url = os.getenv('DATABASE_URL')
if not url:
    raise SystemExit('Missing DATABASE_URL in starter/.env')
embedder = MyEmbedder(os.getenv('EMBEDDING_MODEL') or 'sentence-transformers/all-MiniLM-L6-v2')
store = PgVectorStore(url, embedder.dimensions)
for strategy in 'ABC':
    if store.count(strategy) == 0:
        raise SystemExit(f'No indexed chunks for strategy {strategy}; run CP4 first')
output_dir = ROOT / 'artifacts' / 'cp5'
output_dir.mkdir(parents=True, exist_ok=True)
traces = []
for q in questions:
    vec = embedder.embed_query(q['question'])
    for strategy in 'ABC':
        # Do not use gold page/source to create filters. Only question-authored filters are allowed.
        filters = q.get('filter') if strategy == 'C' else None
        if filters is not None and not isinstance(filters, dict):
            raise ValueError(f'Invalid filter in {q["question_id"]}')
        hits = store.search(strategy, vec, top_k=3, filters=filters)
        trace = evaluate_query(q, hits)
        trace.update({'strategy': strategy, 'filter_applied': filters,
                      'filter_compliant': (all(all(h.get(k) == v for k,v in filters.items()) for h in hits) if filters else None)})
        traces.append(trace)
        print(f'{q["question_id"]} {strategy} | gold={trace["gold_page"]} | top3={[h["page"] for h in hits]} | evidence@3={trace["hit_at_3"]}')
summary = summarize(traces)
(output_dir / f'traces_{args.split}.json').write_text(json.dumps(traces, ensure_ascii=False, indent=2), encoding='utf-8')
(output_dir / f'summary_{args.split}.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
with (output_dir / f'summary_{args.split}.csv').open('w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['strategy','split','questions','evidence_hit1','evidence_hit3','page_hit1','page_hit3'])
    for s in summary:
        w.writerow([s['strategy'],s['split'],s['n'],*[f'{s[k]["count"]}/{s["n"]} ({s[k]["rate"]:.1%})' for k in ('hit_at_1','hit_at_3','page_hit_at_1','page_hit_at_3')]])
print('\nSUMMARY (strict exact evidence; page-hit shown separately)')
for s in summary:
    print(f'{s["strategy"]} {s["split"]}: evidence@1={s["hit_at_1"]["count"]}/{s["n"]}, evidence@3={s["hit_at_3"]["count"]}/{s["n"]}, page@3={s["page_hit_at_3"]["count"]}/{s["n"]}')
print(f'CP5 {args.split} automated evaluation complete: {output_dir}')
print('NOTE: Manual coherence, grounding, and metadata correctness audit still required.')
filter_questions = [q for q in questions if q.get('filter')]
if filter_questions:
    print(f'Filter questions: {len(filter_questions)}; C compliance: '
          f'{sum(all(h.get(k) == v for k, v in q["filter"].items()) for t in traces for q in filter_questions if t["strategy"] == "C" and t["question_id"] == q["question_id"] for h in t["hits"])} checked hits')
if not any(q.get('filter') for q in questions):
    print('WARNING: No question-authored filters in this split; C behaves identically to B. Filter compliance N/A.')
