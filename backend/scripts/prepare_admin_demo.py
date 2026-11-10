"""Create labelled, repeatable local WBS16 demo reports. Never connects to DB."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.core.config import get_settings
from src.documents.news_batch_runner import digest, run


def main():
    articles = [
        {'article_id': 'demo-pending', 'content': 'FPT đã hoàn thiện hai AI Factory.',
         'source': 'DEMO_FIXTURE', 'url': 'https://example.invalid/pending'},
        {'article_id': 'demo-no-candidate', 'content': 'Nội dung minh họa không có mẫu sự kiện hỗ trợ.',
         'source': 'DEMO_FIXTURE'},
        {'article_id': 'demo-review', 'content': 'Bài viết minh họa cần kiểm tra.', 'source': 'DEMO_FIXTURE'},
        {'article_id': 'demo-error', 'content': '', 'source': 'DEMO_FIXTURE'},
    ]
    ids = [a['article_id'] for a in articles] + ['demo-missing-source']
    payload = {'documents': [
        {'document_id': 'fixture-document-' + aid, 'doc_type': 'NEWS',
         'chunks': [{'locator': {'source_table': 'news_articles', 'source_id': aid}}]}
        for aid in ids]}
    manifest = {'corpus_version_id': 'DEMO-FIXTURE-NOT-LIVE',
                'manifest_sha256': digest(payload), 'manifest': payload}
    candidates = {'demo-review': [{'source_span': 'Đoạn này không tồn tại trong bài.'}]}
    output = Path(get_settings().admin_jobs_directory) / 'demo-fixture-wbs16'
    report = run(manifest, articles, output, mode='fixture', candidates=candidates,
                 resume=(output / 'checkpoint.json').exists())
    expected = {'PENDING_REVIEW': 1, 'QUARANTINED': 1, 'NO_CANDIDATE': 1,
                'ERROR': 1, 'MISSING_SOURCE': 1, 'UNPROCESSED': 0}
    if report['counts'] != expected:
        raise RuntimeError('DEMO_STATUS_MISMATCH')
    print(json.dumps({'job_id': output.name, 'mode': 'fixture', 'counts': report['counts'],
                      'database_writes': report['database_writes']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
