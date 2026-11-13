"""Checkpoint 1: inspect local PDFs and write an auditable page manifest."""
import json
from datetime import date
from pathlib import Path
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'starter' / 'data'
OUT = ROOT / 'data' / 'manifest.json'

def main():
    pdfs = sorted(DATA.glob('*.pdf'))
    if not pdfs:
        print('NOT READY: no PDF in starter/data/. Add a legally usable PDF with >=30 content pages.')
        return 1
    sources = []
    total = 0
    for path in pdfs:
        reader = PdfReader(str(path))
        pages = []
        for i, page in enumerate(reader.pages, 1):
            try:
                txt = ' '.join((page.extract_text() or '').split())
                n = len(txt)
                pages.append({'page_id': f'{path.stem}:p{i}', 'physical_page': i, 'characters': n,
                              'candidate_content_page': n >= 150})
            except Exception as exc:
                pages.append({'page_id': f'{path.stem}:p{i}', 'physical_page': i,
                              'characters': 0, 'candidate_content_page': False, 'error': str(exc)})
        candidate = sum(p['candidate_content_page'] for p in pages)
        total += candidate
        sources.append({'source_id': path.stem, 'title': path.stem,
                        'source_path_or_url': f'starter/data/{path.name}',
                        'license_or_permission': 'TODO: verify source license before submission',
                        'accessed_at': date.today().isoformat(),
                        'physical_page_count': len(pages), 'candidate_content_page_count': candidate,
                        'pages': pages})
        print(f'{path.name}: {len(pages)} physical pages, {candidate} candidate content pages')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({'counting_rule': 'Candidate pages have >=150 extracted characters; manually exclude cover, TOC, references, blank and irrelevant pages.', 'sources': sources}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Candidate pages: {total}; manifest: {OUT}')
    print('READY FOR MANUAL REVIEW' if total >= 30 else 'NOT READY: fewer than 30 candidate pages')
    return 0 if total >= 30 else 1

if __name__ == '__main__':
    raise SystemExit(main())
