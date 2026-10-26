"""Bound fuller article answers within the existing 2048 output token ceiling."""


def news_limits(evidence):
    article = any(item.get('verification_basis') == 'FEED_SNAPSHOT_BINDING'
                  and item.get('snapshot', {}).get('content') for item in evidence.values())
    # More short facts, rather than two compound sentences with oversized quotes.
    return (4, 600, 600) if article else (2, 450, 300)


def present_news(draft, evidence, scope):
    """Group the validated facts by article; leave claims and sources untouched."""
    if scope.get('source_type') != 'NEWS' or news_limits(evidence)[0] != 4:
        return draft
    numbers = {item['evidence_id']: item['citation_number'] for item in draft['citations']}
    groups = {}
    for claim in draft['claims']:
        eid = claim['evidence_ids'][0]
        groups.setdefault(eid, []).append(f"• {claim['text']} [{numbers[eid]}]")
    draft['draft'] = '\n\n'.join(evidence[eid]['title']+'\n'+'\n'.join(points)
                                 for eid, points in groups.items())
    return draft
