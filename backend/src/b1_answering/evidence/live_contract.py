"""Version 1.1 evidence binds an exact chunk to a verified DB source locator."""
import hashlib
import math
import re
import uuid
import unicodedata


def reporting_entity_matches(header, expected):
    """Read the explicit reporting-scope field; 'riêng quý' is a period basis."""
    if expected == 'UNKNOWN':
        return True
    norm = ''.join(c for c in unicodedata.normalize('NFD', header.lower().replace('đ', 'd'))
                   if unicodedata.category(c) != 'Mn')
    match = re.search(r'\b(?:pham vi|reporting_entity)\s*:\s*([^|\n]+)', norm)
    values = {'PARENT': {'parent', 'parent_only', 'separate', 'rieng', 'bao cao rieng', 'cong ty me'},
              'CONSOLIDATED': {'consolidated', 'hop nhat'}}
    return bool(match and match[1].strip() in values.get(expected, set()))


def validate_live_item(item):
    from .citations import CitationError
    from ...documents.chunk_reconstruction import _metadata, ReconstructionError
    try:
        for key in ('evidence_id', 'chunk_id', 'source_id'):
            uuid.UUID(item[key])
        if item.get('source_verified') is not True:
            raise ValueError('unverified source')
        content_hash = item.get('content_sha256')
        if (not isinstance(content_hash, str) or not re.fullmatch('[a-f0-9]{64}', content_hash)
                or hashlib.sha256(item['passage'].encode('utf-8')).hexdigest() != content_hash):
            raise ValueError('content mismatch')
        locator, meta = _metadata(item['locator'])
        if (item.get('source_type') != {'financial_reports': 'BCTC', 'news_articles': 'NEWS'}.get(locator.get('source_table'))
                or locator.get('source_table') not in ('financial_reports', 'news_articles')
                or meta['content_hash'] != content_hash
                or len(locator['row_keys']) > 1000
                or any(not isinstance(k, str) or not k for k in locator['row_keys'])):
            raise ValueError('invalid source locator')
        score = item.get('score')
        if (not isinstance(score, dict) or score.get('type') not in ('COSINE_SIMILARITY', 'RRF')
                or type(score.get('value')) not in (int, float)
                or not math.isfinite(score['value'])):
            raise ValueError('invalid ranking score')
        if ((score['type'] == 'COSINE_SIMILARITY' and not -1 <= score['value'] <= 1)
                or (score['type'] == 'RRF' and score['value'] <= 0)):
            raise ValueError('ranking score out of range')
    except (KeyError, ValueError, TypeError, AttributeError, ReconstructionError):
        raise CitationError('INVALID_EVIDENCE') from None
