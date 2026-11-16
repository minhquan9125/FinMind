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


def is_session_summary(text):
    return bool(re.fullmatch(
        r'(?:(?:ban )?co the )?(?:(?:giup|cho) (?:toi|minh|em) )?'
        r'(?:tong hop|tom tat|tong ket)'
        r'(?: lai)? (?:nay gio|(?:toan bo )?noi dung (?:phien hien tai|cuoc hoi thoai|da trao doi)|'
        r'nhung gi (?:vua|da) (?:noi|trao doi)|cuoc hoi thoai(?: nay)?)'
        r'(?: giup (?:toi|minh|em))?(?: nhe| duoc khong| khong)?', _words(text)))
