import asyncio
from uuid import uuid4
import pytest

from src.documents.db_chunking import financial_documents,chunk_document
from src.b1_answering.core.policy import Budget,Limits
from src.retrieval_orchestration.live_research import analyze_live,LiveResearchService
from src.retrieval_orchestration.financial_operations import plan_operation,answer_operation

CID,IID=str(uuid4()),str(uuid4())


class Reader:
    def __init__(self,entity='CONSOLIDATED',unit='VND',missing=None):
        self.entity,self.unit,self.missing=entity,unit,missing
    async def retrieve(self,question,scope):
        metric,period=scope['metric_code'],scope['periods'][0]
        values={('TOTAL_ASSETS','2026-Q1'):100_000_000,('TOTAL_ASSETS','2026-Q2'):125_000_000,
                ('TOTAL_LIABILITIES','2026-Q2'):50_000_000}
        if (metric,period)==self.missing:return {'corpus_version_id':CID,'data_version':{'kind':'INDEX','id':IID},'items':[]}
        doc=financial_documents([dict(report_id='test-'+period,period_code=period,symbol='CTG',company_name='CTG',
            statement_scope=self.entity,section='BALANCE_SHEET',code=metric,canonical_name=metric,
            observation_id=metric+period,value=values[(metric,period)],unit=self.unit)],renderer_version='db-financial-v3')[0]
        ch=chunk_document(doc)[0]
        return {'schema_version':'1.1','query_id':str(uuid4()),'corpus_version_id':CID,'data_version':{'kind':'INDEX','id':IID},
            'items':[dict(evidence_id=ch.chunk_id,chunk_id=ch.chunk_id,source_id=doc.document_id,source_type='BCTC',
                          source_sha256='a'*64,content_sha256=ch.content_hash,source_verified=True,locator=ch.locator,
                          passage=ch.text,title='CTG',score={'type':'RRF','value':1.0})]}


def execute(question,reader=None):
    decision=analyze_live(question)
    plan=plan_operation(question,decision)
    assert plan is not None
    return asyncio.run(answer_operation(question,plan,reader or Reader(),Budget(Limits.load())))


@pytest.mark.parametrize('question',[
    'Tổng tài sản CTG cuối quý 2/2026 tăng hay giảm so với cuối quý 1/2026?',
    'Tổng tài sản CTG cuối 2026-Q1 và 2026-Q2 chênh nhau bao nhiêu?'])
def test_two_explicit_quarters_compare_chronologically_without_model_arithmetic(question):
    result=execute(question)
    assert result['answering']['status']=='DRAFT_READY'
    assert result['answering']['calculation']['value']=='25.00'
    assert result['answering']['calculation']['statement_scope']=='CONSOLIDATED'
    assert len(result['answering']['citations'])==2
    assert result['answering']['budget']['calls_used']==0


def test_ratio_uses_two_exact_metric_rows_and_records_the_formula():
    result=execute('Nợ phải trả trên tổng tài sản CTG 2026-Q2 là bao nhiêu phần trăm?')
    calc=result['answering']['calculation']
    assert calc['formula']=='numerator / denominator * 100'
    assert calc['value']=='40.0'
    assert {v['metric_code']for v in calc['operands']}=={'TOTAL_LIABILITIES','TOTAL_ASSETS'}


@pytest.mark.parametrize(('entity','unit'),[('UNKNOWN','VND'),('CONSOLIDATED','SOURCE_NATIVE')])
def test_unknown_scope_or_unit_keeps_original_rows_and_does_not_calculate(entity,unit):
    result=execute('Tổng tài sản CTG 2026-Q1 và 2026-Q2 chênh bao nhiêu?',Reader(entity,unit))
    assert result['answering']['calculation'] is None
    assert result['answering']['cautions']
    assert len(result['answering']['claims'])==2


def test_one_missing_operand_is_reported_not_replaced_by_another_metric():
    result=execute('Nợ phải trả trên tổng tài sản CTG 2026-Q2 là bao nhiêu phần trăm?',
                   Reader(missing=('TOTAL_LIABILITIES','2026-Q2')))
    assert result['answering']['calculation'] is None
    assert 'Chưa tìm thấy' in result['answering']['draft']


def test_explicit_news_or_annual_report_question_stays_in_its_source():
    for question in ('Theo BCTN 2025, tổng tài sản CTG tăng so với 2024 thế nào?',
                     'Theo tin CTG, nợ phải trả trên tổng tài sản là bao nhiêu?'):
        assert plan_operation(question,analyze_live(question)) is None


@pytest.mark.parametrize('question',[
    'FPT có những công ty con nào và doanh thu thuần, lợi nhuận sau thuế năm 2025 là bao nhiêu?',
    'Ai là Chủ tịch CTG và nợ phải trả trên tổng tài sản CTG quý 2/2026 bao nhiêu phần trăm?',
])
def test_financial_fast_path_does_not_drop_the_relationship_part(question):
    assert plan_operation(question,analyze_live(question)) is None


def test_parent_shareholders_metric_is_not_mistaken_for_a_shareholder_lookup():
    question='Lợi nhuận sau thuế thuộc cổ đông công ty mẹ và doanh thu thuần FPT năm 2025 là bao nhiêu?'
    plan=plan_operation(question,analyze_live(question))
    assert plan is not None and plan['operation']=='VALUES'
    assert {op['metric_code']for op in plan['operands']}=={'PARENT_NET_PROFIT','NET_REVENUE'}


def test_different_report_scopes_cannot_be_subtracted():
    class DifferentScopes(Reader):
        async def retrieve(self,q,scope):
            self.entity='CONSOLIDATED' if scope['periods']==['2026-Q1'] else 'SEPARATE'
            return await super().retrieve(q,scope)
    result=execute('Tổng tài sản CTG 2026-Q1 và 2026-Q2 chênh bao nhiêu?',DifferentScopes())
    assert result['answering']['calculation'] is None


def test_changed_corpus_or_tampered_row_stays_an_integrity_error():
    class ChangedCorpus(Reader):
        async def retrieve(self,q,scope):
            pack=await super().retrieve(q,scope)
            if scope['periods']==['2026-Q2']:pack['corpus_version_id']=str(uuid4())
            return pack
    with pytest.raises(ValueError,match='FINANCIAL_CORPUS_CHANGED'):
        execute('Tổng tài sản CTG 2026-Q1 và 2026-Q2 chênh bao nhiêu?',ChangedCorpus())
    class Tampered(Reader):
        async def retrieve(self,q,scope):
            pack=await super().retrieve(q,scope)
            pack['items'][0]['passage']+=' invented 999'
            return pack
    from src.b1_answering.evidence.citations import CitationError
    with pytest.raises(CitationError):
        execute('Tổng tài sản CTG 2026-Q1 và 2026-Q2 chênh bao nhiêu?',Tampered())


def test_company_slot_continues_same_operation_but_new_topic_drops_it():
    first=execute('Nợ phải trả trên tổng tài sản CTG 2026-Q2 là bao nhiêu phần trăm?')
    context=first['scope']
    assert '_pending_metric'not in context
    following=analyze_live('Còn FPT cùng kỳ?',context)
    plan=plan_operation('Còn FPT cùng kỳ?',following)
    assert plan['operation']=='RATIO'
    assert plan['scope']['companies']==['FPT']
    new=analyze_live('Tin tức FPT mới nhất',context)
    assert plan_operation('Tin tức FPT mới nhất',new) is None
    advice='Có nên mua CTG khi nợ phải trả trên tổng tài sản cao không?'
    assert plan_operation(advice,analyze_live(advice,context)) is None
