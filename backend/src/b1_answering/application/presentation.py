"""Display policy after grounding: preserve source claims, style the visible answer.

A configured default unit is an operator convention, not proof of source units.
The distinction stays in presentation metadata; amounts are never converted here.
"""
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
import re

from ..evidence.grounded import _numbers


@dataclass(frozen=True)
class AnswerStyle:
    version: str = 'b1-answer-style-v1'
    default_financial_currency: str = 'VND'
    show_source_cautions: bool = False

    def __post_init__(self):
        if (self.version != 'b1-answer-style-v1' or self.default_financial_currency not in ('', 'VND')
                or type(self.show_source_cautions) is not bool):
            raise ValueError('Invalid answer presentation policy')


@lru_cache(maxsize=1)
def get_answer_style():
    path = Path(__file__).resolve().parents[1] / 'config/answer_style.json'
    return AnswerStyle(**json.loads(path.read_text(encoding='utf-8')))


MONEY_METRICS = {
    'TOTAL_ASSETS', 'TOTAL_LIABILITIES', 'CURRENT_LIABILITIES', 'NON_CURRENT_LIABILITIES',
    'TOTAL_EQUITY', 'CHARTER_CAPITAL', 'CASH_AND_CASH_EQUIVALENTS',
    'SHORT_TERM_LOANS_AND_FINANCE_LEASES', 'LONG_TERM_LOANS_AND_FINANCE_LEASES',
    'RETAINED_EARNINGS', 'GROSS_REVENUE', 'NET_REVENUE', 'PROFIT_BEFORE_TAX',
    'PROFIT_AFTER_TAX', 'PARENT_NET_PROFIT', 'CASH_FLOW_OPERATING', 'CASH_FLOW_INVESTING', 'CASH_FLOW_FINANCING',
}
NUMBER = r'[-+]?\d+(?:[.,]\d+)*'
UNIT = r'(?:(?:nghìn|ngàn|triệu|tỷ|tỉ)\s+)?(?:VND|USD|EUR|đồng)|%'
AMOUNT = re.compile(r'(?<![\w/])(?P<number>'+NUMBER+r')(?:\s+(?P<unit>'+UNIT+r'))?(?![\w/])', re.I)
CAUTION = re.compile(r'^(?:lưu ý:\s*)?nguồn chưa (?:xác minh đơn vị|xác định phạm vi)', re.I)


def _source_amounts(item, metric, style):
    header = item['passage'].splitlines()[0]
    for line in item['passage'].splitlines():
        match = re.search(r'\('+re.escape(metric)+r'\)\s*:\s*('+NUMBER+r')', line)
        if not match:
            continue
        tail = line[match.end():]
        unit = re.match(r'\s*\(?('+UNIT+r')(?!\w)', tail, re.I)
        if not unit:
            header_unit = re.search(r'Đơn vị:\s*('+UNIT+r')', header, re.I)
            unit = header_unit
        if unit:
            value = re.sub(r'đồng', 'VND', unit[1], flags=re.I)
            yield _numbers(match[1]), value, 'SOURCE'
        elif style.default_financial_currency:
            yield _numbers(match[1]), style.default_financial_currency, 'CONFIGURED_DEFAULT'


def present_answer(draft, evidence, scope, *, style=None):
    style = style or get_answer_style()
    out = deepcopy(draft)
    if scope.get('source_type') != 'BCTC':
        return out
    citations = {item['evidence_id']: item.get('citation_number', index)
                 for index, item in enumerate(draft.get('citations', []), 1)}
    parts, annotations = [], []
    for index, claim in enumerate(draft.get('claims', [])):
        text = '\n'.join(line for line in claim['text'].splitlines() if not CAUTION.match(line.strip()))
        text = re.sub(r'\s*\(đơn vị chưa xác minh\)', '', text, flags=re.I)
        if not text.strip():
            continue
        amounts = []
        if scope.get('metric_code') in MONEY_METRICS:
            for eid in claim['evidence_ids']:
                amounts.extend(_source_amounts(evidence[eid], scope['metric_code'], style))

        def render(match):
            if re.search(r'(?:quý|năm|tháng|ngày|q)\s*$', text[max(0, match.start()-20):match.start()], re.I):
                return match[0]
            matches = [(unit, origin) for number, unit, origin in amounts if number == _numbers(match['number'])]
            if not matches or len({unit for unit, _ in matches}) != 1:
                return match[0]
            unit, origin = matches[0]
            annotations.append({'claim_index': index, 'unit': unit, 'origin': origin,
                                'source_unit_verified': origin == 'SOURCE'})
            return match['number']+' '+unit

        text = AMOUNT.sub(render, text)
        tags = ''.join(f'[{citations[eid]}]' for eid in claim['evidence_ids'])
        parts.append(text+' '+tags)
    if style.show_source_cautions:
        parts.extend(draft.get('cautions', []))
    out['draft'] = '\n\n'.join(parts)
    out['presentation'] = {'version': style.version, 'default_financial_currency': style.default_financial_currency,
                           'source_cautions_visible': style.show_source_cautions, 'unit_annotations': annotations}
    return out
