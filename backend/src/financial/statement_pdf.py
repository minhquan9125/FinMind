"""Evidence reader for Vietnamese financial-statement PDFs. Pure: no network, no DB."""
from datetime import date
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from io import BytesIO
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unicodedata

import pypdf


class NoTextLayer(Exception):
    """PDF opened but has (almost) no extractable text, e.g. a scan."""


class PdfUnreadable(Exception):
    """pypdf could not parse the file."""


class OcrUnavailable(NoTextLayer, PdfUnreadable):
    """OCR could not run on this machine (tools missing, crash, timeout). A fact about the host, not the PDF:
    callers may report it like NoTextLayer/PdfUnreadable but must not cache it."""


_MIN_CHARS = 200
_SNIPPET_RADIUS = 70
_MILLION = Decimal(1_000_000)
# One whole number token. Lookbehind/lookahead keep digit boundaries, so "2660" cannot
# hit inside "…277.2660" and the "12" of a note reference "V.12" is not a figure.
_NUMBER = re.compile(
    r'(?<![\w.,])(\(|-)?(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d+))?(?!\d|[.,]\d)(\))?'
)


# Most Vietstock BCTC PDFs are scans, and some text layers use broken font encodings
# (real check 13/11: 7 of 10 symbols scanned, MBB garbled). The statements and the
# "năm tài chính" note sit in the first pages, so only those are OCR'd.
OCR_MAX_PAGES = 15
OCR_FISCAL_MAX_PAGES = 30  # extra pages read only while the fiscal-year note is still missing
_MIN_PAGE_CHARS = 100
_OCR_DPI = '300'
_VI_MARKERS = ('tai san', 'loi nhuan', 'nguon von', 'doanh thu', 'thu nhap', 'von chu so huu', 'don vi')


def _native_pages(data: bytes) -> list[str]:
    try:
        return [page.extract_text() or '' for page in pypdf.PdfReader(BytesIO(data)).pages]
    except Exception as exc:  # pypdf raises many types on malformed input
        raise PdfUnreadable(str(exc)) from exc


def _usable(pages: list[str]) -> bool:
    """Enough text, and readable Vietnamese statement words (garbled font maps fail this)."""
    head = pages[:OCR_MAX_PAGES]
    if sum(len(page.strip()) for page in head) < _MIN_CHARS:
        return False
    folded = _fold(' '.join(head))
    return sum(marker in folded for marker in _VI_MARKERS) >= 2


def _ocr_tools() -> tuple[str, str] | None:
    """(tesseract, pdftoppm) from FINMIND_TESSERACT / FINMIND_PDFTOPPM, PATH or the usual Windows install."""
    tesseract = (os.environ.get('FINMIND_TESSERACT') or shutil.which('tesseract')
                 or next((p for p in (r'C:\Program Files\Tesseract-OCR\tesseract.exe',) if os.path.exists(p)), None))
    pdftoppm = os.environ.get('FINMIND_PDFTOPPM') or shutil.which('pdftoppm') or next(
        (str(p) for p in Path.home().glob('.cache/codex-runtimes/*/dependencies/native/poppler/Library/bin/pdftoppm.exe')),
        None)
    return (tesseract, pdftoppm) if tesseract and pdftoppm else None


def _ocr_page(pdf: Path, page_number: int, tools: tuple[str, str]) -> str:
    tesseract, pdftoppm = tools
    prefix = pdf.with_name(f'p{page_number}')
    env = {**os.environ, 'OMP_THREAD_LIMIT': '1'}  # one core: OCR runs beside the API on the same host
    subprocess.run([pdftoppm, '-f', str(page_number), '-l', str(page_number), '-singlefile', '-r', _OCR_DPI,
                    '-png', str(pdf), str(prefix)], check=True, capture_output=True, timeout=120, env=env)
    result = subprocess.run([tesseract, f'{prefix}.png', 'stdout', '-l', 'vie', '--psm', '6'],
                            check=True, capture_output=True, timeout=300, env=env)
    return result.stdout.decode('utf-8', 'replace')


