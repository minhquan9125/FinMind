"""CLI for source-verified HNSW/BM25 retrieval; no model or DB work at import."""
import argparse
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from src.vector_retrieval.backend import HybridRetriever, RetrievalError
from src.vector_retrieval.sources import SnapshotResolver, SnapshotError

CACHE_DIR=Path(__file__).resolve().parent/'.cache'


async def connect():
    from src.core.db import connect as operation
    return await operation()


async def disconnect():
    from src.core.db import disconnect as operation
    return await operation()


def get_pool():
    from src.core.db import get_pool as operation
    return operation()


def get_embedding_service():
    from src.documents.embeddings import get_embedding_service as operation
    return operation()


def _error(code):
    hints={
        'CACHE_BUILD_REQUIRED':'Chạy lệnh build trước khi tìm kiếm.',
        'CACHE_EXPIRED':'Cache hết hạn; chạy lại build.',
        'CACHE_STALE':'Index thay đổi; cần dựng lại cache.',
        'CACHE_VERSION_MISMATCH':'Cache cũ không tương thích; chạy lại build.',
        'SOURCE_CHANGED':'Nguồn đã đổi so với vector. Cần đồng bộ phiên bản nguồn trước khi dựng cache.',
        'INDEX_NOT_ACTIVE':'Index chưa ACTIVE; chỉ dùng BUILDING khi chọn --allow-building.',
    }
    print(json.dumps(dict(status='ERROR',code=code,message=hints.get(code,'Không thể hoàn tất truy vấn.')),ensure_ascii=False),file=sys.stderr)


def _display(result,question,json_output):
    if json_output:
        print(json.dumps(result,ensure_ascii=False))
        return
    if result.get('source_provenance'):
        print('Nguồn: '+json.dumps(result['source_provenance'],ensure_ascii=False))
    print('\nKết quả cho: '+question)
    if result.get('scope'):
        print('Phạm vi: '+json.dumps(result['scope'],ensure_ascii=False))
    if not result.get('results'):
        print('Không tìm thấy đoạn phù hợp trong phạm vi đã chọn.')
    for i,row in enumerate(result.get('results',[]),1):
        print(f"\n[{i}] {row.get('text','')}")
        print('Chunk: '+row.get('chunk_id',''))
        print('Locator: '+json.dumps(row.get('locator',{}),ensure_ascii=False))
        print('Điểm RRF: '+str(row.get('rrf_score','')))


def _snapshot(path, digest):
    if (path is None) != (digest is None):
        raise SnapshotError('SNAPSHOT_ARGUMENTS_REQUIRED')
    return SnapshotResolver(path,digest) if path is not None else None


def _service(path,digest,resolver):
    reader=resolver if resolver is not None else _snapshot(path,digest)
    options={'resolver':reader} if reader is not None else {}
    return HybridRetriever(get_pool(),get_embedding_service(),**options),reader


async def build_cache(index_id,cache_path,allow_building,snapshot_path=None,snapshot_sha256=None,*,resolver=None):
    try:
        service,reader=_service(snapshot_path,snapshot_sha256,resolver)
        result=await service.build_cache(index_id,cache_path,allow_building=allow_building)
        if reader is not None:
            result=dict(result,source_provenance=reader.provenance)
        print(json.dumps(result,ensure_ascii=False))
        return 0
    except (RetrievalError,SnapshotError) as exc:
        _error(exc.code)
        return 1
    except Exception:
        _error('INTERNAL_ERROR')
        return 2


