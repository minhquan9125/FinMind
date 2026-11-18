"""Select reusable slots from explicit wording; never infer from full history."""
import copy
import re
from .retrieval_flow.intent import _fold
from .input_normalization import registered_symbols
from .market_dialogue import article_content_request


def question_context(question, context, today):
    if not context:
        return context
    norm = _fold(question).strip(' .?!')
    # Slot replies intentionally continue the previous request.
    if re.fullmatch(r'(?:(?:the )?con |nam |quy )?(?:[a-z]{3}|\d{1,4})(?: thi sao)?', norm):
        return copy.deepcopy(context)
    if (re.search(r'\bgiu (?:nguyen )?(?:chi tieu|ky)\b', norm)
            or re.match(r'^(?:the )?con\b', norm)):
        return copy.deepcopy(context)
    source = None
    if article_content_request(question, today) or re.search(r'\b(?:tin tuc|news)\b', norm):
        source = 'NEWS'
    elif re.search(r'\b(?:bctn|bao cao thuong nien)\b', norm):
        source = 'BCTN'
    elif (re.search(r'\b(?:bctc|bao cao tai chinh|doanh thu|loi nhuan|tong tai san|no phai tra)\b', norm)
          and not (context.get('source_type')=='BCTN' and not re.search(r'\bbctc|bao cao tai chinh\b', norm)
                   and re.search(r'\b(?:ke hoach|chien luoc|dinh huong|thuyet minh)\b', norm))):
        source = 'BCTC'
    elif re.search(r'\b(?:gia co phieu|gia dong cua|thi gia|gia [a-z]{3})\b', norm):
        source = 'PRICE'
    symbols = [s for s in registered_symbols() if re.search(r'\b'+re.escape(s.lower())+r'\b', norm)]
    explicit_company = bool(symbols and len(norm.split()) >= 4)
    if explicit_company or (source and source != context.get('source_type')):
        # Never carry a previous year, person, article URL, pending slot or graph
        # restriction into a standalone new company/source question.
        return {'companies': symbols or list(context.get('companies') or [])}
    return copy.deepcopy(context)
