"""Prepare N18/N30/N40 for re-review, offline; never writes reviews or graphs.

Run as a module from the repository root. Input is the original WBS06 review ZIP;
output is a new directory. The 34 approved envelopes and all originals stay intact.
"""
import argparse
import asyncio
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

from backend.src.graph_review.adapters import from_envelope
from backend.src.graph_review.engine import IdentityRegistry, ReviewEngine
from backend.src.graph_review.models import VerifiedSource
from backend.src.graph_review.sources import FixtureSourceReader
from backend.src.sprint4_runtime.contracts import validate_envelope

RUNTIME = Path(__file__).resolve().parents[1] / 'src/sprint4_runtime'
PLANS = {
    'N18': ('accounting_basis', 'phương pháp vốn chủ sở hữu',
            ['91aef6a2-2cef-5208-ad0e-ea9e2b562b48'],
            ['JOINT_VENTURE_MAPPING_UNCONFIRMED']),
    'N30': ('consolidation_basis', 'kiểm soát',
            ['4b7e4205-f25e-5e6e-b7cd-dc369dd5d468', 'b3b3764c-99ab-5f1b-bfa7-42c4bf206b38'],
            ['FTEL_CANONICAL_ID_MAPPING_UNCONFIRMED']),
    'N40': ('consolidation_basis', 'hợp nhất toàn bộ',
            ['d772bc16-0492-5ac8-8a6e-f23a7ad7b86b'],
            ['FTEL_CANONICAL_ID_MAPPING_UNCONFIRMED', 'READ_FTEL_POLICY_CONTINUATION']),
}