async def search_question(index_id,cache_path,question,allow_building,company,period,doc_type,top_k,candidates,json_output,snapshot_path=None,snapshot_sha256=None,*,resolver=None,publisher=None,published_date=None):
    try:
        service,reader=_service(snapshot_path,snapshot_sha256,resolver)
        async def ask(text):
            result=await service.search(text,index_id,cache_path,allow_building=allow_building,
                company=company,period=period,doc_type=doc_type,publisher=publisher,published_date=published_date,top_k=top_k,candidates=candidates)
            if reader is not None:
                result=dict(result,source_provenance=reader.provenance)
            _display(result,text,json_output)
        if question is not None:
            await ask(question)
            return 0
        print('Nhập câu hỏi; exit để thoát. Mỗi lượt là truy vấn độc lập, không gọi Gemini.',file=sys.stderr)
        while True:
            try:
                print('Bạn: ',end='',file=sys.stderr,flush=True)
                text=input()
            except EOFError:
                return 0
            if text.strip().casefold() in {'exit','quit','thoát'}:
                return 0
            try:
                await ask(text)
            except (RetrievalError,SnapshotError) as exc:
                _error(exc.code)
    except (RetrievalError,SnapshotError) as exc:
        _error(exc.code)
        return 1
    except Exception:
        _error('INTERNAL_ERROR')
        return 2


def parse_args(argv=None):
    parser=argparse.ArgumentParser(description='Truy xuất HNSW + BM25 + RRF, kiểm tra nguồn trước khi trả kết quả.')
    commands=parser.add_subparsers(dest='command',required=True)
    for name in ('build','search'):
        command=commands.add_parser(name)
        command.add_argument('--index',required=True,help='UUID index tường minh')
        command.add_argument('--allow-building',action='store_true')
        command.add_argument('--allow-model-download',action='store_true',help='Cho phép tải model nếu chưa có cache máy')
        command.add_argument('--source-snapshot',help='Snapshot nguồn gốc, dùng cùng --snapshot-sha256')
        command.add_argument('--snapshot-sha256',help='SHA256 payload manifest đã chốt')
        command.add_argument('--cache-path',help='Đường dẫn cache nằm trong folder .cache của module')
        if name=='search':
            command.add_argument('--question')
            command.add_argument('--company')
            command.add_argument('--period')
            command.add_argument('--doc-type')
            command.add_argument('--publisher',help='cafef hoặc fireant; lọc theo nguồn tin từ URL frozen')
            command.add_argument('--published-date',dest='published_date',help='YYYY-MM-DD; lọc ngày đăng frozen (Asia/Ho_Chi_Minh đã chuẩn hóa)')
            command.add_argument('--top-k',type=int,default=5)
            command.add_argument('--candidates',type=int,default=50)
            command.add_argument('--json',action='store_true')
    return parser.parse_args(argv)


async def main(argv=None):
    args=parse_args(argv)
    try:
        index_id=str(uuid.UUID(args.index))
    except (ValueError,TypeError,AttributeError):
        _error('INVALID_INDEX_ID')
        return 1
    try:
        reader=_snapshot(args.source_snapshot,args.snapshot_sha256)
    except SnapshotError as exc:
        _error(exc.code)
        return 1
    cache_root=CACHE_DIR.resolve()
    path=Path(args.cache_path).resolve() if args.cache_path else cache_root/(index_id+'.json')
    if cache_root.parent!=Path(__file__).resolve().parent or not path.is_relative_to(cache_root):
        _error('INVALID_CACHE_PATH')
        return 1
    os.environ['HF_HUB_OFFLINE']='0' if args.allow_model_download else '1'
    os.environ['TRANSFORMERS_OFFLINE']='0' if args.allow_model_download else '1'
    print('HNSW + BM25; phạm vi INDEX, không phải xác nhận corpus đã đóng băng.',file=sys.stderr)
    if reader is not None:
        print('Nguồn lịch sử: '+json.dumps(reader.provenance,ensure_ascii=False),file=sys.stderr)
    if args.allow_building:
        print('Đã chọn cho phép index BUILDING; trạng thái database được giữ nguyên.',file=sys.stderr)
    try:
        await connect()
        if args.command=='build':
            return await build_cache(index_id,str(path),args.allow_building,resolver=reader)
        return await search_question(index_id,str(path),args.question,args.allow_building,
            args.company,args.period,args.doc_type,args.top_k,args.candidates,args.json,resolver=reader,
            publisher=getattr(args,'publisher',None),published_date=getattr(args,'published_date',None))
    except Exception:
        _error('DATABASE_UNAVAILABLE')
        return 2
    finally:
        try:
            await disconnect()
        except Exception:
            _error('DATABASE_CLOSE_FAILED')


if __name__=='__main__':
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)