def read_pages(data: bytes) -> list[str]:
    """Page texts; scans and garbled text layers fall back to OCR of the first OCR_MAX_PAGES pages.
    Any OCR tool failure (bad page, timeout, missing language data) is reported as PdfUnreadable."""
    try:
        return _read_pages(data)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        raise OcrUnavailable(f'OCR failed: {type(exc).__name__}') from exc


def _read_pages(data: bytes) -> list[str]:
    pages = _native_pages(data)
    if _usable(pages):
        # Mixed PDFs (BID): narrative pages carry text but the statement tables are images.
        blank = [n for n, page in enumerate(pages[:OCR_MAX_PAGES], 1) if len(page.strip()) < _MIN_PAGE_CHARS]
        tools = _ocr_tools() if blank else None
        if tools:
            with tempfile.TemporaryDirectory(prefix='finmind-bctc-ocr-') as folder:
                pdf = Path(folder) / 'statement.pdf'
                pdf.write_bytes(data)
                for number in blank:
                    pages[number - 1] = _ocr_page(pdf, number, tools)
        return pages
    tools = _ocr_tools()
    if tools is None:
        raise OcrUnavailable('PDF has no usable text layer and OCR tools are not installed')
    with tempfile.TemporaryDirectory(prefix='finmind-bctc-ocr-') as folder:
        pdf = Path(folder) / 'statement.pdf'
        pdf.write_bytes(data)
        count = min(len(pages), OCR_MAX_PAGES)
        ocr = [_ocr_page(pdf, number, tools) for number in range(1, count + 1)]
        # Banks put the "Kỳ kế toán năm" note after the statements: keep reading until it appears.
        while fiscal_year_end(ocr) is None and count < min(len(pages), OCR_FISCAL_MAX_PAGES):
            count += 1
            ocr.append(_ocr_page(pdf, count, tools))
    pages = ocr + [''] * (len(pages) - count)
    if sum(len(page.strip()) for page in ocr) < _MIN_CHARS:
        raise NoTextLayer('OCR found no usable text')
    return pages


def _scan(text: str):
    """Yield (value, start, end) per number as written."""
    for m in _NUMBER.finditer(text):
        sign, digits, frac, close = m.groups()
        value = Decimal(digits.replace('.', '') + ('.' + frac if frac else ''))
        if sign == '-' or (sign == '(' and close):
            value = -value
        yield value, m.start(), m.end()


def numbers_in(text: str) -> list[Decimal]:
    """Every number as written, in order: '.' thousands, ',' decimal, '(n)' and '-n'
    negative. Years such as 2025 are returned like any number; note references such
    as 'V.12' are skipped (their digits follow a letter and dot)."""
    return [value for value, _, _ in _scan(text)]


def _units(number: Decimal, value: Decimal) -> list[str]:
    units = []
    if number == value:
        units.append('VND')
    # shortcut: scaled numbers 1-999 collide with line codes, note and page numbers,
    # so the million scale is only tried when it yields at least 1,000.
    if abs(value) >= _MILLION * 1000:
        scaled = value / _MILLION
        one = Decimal(1)
        if number in (scaled.quantize(one, ROUND_HALF_UP), scaled.quantize(one, ROUND_DOWN)):
            units.append('MILLION_VND')
    return units


def _snippet(text: str, start: int, end: int) -> str:
    window = text[max(0, start - _SNIPPET_RADIUS):end + _SNIPPET_RADIUS].replace('\x00', ' ')  # jsonb rejects NUL
    return ' '.join(window.split())[:160]


def find_value(pages: list[str], value: Decimal) -> list[dict]:
    hits = []
    for page_no, text in enumerate(pages, start=1):
        for number, start, end in _scan(text):
            for unit in _units(number, value):
                hits.append({'page': page_no, 'unit': unit, 'snippet': _snippet(text, start, end)})
    return hits


