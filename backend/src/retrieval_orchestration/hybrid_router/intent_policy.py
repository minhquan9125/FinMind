"""Business routing policy, independent of classifier scores and data availability.

Scope is not always a ticker: a market, industry or investing concept is also a
valid retrieval target. Graph is required for entity/relationship discovery, not
merely because the user asks for an explanation or forecast.
"""

from dataclasses import dataclass
import re


def contains(text: str, phrases) -> bool:
    return any(re.search(rf"\b{re.escape(phrase)}\b", text) for phrase in phrases)


MARKET_TERMS = (
    "thi truong", "tt", "ttck", "vni", "vnindex", "vn index", "chung khoan",
    "san chung khoan", "toan san",
)
KNOWLEDGE_TERMS = (
    "dca", "etf", "eps", "p e", "pe", "p b", "pb", "roe", "roa", "rsi", "macd",
    "margin", "fomo", "fud", "stop loss", "cat lo", "chot loi", "trung binh gia",
    "phan tich ky thuat", "phan tich co ban", "dinh gia", "da dang hoa",
    "phan bo von", "chia von", "quan tri rui ro", "danh muc", "lai kep",
    "co phieu la gi", "co tuc la gi", "trai phieu", "chung chi quy",
    "lenh ato", "lenh atc", "dau tu chung khoan", "hoc chung khoan",
    "co phieu quy", "co phieu uu dai", "co phieu thuong", "phien ato", "phien atc",
    "thanh khoan", "free float", "bull market", "bear market", "uptrend", "downtrend",
    "swing trading", "long term", "gia von", "tich san", "gia tri so sach",
    "ky quy", "don bay", "von hoa", "loi suat", "bien do", "gia tran", "gia san",
    "lenh gioi han", "lenh thi truong", "ty le no",
)
MARKET_ANALYSIS_TERMS = (
    "du doan", "du bao", "xu huong", "nhan dinh", "phan tich", "trien vong",
    "tiem nang", "ho tro", "khang cu", "xac nhan", "moc", "nen mua", "nen ban",
    "mua them", "ngoi quan sat", "giai thich", "vi sao", "tai sao", "nguyen nhan",
    "ly do", "sao", "chuyen gi", "dang xay ra", "tang", "giam", "do", "xanh",
    "do lua", "rung lac", "sap", "lao doc", "khoi sac", "bien dong", "the nao",
    "nhu nao", "dao nay", "gan day", "may phien", "bat day", "vao hang",
)
GRAPH_TERMS = (
    "nhan su", "bo nhiem", "mien nhiem", "bai nhiem", "tu nhiem", "tu chuc",
    "cong ty con", "cong ty lien ket", "cong ty me", "don vi thanh vien",
    "he sinh thai", "so huu", "co dong", "ban lanh dao", "chu tich", "ceo",
    "tong giam doc", "giam doc", "sep lon", "nam quyen", "giu ghe",
    "cam nhieu co phieu", "doi thu", "cung nganh", "chung mam", "doi tac",
    "chuoi cung ung", "kiem soat", "dieu hanh", "lanh dao",
)
PROFILE_TERMS = (
    "linh vuc", "nganh nghe", "nganh kinh doanh", "hoat dong trong",
    "thuoc nganh", "nganh gi", "nganh nao", "kinh doanh gi", "lam mang gi",
)
CONTENT_TERMS = (
    "doanh thu", "loi nhuan", "lnst", "lntt", "lai", "lo", "lam an",
    "ket qua kinh doanh", "co tuc", "chia chac", "chia giay", "no", "bien loi nhuan",
    "bao cao", "bctc", "bctn", "ke hoach", "nhan dinh", "chia se", "phat bieu",
    "noi gi", "du an", "tien do", "xa rong", "gom rong", "gia co phieu",
    "gia cp", "gia ck", "thi gia", "tang", "giam", "tin tuc", "so lieu",
    "tong tai san", "von chu so huu", "dong tien", "chien luoc", "muc tieu",
    "cam ket", "quan diem", "tin moi", "lich su", "tru so",
)
EVENT_TERMS = (
    "lien quan", "dinh dang", "an theo", "vu chay", "chay", "bi bat", "bat giu",
    "thanh tra", "bi phat", "xu phat", "khoi to", "tin don", "su kien",
    "bat tay", "hop tac", "dieu tra", "truy to", "tam giam",
)
MACRO_TERMS = ("lai suat", "ty gia", "lam phat", "gia dau", "thue", "chinh sach",
               "dau tu cong", "gdp", "tin dung", "cung tien")
