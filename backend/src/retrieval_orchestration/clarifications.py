"""Declarative disambiguation choices and a bounded no-progress policy.

Choices select explicit supported metrics. Repeating an ambiguous word never
chooses a financial value or silently substitutes a different metric.
"""
from copy import deepcopy
import re

from .retrieval_flow.intent import _fold


# key -> label, explanation, short replies. Keys match the financial mapping.
OPTIONS = {
    'TOTAL_LIABILITIES': ('Tổng nợ phải trả', 'Toàn bộ các khoản phải trả, không chỉ tiền vay.', ('tong', 'tong no', 'tat ca', 'tong cong')),
    'CURRENT_LIABILITIES': ('Nợ ngắn hạn', 'Toàn bộ nợ phải trả được phân loại ngắn hạn.', ('ngan han',)),
    'NON_CURRENT_LIABILITIES': ('Nợ dài hạn', 'Toàn bộ nợ phải trả được phân loại dài hạn.', ('dai han',)),
    'GROUP:BORROWING': ('Nợ vay', 'Chỉ các khoản vay và nợ thuê tài chính.', ('vay', 'khoan vay')),
    'SHORT_TERM_LOANS_AND_FINANCE_LEASES': ('Nợ vay ngắn hạn', 'Vay và nợ thuê tài chính ngắn hạn.', ('ngan han',)),
    'LONG_TERM_LOANS_AND_FINANCE_LEASES': ('Nợ vay dài hạn', 'Vay và nợ thuê tài chính dài hạn.', ('dai han',)),
    'GROSS_REVENUE': ('Doanh thu trước giảm trừ', 'Doanh thu bán hàng và cung cấp dịch vụ trước giảm trừ.', ('truoc giam tru', 'chua giam tru', 'gop')),
    'NET_REVENUE': ('Doanh thu thuần', 'Doanh thu sau các khoản giảm trừ.', ('thuan', 'sau giam tru')),
    'PROFIT_BEFORE_TAX': ('Lợi nhuận trước thuế', 'Kết quả trước chi phí thuế thu nhập doanh nghiệp.', ('truoc', 'truoc thue')),
    'PROFIT_AFTER_TAX': ('Lợi nhuận sau thuế', 'LNST tổng; khác phần thuộc cổ đông công ty mẹ.', ('sau', 'sau thue')),
    'PARENT_NET_PROFIT': ('LNST thuộc cổ đông công ty mẹ', 'Phần LNST thuộc cổ đông công ty mẹ.', ('co dong cong ty me', 'thuoc cong ty me')),
    'TOTAL_ASSETS': ('Tổng tài sản', 'Toàn bộ tài sản trên bảng cân đối.', ('tong', 'tat ca')),
    'CASH_AND_CASH_EQUIVALENTS': ('Tiền và tương đương tiền', 'Tiền và các khoản tương đương tiền.', ('tien',)),
    'TOTAL_EQUITY': ('Vốn chủ sở hữu', 'Tổng vốn chủ sở hữu, không chỉ vốn điều lệ.', ('chu so huu', 'tong')),
    'CHARTER_CAPITAL': ('Vốn điều lệ', 'Vốn điều lệ của công ty.', ('dieu le',)),
    'CASH_FLOW_OPERATING': ('Dòng tiền hoạt động kinh doanh', 'Lưu chuyển tiền thuần từ hoạt động kinh doanh.', ('kinh doanh',)),
    'CASH_FLOW_INVESTING': ('Dòng tiền hoạt động đầu tư', 'Lưu chuyển tiền thuần từ hoạt động đầu tư.', ('dau tu',)),
    'CASH_FLOW_FINANCING': ('Dòng tiền hoạt động tài chính', 'Lưu chuyển tiền thuần từ hoạt động tài chính.', ('tai chinh',)),
}
GROUPS = {
    'DEBT': ('nợ', ['TOTAL_LIABILITIES', 'CURRENT_LIABILITIES', 'NON_CURRENT_LIABILITIES', 'GROUP:BORROWING']),
    'BORROWING': ('nợ vay', ['SHORT_TERM_LOANS_AND_FINANCE_LEASES', 'LONG_TERM_LOANS_AND_FINANCE_LEASES']),
    'PROFIT': ('lợi nhuận', ['PROFIT_BEFORE_TAX', 'PROFIT_AFTER_TAX', 'PARENT_NET_PROFIT']),
    'REVENUE': ('doanh thu', ['GROSS_REVENUE', 'NET_REVENUE']),
    'ASSETS': ('tài sản', ['TOTAL_ASSETS', 'CASH_AND_CASH_EQUIVALENTS']),
    'EQUITY': ('vốn', ['TOTAL_EQUITY', 'CHARTER_CAPITAL']),
    'CASH_FLOW': ('dòng tiền', ['CASH_FLOW_OPERATING', 'CASH_FLOW_INVESTING', 'CASH_FLOW_FINANCING']),
    'GENERIC': ('chỉ tiêu', ['TOTAL_ASSETS', 'NET_REVENUE', 'PROFIT_AFTER_TAX', 'TOTAL_LIABILITIES']),
}


