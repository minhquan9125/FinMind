/* Canonical demo facts shared by every screen ("Dữ liệu minh họa").
 * The Stitch pages keep their own render arrays (TRACES, SOURCES, CORPORA, versions, rawEvents);
 * tools/check-consistency.mjs loads every page and asserts that those arrays agree with this file. */
window.FM_DEMO = {
  label: 'Dữ liệu minh họa',
  activeConfig: 'CFG v2.4',
  pendingConfig: 'CFG v2.5',
  activeCorpus: 'Corpus v1.4',
  unactivatedCorpus: 'Corpus v1.5',

  traces: [
    { id: 'TRC-DEMO-001', co: 'FPT', status: 'Thành công' },
    { id: 'TRC-DEMO-002', co: 'VCB', status: 'Không đủ bằng chứng' },
    { id: 'TRC-DEMO-003', co: 'MBB', status: 'Đang xử lý' },
    { id: 'TRC-DEMO-004', co: 'TCB', status: 'Xác minh không đạt' },
    { id: 'TRC-DEMO-005', co: 'CMG', status: 'Lỗi vận hành' },
    { id: 'TRC-DEMO-006', co: 'BID', status: 'Lỗi vận hành' },
    { id: 'TRC-DEMO-007', co: 'CTG', status: 'Thành công' }
  ],

  sources: [
    { id: 'src-1', name: 'FPT Investor Relations', status: 'Hoạt động' },
    { id: 'src-2', name: 'HOSE', status: 'Hoạt động' },
    { id: 'src-3', name: 'HNX', status: 'Chưa kiểm tra' },
    { id: 'src-4', name: 'SSC', status: 'Kiểm tra thất bại' },
    { id: 'src-5', name: 'Tệp CSV có kiểm soát', status: 'Tạm dừng' },
    { id: 'src-6', name: 'API được phê duyệt', status: 'Vô hiệu hóa' }
  ],

  corpora: [
    { v: 'v1.4', status: 'Đang hoạt động' },
    { v: 'v1.5', status: 'Chưa kích hoạt' },
    { v: 'v1.6', status: 'Đang chuẩn bị' },
    { v: 'v1.3', status: 'Đã lưu trữ' },
    { v: 'v1.2', status: 'Đã lưu trữ' },
    { v: 'v1.1', status: 'Kiểm tra không đạt' }
  ],

  configs: [
    { v: 'CFG v2.5', status: 'Đang chờ kích hoạt' },
    { v: 'CFG v2.4', status: 'Đang hoạt động' },
    { v: 'CFG v2.3', status: 'Đã thay thế' },
    { v: 'CFG v2.2', status: 'Đã thay thế' }
  ]
};
