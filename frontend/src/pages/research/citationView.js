export function safeSourceUrl(raw) {
  if (typeof raw !== 'string' || raw.length > 2048) return null;
  try {
    const url = new URL(raw);
    return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}

export function modeLabel(snapshot) {
  if (!snapshot) return 'Đang kết nối hội thoại…';
  return snapshot.execution_mode === 'LIVE'
    ? 'Nguồn dữ liệu thật · Xem nguồn và kỳ báo cáo trước khi sử dụng số liệu'
    : 'Dữ liệu mẫu · Chưa phải số liệu tài chính thật';
}

export function citationView(result) {
  if (result?.execution_mode !== 'LIVE') return [];
  if (result.scope?.source_type === 'PRICE' || result.presentation?.sources === 'HIDDEN') return [];
  const bound = new Set(result.answering?.status === 'DRAFT_READY'
    ? (result.answering.citations || []).map(c => c.evidence_id) : []);
  const numbers = new Map(result.answering?.status === 'DRAFT_READY'
    ? (result.answering.citations || []).filter(c => Number.isInteger(c.citation_number) && c.citation_number > 0)
      .map(c => [c.evidence_id, c.citation_number]) : []);
  return (result.evidence_pack?.items || []).filter(item => item.source_verified === true && item.source_type !== 'PRICE'
    && (result.presentation?.sources !== 'USED_LINKS' || bound.has(item.evidence_id))).map(item => ({
    id: item.evidence_id,
    used: bound.has(item.evidence_id),
    citationNumber: numbers.get(item.evidence_id) ?? null,
    title: item.title || (item.source_type === 'NEWS' ? 'Bài tin' : 'Báo cáo tài chính'),
    location: item.locator?.section || 'Đoạn nguồn',
    passage: item.passage,
    rows: Array.isArray(item.locator?.row_keys) ? item.locator.row_keys : [],
    url: safeSourceUrl(item.locator?.url),
    compact: item.source_type === 'NEWS',
  }));
}
