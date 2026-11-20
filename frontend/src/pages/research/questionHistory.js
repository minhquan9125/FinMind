// Input-only history: never sends a request or edits a saved conversation.
export function navigateQuestionHistory({ key, text, messages, scope, state }) {
  if (!['ArrowUp', 'ArrowDown'].includes(key)) return null;
  const questions = (messages || []).filter(m => m.role === 'user' && typeof m.content === 'string')
    .map(m => m.content);
  if (!questions.length) return null;
  const active = state?.scope === scope && Number.isInteger(state.index);
  if (!active && key === 'ArrowDown') return null;
  const index = active ? state.index : questions.length;
  const next = Math.max(0, Math.min(questions.length, index + (key === 'ArrowUp' ? -1 : 1)));
  const draft = active ? state.draft : text;
  return { text: next === questions.length ? draft : questions[next],
    state: next === questions.length ? null : { scope, index: next, draft } };
}
