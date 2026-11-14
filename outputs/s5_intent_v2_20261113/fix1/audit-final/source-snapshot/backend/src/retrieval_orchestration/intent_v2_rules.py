"""Goal evidence for eleven labels. No thresholds, retrieval, or ticker exceptions."""
import re
import unicodedata


def plain(text):
    text = unicodedata.normalize('NFKD', text.casefold().replace('đ', 'd'))
    return ''.join(c for c in text if not unicodedata.combining(c))


def has(pattern, text):
    return re.search(pattern, text) is not None


NEWS = r'\b(?:bai (?:bao|tin)|ban tin|tin tuc|thong bao|bai viet|(?:tom tat|tom luoc|tim|tong hop|liet ke)(?: cac)? tin)\b'
REPORT = r'\b(?:bctc|bctn|bao cao(?: thuong nien| tai chinh| quan tri)?|thuyet minh)\b'
CONTENT = r'\b(?:tom tat|tom luoc|tom gon|trich|chep|thuat lai|mo ta|noi gi|noi ve|trinh bay|neu (?:gi|cac|nhung)|giai thich ra sao|duoc giai thich|noi bat)\b'
FIND = r'\b(?:tim|liet ke|danh sach|co .* nao|nhung .* nao|duong dan|dau la|cho (?:toi )?(?:xem|bao cao)|mo phan)\b'
METRIC = r'\b(?:doanh thu|doanh thuu|dt|loi nhuan|lnst|lntt|eps|bvps|roe|roa|p/e|so du tien|tong tai san|tai san|von chu so huu|vcsh|no vay|tong no|no phai tra|du phong|no xau|dong tien|luu chuyen tien|co tuc|bien loi nhuan|gia von|thu nhap binh quan|san luong|khoi luong (?!giao dich)|so (?:cua hang|nhan vien)|cua hang.*van hanh)\b'
VALUE = r'\b(?:bao nhieu|bang may|con so|xin so|gia tri|so lieu|chenh lech|tinh|cong|ty dong|diem phan tram|bao nhieu.*phan tram)\b'
JUDGEMENT = r'\b(?:phan tich|danh gia|nhan dinh|xu huong|xh|tang toc|cham lai|dien bien|chieu huong|vi sao|tai sao|suc khoe|trien vong|kha thi|ben vung|lanh manh|on dinh|cai thien|suy yeu|phan anh dieu gi|nguyen nhan|yeu to|nghieng ve|chat luong (?:loi nhuan|tai san)|manh hay yeu|yeu hay manh)\b'
TITLE = r'\b(?:ceo|cfo|tgd|ktt|chu tich|tong giam doc|giam doc|ke toan truong|hoi dong quan tri|hdqt|ban kiem soat|ban dieu hanh|nguoi dung dau|nguoi dieu hanh|chuc vu|chuc danh|giu chuc|vai tro)\b'
RELATION = r'\b(?:cong ty (?:con|lien ket|me)|co dong|co phan|so huu|gop von|kiem soat|lien doanh|doi tac|quan he (?:hop tac|so huu)|doanh nghiep.*tham gia|ben mua|ben ban)\b'
JOIN = re.compile(r'\s+(?:và|va|rồi|roi|kèm theo|kem theo|kèm|kem|đồng thời|dong thoi|sau đó|sau do)\s+|[;\n]+|\?\s+(?=\w)', re.IGNORECASE)
ACTION = r'^(?:(?:hay|vui long)\s+)?(?:cho(?: toi)?(?: biet| gia)?|xin(?: so)?|lay|tra|tim|liet ke|tom tat|tom luoc|trich|doc|lam|giai thich|xac dinh|xac nhan|danh gia|nhan dinh|phan tich|so sanh|doi chieu|gioi thieu|ai|du (?:bao|doan)|khuyen|cam ket|tu dat)\b'
QUOTE = re.compile(r'"[^"]*"|“[^”]*”|\'[^\']*\'')
SALUTATION = re.compile(r'^\s*(?:(?:xin\s+)?(?:chào|chao)(?:\s+(?:bạn|ban|finmind))?|hello|hi|cảm\s+ơn(?:\s+bạn)?|cam\s+on(?:\s+ban)?)\b[\s,.:;!—-]*', re.IGNORECASE)
POLITE = re.compile(r'^\s*(?:vui lòng|vui long|làm ơn|lam on|bạn có thể giúp tôi|ban co the giup toi|giúp tôi|giup toi)\b[\s,:!—-]*', re.IGNORECASE)


def standalone_conversation(text):
    """A greeting/help/new-session action needs no previous conversation."""
    if SALUTATION.fullmatch(text.strip()):
        return True
    p = plain(text).strip()
    return has(r'^(?:cam on(?: ban)?(?: vi| ve)? (?:cau tra loi|phan giai dap|su giup do)(?: vua roi| nay)?(?: nhe)?|rat vui duoc tro chuyen|ban co the giup toi (?:nhung viec gi|khong)|(?:toi muon )?(?:bat dau|tao|mo)(?: mot)?(?: phien)? nghien cuu(?: moi)?)[.!?]*$', p)


