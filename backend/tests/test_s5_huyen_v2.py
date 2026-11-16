"""V2 requirements owned by Huyen; no provider/network/model calls."""
from copy import deepcopy
import json
import pytest
from src.retrieval_orchestration import intent_routing as routing
from src.retrieval_orchestration import intent_fallback_contract as contract

POLICY = 'intent-request-objectives-v2-11-r2'

def proposal(question, label, evidence, components=(), reason='EXPLICIT_REQUEST_TYPE', status='PROPOSED', unresolved=()):
    return {'question': question, 'resolution': dict(question=question, intent_label=label,
        ranking_policy=POLICY, score_type='DECISION_EVIDENCE_NO_CONFIDENCE', confidence=None,
        runtime_enabled=False, reason=reason, status=status, component_labels=list(components),
        explicit_evidence=[dict(text=text, intent_label=kind) for text, kind in evidence],
        unresolved_requests=list(unresolved), contains_restricted_component=label=='OUT_OF_SCOPE' or 'OUT_OF_SCOPE' in components)}

CASES = [
    ('Gia FPT hom nay?', 'PRICE', 'MARKET'),
    ('Doanh thu FPT nam 2025 bao nhieu?', 'NUMERIC', 'VECTOR'),
    ('Phan tich xu huong FPT', 'ANALYSIS', 'MARKET'),
    ('Tin tuc FPT hom nay', 'NEWS', 'MARKET'),
    ('Tom tat bao cao thuong nien FPT', 'REPORT_CONTENT', 'VECTOR'),
    ('Ai la Chu tich FPT?', 'PERSON_ROLE', 'GRAPH'),
    ('FPT co nhung cong ty con nao?', 'ENTITY_RELATION', 'GRAPH'),
    ('FPT la cong ty gi?', 'COMPANY_OVERVIEW', 'BOTH'),
    ('Xin chao', 'CONVERSATION', 'SESSION'),
    ('Co nen mua FPT?', 'OUT_OF_SCOPE', 'REFUSE'),
]

@pytest.mark.parametrize('question,label,route', CASES)
def test_explicit_current_rules_route_all_single_v2_labels(question,label,route):
    raw=proposal(question,label,[(question,label)])
    before=deepcopy(raw)
    out=routing.decide_intent_route_v2(raw, question=question, company_ticker='FPT')
    assert out['route']==route and out['intent_label']==label
    assert out['source']=='RULES' and out['need_fallback'] is False
    assert raw==before

@pytest.mark.parametrize('question,parts,route', [
    ('Gia FPT hom nay? Cho biet doanh thu FPT nam 2025.', [('Gia FPT hom nay?', 'PRICE'),('Cho biet doanh thu FPT nam 2025','NUMERIC')], 'BOTH'),
    ('Ai la Chu tich FPT? FPT co nhung cong ty con nao?', [('Ai la Chu tich FPT?', 'PERSON_ROLE'),('FPT co nhung cong ty con nao?', 'ENTITY_RELATION')], 'GRAPH'),
    ('Gia FPT hom nay? Co nen mua FPT?', [('Gia FPT hom nay?', 'PRICE'),('Co nen mua FPT?', 'OUT_OF_SCOPE')], 'REFUSE'),
])
def test_mixed_routes_need_verified_current_components(question,parts,route):
    from src.retrieval_orchestration.intent_v2_rules import requests, explicit_intent
    evidence=[(s,explicit_intent(s)) for s in requests(question)]
    raw=proposal(question,'MIXED',evidence,sorted({kind for _,kind in evidence}),reason='MULTIPLE_REQUEST_TYPES')
    out=routing.decide_intent_route_v2(raw,question=question,company_ticker='FPT')
    assert out['route']==route and not out['need_fallback']


def test_model_guess_never_uses_old_cosine_threshold_or_refuses():
    q='C?u ch?a r?'
    raw=proposal(q,'OUT_OF_SCOPE',[],reason='CLASSIFIER_PROPOSAL',unresolved=[q])
    out=routing.decide_intent_route_v2(raw,question=q,company_ticker='FPT')
    assert out['decision']=='NEED_FALLBACK' and out['route'] is None