def enrich_proposal(original, proof_chunks, field, value):
    """Add explicitly selected proof to a new PENDING claim, without changing time/IDs of endpoints."""
    validate_envelope(original)
    if len(original['relations']) != 1 or original['relations'][0]['review']['status'] != 'PENDING':
        raise ValueError('Expected exactly one original PENDING candidate')
    result = deepcopy(original)
    relation = result['relations'][0]
    expected = {'HAS_SUBSIDIARY': 'consolidation_basis', 'HAS_ASSOCIATE': 'accounting_basis'}
    if field != expected.get(relation['relation_type']) or not value.strip():
        raise ValueError('Basis does not match relation type')
    if not proof_chunks or not any(value in chunk['text'] for chunk in proof_chunks):
        raise ValueError('Selected source does not contain the basis')
    document_ids = {e['document_id'] for e in relation['evidence']}
    documents = {d['document_id']: d for d in result['documents']}
    chunks = {(c['document_id'], c['chunk_id']): c for c in result['chunks']}
    for chunk in proof_chunks:
        if (chunk['document_id'] not in document_ids
                or chunk['document_version'] != documents[chunk['document_id']]['document_version']):
            raise ValueError('Basis must belong to the same document and version as the original claim')
        key = chunk['document_id'], chunk['chunk_id']
        if key in chunks and chunks[key] != chunk:
            raise ValueError('Conflicting proof chunk ID')
        if key not in chunks:
            result['chunks'].append(deepcopy(chunk))
            chunks[key] = chunk
        evidence = {k: chunk[k] for k in ('document_id', 'chunk_id')} | {'quote': chunk['text']}
        if evidence not in relation['evidence']:
            relation['evidence'].append(evidence)
    relation['attributes'][field] = value
    # New identity explicitly distinguishes this proposal from the rejected input
    # and from any separately approved WBS06 envelope.
    fingerprint = sha256(json.dumps(result, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    relation['relation_id'] = 'proposal:' + fingerprint[:32]
    relation['review'] = {'status': 'PENDING', 'reviewer': None, 'reviewed_at': None}
    return validate_envelope(result)


async def diagnose(payload, registry):
    documents = {d['document_id']: d for d in payload['documents']}
    sources = [VerifiedSource(
        c['document_id'], c['document_version'], c['chunk_id'], payload['corpus_id'],
        payload['dataset_version'], documents[c['document_id']]['source_sha256'],
        sha256(c['text'].encode()).hexdigest(), c['locator'], c['text'],
        verification_mode='FIXTURE') for c in payload['chunks']]
    engine = ReviewEngine(FixtureSourceReader(sources), IdentityRegistry(registry))
    return (await engine.evaluate(from_envelope(payload)[0])).model_dump(mode='json')


def build(package, output, registry_path):
    output = Path(output)
    if output.exists():
        raise ValueError('Choose a new output directory; existing reviews are never overwritten')
    registry_bytes = Path(registry_path).read_bytes()
    registry = json.loads(registry_bytes)
    prepared = []
    with ZipFile(package) as archive:
        root = 'WBS06_REVIEW_NHAN_20261105/'
        names = archive.namelist()
        if len(names) != len(set(names)) or archive.testzip() is not None:
            raise ValueError('Invalid or duplicate ZIP entries')
        manifest = json.loads(archive.read(root + 'package-manifest.json'))
        for filename, expected_hash in manifest['files_sha256'].items():
            if sha256(archive.read(root + filename)).hexdigest() != expected_hash:
                raise ValueError('Package hash differs: ' + filename)
        decisions = json.loads(archive.read(root + 'reviewer-decisions-reassessed.json'))
        by_case = {item['case']: item for item in decisions['items']}
        originals = root + 'WBS03_NEW_46_REVIEW_20261105/'
        for case, (field, value, chunk_ids, blockers) in PLANS.items():
            decision = by_case[case]
            if decision['status'] != 'REJECTED':
                raise ValueError('Expected rejected input: ' + case)
            raw = archive.read(originals + 'envelopes/' + case + '.json')
            original = json.loads(raw)
            if (sha256(raw).hexdigest() != decision['original_envelope_sha256']
                    or original['relations'][0]['relation_id'] != decision['original_candidate_id']):
                raise ValueError('Original candidate differs: ' + case)
            doc_id = original['documents'][0]['document_id']
            context = json.loads(archive.read(originals + 'context/' + doc_id + '.json'))
            available = {item['chunk']['chunk_id']: item['chunk'] for item in context['items']}
            proposal = enrich_proposal(original, [available[c] for c in chunk_ids], field, value)
            diagnosis = asyncio.run(diagnose(proposal, registry))
            prepared.append((case, raw, proposal, {
                'case': case, 'original_candidate_id': decision['original_candidate_id'],
                'proposal_id': proposal['relations'][0]['relation_id'],
                'original_sha256': sha256(raw).hexdigest(), 'status': 'PENDING',
                'original_review_decision': decision,
                'basis_field': field, 'basis_value': value, 'selected_chunk_ids': chunk_ids,
                'required_decisions': blockers, 'technical_evaluation': diagnosis,
                'application_load_allowed': False,
            }))
    output.mkdir(parents=True)
    (output / 'originals').mkdir()
    (output / 'proposals').mkdir()
    (output / 'cases').mkdir()
    (output / 'registry').mkdir()
    (output / 'registry' / Path(registry_path).name).write_bytes(registry_bytes)
    for case, original_bytes, proposal, item in prepared:
        (output / 'originals' / (case + '.json')).write_bytes(original_bytes)
        data = (json.dumps(proposal, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        item['proposal_file'] = 'proposals/' + case + '.json'
        item['proposal_sha256'] = sha256(data).hexdigest()
        (output / item['proposal_file']).write_bytes(data)
        relation = proposal['relations'][0]
        case_text = (f"# {case} — đề xuất gửi review lại\n\n"
                     f"Trạng thái: PENDING. Không phải quyết định APPROVED.\n\n"
                     f"- ID gốc: `{item['original_candidate_id']}`\n"
                     f"- ID proposal: `{item['proposal_id']}`\n"
                     f"- Thời gian giữ nguyên: `{relation['temporal']}`\n"
                     f"- Bổ sung: `{item['basis_field']}={item['basis_value']}`\n"
                     f"- Cần chốt: {', '.join(item['required_decisions'])}\n"
                     f"- Chẩn đoán offline: {', '.join(item['technical_evaluation']['reasons'])}\n\n"
                     f"[Bản gốc](../originals/{case}.json) · [Proposal](../proposals/{case}.json)\n\n"
                     "## Evidence trong proposal\n\n")
        for evidence in relation['evidence']:
            case_text += (f"Chunk `{evidence['chunk_id']}`\n\n```text\n"
                          + evidence['quote'] + "\n```\n\n")
        (output / 'cases' / (case + '.md')).write_text(case_text, 'utf-8')
    report = {'schema': 'wbs03-rejected-proposals-v1',
              'source_package_sha256': sha256(Path(package).read_bytes()).hexdigest(),
              'registry_sha256': sha256(registry_bytes).hexdigest(),
              'database_writes': 0, 'neo4j_writes': 0, 'verification_mode': 'FIXTURE',
              'application_load_allowed': False, 'items': [item[3] for item in prepared]}
    (output / 'proposal-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    (output / 'README.md').write_text(
        '# WBS03 — ba proposal gửi review lại\n\n'
        'Mở cases/N18.md, N30.md, N40.md. Đây là proposal PENDING, không phải gói duyệt/nạp graph.\n\n'
        '- N18: đã bổ sung basis. Cần chốt cách biểu diễn liên doanh và review hàng bảng.\n'
        '- N30 (2024), N40 (2025): giữ ngày/tỷ lệ/hai đầu, bổ sung basis; cần Hưng/WBS02 '
        'xác nhận registry r3. Không suy valid_to từ thay đổi phương pháp năm 2026.\n'
        '- N40 còn cảnh báo dự kiến do đoạn nguồn nói cả chính sách hiện tại và thay đổi '
        'trong tương lai. Cần đọc đoạn nối tiếp, không tự bỏ cảnh báo.\n'
        '- Registry kèm theo là bản ĐỀ XUẤT, chưa kích hoạt trong ứng dụng.\n'
        '- Kiểm tra lượt này là FIXTURE trên dữ liệu đã lưu; phải chạy reader LIVE trước khi duyệt.\n'
        '- Không thay 34 envelope đã duyệt, 12 quyết định cũ, DB hoặc graph READY.\n\n'
        'proposal-report.json giữ mapping ID, hash, quyết định gốc và chẩn đoán mới. '
        'Người review quyết định riêng, không ký thay người khác.\n', 'utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--registry', type=Path, default=RUNTIME / 'company.registry.20261105.r3.json')
    args = parser.parse_args()
    report = build(args.package, args.output_dir, args.registry)
    print(json.dumps({'proposals': len(report['items']), 'application_load_allowed': False,
                      'output': str(args.output_dir)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
