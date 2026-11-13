import json, pathlib, collections, sys
p=pathlib.Path(__file__).resolve().parents[1]/"benchmark"/"questions.jsonl"
rows=[json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
assert len(rows)==20, f"Expected 20 questions, got {len(rows)}"
assert len({r["question_id"] for r in rows})==20
assert collections.Counter(r["split"] for r in rows)=={"dev":15,"test":5}
assert all(r["evidence"] and r["reference_answer"] and r["question"] for r in rows)
assert all(1<=r["physical_page"]<=30 and r["page_id"]==f'aimlBook_30_trang:p{r["physical_page"]}' for r in rows)
print("CP2 PASS: 20 questions | dev=15 | test=5 | evidence and page metadata present")