@pytest.mark.parametrize('change', [dict(question='c?u c?'), dict(confidence=.99), dict(runtime_enabled=True), dict(explicit_evidence=[]), dict(contains_restricted_component=True)])
def test_forged_or_stale_evidence_is_contract_error(change):
    q='Gia FPT hom nay?'; raw=proposal(q,'PRICE',[(q,'PRICE')]); raw['resolution'].update(change)
    with pytest.raises(routing.IntentClassificationContractError):
        routing.decide_intent_route_v2(raw,question=q,company_ticker='FPT')


def test_direct_rule_switch_and_verified_scope_guards():
    q='Gia FPT hom nay?'; raw=proposal(q,'PRICE',[(q,'PRICE')])
    assert routing.decide_intent_route_v2(raw,question=q,company_ticker='FPT',allow_direct_rules=False)['need_fallback']
    assert routing.decide_intent_route_v2(raw,question=q)['decision']=='ASK_CLARIFICATION'
    q='Co nen mua FPT?'; raw=proposal(q,'OUT_OF_SCOPE',[(q,'OUT_OF_SCOPE')])
    assert routing.decide_intent_route_v2(raw,question=q)['route']=='REFUSE'
    q='Xin chao'; raw=proposal(q,'CONVERSATION',[(q,'CONVERSATION')])
    assert routing.decide_intent_route_v2(raw,question=q)['route']=='SESSION'


def test_historical_news_uses_verified_archive_period():
    q='Tin tuc FPT nam 2025'; raw=proposal(q,'NEWS',[(q,'NEWS')])
    assert routing.decide_intent_route_v2(raw,question=q,company_ticker='FPT',period='2025')['route']=='VECTOR'


def req():
    return {'question':'Ai la Chu tich FPT?', 'conversation_scope':{'company_ticker':'FPT','period':'2025'},
            'allowed_labels':list(contract.V2_ALLOWED_LABELS)}

def reply(**kw):
    return dict(intent_label='CHUC_VU',confidence=.85,reason='Tra c?u ch?c v?',extracted_company='FPT')|kw


def test_v2_wire_schema_matches_deployed_demo_without_provider_route_or_period():
    from src.retrieval_orchestration.intent_gate_v2 import RESPONSE_SCHEMA
    assert contract.V2_RESPONSE_JSON_SCHEMA['properties']==RESPONSE_SCHEMA['properties']
    out=contract.validate_fallback_response_v2(reply(),request=req())
    assert out['route']=='GRAPH' and out['extracted_period']=='2025'
    assert out['status']=='FALLBACK_VALIDATED'

@pytest.mark.parametrize('raw', [reply(route='GRAPH'),reply(extracted_period='2025'),reply(confidence=True),reply(confidence=.59),reply(confidence=float('nan')),reply(extracted_company='VCB'),reply(reason=' '),reply(intent_label='XU_HUONG'),'{"intent_label":"GIA","intent_label":"CHUC_VU"}', '```json {} ```'])
def test_invalid_provider_output_asks_clarification(raw):
    out=contract.validate_fallback_response_v2(raw,request=req())
    assert out['status']=='FALLBACK_FAILED' and out['route']=='ASK_CLARIFICATION'


def test_ai_cannot_invent_scope_even_with_high_confidence():
    r=req(); r['conversation_scope']['company_ticker']=None
    out=contract.validate_fallback_response_v2(reply(),request=r,company_required=False)
    assert out['reason_code']=='UNVERIFIED_COMPANY'

@pytest.mark.parametrize('options', [dict(timed_out=True),dict(provider_error=RuntimeError('503'))])
def test_provider_failure_stays_safe(options):
    assert contract.validate_fallback_response_v2(reply(),request=req(),**options)['route']=='ASK_CLARIFICATION'


