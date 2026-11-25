export function normalizeSearch(value) {
  return value.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d").trim();
}

export function companyPlaceholder(value) {
  const id = value.trim().toUpperCase();
  return /^[A-Z]{3}$/.test(id) ? {
    id, name: `Cổ phiếu ${id}`, sector: "Chưa có hồ sơ", exchange: null,
    financials: [], reports: [], source: "Chưa có dữ liệu hồ sơ", unit: "—",
  } : null;
}

export function searchCompanies(catalog, query) {
  const text = normalizeSearch(query);
  const matches = catalog.filter((item) => normalizeSearch(`${item.id} ${item.name} ${item.sector}`).includes(text));
  const candidate = companyPlaceholder(query);
  if (candidate && !matches.some((item) => item.id === candidate.id)) matches.unshift(candidate);
  return matches;
}
