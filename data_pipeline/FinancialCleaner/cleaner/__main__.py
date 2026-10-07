import argparse
from .files import clean_symbols


def main():
    parser = argparse.ArgumentParser(description='Lọc báo cáo tài chính, xuất tên chỉ tiêu tiếng Việt; bỏ lịch sử giá.')
    parser.add_argument('--symbols',nargs='+',help='Các mã cần lọc, ví dụ BID FPT. Không truyền: lọc tất cả.')
    parser.add_argument('--bo-dinh-gia',action='store_true',help='Bỏ thêm PE, PB và các chỉ số định giá theo giá thị trường.')
    args = parser.parse_args()
    try:
        report = clean_symbols(args.symbols,exclude_market_ratios=args.bo_dinh_gia)
    except (ValueError,OSError) as issue:
        parser.exit(1,f'Lỗi: {issue}\n')
    print(f"Đã lọc {report['số_mã_đã_lọc']} mã. Xem folder data và reports/bao_cao_loc.json.")


if __name__ == '__main__':
    main()
