// Hiển thị phạm vi hội thoại và gợi ý theo lượt, chỉ dựa trên phản hồi backend.
// Không tự suy luận dữ liệu tài chính; khóa bắt đầu bằng "_" là trạng thái nội bộ nên bỏ qua.

const METRIC_LABELS = {
  TOTAL_ASSETS: 'Tổng tài sản', CASH_AND_CASH_EQUIVALENTS: 'Tiền và tương đương tiền',
  SHORT_TERM_LOANS_AND_FINANCE_LEASES: 'Nợ vay ngắn hạn', LONG_TERM_LOANS_AND_FINANCE_LEASES: 'Nợ vay dài hạn',
  CURRENT_LIABILITIES: 'Nợ ngắn hạn', NON_CURRENT_LIABILITIES: 'Nợ dài hạn',
  RETAINED_EARNINGS: 'LNST chưa phân phối', NET_REVENUE: 'Doanh thu thuần', GROSS_REVENUE: 'Doanh thu bán hàng',
  PROFIT_BEFORE_TAX: 'Lợi nhuận trước thuế', PROFIT_AFTER_TAX: 'Lợi nhuận sau thuế',
  PARENT_NET_PROFIT: 'LNST cổ đông công ty mẹ', CASH_FLOW_OPERATING: 'Dòng tiền kinh doanh',
  CASH_FLOW_INVESTING: 'Dòng tiền đầu tư', CASH_FLOW_FINANCING: 'Dòng tiền tài chính',
  CHARTER_CAPITAL: 'Vốn điều lệ', TOTAL_LIABILITIES: 'Tổng nợ phải trả', TOTAL_EQUITY: 'Vốn chủ sở hữu',
};
const SOURCE_LABELS = { BCTC: 'Báo cáo tài chính', NEWS: 'Tin tức', PRICE: 'Giá cổ phiếu',
  BCTN: 'Báo cáo thường niên', MARKET_ANALYSIS: 'Phân tích thị trường' };

const text = value => typeof value === 'string' && value.trim() ? value.trim().slice(0, 40) : null;

function periodLabel(value) {
  const raw = text(value);
  if (!raw) return null;
  if (raw === 'LATEST_AVAILABLE_PERIOD') return 'Kỳ mới nhất';
  const quarter = raw.match(/^(\d{4})-Q([1-4])$/);
  if (quarter) return `Quý ${quarter[2]}/${quarter[1]}`;
  if (/^\d{4}$/.test(raw)) return `Năm ${raw}`;
  return raw;
}

/** Phạm vi của lượt trả lời gần nhất, dạng [{key,label,value}] chỉ gồm trường backend đã xác định. */
export function scopeChips(result) {
  const scope = result?.scope;
  if (!scope || typeof scope !== 'object') return [];
  const chips = [];
  const companies = (Array.isArray(scope.companies) ? scope.companies : []).map(text).filter(Boolean).slice(0, 4);
  if (companies.length) chips.push({ key: 'companies', label: 'Mã', value: companies.join(', ') });
  const periods = (Array.isArray(scope.periods) ? scope.periods : []).map(periodLabel).filter(Boolean).slice(0, 4);
  if (periods.length) chips.push({ key: 'periods', label: 'Kỳ', value: periods.join(', ') });
  const metric = text(scope.metric_code);
  if (metric) chips.push({ key: 'metric', label: 'Chỉ tiêu', value: METRIC_LABELS[metric] || metric });
  const source = text(scope.source_type);
  if (source) chips.push({ key: 'source', label: 'Nguồn', value: SOURCE_LABELS[source] || source });
  return chips;
}

const SUPPORT = 'Hiện tại FinMind tra cứu được giá cổ phiếu, tin tức theo mã và thời gian, '
  + 'và chỉ tiêu báo cáo tài chính theo mã, kỳ và chỉ tiêu cụ thể.';
const EXPLANATIONS = {
  SOURCE_NOT_AVAILABLE: 'Nội dung báo cáo thường niên dạng PDF chưa được đưa vào luồng chat này. '
    + 'Bạn có thể hỏi số liệu trong báo cáo tài chính, tin tức hoặc giá của công ty đó.',
  NO_DATA: 'Kho dữ liệu chưa có đoạn nguồn khớp đúng mã, kỳ và chỉ tiêu bạn hỏi. '
    + 'Thử đổi kỳ, đổi chỉ tiêu hoặc hỏi cụ thể hơn. ' + SUPPORT,
  AMBIGUOUS_PERIOD: 'Mỗi lượt chỉ tra một kỳ. Bạn hãy chọn một quý hoặc một năm, hoặc hỏi lần lượt từng kỳ.',
  SCOPE_TOO_LARGE: 'Câu hỏi bao quát nhiều nội dung. Hãy thu hẹp theo một mã, một kỳ và một chỉ tiêu.',
  UNSUPPORTED: 'Câu hỏi này nằm ngoài phạm vi hỗ trợ. ' + SUPPORT,
  BUDGET_EXCEEDED: 'Hệ thống đã chạm giới hạn số lượt tạo câu trả lời. Bạn có thể xem nguồn ứng viên hoặc thử lại sau.',
};

/** Lời giải thích phạm vi hỗ trợ cho các kết quả "không trả lời được"; null nếu không cần. */
export function outcomeNotice(result) {
  if (!result) return null;
  const status = result.status;
  if (result.reason_code && EXPLANATIONS[result.reason_code] && status !== 'EVIDENCE_READY') {
    return EXPLANATIONS[result.reason_code];
  }
  if (['NO_DATA', 'UNSUPPORTED', 'BUDGET_EXCEEDED'].includes(status)) return EXPLANATIONS[status];
  return null;
}

/**
 * Gợi ý bước tiếp theo, chỉ dùng cụm từ chat đã hỗ trợ và chỉ dựa trên phạm vi backend trả về.
 * Không hiện khi đang có menu làm rõ (đã có nút riêng) hoặc khi kết quả là lỗi.
 */
export function followUps(result, hasChoices = false) {
  if (!result || hasChoices) return [];
  if (!['DRAFT_READY', 'SOURCE_EXTRACT_FALLBACK', 'EVIDENCE_READY', 'NO_DATA'].includes(result.status)) return [];
  const scope = result.scope || {};
  const company = text((Array.isArray(scope.companies) ? scope.companies : [])[0]);
  const items = [];
  if (result.status !== 'NO_DATA' && result.evidence_pack?.items?.length && scope.source_type !== 'PRICE') {
    items.push({ id: 'source', label: 'Xem nguồn', reply: 'Nguồn đâu?' });
  }
  if (company) {
    if (scope.source_type !== 'NEWS') items.push({ id: 'news', label: `Tin tức mới về ${company}`, reply: `Tin tức ${company} mới nhất` });
    if (scope.source_type !== 'PRICE') items.push({ id: 'price', label: `Giá ${company} hiện tại`, reply: `Giá ${company} hiện tại` });
  }
  return items.slice(0, 3);
}