IMPACT_TERMS = ("anh huong", "tac dong", "huong loi", "thiet hai", "rui ro")
COMPARISON_TERMS = ("so sanh", "doi chieu", "so voi", "ben nao", "ma nao", "con nao",
                    "khoe hon", "tot hon", "ngon hon", "cao hon", "thap hon",
                    "so gang", "dat len ban can", "huong loi")


@dataclass(frozen=True)
class RetrievalIntent:
    route: str | None = None
    topic: str | None = None
    company_optional: bool = False


def resolve_intent(text, companies, industry, metric=None, entity_mentions=()):
    market = contains(text, MARKET_TERMS)
    knowledge = contains(text, KNOWLEDGE_TERMS) or (
        not companies and contains(text, ("la gi", "khai niem", "dinh nghia", "giai thich",
                                         "khac gi", "khac nhau", "cach tinh", "cach dung", "vi du"))
        and contains(text, GRAPH_TERMS + PROFILE_TERMS + CONTENT_TERMS)
    )
    portfolio = bool(re.search(
        r"\b(?:von|co|cam)\s+\d+\s*(?:cu|trieu|tr|ty|trd)\b", text
    )) and contains(text, ("chia", "phan bo", "bao nhieu ma", "bn ma", "dau tu", "nen mua"))
    graph = contains(text, GRAPH_TERMS)
    profile = contains(text, PROFILE_TERMS)
    # Leadership phrases contain 'giam'; ownership phrases contain stock words.
    # Remove whole relationship phrases before looking for a second content task.
    content_text = text
    for phrase in sorted(GRAPH_TERMS + PROFILE_TERMS, key=len, reverse=True):
        content_text = re.sub(rf"\b{re.escape(phrase)}\b", " ", content_text)
    content = (metric is not None or contains(content_text, CONTENT_TERMS)
               or bool(re.search(r"\b(?:ke hoach|du an|chien luoc)\b.*\bai\b", text)))
    event = contains(text, EVENT_TERMS)
    impact = contains(text, IMPACT_TERMS)
    macro = contains(text, MACRO_TERMS)
    analysis = contains(text, MARKET_ANALYSIS_TERMS)

    if len(companies) >= 2 and metric and not (graph or profile or event or impact):
        return RetrievalIntent("VECTOR", "FINANCIAL_COMPARISON")
    if len(companies) >= 2:
        return RetrievalIntent("BOTH", "OVERALL_COMPARISON")
    if event and (companies or entity_mentions):
        return RetrievalIntent("BOTH", "EVENT_IMPACT", bool(entity_mentions))
    if industry and not companies and (macro or impact or contains(text, COMPARISON_TERMS)):
        return RetrievalIntent("BOTH", "INDUSTRY_ANALYSIS", True)
    if (knowledge or portfolio) and (not companies or not (graph or profile)):
        return RetrievalIntent("VECTOR", "PORTFOLIO_EDUCATION" if portfolio else "INVESTING_KNOWLEDGE", True)
    if (graph or profile) and (content or knowledge):
        return RetrievalIntent("BOTH", "MULTI_HOP")
    if graph:
        return RetrievalIntent("GRAPH", "RELATIONSHIP_LOOKUP")
    if profile:
        return RetrievalIntent("GRAPH", "COMPANY_PROFILE")
    if market and not companies:
        digest = contains(text, ("tin tuc", "tin moi", "co gi moi", "diem tin", "tong hop",
                                 "co gi hot", "co bien", "co drama", "the nao", "nhu nao",
                                 "do lua", "rung lac"))
        return RetrievalIntent("VECTOR", "MARKET_DAILY_DIGEST" if digest and not contains(
            text, ("du doan", "du bao", "xu huong", "vi sao", "tai sao", "giai thich")
        ) else "MARKET_ANALYSIS", True)
    if not companies and not industry and analysis and contains(text, (
        "gia", "co phieu", "gia cp", "gia ck", "do lua", "rung lac",
    )):
        return RetrievalIntent("VECTOR", "MARKET_ANALYSIS", True)
    if companies and analysis and metric in (None, "STOCK_PRICE"):
        return RetrievalIntent("VECTOR", "PRICE_ANALYSIS")
    if content or (companies and metric):
        return RetrievalIntent("VECTOR", "FINANCIAL_RESEARCH")
    if industry and not companies:
        return RetrievalIntent("VECTOR", "SECTOR_RESEARCH", True)
    return RetrievalIntent()
