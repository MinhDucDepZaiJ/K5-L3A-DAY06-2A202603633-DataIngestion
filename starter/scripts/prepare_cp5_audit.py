"""Generate blank, trace-grounded manual audit sheets; does not invent human ratings."""
import argparse,csv,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--split',choices=['dev','test'],default='test');a=p.parse_args()
root=Path(__file__).resolve().parents[2]; out=root/'artifacts'/'cp5';path=out/f'traces_{a.split}.json'
if not path.exists():raise SystemExit(f'Missing {path}; run run_cp5.py --split {a.split} first')
traces=json.loads(path.read_text(encoding='utf8'))
# Coherence: fixed ten page locations chosen without reading scores; sample same pages for A and B.
if a.split=='dev':
    pages=sorted({t['gold_page'] for t in traces})[:10]
    rows=[]
    for strategy in 'AB':
        for page in pages:
            hits=[h for t in traces if t['strategy']==strategy for h in t['hits'] if h['page']==page]
            hit=next(iter(hits),None)
            rows.append({'strategy':strategy,'page':page,'chunk_id':hit['chunk_id'] if hit else '',
                         'text_excerpt':hit['text'][:350] if hit else 'NOT IN RETRIEVED TOP3; inspect indexed chunk manually',
                         'coherence_0_1_2':'','reason':''})
    with (out/'manual_coherence_dev.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
else:
    grounding=[]; metadata=[]
    for t in traces:
        grounding.append({'question_id':t['question_id'],'strategy':t['strategy'],
            'gold_page':t['gold_page'],'top3_pages':','.join(str(h['page']) for h in t['hits']),
            'evidence_hit3_automatic':t['hit_at_3'],'grounding_0_1_2':'','reason':''})
        for h in t['hits']:
            metadata.append({'question_id':t['question_id'],'strategy':t['strategy'],'rank':h['rank'],
                'chunk_id':h['chunk_id'],'document_id':h['document_id'],'source':h['source'],
                'page':h['page'],'section':h['section'],'metadata_correct_0_1':'','reason':''})
    for filename,rows in [('manual_grounding_test.csv',grounding),('manual_metadata_test.csv',metadata)]:
        with (out/filename).open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
print('Blank manual audit templates created in',out)