def request_text(text):
    """Remove only a salutation wrapper; retain the actual request and quotes."""
    text = text.strip()
    while not standalone_conversation(text):
        match = SALUTATION.match(text) or POLITE.match(text)
        if not match or ';' in match.group() or not text[match.end():].strip():
            break
        text = re.sub(r'^(?:và|va|rồi|roi)\s+', '', text[match.end():].strip(), flags=re.IGNORECASE)
    return text


def _goal_text(text):
    # A quoted title is evidence/source content, not the user's own instruction.
    return QUOTE.sub(' quoted_source ', request_text(text))


def explicit_components(text):
    p = plain(_goal_text(text))
    if has(NEWS, p) and has(REPORT, p) and has(r'\b(?:doi chieu|so sanh)\b', p) and has(CONTENT + r'|\bphan\b', p) and not has(VALUE, p):
        return ['NEWS', 'REPORT_CONTENT']
    return []


def explicit_intent(text):
    text = request_text(text)
    if standalone_conversation(text):
        return 'CONVERSATION'
    goal = _goal_text(text)
    p = plain(goal).strip()
    # A citation instruction supports the preceding answer, rather than a second goal.
    p = re.split(r'\?\s*trich (?:cau|nguon)\b.*\bbang chung\b', p)[0]
    if not p:
        return None
    news, report = has(NEWS, p), has(REPORT, p)
    content = has(CONTENT, p) or has(r'^(?:noi dung|phan noi dung)\b', p)
    who = has(r'\b(?:ai|nguoi nao|gom nhung ai|gom ai|cho (?:biet )?ten)\b', p)
    role_goal = has(TITLE, p) and (who or has(r'\b(?:giu|dam nhiem).*chuc|\b(?:bo nhiem|mien nhiem).*?(?:khi nao|ngay nao|hieu luc)|\bchuc (?:vu|danh).*\b(?:gi|nao)\b|\b(?:cho biet|xac dinh|tra cuu|xin)\b.*\b(?:chuc vu|chuc danh|vai tro)\b', p))
    if explicit_components(text):
        return 'MIXED'
    if has(r'^(?:toi )?chon\b.*\b(?:trong danh sach|cho cau hoi tiep theo)\b', p):
        return 'CONVERSATION'
    # Asking to reproduce a source is different from making the source's claim.
    published_value = has(r'\bgia(?: ban)? muc tieu\b', p) and has(r'\b(?:da cong bo|da neu|da dua ra)\b', p)
    article_discovery = has(r'\b(?:bai (?:bao|tin)|ban tin|bai viet) nao\b', p)
    if news and (content or published_value or article_discovery or (has(FIND, p) and not role_goal)):
        return 'NEWS'
    read_report = has(r'\bđọc\b', goal.casefold()) or has(r'^doc\s+(?:thuyet minh|bctc|bctn|bao cao)\b', p)
    if report and (read_report or (has(r'^thuyet minh\b', p) and not has(VALUE, p))):
        return 'REPORT_CONTENT'
    if report and (content or has(r'^(?:tim|mo|dau la|cho (?:toi )?(?:bao cao|xem))\b|\b(?:chinh sach|nguyen tac|quan tri rui ro|dao tao)\b', p)):
        return 'REPORT_CONTENT'
    if has(r'\b(?:cau tra loi (?:truoc|tren)|vua (?:noi|dung|trao doi|goi y)|nay gio|cuoc tro chuyen|nguon o dau|tai lieu nao.*cau tra loi|nguon.*cau tra loi|dung lua chon|chon phuong an|chon muc|toi chon|phien .*moi|nghien cuu moi|tiep tuc cau tra loi)\b|^(?:con [a-z0-9]+(?: thi sao)?|giu nguyen|cung chi tieu|quay lai|xem muc|lay cong ty thu|toi dang hoi|so \d+)\b', p):
        return 'CONVERSATION'
    if has(r'\b(?:co nen (?:mua|ban)|khuyen toi|nen ban hay giu|toi nen giu hay ban|hay (?:quyet dinh|chon ma|chon cho toi|chac chan)|chac chan.*(?:tang|lo)|cam ket|bao dam.*(?:lai|tang)|khong bao gio lo|hay hua|tu dat gia muc tieu|dat gia muc tieu|dua muc gia.*muc tieu|gia tuong lai|diem mua.*chot loi|du (?:bao|doan|doan).*gia|hay doan gia|hay tinh gia tuong lai|hay chon ma|hay khuyen toi|thoi tiet|nau (?:pho|an)|cong thuc nau|dat ve|ke .*truyen cuoi)\b', p):
        return 'OUT_OF_SCOPE'
    if has(r'\btu dat (?:muc )?chot loi\b', p):
        return 'OUT_OF_SCOPE'
    price_object = has(r'\b(?:gia|co phieu|cp)\b', p) or (has(r'\b(?:len|xuong)\b', p) and not has(METRIC, p))
    future_price = has(r'\b(?:tuan sau|thang sau|nam sau|nam toi)\b.*\b(?:(?:se )?(?:len|xuong|tang|giam)|gia nao|bao nhieu)\b', p) and price_object
    if has(r'\bgia(?: ban)? muc tieu\b', p) or future_price:
        return 'OUT_OF_SCOPE'
    # A request for a person stays a person request even when salary is mentioned.
    if role_goal:
        return 'PERSON_ROLE'
    metric = has(METRIC, p) or has(r'\blương\b', text.casefold()) or has(r'\blu[oơ]ng (?:ceo|cfo|tgd)\b', p)
    if has(r'\b(?:la gi|y nghia|khai niem|khac .*diem nao|khac .*o dau|giai thich su khac biet|co the lam rui ro)\b', p) and (metric or has(r'\b(?:don bay|tai chinh|chi so)\b', p)):
        return 'ANALYSIS'
    judgement = has(JUDGEMENT, p)
    price = (has(r'\b(?:gia|thi gia)\b', p) and not has(r'\b(?:tham gia|chuyen gia|quoc gia|gia tri|gia von|gia thanh|danh gia|gia dinh)\b', p)) or has(r'\b(?:khoi luong|luong|gia tri).*giao dich|\b(?:khop lenh|giao dich thoa thuan|so co phieu.*khop lenh)\b', p)
    if judgement:
        return 'ANALYSIS'
    if price:
        return 'PRICE'
    # Ownership percentages and relationship discovery are not financial ratios.
    relation = has(RELATION, p) and not has(r'\bban kiem soat\b', p)
    financial_goal = metric and (has(VALUE, p) or has(r'^(?:cho biet|lay|xin|so sanh|liet ke)\b', p))
    if relation and not financial_goal:
        return 'ENTITY_RELATION'
    if metric and not has(r'\b(?:doc lap|phu thuoc|chat luong dich vu)\b', p):
        return 'NUMERIC'
    if news or has(r'\b(?:co tin gi moi|tin moi|tin thi truong|tin .*hom nay|tong hop tin|tin tuc)\b', p):
        return 'NEWS'
    if report:
        return 'REPORT_CONTENT'
    if has(r'\b(?:tong quan|ho so|la cong ty gi|linh vuc|nganh nao|nganh nghe|hoat dong (?:chinh|kinh doanh)|mang kinh doanh|tru so|ten (?:day du|tieng anh)|website|san pham|dich vu nao|niem yet|ma chung khoan|ten giao dich|thanh lap|cot moc|nguon goc|doi ten|lich su.*doanh nghiep|gioi thieu)\b', p):
        return 'COMPANY_OVERVIEW'
    return None


