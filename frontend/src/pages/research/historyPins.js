export const historyPinsKey = owner => owner ? `finmind:chat-pins:v1:${encodeURIComponent(owner)}` : null;
const clean = ids => [...new Set(Array.isArray(ids) ? ids.filter(id => typeof id === 'string' && id.length > 0) : [])];

export function loadHistoryPins(owner, storage) {
  if (!owner) return { ids: [], error: null };
  try {
    const raw = (storage ?? globalThis.localStorage).getItem(historyPinsKey(owner));
    return { ids: clean(raw ? JSON.parse(raw) : []), error: null };
  } catch {
    return { ids: [], error: 'Không đọc được mục ghim trên trình duyệt này.' };
  }
}

export function toggleHistoryPin(owner, id, storage) {
  if (!owner || typeof id !== 'string' || !id) return { ids: [], error: 'Chưa xác định được tài khoản hoặc hội thoại.' };
  const current = loadHistoryPins(owner, storage);
  if (current.error) return current;
  const ids = current.ids.includes(id) ? current.ids.filter(value => value !== id) : [...current.ids, id];
  try {
    (storage ?? globalThis.localStorage).setItem(historyPinsKey(owner), JSON.stringify(ids));
    return { ids, error: null };
  } catch {
    return { ids: current.ids, error: 'Không lưu được mục ghim. Hãy cho phép lưu trữ trên trình duyệt này.' };
  }
}

export function sortPinnedHistory(items, ids) {
  const pinned = new Set(ids);
  return [...items.filter(item => pinned.has(item.session_id)), ...items.filter(item => !pinned.has(item.session_id))];
}
