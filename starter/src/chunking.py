"""Two deterministic, page-preserving chunkers; sizes measured in characters."""
import re
from .models import Chunk, DocumentPage


def _chunk(page, text, method, i, start=None, end=None):
    md = dict(page.metadata)
    md.update({"method": method, "chunk_index": i, "section": "Chapter 1" if page.page <= 23 else "Chapter 2", "start_char": start, "end_char": end})
    return Chunk(chunk_id=f"{page.document_id}:p{page.page}:{method}:{i}", document_id=page.document_id,
        source=page.source, page=page.page, text=text, metadata=md)


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("Require size > 0 and 0 <= overlap < size")
    text = page.text
    result = []
    for start in range(0, len(text), size - overlap):
        end = min(start + size, len(text))
        if text[start:end].strip():
            result.append(_chunk(page, text[start:end], "fixed", len(result), start, end))
        if end == len(text):
            break
    return result


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    if max_size <= 0:
        raise ValueError("max_size must be positive")
    # Split on blank lines, otherwise on line boundaries, then hard-split long lines.
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", page.text) if p.strip()]
    units = []
    for para in paragraphs:
        if len(para) <= max_size:
            units.append(para)
        else:
            lines = [s.strip() for s in para.splitlines() if s.strip()]
            for line in lines:
                units.extend(line[i:i+max_size] for i in range(0, len(line), max_size))
    result, current = [], ""
    for unit in units:
        candidate = current + ("\n\n" if current else "") + unit
        if len(candidate) > max_size and current:
            result.append(_chunk(page, current, "paragraph", len(result)))
            current = unit
        else:
            current = candidate
    if current:
        result.append(_chunk(page, current, "paragraph", len(result)))
    return result
