"""Explicit role abbreviations. No fuzzy spelling or inferred office scope."""
import re,unicodedata

def role_key(text):
    value=' '.join(unicodedata.normalize('NFC',text).casefold().split())
    for pattern,replacement in (
        (r'\bhđqt\b','hội đồng quản trị'),(r'\btgđ\b','tổng giám đốc'),
        (r'\bbks\b','ban kiểm soát'),(r'\bbđh\b','ban điều hành'),
        (r'\bubkt\b','ủy ban kiểm toán'),(r'\btv\b','thành viên'),
        (r'\bgđ\b','giám đốc'),(r'\btp\.(?=\s)','tp'),
    ):value=re.sub(pattern,replacement,value)
    return value

def position_supported(position, quote):
    wanted,source=role_key(position),role_key(quote)
    for match in re.finditer(r'(?<!\w)'+re.escape(wanted)+r'(?!\w)',source):
        prefix=source[max(0,match.start()-8):match.start()]
        if not wanted.startswith('phó ') and re.search(r'\bphó\s*$',prefix):continue
        if 'độc lập' in wanted and 'độc lập' not in match[0]:continue
        return True
    return False
