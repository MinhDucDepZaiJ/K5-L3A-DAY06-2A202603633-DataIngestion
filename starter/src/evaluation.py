"""Conservative automatic evidence scoring; human labels remain separate."""
import re
from collections import defaultdict

def norm(text):
    return re.sub(r'\s+', ' ', str(text)).strip().casefold()

def evaluate_query(question, hits):
    gold_page = int(question.get('physical_page', question.get('gold_page')))
    gold_source = question.get('source_id', question.get('gold_source_id'))
    evidence = norm(question.get('evidence', question.get('evidence_quote', '')))
    annotated = []
    for rank, hit in enumerate(hits, 1):
        page_match = int(hit['page']) == gold_page and (hit.get('document_id') == gold_source or hit.get('source') == gold_source)
        evidence_match = bool(evidence) and evidence in norm(hit.get('text', ''))
        annotated.append({**hit, 'rank': rank, 'page_match': page_match,
                          'evidence_exact_match': evidence_match,
                          'automatic_evidence_hit': page_match and evidence_match})
    return {'question_id': question['question_id'], 'split': question['split'],
            'question': question['question'], 'gold_source_id': gold_source,
            'gold_page': gold_page, 'evidence': question.get('evidence', ''),
            'hit_at_1': int(bool(annotated) and annotated[0]['automatic_evidence_hit']),
            'hit_at_3': int(any(x['automatic_evidence_hit'] for x in annotated[:3])),
            'page_hit_at_1': int(bool(annotated) and annotated[0]['page_match']),
            'page_hit_at_3': int(any(x['page_match'] for x in annotated[:3])),
            'hits': annotated}

def summarize(traces):
    groups = defaultdict(list)
    for t in traces:
        groups[(t['strategy'], t['split'])].append(t)
    result = []
    for (strategy, split), group in sorted(groups.items()):
        n = len(group)
        result.append({'strategy': strategy, 'split': split, 'n': n,
                       **{key: {'count': sum(x[key] for x in group), 'rate': round(sum(x[key] for x in group)/n, 4)}
                          for key in ('hit_at_1','hit_at_3','page_hit_at_1','page_hit_at_3')}})
    return result
