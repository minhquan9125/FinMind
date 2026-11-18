"""Recognize contextual commands without consuming new, explicit subjects."""
import re

from .retrieval_flow.intent import _fold


def _words(text):
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', _fold(text)).split())


def is_list_followup(text):
    return bool(re.fullmatch(
        r'(?:(?:ban )?co the |ban |cho (?:toi|minh|em) )?'
        r'(?:liet ke|ke|(?:xem |cho xem )?danh sach)'
        r'(?: ra| lai)?(?: (?:nhung )?noi dung (?:vua|dang) noi)?'
        r'(?: giup (?:toi|minh|em))?(?: duoc)?(?: khong| nhe| di| xem)?', _words(text)))


def is_contextual_overview(text):
    return bool(re.fullmatch(
        r'(?:(?:cho|giup) (?:toi|minh|em) )?'
        r'(?:gioi thieu(?: tong quan)?|tong quan)'
        r'(?: ve)?(?: (?:cong ty|doanh nghiep|ma))?'
        r'(?: nay| do| dang noi| vua noi)?(?: giup (?:toi|minh|em))?(?: nhe)?', _words(text)))


def profile_detail_question(text, context=None):
    """Expand a short profile follow-up into report retrieval, not a rephrase.

    Only use the explicit stored topic and one company; do not guess a subject
    from unrelated history or intercept a new question with its own subject.
    """
    context = context or {}
    if context.get('source_type') != 'COMPANY_PROFILE' or len(context.get('companies') or []) != 1:
        return None
    if not re.fullmatch(
        r'(?:(?:ban )?(?:noi|cho biet|giai thich|trinh bay) |(?:cho|giup) (?:toi|minh|em) )?'
        r'(?:chi tiet(?: hon)?|cu the hon|noi ro hon)'
        r'(?: (?:ve )?(?:cong ty|doanh nghiep)(?: nay| do)?)?'
        r'(?: (?:di|nhe|voi|duoc khong))?', _words(text)):
        return None
    symbol = context['companies'][0]
    return f'Theo BCTN mới nhất của {symbol}, mô tả hoạt động kinh doanh, sản phẩm và dịch vụ chính.'


def is_session_summary(text):
    words = _words(text)
    words = re.sub(r'^(?:(?:vay gio|bay gio|gio|vay) )?(?:toi (?:can|muon) ban |ban hay )?', '', words)
    # An explicit chat object plus a summary action may also carry style
    # instructions ("không cần chi tiết từng đoạn chat"). Those are not a
    # negation of the summary action itself.
    styled = re.match(r'^(?:tong hop|tom tat|tong ket)\b(.*)$', words)
    if styled and re.search(r'\b(?:noi dung chat|lich su chat|cuoc hoi thoai|doan chat)\b', styled[1]):
        allowed = set('lai thoi khong can phai dua ra chi tiet tung doan chat noi dung lich su cuoc hoi thoai '
                      'nay gio toan bo ve cac y chinh ngan gon giup cho toi minh em di nhe voi duoc tong quan'.split())
        if set(styled[1].split()) <= allowed:
            return True
    if re.fullmatch(
        r'(?:(?:ban )?co the )?(?:(?:giup|cho) (?:toi|minh|em) )?'
        r'(?:tong hop|tom tat|tong ket)'
        r'(?: lai)? (?:nay gio|(?:toan bo )?noi dung (?:phien hien tai|cuoc hoi thoai|da trao doi)|'
        r'nhung gi (?:vua|da) (?:noi|trao doi)|cuoc hoi thoai(?: nay)?)'
        r'(?: giup (?:toi|minh|em))?(?: nhe| duoc khong| khong)?', words):
        return True
    # Recognize an action plus an explicit conversation object, rather than
    # letting generic words such as 'tổng quan' turn it into a company lookup.
    command = re.match(r'^(?:(?:ban )?co the |(?:cho|giup) (?:toi|minh|em) |(?:ban )?hay )?'
                       r'(?:tong hop|tom tat|tong ket)\b', words)
    if not command:
        return False
    rest = words[command.end():].strip()
    target = re.search(r'\b(?:noi dung (?:cuoc )?chat|lich su (?:chat|hoi thoai)|'
                       r'(?:cuoc |doan )?(?:hoi thoai|tro chuyen)|phien hien tai|'
                       r'(?:nhung )?noi dung (?:toi |minh |em )?(?:nhan|da nhan|da trao doi)|'
                       r'nhung gi (?:vua|da) (?:noi|trao doi)|nay gio)\b', rest)
    if not target:
        return False
    modifiers = {'lai','chi','tiet','tong','quan','toan','bo','ve','noi','dung','nhung','cac','y','chinh'}
    suffixes = {'nay','gio','di','nhe','voi','a','giup','cho','toi','minh','em','duoc','khong'}
    return (set(rest[:target.start()].split()) <= modifiers
            and set(rest[target.end():].split()) <= suffixes)


def wants_brief_summary(text):
    words = _words(text)
    return bool(re.search(r'\b(?:ngan gon|y chinh|tong hop chung|tong hop lai thoi)\b|'
                          r'\bkhong\b.*\b(?:chi tiet|tung doan|tung luot)\b', words))


def conversation_action(text, context=None):
    """Resolve dialogue actions before research routing; uncertain actions ask.

    A summary verb alone is never enough to guess a research topic. Explicit
    report/news subjects remain research questions. No model sees chat history.
    """
    words = _words(text)
    pending = (context or {}).get('_pending_conversation_action')
    if pending:
        if words in ('co','dung','dung roi','dong y','ok','oke','duoc','yes'):
            return 'SUMMARY'
        if words in ('khong','thoi','huy','khong phai','no'):
            return 'CANCEL'
    verb = re.search(r'\b(?:tong hop|tom tat|tong ket|tom gon|rut gon|gom|he thong lai|chot lai)\b', words)
    if not verb:
        return None
    if re.search(r'\b(?:dung|khong)\b', words[:verb.start()]):
        return None
    dialogue = re.search(r'\b(?:chat|hoi thoai|cuoc trao doi|cuoc tro chuyen|nay gio|'
                         r'nhung gi (?:vua|da) (?:noi|trao doi)|noi dung (?:vua|da) trao doi)\b', words)
    research = re.search(r'\b(?:bctn|bctc|bao cao|tin tuc|bai bao|doanh thu|loi nhuan|'
                         r'cong ty|doanh nghiep|co phieu)\b', words)
    if dialogue:
        # Mixed instructions or unimplemented content filters must be confirmed,
        # rather than silently ignoring one clause or executing a research query.
        if re.search(r'\b(?:chi ve|rieng ve|bo qua|dung nhac|va tim|roi tim|roi xoa|thanh \d+|thanh mot doan)\b', words):
            return 'CONFIRM'
        if research and research.start() < dialogue.start() and not is_session_summary(text):
            return 'CONFIRM'
        return 'SUMMARY'
    if is_session_summary(text):
        return 'SUMMARY'
    return None if research else 'CONFIRM'
