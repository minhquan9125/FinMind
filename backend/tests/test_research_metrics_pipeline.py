"""Per-request routing and grounding facts recorded for the admin Trace page."""
from datetime import datetime, timezone

from src.documents.research_metrics import ResearchMetrics, observed_details


def graph_result():
    return {
        'status': 'EVIDENCE_READY', 'scope': {'companies': ['FPT']},
        'hybrid_router': {'route': 'BOTH', 'tasks': [{'adapter': 'GRAPH'}, {'adapter': 'CONTENT'}, 'junk'],
                          'graph_calls': 1, 'vector_calls': 2},
        'evidence_pack': {'items': [{'source_type': 'BCTN'}, {'source_type': 'BCTN'}, {'source_type': 'NEWS'}, {}]},
        'answering': {
            'status': 'DRAFT_READY', 'reason_code': 'OK', 'citations': [{'evidence_id': 'a'}, {'evidence_id': 'b'}],
            'manifest': {'response_mode': 'NATURAL', 'components': {
                'gemini': True, 'citation_binding': True, 'extractive_claim_check': False, 'support_quote_check': True,
                'numeric_source_check': True, 'b3_evidence_gate': False, 'b3_answer_verification': False, 'tools': False}},
            'trace': [{'event': 'generation_reserved'}, {'event': 'draft_bound_to_evidence'}, {'nonsense': 1}]},
    }


def test_observed_details_report_only_what_the_pipeline_measured():
    d = observed_details(graph_result())
    assert d['router'] == {'route': 'BOTH', 'adapters': ['GRAPH', 'CONTENT'], 'graph_calls': 1, 'vector_calls': 2}
    assert d['evidence_types'] == {'BCTN': 2, 'NEWS': 1, 'UNKNOWN': 1}
    g = d['grounding']
    assert (g['status'], g['citations'], g['response_mode']) == ('DRAFT_READY', 2, 'NATURAL')
    assert g['checks'] == {'citation_binding': True, 'extractive_claim_check': False,
                           'support_quote_check': True, 'numeric_source_check': True}
    assert g['events'] == ['generation_reserved', 'draft_bound_to_evidence'] and g['draft_rejected_reason'] is None
    assert d['b3'] == {'b3_evidence_gate': False, 'b3_answer_verification': False}


def test_a_rejected_gemini_draft_is_visible_with_its_reason():
    result = graph_result()
    result['answering']['trace'].append({'event': 'draft_bound_to_source_row', 'reason_code': 'UNSUPPORTED_NUMBER'})
    assert observed_details(result)['grounding']['draft_rejected_reason'] == 'UNSUPPORTED_NUMBER'


def test_missing_sections_stay_missing_instead_of_being_invented():
    d = observed_details({'status': 'NO_DATA'})
    assert d['router'] is None and d['grounding'] is None and d['evidence_types'] == {} and d['b3'] == {}
    assert observed_details({'answering': {'status': 'X', 'manifest': {'components': {'b3_evidence_gate': 'yes'}}}})['b3'] == {}


def test_details_are_stored_per_request_and_rolled_up(tmp_path):
    metrics = ResearchMetrics(tmp_path)
    now = datetime.now(timezone.utc).isoformat()
    metrics.record('r1', now, 1200, graph_result(), [])
    rejected = graph_result()
    rejected['answering']['trace'].append({'event': 'draft_bound_to_source_row', 'reason_code': 'X'})
    rejected['hybrid_router'] = {'route': 'VECTOR', 'tasks': [], 'graph_calls': 0, 'vector_calls': 1}
    metrics.record('r2', now, 900, rejected, [])
    metrics.record('r3', now, 10, {'status': 'ASK_CLARIFICATION'}, [])           # no router/grounding data

    detail = metrics.detail('r1')['details']
    assert detail['router']['route'] == 'BOTH' and detail['grounding']['citations'] == 2
    assert detail['question'] is None                                            # existing fields still written

    pipeline = metrics.summary()['pipeline']
    assert pipeline['requests_observed'] == 2
    assert pipeline['routes'] == {'BOTH': 1, 'VECTOR': 1}
    assert (pipeline['graph_calls'], pipeline['vector_calls']) == (1, 3)
    assert pipeline['grounded_answers'] == 2 and pipeline['drafts_rejected_by_source_check'] == 1
