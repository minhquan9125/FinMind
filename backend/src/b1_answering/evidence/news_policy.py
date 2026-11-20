"""Bound fuller article answers within the existing 2048 output token ceiling."""


def full_article(item):
    return bool((item.get('verification_basis') == 'FEED_SNAPSHOT_BINDING'
                 and item.get('snapshot', {}).get('content'))
        or (item.get('source_type') == 'NEWS' and item.get('source_verified') is True
            and item.get('locator', {}).get('source_table') == 'news_articles'))


def news_limits(evidence):
    article = any(full_article(item) for item in evidence.values())
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
        item=evidence[eid]
        article=item.get('source_url') or item.get('locator',{}).get('url') or item.get('source_id') or eid
        group=groups.setdefault(article,{'title':item['title'],'points':[]})
        group['points'].append(f"• {claim['text']} [{numbers[eid]}]")
    draft['draft'] = '\n\n'.join(group['title']+'\n'+'\n'.join(group['points'])for group in groups.values())
    return draft
