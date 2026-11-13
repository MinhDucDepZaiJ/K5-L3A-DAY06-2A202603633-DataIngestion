"""Run CP3 from starter: python scripts/run_cp3.py"""
import csv
import json
import sys
from pathlib import Path
from statistics import mean

STARTER = Path(__file__).resolve().parents[1]
ROOT = STARTER.parent
sys.path.insert(0, str(STARTER))
from src.ingestion import load_pdf
from src.chunking import fixed_size, by_paragraph

pdfs = list((STARTER / "data").glob("*.pdf")) + list((ROOT / "data").glob("*.pdf"))
if not pdfs:
    raise SystemExit("ERROR: Put aimlBook_30_trang.pdf in starter/data/ or ../data/")
if len(pdfs) != 1:
    raise SystemExit(f"ERROR: expected exactly one PDF, found {len(pdfs)}: {pdfs}")
pdf = pdfs[0]
pages = load_pdf(pdf, "aimlBook_30_trang", str(pdf.relative_to(STARTER)) if pdf.is_relative_to(STARTER) else str(pdf))
out = ROOT / "artifacts" / "cp3"
out.mkdir(parents=True, exist_ok=True)
errors = [{"page": p.page, "error": p.metadata["extraction_error"], "empty": p.metadata["empty"], "characters": len(p.text)} for p in pages if p.metadata["extraction_error"] or p.metadata["empty"]]
(out / "page_audit.json").write_text(json.dumps({"total_pages": len(pages), "issues": errors}, indent=2), encoding="utf-8")
configs = {"fixed": [c for p in pages for c in fixed_size(p, 800, 120)], "paragraph": [c for p in pages for c in by_paragraph(p, 800)]}
for name, chunks in configs.items():
    with (out / f"chunks_{name}.jsonl").open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps({"chunk_id": c.chunk_id, "document_id": c.document_id, "source": c.source, "page": c.page, "text": c.text, "metadata": c.metadata}, ensure_ascii=False) + "\n")
    lengths = [len(c.text) for c in chunks]
    print(f"{name}: {len(chunks)} chunks; min={min(lengths)} max={max(lengths)} avg={mean(lengths):.1f}")
    assert all(c.document_id and c.source and 1 <= c.page <= len(pages) and c.metadata["section"] for c in chunks)
    assert all(len(c.text) <= 800 for c in chunks)
print(f"PDF: {pdf.name} | pages={len(pages)} | empty/error pages={len(errors)}")
print(f"CP3 PASS: output in {out}" if len(pages) >= 30 and not errors else "CP3 REVIEW: inspect page_audit.json")
