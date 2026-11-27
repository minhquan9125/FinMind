export const LANDING_SYMBOL = 'FPT';
export const LANDING_INDICES = [
  ['VNINDEX', 'VN-Index'], ['VN30', 'VN30'], ['HNXINDEX', 'HNX-Index'], ['UPCOMINDEX', 'UPCoM'],
];

export function readMarketNumber(value) {
  if (!['number', 'string'].includes(typeof value) || String(value).trim() === '') return null;
  return Number.isFinite(Number(value)) ? Number(value) : null;
}

export function summarizeMarket(data) {
  const bars = Array.isArray(data?.bars) ? data.bars : [];
  const latest = bars.at(-1);
  const close = readMarketNumber(latest?.close);
  if (close === null || close <= 0) return null;
  const previous = bars.at(-2);
  const reference = readMarketNumber(previous?.close);
  const hasPrevious = reference !== null && reference > 0;
  const change = hasPrevious ? close - reference : null;
  return { close, change, percent: hasPrevious ? change / reference * 100 : null, date: latest.date, status: latest.status };
}

export function selectFinancialEvidence(company) {
  // A citation must belong to the same period as the displayed fact.
  for (const period of company?.periods || []) {
    const report = company.reports?.find((item) => item.period === period.period && /^https?:\/\//i.test(item.url || ''));
    if (!report) continue;
    const fact = period.facts?.netProfit;
    // Match the monetary units handled by the shared company formatter.
    return { period, report, fact: ['VND', 'SOURCE_NATIVE'].includes(fact?.unit) && readMarketNumber(fact.value) !== null ? fact : null };
  }
  return null;
}