def test_preparation_only_for_current_v2_fallback_and_no_history_on_wire():
    q='Ai la Chu tich FPT?'; raw=proposal(q,'PERSON_ROLE',[(q,'PERSON_ROLE')])
    out=routing.decide_intent_route_v2(raw,question=q,company_ticker='FPT',allow_direct_rules=False)
    prepared=contract.prepare_fallback_request_v2(out,question=q)
    assert set(prepared['request'])=={'question','conversation_scope','allowed_labels'}
    with pytest.raises(routing.IntentClassificationContractError):
        contract.prepare_fallback_request_v2(out,question='c?u kh?c')


def test_provider_mixed_cannot_invent_components():
    assert contract.validate_fallback_response_v2(reply(intent_label='KET_HOP'),request=req())['route']=='ASK_CLARIFICATION'


def test_out_of_scope_and_conversation_do_not_need_company():
    r=req(); r['conversation_scope']['company_ticker']=None
    for code,route in [('NGOAI_PHAM_VI','REFUSE'),('HOI_THOAI','SESSION')]:
        assert contract.validate_fallback_response_v2(reply(intent_label=code,extracted_company=None),request=r)['route']==route


def test_scope_clarification_never_prepares_a_provider_call():
    q='Gia FPT hom nay?'; raw=proposal(q,'PRICE',[(q,'PRICE')])
    out=routing.decide_intent_route_v2(raw,question=q)
    prepared=contract.prepare_fallback_request_v2(out,question=q)
    assert prepared['request'] is None and prepared['need_fallback'] is False


@pytest.mark.parametrize('bad_score',[True,'0.9',float('nan'),float('inf'),-1,1.01])
def test_bad_v2_classifier_score_is_not_a_valid_rule_trace(bad_score):
    q='Gia FPT hom nay?'; raw=proposal(q,'PRICE',[(q,'PRICE')])
    raw['base_ranking']=dict(question=q,ranking_policy='intent-linear-v2',
        score_type='CLASSIFIER_PROBABILITY_UNCALIBRATED',groups=[dict(intent_label='PRICE',score=bad_score),dict(intent_label='NEWS',score=.1)])
    with pytest.raises(routing.IntentClassificationContractError):
        routing.decide_intent_route_v2(raw,question=q,company_ticker='FPT')


def test_invalid_provider_mixed_components_fail_closed_instead_of_raising():
    assert contract.validate_fallback_response_v2(reply(intent_label='KET_HOP'),request=req(),
        query_components=[{},'PRICE'],query_components_confirmed=True)['route']=='ASK_CLARIFICATION'


def test_provider_json_is_compatible_with_existing_gate():
    from src.retrieval_orchestration.intent_gate_v2 import validate_fallback
    r=req(); raw=reply()
    assert validate_fallback(raw,request=r)['label']=='PERSON_ROLE'
    assert contract.validate_fallback_response_v2(raw,request=r)['canonical_intent']=='PERSON_ROLE'


@pytest.mark.parametrize('field,value', [('ranking_policy','wrong'),('score_type','wrong'),
    ('status','BAD'),('intent_label','TREND'),('reason','CLASSIFIER_PROPOSAL')])
def test_v2_resolution_metadata_and_rule_reason_are_checked(field,value):
    q='Gia FPT hom nay?'; raw=proposal(q,'PRICE',[(q,'PRICE')]); raw['resolution'][field]=value
    with pytest.raises(routing.IntentClassificationContractError):
        routing.decide_intent_route_v2(raw,question=q,company_ticker='FPT')


@pytest.mark.parametrize('setting',['yes',1,None])
def test_only_server_boolean_configuration_is_accepted(setting):
    q='Gia FPT hom nay?'; raw=proposal(q,'PRICE',[(q,'PRICE')])
    for key in ['allow_direct_rules','company_required']:
        with pytest.raises(routing.IntentClassificationContractError):
            routing.decide_intent_route_v2(raw,question=q,company_ticker='FPT',**{key:setting})