def metric_group(norm):
    for pattern, group in (
        (r'\b(?:no vay|khoan vay)\b', 'BORROWING'), (r'\bno\b', 'DEBT'),
        (r'\bdoanh thu\b', 'REVENUE'), (r'\b(?:dong tien|luu chuyen tien)\b', 'CASH_FLOW'),
        (r'\btai san\b', 'ASSETS'), (r'\bvon\b', 'EQUITY'),
    ):
        if re.search(pattern, norm):
            return group
    return None


def resolve_reply(norm, context):
    state = (context or {}).get('_clarification_state') or {}
    keys = state.get('choice_keys', [])
    if not keys and (context or {}).get('_pending_metric') in GROUPS:
        keys = GROUPS[context['_pending_metric']][1]
    cleaned = norm.rstrip(' .?!')
    number = re.fullmatch(r'(?:(?:chon|so|muc|loai|cai|phuong an)\s+)?([1-9])', cleaned)
    if number:
        index = int(number[1])-1
        if index < len(keys):
            return _replacement(keys[index])
    # A user may answer the metric before the company we asked for. Keep that
    # information too; numeric replies still refer only to the displayed menu.
    pending = (context or {}).get('_pending_metric')
    if pending in GROUPS:
        keys = list(dict.fromkeys([*keys, *GROUPS[pending][1]]))
    cleaned = re.sub(r'^(?:cho toi xem|cho minh xem|cho t xem|xem|chon|lay|loai|cai|muc)\s+', '', cleaned)
    matches = []
    for key in keys:
        if key in OPTIONS:
            label, _, aliases = OPTIONS[key]
            if cleaned in {_fold(label), *aliases}:
                matches.append(key)
        elif key.startswith('TEXT:') and cleaned == _fold(key[5:]):
            matches.append(key)
    return _replacement(matches[0]) if len(matches) == 1 else norm


def _replacement(key):
    if key.startswith('GROUP:'):
        return _fold(OPTIONS[key][0])
    if key.startswith('TEXT:'):
        return _fold(key[5:])
    return key.lower()


def _public_options(keys):
    values = []
    for index, key in enumerate(keys, 1):
        if key in OPTIONS:
            label, description, _ = OPTIONS[key]
            item = {'id': str(index), 'label': label, 'reply': label, 'description': description}
            if not key.startswith('GROUP:'):
                item['metric_code'] = key
        else:
            label = key[5:]
            item = {'id': str(index), 'label': label, 'reply': label, 'description': ''}
        values.append(item)
    return values


