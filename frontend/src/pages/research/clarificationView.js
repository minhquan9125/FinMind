export function clarificationChoices(result) {
  if (!['ASK_CLARIFICATION', 'CLARIFICATION_STALLED'].includes(result?.status)) return [];
  if (!Array.isArray(result.clarification_options)) return [];
  const seen = new Set();
  return result.clarification_options.filter(item => {
    if (!item || typeof item.id !== 'string' || seen.has(item.id) ||
        typeof item.label !== 'string' || !item.label.trim() || item.label.length > 150 ||
        typeof item.reply !== 'string' || !item.reply.trim() || item.reply.length > 200) return false;
    seen.add(item.id);
    return true;
  }).slice(0, 8).map(item => ({ id: item.id, label: item.label, reply: item.reply,
    description: typeof item.description === 'string' ? item.description.slice(0, 500) : '' }));
}
