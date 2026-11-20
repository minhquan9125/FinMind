"""Shared source boundary for a report named by subject rather than acronym."""
import re
from .retrieval_flow.intent import _fold
from .metric_vocabulary import find_metrics


def company_overview_question(text):
    """Recognize a general company question, without swallowing specific topics."""
    norm=_fold(text)
    if find_metrics(norm) or re.search(r'\b(?:bctn|bctc|bao cao|tin tuc|bai|gia|nhan su|chu tich|co dong|chi nhanh)\b',norm):
        return False
    if not re.search(r'\b(?:ra sao|nhu the nao|the nao)\b',norm):return False
    from .input_normalization import registered_symbols
    from .retrieval_flow.intent import TICKERS
    symbols=set(registered_symbols()) | set(TICKERS)
    if not any(re.search(r'\b'+re.escape(s.lower())+r'\b',norm) for s in symbols):return False
    rest=norm
    for symbol in symbols:rest=re.sub(r'\b'+re.escape(symbol.lower())+r'\b',' ',rest)
    allowed=set('ban cho toi minh em xem cong ty doanh nghiep ngan hang tap doan bay gio hien tai nay ra sao nhu the nao dang thi voi nhe a duoc khong'.split())
    return set(re.findall(r'[a-z]+',rest)) <= allowed


def generic_annual_report(text):
    norm=_fold(text)
    if not re.search(r'\bbao cao\b',norm):return False
    if re.search(r'\b(?:bctc|bao cao tai chinh|tin tuc|news|bai bao|theo bai|trong bai|dang ngay|ngay dang)\b',norm):
        return False
    topic=re.search(r'\b(?:nhan su|quan tri|ban lanh dao|ban dieu hanh|hoi dong quan tri|hdqt|co dong|'
                    r'cong ty con|cong ty lien ket|chien luoc|ke hoach|dinh huong|thuyet minh|'
                    r'rui ro|kiem soat noi bo|nhan luc|hoat dong kinh doanh|kiem tien|san pham|dich vu|'
                    r'thong diep chu tich|phat trien ben vung)\b',norm)
    qualitative=re.search(r'\b(?:chien luoc|ke hoach|dinh huong|thuyet minh|nhan dinh)\b',norm)
    return bool(topic and (not find_metrics(norm) or qualitative))