def prior_column_value(pages: list[str], current: Decimal, prior: Decimal) -> bool:
    """True when one line holds a number matching `current` and, after it, one matching
    `prior` (same unit rules as find_value). Ties the evidence to the metric's own row."""
    for text in pages:
        for line in text.splitlines():
            numbers = numbers_in(line)
            for i, number in enumerate(numbers):
                if _units(number, current) and any(_units(n, prior) for n in numbers[i + 1:]):
                    return True
    return False


def _fold(text: str) -> str:
    text = unicodedata.normalize('NFD', text.lower().replace('đ', 'd'))
    return ''.join(c for c in text if not unicodedata.combining(c))


_UNIT = re.compile(r'don vi(?: tinh)?\s*:?\s*(trieu|vnd|dong)')


# Statement tables usually state the unit in the column header row ("Thuyết minh VND VND",
# "Triệu VND Triệu VND"), not on a "Đơn vị tính" line; one repeat per amount column.
_HEADER_MILLION = re.compile(r'\btrieu\s+(?:vnd|dong)\b')
_HEADER_VND = re.compile(r'\bvnd\b')
_CARRY_PAGES = 2  # "(tiếp theo)" pages of the same table do not repeat the unit


def page_unit(text: str) -> str | None:
    folded = _fold(text)
    m = _UNIT.search(folded)
    if m:
        return 'MILLION_VND' if m.group(1) == 'trieu' else 'VND'
    for line in folded.splitlines():
        if len(_HEADER_MILLION.findall(line)) >= 2:
            return 'MILLION_VND'
        if len(_HEADER_VND.findall(line)) >= 2 and 'trieu' not in line:
            return 'VND'
    return None


def unit_for_page(pages: list[str], index: int) -> str | None:
    """Unit of pages[index] (0-based): its own, else the nearest of the previous _CARRY_PAGES pages."""
    for i in range(index, max(index - _CARRY_PAGES, 0) - 1, -1):
        unit = page_unit(pages[i])
        if unit:
            return unit
    return None


# Only "năm tài chính kết thúc …" is a fiscal year end; quarter/half-year headers are not.
_YEAR_END = (
    re.compile(r'nam tai chinh\s+ket thuc\s+(?:vao\s+)?ngay\s+(\d{1,2})\s+thang\s+(\d{1,2})\s+nam\s+(\d{4})'),
    re.compile(r'nam tai chinh\s+ket thuc\s+(?:vao\s+)?ngay\s+(\d{1,2})/(\d{1,2})/(\d{4})'),
)


# Quarterly notes state the year end without a year: "Năm tài chính … bắt đầu từ ngày 01 tháng 01
# và kết thúc vào ngày 31 tháng 12". Same sentence only, so a "kỳ kế toán" period end never matches.
_YEAR_END_NO_YEAR = re.compile(
    r'(?:nam tai chinh|ky ke toan nam)[^.]{0,160}?ket thuc\s+(?:vao\s+)?ngay\s+(\d{1,2})\s+thang\s+(\d{1,2})'
    r'(?!\s+nam\s+\d)')  # banks write "Kỳ kế toán năm của Ngân hàng … kết thúc vào ngày 31 tháng 12"


def fiscal_year_end(pages: list[str]) -> tuple[str, int | None] | None:
    """(MM-DD, year) from a dated "năm tài chính kết thúc ngày …" clause; (MM-DD, None) from an undated one."""
    folded = [_fold(text) for text in pages]
    for text in folded:
        for pattern in _YEAR_END:
            for m in pattern.finditer(text):
                day, month, year = (int(g) for g in m.groups())
                try:
                    date(year, month, day)
                except ValueError:
                    continue
                return f'{month:02d}-{day:02d}', year
    for text in folded:
        for m in _YEAR_END_NO_YEAR.finditer(text):
            day, month = int(m.group(1)), int(m.group(2))
            try:
                date(2000, month, day)  # leap year: 29/02 stays valid
            except ValueError:
                continue
            return f'{month:02d}-{day:02d}', None
    return None