def apply_clarification(decision, previous, today):
    """Apply to every clarification exit, including unknown and invalid inputs."""
    scope = decision['scope']
    if decision['decision'] != 'ASK_CLARIFICATION':
        if decision['decision'] in ('SEARCH', 'MARKET_LOOKUP'):
            scope.pop('_clarification_state', None)
            scope.pop('_metric_candidates', None)
        return decision
    reason = decision['reason_code']
    if reason == 'NEW_CONVERSATION':
        return decision
    if reason in ('MISSING_METRIC', 'MULTIPLE_METRICS'):
        group = scope.get('_pending_metric', 'GENERIC')
        label, keys = GROUPS.get(group, GROUPS['GENERIC'])
        keys = (scope.get('_metric_candidates') or keys)[:8]
        field = 'metric'
        message = f'Bạn muốn xem loại {label} nào?'
    elif reason == 'MISSING_COMPANY':
        field, label, keys = 'company', 'công ty', ['TEXT:FPT', 'TEXT:SSI', 'TEXT:VCB']
        message = decision['message']
    elif reason in ('MISSING_PERIOD', 'MISSING_YEAR'):
        field, label = 'period', 'kỳ hoặc năm báo cáo'
        quarter = scope.get('_pending_quarter')
        keys = [f'TEXT:{today.year}', f'TEXT:{today.year-1}'] if quarter else [
            f'TEXT:quý 2/{today.year}', f'TEXT:năm {today.year-1}']
        message = decision['message']
    elif reason == 'AMBIGUOUS_PUBLISHER':
        field, label, keys = 'publisher', 'nguồn tin', ['TEXT:CafeF', 'TEXT:FireAnt']
        message = 'Bạn muốn xem tin theo CafeF hay FireAnt?'
    elif reason == 'AMBIGUOUS_REPORTING_ENTITY':
        field, label, keys = 'reporting_entity', 'phạm vi báo cáo', ['TEXT:Báo cáo hợp nhất', 'TEXT:Báo cáo riêng']
        message = 'Bạn muốn dùng báo cáo hợp nhất hay báo cáo riêng?'
    elif reason in ('AMBIGUOUS_PERIOD', 'INVALID_DATE', 'UNSUPPORTED_PERIOD'):
        field, label = 'period', 'một kỳ hợp lệ'
        keys = [f'TEXT:quý 2/{today.year}', f'TEXT:năm {today.year-1}']
        message = decision['message']
    else:
        field, label, keys = reason, 'thông tin được hỏi', ['TEXT:/moi']
        message = decision['message']
    signature = {key: deepcopy(scope.get(key)) for key in (
        'companies', 'periods', 'metric_code', 'source_type', 'reporting_entity', 'measure_basis',
        '_pending_metric', '_pending_quarter', 'publisher')}
    old = (previous or {}).get('_clarification_state') or {}
    ident = f'{field}:{scope.get("_pending_metric", "")}'
    same = old.get('id') == ident and old.get('signature') == signature
    attempts = min(old.get('attempts', 0)+1, 3) if same else 1
    core = {key: value for key, value in signature.items() if key != '_pending_metric'}
    unproductive = min(old.get('unproductive_turns', 0)+1, 6) if old.get('core_signature') == core else 1
    scope['_clarification_state'] = {'id': ident, 'signature': signature, 'attempts': attempts,
                                      'choice_keys': list(keys), 'core_signature': core,
                                      'unproductive_turns': unproductive}
    options = _public_options(keys)
    rendered = ' '.join(f"{item['id']}. {item['label']}." for item in options)
    if attempts >= 3 or unproductive >= 6:
        decision['decision'] = 'CLARIFICATION_STALLED'
        decision['reason_code'] = 'CLARIFICATION_STALLED'
        message = (f'Mình tạm dừng yêu cầu vì chưa xác định được {label}. '
                   'Bạn có thể bấm một lựa chọn dưới đây, nhập tên cụ thể hoặc gõ /moi để bắt đầu lại.')
    elif attempts == 2:
        message = f'Mình vẫn chưa xác định được {label}. Hãy chọn một mục dưới đây hoặc nhập số thứ tự.'
    decision['message'] = message+(' '+rendered if field == 'metric' or attempts >= 2 else '')
    decision['clarification_options'] = options
    return decision
