"""Replay the explicit evidence selected in WBS06's source review.

Produces offline review recommendations and enriched envelopes for acceptance
testing. Does not impersonate an application ADMIN or write review/graph data.
"""
import argparse
import asyncio
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
import asyncpg
from src.core.config import get_settings
from src.graph_review.engine import IdentityRegistry,ReviewEngine
from src.graph_review.adapters import source_ref,from_envelope
from src.graph_review.models import Evidence,digest
from src.graph_review.sources import PostgresSourceReader,compare_source
from src.sprint4_runtime.contracts import validate_envelope

TCB24='8ec9c4e6-cd43-559a-837b-49335340f4c5'
TCB25='85deaf00-3748-5f3d-95a2-68495dc229fc'
ELC24='f0730a07-8ab5-548a-a3b8-e099489d0f29'

# Each proof is selected by the reviewer from actual paragraphs; no missing
# date is filled from an annual-report title, an embedding, or a fixture.
PROOFS={
 TCB24:dict(as_of='2024-12-31',chunks=['a7e9a633-7d76-5ca8-9c00-d4fb668ff5cf'],
  field='consolidation_basis',value='hợp nhất toàn bộ',
  explanation='Sơ đồ có ngày 31/12/2024 và liên kết tên pháp lý; thuyết minh xác nhận hợp nhất toàn bộ các công ty con.'),
 TCB25:dict(as_of='2025-12-31',chunks=['4d3df972-94af-535a-ad99-fefdc1aa69e1'],
  field='consolidation_basis',value='hợp nhất toàn bộ',
  explanation='Thuyết minh nêu tại ngày 31/12/2025 và cơ sở hợp nhất; đối chiếu tên pháp lý và mục công ty con trong cùng báo cáo.'),
 ELC24:dict(as_of='2024-12-31',chunks=['a9fdcc2c-b4f2-57c5-b9e6-f6580f839882','37692544-1a46-5d1f-b6a1-4df385489542',
  'feaa35e5-66e3-5141-98a4-0acff926784b'],
  field='consolidation_basis',value='kiểm soát',
  explanation='Báo cáo kiểm toán xác định BCTC tại 31/12/2024 gồm bản thuyết minh; danh sách công ty nằm trong thuyết minh 1.5, cùng cơ sở kiểm soát tại 3.1.'),
}


def select_quote(chunk,role):
    text=chunk['text']
    if role=='tcb24_policy':
        match=re.search(r'Các công ty con được hợp nhất toàn bộ[\s\S]*?đối với công ty con\.',text)
        if not match:raise ValueError('Expected TCB24 consolidation paragraph absent')
        return match.group(0)
    if role=='elc_policy':
        match=re.search(r'các công ty do Công ty mẹ kiểm soát \(các công ty con\)\.',text)
        if not match:raise ValueError('Expected ELC control paragraph absent')
        return match.group(0)
    if role=='associate_policy':
        match=re.search(r'Các khoản đầu tư vào các công ty liên kết được ghi nhận theo phương pháp vốn chủ sở hữu\.',text)
        if not match:raise ValueError('Expected ELC equity-method paragraph absent')
        return match.group(0)
    return text


