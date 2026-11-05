"""News adapter for the existing annual-report PDF/Tesseract implementation."""
import hashlib
import importlib.util
import os
import shutil
import tempfile
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

from .admin_ingestion import source_attachments, auto_review_reasons


@lru_cache
def engine():
    path = Path(__file__).resolve().parents[3] / 'data_pipeline/annual_reports/OCR_annuals.py'
    spec = importlib.util.spec_from_file_location('finmind_existing_ocr', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def executable(name, variable):
    from ..core.config import get_settings
    configured = os.environ.get(variable) or getattr(get_settings(),variable.lower(),None)
    candidates = [configured, shutil.which(name)]
    if name == 'tesseract':
        candidates.append(r'C:\Program Files\Tesseract-OCR\tesseract.exe')
    else:
        candidates.extend((Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin').glob('pdftoppm.exe'))
    return next((str(p) for p in candidates if p and Path(p).is_file()), None)


def checked_url(url):
    parsed = urlparse(url)
    host = parsed.hostname or ''
    if (parsed.scheme != 'https' or parsed.username or parsed.password
            or parsed.port not in (None, 443)
            or not (host == 'fireant.vn' or host.endswith('.fireant.vn'))):
        raise ValueError('OCR_SOURCE_HOST_NOT_ALLOWED')
    return url


class Images(HTMLParser):
    def __init__(self):
        super().__init__(); self.urls = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'img' and attrs.get('src'):
            self.urls.append(attrs['src'])


def sources(payload):
    result = list(source_attachments(payload))
    raw = payload.get('raw') or {}
    parser = Images()
    parser.feed(str(raw.get('content') or raw.get('originalContent') or ''))
    for url in parser.urls:
        result.append({'name': 'Ảnh trong bài', 'url': urljoin(payload['url'], url)})
    return list({item['url']: item for item in result}.values())


def download(url, target):
    for _ in range(5):
        checked_url(url)
        with requests.get(url, stream=True, timeout=(10, 60), allow_redirects=False) as response:
            if response.is_redirect:
                url = urljoin(url, response.headers['Location']); continue
            response.raise_for_status()
            size = 0
            with target.open('wb') as stream:
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > 25 * 1024 * 1024: raise ValueError('OCR_FILE_EXCEEDS_25_MB')
                    stream.write(chunk)
            return
    raise ValueError('OCR_TOO_MANY_REDIRECTS')


def extract_file(path, work):
    ocr = engine()
    pdf = path.read_bytes()[:5] == b'%PDF-'
    if pdf:
        if ocr.count_pdf_pages(path) > 100: raise ValueError('OCR_PDF_EXCEEDS_100_PAGES')
        texts = ocr.extract_native_pages(path)
    else:
        from PIL import Image
        with Image.open(path) as image:
            image.verify()
        texts = ['']
    pages = []
    for number, text in enumerate(texts, 1):
        method = 'pdf_text'
        if not ocr.native_text_usable(text):
            tesseract = executable('tesseract', 'TESSERACT_CMD')
            poppler = executable('pdftoppm', 'PDFTOPPM_CMD')
            if not tesseract: raise ValueError('TESSERACT_NOT_AVAILABLE: cấu hình TESSERACT_CMD')
            if pdf and not poppler: raise ValueError('PDFTOPPM_NOT_AVAILABLE: cấu hình PDFTOPPM_CMD')
            local_data = Path(__file__).resolve().parents[3] / 'outputs/tools/tessdata'
            from ..core.config import get_settings
            configured_data = get_settings().tessdata_prefix
            if configured_data: os.environ.setdefault('TESSDATA_PREFIX',configured_data)
            if all((local_data / f'{language}.traineddata').is_file() for language in ('vie', 'eng')):
                os.environ.setdefault('TESSDATA_PREFIX', str(local_data))
            image = ocr.render_page(path, number, 350, poppler, work) if pdf else path
            image = ocr.preprocess_for_tesseract(image)
            text = ocr.run_tesseract(image, tesseract, 'vie+eng', 3)
            if not text.strip(): text = ocr.run_tesseract(image, tesseract, 'vie+eng', 6)
            method = 'tesseract'
        if not text.strip(): raise ValueError(f'OCR_EMPTY_PAGE_{number}')
        pages.append({'page_number': number, 'text': text.strip(), 'method': method})
    if not pages: raise ValueError('OCR_EMPTY_DOCUMENT')
    return pages


def extract_revision(queue, ident, aid, actor):
    record = queue.article(aid)
    files = sources(record['payload'])
    if not files: raise ValueError('NO_PDF_OR_IMAGE_SOURCE')
    if len(files) > 10: raise ValueError('OCR_EXCEEDS_10_FILES')
    results = []
    folder = queue.root / 'ocr' / ident / aid
    folder.mkdir(parents=True, exist_ok=True)
    for i, source in enumerate(files):
        queue.update_job(ident, 'RUNNING', current_article_id=aid,
                         current_file=i + 1, total_files=len(files))
        path = folder / f'source-{i + 1}.bin'
        download(source['url'], path)
        with tempfile.TemporaryDirectory(dir=folder) as work:
            pages = extract_file(path, Path(work))
        results.append({**source, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'pages': pages})
    payload = dict(record['payload'])
    payload['content'] = payload.get('content', '') + '\n\n' + '\n\n'.join(
        f"[{file['name']} — trang {page['page_number']}]\n{page['text']}"
        for file in results for page in file['pages'])
    payload['extraction'] = {'parent_article_id': aid, 'engine': 'annual_reports/OCR_annuals.py',
                             'requires_review': True, 'files': results}
    return queue.save_ocr_revision(ident, aid, payload, actor), len(files)


def ocr_job(queue, ident):
    try:
        job = queue.get_job(ident)
        queue.update_job(ident, 'RUNNING', phase='OCR')
        aid = job['details']['article_ids'][0]
        revision, count = extract_revision(queue, ident, aid, job['actor'])
        queue.update_job(ident, 'COMPLETED', phase='OCR', article_id=revision, completed=count, total=count)
    except Exception as exc:
        if queue.get_job(ident)['status'] != 'INTERRUPTED':
            queue.update_job(ident, 'FAILED', error=str(exc)[:500])


def recheck_job(queue, ident):
    """Recheck held sources, extracting missing image/PDF text before review."""
    job = queue.get_job(ident)
    ids = job['details']['article_ids']
    results, errors, approved = [], [], 0
    try:
        queue.update_job(ident, 'RUNNING', phase='OCR', completed=0, total=len(ids))
        for i, aid in enumerate(ids):
            queue.update_job(ident, 'RUNNING', current_article_id=aid)
            try:
                record = queue.article(aid)
                if record['status'] != 'QUARANTINED':
                    results.append({'source_article_id': aid, 'status': 'SKIPPED'})
                elif {'OCR_REQUIRED', 'ATTACHMENT_TEXT_REQUIRED'} & set(auto_review_reasons(record['payload'])):
                    revision, _ = extract_revision(queue, ident, aid, job['actor'])
                    results.append({'source_article_id': aid, 'article_id': revision, 'status': 'PENDING',
                                    'title': record['payload'].get('title')})
                else:
                    decision = queue.auto_review(job['actor'], {aid}, recheck_previous=True, include_current=True)
                    approved += decision['approved']
                    results.append({'source_article_id': aid, 'status': queue.article(aid)['status']})
            except Exception as exc:
                if queue.get_job(ident)['status'] == 'INTERRUPTED': return
                errors.append({'article_id': aid, 'error': str(exc)[:500]})
            queue.update_job(ident, 'RUNNING', completed=i + 1, results=results, errors=errors, approved=approved,
                             extracted=sum(r['status'] == 'PENDING' for r in results))
        queue.update_job(ident, 'PARTIAL' if errors else 'COMPLETED', phase='WAITING_REVIEW')
    except Exception as exc:
        if queue.get_job(ident)['status'] != 'INTERRUPTED':
            queue.update_job(ident, 'FAILED', error=str(exc)[:500])
