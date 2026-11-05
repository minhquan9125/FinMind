export function retainApprovedSelection(selected, approvedIds) {
  const allowed = new Set(approvedIds);
  return selected.filter(id => allowed.has(id));
}
export function toggleArticleSelection(selected, id, checked) {
  return checked ? [...new Set([...selected, id])] : selected.filter(item => item !== id);
}