async def main(args):
    folder=args.input.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    original=json.loads((folder/'original_reproduction.json').read_text('utf-8'))
    automatic=json.loads((folder/'automatic_r1_audit.json').read_text('utf-8'))
    if original['reproduced_count']!=23 or original['identical_compact_relation_count']!=23:
        raise ValueError('Original output reproduction not equivalent to the 23-candidate handoff')
    registry_rows=json.loads((folder/'runtime/nhan_original_runtime/company.registry.20261030.r1.json').read_text('utf-8'))
    current_registry=json.loads((ROOT/'backend/src/sprint4_runtime/company.registry.20261030.r1.json').read_text('utf-8'))
    if registry_rows!=current_registry:raise ValueError('Registry content differs from original extractor')
    registry=IdentityRegistry(registry_rows)
    raw_by_id={r['candidate']['candidate_id']:r for r in automatic['owners']['NHAN']['items']}
    timestamp=datetime.now(timezone.utc).isoformat()
    report=dict(schema='wbs06-nhan-source-review-v3',checked_at=timestamp,commit=original['commit'],
        database_writes=0,neo4j_writes=0,application_admin_action=False,registry_sha256=registry.sha256,
        original_reproduced_count=23,original_equivalent_count=23,source_verified_count=23,
        original_evidence_count=49,role='WBS06 offline evidence review, for user acceptance',
        recommendation_is_not_db_approval=True,items=[],approved_envelopes=[],findings=[])
    connection=await asyncpg.connect(get_settings().database_url,timeout=15,statement_cache_size=0)
    try:
        async with connection.transaction(readonly=True,isolation='repeatable_read'):
            reader=PostgresSourceReader(connection);engine=ReviewEngine(reader,registry)
            for original_item in original['items']:
                ident=original_item['candidate_id'];doc_id=original_item['document_id']
                auto=raw_by_id[ident];candidate=deepcopy(auto['candidate'])
                # Restore the original entity aliases/identity fields as well;
                # the compact bundle intentionally omits some of these fields.
                for endpoint in ('subject','object'):
                    original_entity=original_item[endpoint]
                    candidate[endpoint]={k:original_entity.get(k) for k in
                        ('entity_id','entity_type','canonical_name','identity_key','resolution_status')}
                    candidate[endpoint]['aliases']=original_entity.get('aliases',[])
                # Always replay even the original refs: saved reports alone
                # cannot establish current source verification.
                for ref in candidate['evidence']:
                    evidence=Evidence.model_validate(ref)
                    compare_source(evidence,await reader.resolve(evidence))
                item=dict(candidate_id=ident,document_id=doc_id,relation_type=candidate['relation_type'],
                    subject=candidate['subject'],object=candidate['object'],source_verified=True,
                    original_attributes=original_item['relation']['attributes'],
                    original_temporal=original_item['relation']['temporal'],
                    original_relation_supported=True,application_load_allowed=False)
                proof=PROOFS.get(doc_id)
                if proof:
                    envelope=json.loads((folder/f'{doc_id}.original-envelope.json').read_text('utf-8'))
                    chunks={c['chunk_id']:c for c in envelope['chunks']}
                    selected=list(proof['chunks'])
                    if doc_id==ELC24 and candidate['relation_type']=='HAS_ASSOCIATE':
                        selected[-1]='537ad7c6-be07-59ce-9bb9-c7fab0d08f39'
                        field,value='accounting_basis','phương pháp vốn chủ sở hữu'
                    else:field,value=proof['field'],proof['value']
                    for chunk_id in selected:
                        role=('tcb24_policy' if doc_id==TCB24 else 'elc_policy' if chunk_id=='feaa35e5-66e3-5141-98a4-0acff926784b'
                              else 'associate_policy' if chunk_id=='537ad7c6-be07-59ce-9bb9-c7fab0d08f39' else 'scope')
                        quote=select_quote(chunks[chunk_id],role)
                        source=await reader.read_current(chunk_id,automatic['corpus_id']) if 'corpus_id' in automatic else await reader.read_current(chunk_id,original['corpus_id'])
                        candidate['evidence'].append(source_ref(source,quote))
                    attrs={k:v for k,v in candidate['attributes'].items() if k!='inference_basis'}
                    attrs[field]=value
                    candidate['attributes']=attrs
                    candidate['temporal']['as_of']=proof['as_of']
                    candidate['extractor_metadata']['original_attributes']=original_item['relation']['attributes']
                    candidate['extractor_metadata']['review_context']=proof['explanation']
                    # A revised proposal is distinct from the immutable raw candidate.
                    candidate['candidate_id']='review:'+digest(candidate)[:32]
                    evaluated=await engine.evaluate(candidate)
                    if not evaluated.source_verified or evaluated.verification_mode!='LIVE' or evaluated.status=='REJECTED':
                        raise ValueError(f'Reviewed proposal failed live checks: {ident}: {evaluated.reasons}')
                    if set(evaluated.reasons)-{'WARN_EVIDENCE_INSUFFICIENT'}:
                        raise ValueError(f'Unexpected unresolved facts: {ident}: {evaluated.reasons}')
                    # The table/notes scope was reviewed above. This is an
                    # offline recommendation; no ADMIN identity is fabricated.
                    reviewed=deepcopy(original_item['relation'])
                    reviewed.update(relation_id=candidate['candidate_id'],attributes=attrs,temporal=candidate['temporal'],
                        evidence=[dict(document_id=e['document_id'],chunk_id=e['chunk_id'],quote=e['quote']) for e in candidate['evidence']],
                        review=dict(status='APPROVED',reviewer='WBS06-offline-proposal-for-user-acceptance',reviewed_at=timestamp))
                    ids={e['chunk_id'] for e in reviewed['evidence']}
                    payload=dict(schema_version='2.1.0',corpus_id=original['corpus_id'],dataset_version=original['index_version_id'],
                        documents=envelope['documents'],chunks=[chunks[c] for c in ids],
                        entities=[original_item['subject'],original_item['object']],mentions=[],relations=[reviewed])
                    validate_envelope(payload)
                    # Export must represent exactly the proposal we checked.
                    exported=from_envelope(payload)[0]
                    for key in ('relation_type','subject','object','attributes','temporal','evidence'):
                        if exported[key]!=candidate[key]:raise ValueError('Reviewed/exported field differs: '+key)
                    item.update(handoff_status='APPROVED',reasons=[],explanation=proof['explanation'],
                        reviewed_attributes=attrs,reviewed_temporal=candidate['temporal'],
                        reviewed_candidate=candidate,technical_evaluation=evaluated.model_dump(mode='json'),
                        evidence=candidate['evidence'],envelope_file=f"approved-{candidate['candidate_id'].replace(':','-')}.json")
                    target=out/item['envelope_file'];target.write_text(json.dumps(payload,ensure_ascii=False,indent=2),'utf-8')
                    report['approved_envelopes'].append(item['envelope_file'])
                else:
                    if candidate['relation_type']=='OWNS_SHARES':
                        reasons=['ERR_REVIEW_HOLDING_BASIS_NOT_GROUNDED','ERR_REVIEW_TEMPORAL_BASIS_NOT_GROUNDED']
                        explanation='Nguồn xác nhận tỷ lệ sở hữu, nhưng chưa chứng minh rõ trực tiếp/gián tiếp và mốc cho phát biểu này. Không suy direct từ 100%.'
                    else:
                        reasons=['ERR_REVIEW_TEMPORAL_BASIS_NOT_GROUNDED']
                        explanation='Nguồn có xác nhận quan hệ; chưa ghim được mốc as_of/valid_from đủ rõ cho phát biểu này. Không lấy năm ở tiêu đề BCTN làm ngày hiệu lực.'
                    item.update(handoff_status='REJECTED',reasons=reasons,explanation=explanation,evidence=candidate['evidence'])
                    if candidate['relation_type']=='COOPERATES_WITH':
                        item['available_scope_from_full_chunk']='ứng dụng công nghệ xanh'
                report['items'].append(item)
    finally:await connection.close()
    from collections import Counter
    report['counts']=dict(Counter(i['handoff_status'] for i in report['items']))
    report['findings'].append(dict(code='UNRESOLVED_SMARTEK_NUMERIC_CLAIM',
        explanation='Nguồn phần giới thiệu có 74,4%, bảng thuyết minh có 88,35%; không duyệt hoặc đưa tỷ lệ Smartek vào các proposal quan hệ định tính.',
        source_chunks=['e67bc152-bd52-539e-9cde-32ef4bfca7a6','45bd4880-51e0-5f49-8a77-41a51fb3bb42']))
    for item in report['items']:
        if 'Smartek' in item['object']['canonical_name']:
            if item.get('reviewed_attributes',{}).get('ownership_percent') is not None:raise ValueError('Unresolved Smartek percentage must not be approved')
            item['excluded_claims']=['ownership_percent: 74.4% vs 88.35% unresolved; do not infer a direct stake from group benefits']
    report['sha256_original_reproduction']=hashlib.sha256((folder/'original_reproduction.json').read_bytes()).hexdigest()
    (out/'nhan_review_v3.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(dict(counts=report['counts'],original_reproduced=23,original_equivalent=23,db_writes=0,neo4j_writes=0)),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    asyncio.run(main(parser.parse_args()))