def requests(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError('INVALID_QUESTION')
    text = request_text(text)
    quoted = [(m.start(), m.end()) for m in QUOTE.finditer(text)]
    matches = list(JOIN.finditer(text))
    if not matches:
        return [text.strip()]
    current, result = text[:matches[0].start()], []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        right = text[match.end():end]
        left_label, right_label = explicit_intent(current), explicit_intent(right)
        action = has(ACTION, plain(right).strip())
        predicate = has(r'\b(?:bao nhieu|la ai|gom ai|thuoc nganh nao|co nen mua|co nen ban|ra sao|nhu the nao)\b', plain(right))
        protected = any(start <= match.start() < stop for start, stop in quoted)
        strong_separator = has(r'[;?\n]', match.group()) or current.rstrip().endswith((';', '?'))
        independent_goal = (predicate or strong_separator) and left_label is not None and right_label is not None and left_label != right_label
        noun_goal = has(r'^(?:danh sach|bang)\b', plain(right).strip()) and right_label is not None and right_label != left_label
        independent = (action or independent_goal or noun_goal) and (left_label is not None or has(ACTION, plain(current).strip()))
        if left_label is None and len(plain(current).split()) == 1:
            independent = False
        if left_label in {'NEWS', 'REPORT_CONTENT'} and has(r'^(?:hay )?tom (?:tat|luoc) (?:bai|tai lieu)[.!?]*$', plain(right).strip()):
            independent = False
        if has(r'^trich (?:cau|nguon)\b.*\bbang chung\b', plain(right).strip()):
            independent = False
        if independent and not protected and right.strip():
            result.append(current.strip(' .'))
            current = right
        else:
            current += match.group() + right
    return result + [current.strip(' .')]
