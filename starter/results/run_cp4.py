"""Run from starter: .\\.venv\\Scripts\\python.exe scripts/run_cp4.py"""
import json, os, sys, time
from pathlib import Path
from dotenv import load_dotenv
STARTER=Path(__file__).resolve().parents[1]
ROOT=STARTER.parent
sys.path.insert(0,str(STARTER))
from src.models import Chunk
from src.embeddings import MyEmbedder
from src.store import PgVectorStore
load_dotenv(STARTER/'.env')
url=os.getenv('DATABASE_URL')
if not url:
    raise SystemExit('DATABASE_URL missing in starter/.env')
files={'A':'chunks_fixed.jsonl','B':'chunks_paragraph.jsonl'}
chunks={}
for strategy, filename in files.items():
    path=ROOT/'artifacts'/'cp3'/filename
    if not path.exists():
        raise SystemExit(f'Missing {path}; run CP3 first')
    rows=[json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s.strip()]
    chunks[strategy]=[Chunk(**{k:r[k] for k in ('chunk_id','document_id','source','page','text','metadata')}) for r in rows]
    print(f'{strategy}: loaded {len(rows)} chunks',flush=True)
model=os.getenv('EMBEDDING_MODEL') or 'sentence-transformers/all-MiniLM-L6-v2'
t0=time.perf_counter()
embedder=MyEmbedder(model)
print(f'Embedding model: {embedder.model_name} | dimensions={embedder.dimensions}',flush=True)
store=PgVectorStore(url,embedder.dimensions)
store.create_schema()
# C uses the same B chunks and embeddings, but applies question-supplied metadata filters at query time.
for strategy in ('A','B'):
    t=time.perf_counter()
    vectors=embedder.embed_documents([c.text for c in chunks[strategy]])
    store.upsert(strategy,chunks[strategy],vectors)
    print(f'{strategy}: indexed {store.count(strategy)} chunks in {time.perf_counter()-t:.1f}s',flush=True)
# C: physical copy of B for an independently queryable strategy; identical vectors.
store.upsert('C',chunks['B'],embedder.embed_documents([c.text for c in chunks['B']]))
print(f'C: indexed {store.count("C")} chunks (same as B)',flush=True)
question='What is narrow artificial intelligence?'
qvec=embedder.embed_query(question)
output={}
for strategy in ('A','B','C'):
    results=store.search(strategy,qvec,top_k=3,filters={'section':'Chapter 1'} if strategy=='C' else None)
    output[strategy]=results
    print(f'{strategy}: top-3 pages {[r["page"] for r in results]}',flush=True)
    assert len(results)==3
assert store.count('A')==len(chunks['A'])
assert store.count('B')==store.count('C')==len(chunks['B'])
out=ROOT/'artifacts'/'cp4';out.mkdir(parents=True,exist_ok=True)
(out/'smoke_retrieval.json').write_text(json.dumps({'question':question,'model':model,'dimensions':embedder.dimensions,'results':output},ensure_ascii=False,indent=2),encoding='utf-8')
print(f'CP4 PASS: PostgreSQL + real embeddings; output={out}; elapsed={time.perf_counter()-t0:.1f}s')
