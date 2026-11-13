"""PDF ingestion preserving physical page provenance."""
from pathlib import Path
import re
import unicodedata
from pypdf import PdfReader
from .models import DocumentPage


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\t\f\v ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    reader = PdfReader(str(path))
    pages = []
    for i, p in enumerate(reader.pages, 1):
        try:
            raw = p.extract_text(extraction_mode="layout") or ""
            error = None
        except Exception as exc:
            raw, error = "", f"{type(exc).__name__}: {exc}"
        text = normalize_text(raw)
        pages.append(DocumentPage(document_id=document_id, source=source, page=i,
            text=text, metadata={"page_id": f"{document_id}:p{i}", "extraction_error": error,
            "empty": not bool(text), "char_count": len(text)}))
    return pages
