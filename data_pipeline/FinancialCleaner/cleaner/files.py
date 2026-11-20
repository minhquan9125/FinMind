"""Read normalized sources and write clean copies inside this new project."""
import hashlib
import os
from pathlib import Path
import tempfile

from . import codec
from .core import clean_financial_data, validate_symbol
from .display import add_display_values, load_display_config
from .mapping import PROJECT, SOURCE_DIR, MAPPING_PATH, MARKET_CODES, load_mapping


def _inside(path, root):
    path = Path(path).absolute()
    root = Path(root).resolve()
    if not path.resolve().is_relative_to(root):
        raise ValueError(f'Đường dẫn nằm ngoài folder cho phép: {path}')
    current = path
    while current != root:
        if current.is_symlink() or (hasattr(current,'is_junction') and current.is_junction()):
            raise ValueError('Không ghi qua symlink/junction.')
        current = current.parent
    return path


def _write(path, payload):
    path = _inside(path, PROJECT)
    path.parent.mkdir(parents=True,exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix='.clean-',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(descriptor,'w',encoding='utf-8',newline='\n') as output:
            output.write(codec.dumps(payload)+'\n')
            output.flush()
            os.fsync(output.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def clean_file(source, output_root=None, *, exclude_market_ratios=False):
    """Write one ticker's financial copy; original JSON is never rewritten."""
    source = _inside(source,SOURCE_DIR)
    raw = source.read_bytes()
    payload = codec.loads(raw.decode('utf-8-sig'))
    if payload.get('symbol') != source.stem:
        raise ValueError('Mã trong JSON không khớp tên file nguồn.')
    maps, labels, meta = load_mapping(payload.get('industry'))
    cleaned = clean_financial_data(payload,section_maps=maps,labels_vi=labels,meta_keys=meta,
        exclude_codes=MARKET_CODES if exclude_market_ratios else ())
    add_display_values(cleaned,load_display_config())
    cleaned['nguồn_dữ_liệu'] = {
        'file_nguồn': source.name,
        'sha256_nguồn': hashlib.sha256(raw).hexdigest(),
        'sha256_mapping': hashlib.sha256(MAPPING_PATH.read_bytes()).hexdigest(),
        'nguồn_tài_chính': payload.get('sources',{}).get('fundamentals'),
        'thời_điểm_tạo_nguồn': payload.get('generated_at'),
        'đơn_vị_giá_trị': 'Giữ nguyên đơn vị và giá trị trong JSON nguồn; không quy đổi hoặc làm tròn.',
        'bỏ_chỉ_số_định_giá': exclude_market_ratios,
    }
    destination = _inside(Path(output_root or PROJECT/'data')/cleaned['mã_chứng_khoán']/'tai_chinh_clean.json',PROJECT)
    _write(destination,cleaned)
    return destination, cleaned['thống_kê_lọc']


def clean_symbols(symbols=None, *, exclude_market_ratios=False):
    """Filter all authorized JSON files, or a selected list of stock symbols."""
    paths = sorted(SOURCE_DIR.glob('*.json')) if symbols is None else [SOURCE_DIR/f'{validate_symbol(s.upper())}.json' for s in symbols]
    results = []
    for source in paths:
        destination, stats = clean_file(source,exclude_market_ratios=exclude_market_ratios)
        results.append({'mã_chứng_khoán':source.stem,'file_kết_quả':str(destination.relative_to(PROJECT)),**stats})
    report = {'số_mã_đã_lọc':len(results),'bỏ_chỉ_số_định_giá':exclude_market_ratios,'kết_quả':results}
    _write(PROJECT/'reports/bao_cao_loc.json',report)
    return report