@pytest.mark.parametrize('q,scope',[('',{}),('Doanh thu FPT quy 5/2025?',{'company_ticker':'FPT'}),
    ('Gia FPT hom nay?',{'company_ticker':'not a ticker'})])
def test_scope_invalid_before_reading_malformed_classifier(q,scope):
    out=routing.decide_intent_route_v2(None,question=q,**scope)
    assert out['decision']=='ASK_CLARIFICATION' and out['contract_version']=='v2'
    assert contract.prepare_fallback_request_v2(out,question=q)['request'] is None


def test_followup_asks_for_context_before_search_or_ai():
    q='Con FPT thi sao?'; raw=proposal(q,'CONVERSATION',[(q,'CONVERSATION')],status='NEEDS_CONTEXT')
    out=routing.decide_intent_route_v2(raw,question=q)
    assert out['reason_code']=='CONTEXT_REQUIRED'
    assert contract.prepare_fallback_request_v2(out,question=q)['request'] is None


def test_known_and_unknown_clauses_keep_fallback():
    from src.retrieval_orchestration.intent_v2_rules import requests, explicit_intent
    q='Gia FPT hom nay? Lam xyzzy cho toi'
    spans=requests(q)
    evidence=[(s,explicit_intent(s)) for s in spans if explicit_intent(s)]
    unresolved=[s for s in spans if not explicit_intent(s)]
    raw=proposal(q,'PRICE',evidence,status='UNRESOLVED',reason='CLASSIFIER_PROPOSAL',unresolved=unresolved)
    assert routing.decide_intent_route_v2(raw,question=q,company_ticker='FPT')['need_fallback']


def test_classifier_trace_keeps_probability_separate_from_rule_evidence():
    q='Gia FPT hom nay?'; raw=proposal(q,'PRICE',[(q,'PRICE')])
    raw['base_ranking']=dict(question=q,ranking_policy='intent-linear-v2',
        score_type='CLASSIFIER_PROBABILITY_UNCALIBRATED',groups=[dict(intent_label='NEWS',score=.7),dict(intent_label='PRICE',score=.2)])
    out=routing.decide_intent_route_v2(raw,question=q,company_ticker='FPT')
    assert out['intent_label']=='PRICE' and out['route']=='MARKET'
    assert out['model_ranking']['groups'][0]['intent_label']=='NEWS'
    assert out['model_top_1_score']==.7 and out['top_1_score'] is None


@pytest.mark.parametrize('base', [[],{},dict(ranking_policy='wrong'),
    dict(ranking_policy='intent-linear-v2',question='old',score_type='CLASSIFIER_PROBABILITY_UNCALIBRATED',groups=[]),
    dict(ranking_policy='intent-linear-v2',question='Gia FPT hom nay?',score_type='CLASSIFIER_PROBABILITY_UNCALIBRATED',groups=[None,None])])
def test_invalid_base_ranking_is_contract_error(base):
    q='Gia FPT hom nay?'; raw=proposal(q,'PRICE',[(q,'PRICE')]); raw['base_ranking']=base
    with pytest.raises(routing.IntentClassificationContractError):
        routing.decide_intent_route_v2(raw,question=q,company_ticker='FPT')


def test_session_component_must_be_resolved_before_mixed_search():
    assert routing._v2_route('MIXED',['CONVERSATION','PRICE']) is None
    with pytest.raises(routing.IntentClassificationContractError):
        routing._v2_route('TREND')


@pytest.mark.parametrize('question', ['Co nen mua FPT?', 'Gia FPT hom nay? Co nen mua FPT?'])
def test_ai_cannot_turn_a_rule_verified_restricted_request_into_search(question):
    r=req(); r['question']=question
    out=contract.validate_fallback_response_v2(reply(intent_label='GIA'),request=r)
    assert out['route']=='ASK_CLARIFICATION' and out['reason_code']=='RESTRICTED_LABEL_CONFLICT'
