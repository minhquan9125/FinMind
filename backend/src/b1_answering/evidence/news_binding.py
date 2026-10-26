"""Repair a valid article reference whose teaser quote omits its numeric facts.

No claim rewriting, new sources, generation retry or B3 semantic verification.
Only exact sentences from the same verified, provided article may replace a quote.
"""
from copy import deepcopy
import re

from .citations import CitationError
from .grounded import _check_facts, _facts, _numbers, _units
from .news_policy import news_limits


def _signature(text):
    return ({'number:'+v for v in _numbers(text)} | {'unit:'+v for v in _units(text)}
            | {'acronym:'+v for v in re.findall(r'\b[A-ZĐ]{2,}\b', text)})


def _supporting_quotes(item, claim_text, scope, max_quote, max_quotes):
    text = item['passage'][:8500]
    needed = _signature(claim_text)-_signature(_facts(item, [], scope))
    sentences = list(re.finditer(r'[^.!?\n]+(?:[.!?]|(?=\n|$))', text))
    windows = []
    for index, start in enumerate(sentences):
        for end in sentences[index:index+3]:
            quote = text[start.start():end.end()].strip()
            if len(quote) > max_quote: break
            if quote: windows.append(quote)
    # Long sentences may still contain a short exact span supporting the fact.
    for word in re.finditer(r'\S+', text):
        quote = text[word.start():word.start()+max_quote]
        if word.start()+max_quote < len(text): quote = quote.rsplit(' ', 1)[0]
        if quote.strip(): windows.append(quote.strip())
    by_coverage = {}
    for quote in windows:
        coverage = frozenset(_signature(quote) & needed)
        if needed and not coverage: continue
        if coverage not in by_coverage or len(quote) < len(by_coverage[coverage]):
            by_coverage[coverage] = quote
        try:
            _check_facts(claim_text, _facts(item, [quote], scope))
            return [quote]
        except CitationError:
            pass
    if max_quotes < 2: return None
    choices = sorted(by_coverage.items(), key=lambda pair: (-len(pair[0]), len(pair[1])))[:60]
    for index, (covered, first) in enumerate(choices):
        for other, second in choices[index+1:]:
            if not needed.issubset(covered | other): continue
            try:
                _check_facts(claim_text, _facts(item, [first, second], scope))
                return [first, second]
            except CitationError:
                pass
    return None


def bind_article_quotes(payload, evidence, scope):
    if scope.get('source_type') != 'NEWS' or not isinstance(payload, dict): return None
    claims = payload.get('claims')
    max_claims, max_text, max_quote = news_limits(evidence)
    max_quotes = 2 if max_claims == 4 else 1
    if not isinstance(claims, list) or not 1 <= len(claims) <= max_claims: return None
    candidate, changes = deepcopy(payload), []
    for claim in candidate['claims']:
        if not isinstance(claim, dict): return None
        ids, quotes = claim.get('evidence_ids'), claim.get('support_quotes')
        if not isinstance(ids, list) or len(ids) != 1 or not isinstance(ids[0], str): return None
        item = evidence.get(ids[0])
        if (not item or item.get('verification_basis') != 'FEED_SNAPSHOT_BINDING'
                or not item.get('snapshot', {}).get('content')
                or not isinstance(claim.get('text'), str) or len(claim['text']) > max_text
                or not isinstance(quotes, list) or not 1 <= len(quotes) <= max_quotes): return None
        originals = []
        for original in quotes:
            if (not isinstance(original, dict) or original.get('evidence_id') != ids[0]
                    or not isinstance(original.get('quote'), str) or not original['quote'].strip()
                    or len(original['quote']) > 1200 or original['quote'] not in item['passage']): return None
            originals.append(original['quote'])
        try:
            _check_facts(claim['text'], _facts(item, originals, scope))
            if all(len(quote) <= max_quote for quote in originals): continue
        except CitationError:
            pass
        replacement = _supporting_quotes(item, claim['text'], scope, max_quote, max_quotes)
        if replacement is None: return None
        changes.append({'evidence_id': ids[0], 'original_quote': '\n'.join(originals),
                        'bound_quote': '\n'.join(replacement), 'bound_quotes': replacement})
        claim['support_quotes'] = [{'evidence_id': ids[0], 'quote': quote} for quote in replacement]
    return (candidate, changes) if changes else None
