// Keep source inspection bound to the displayed account, session and answer.
export function sourceInspection(snapshot, selection, owner) {
  const empty = { result: null, question: '', index: -1 };
  if (!owner || !snapshot?.messages?.length) return empty;
  const messages = snapshot.messages;
  const candidate = Number.isInteger(selection?.index) ? messages[selection.index] : null;
  const valid = selection?.owner === owner && selection?.session === snapshot.session_id
    && candidate?.role !== 'user' && candidate?.result;
  let index = valid ? selection.index : messages.length - 1;
  if (!valid) {
    while (index >= 0 && (messages[index].role === 'user' || !messages[index].result)) index--;
  }
  if (index < 0) return empty;
  let questionIndex = index - 1;
  while (questionIndex >= 0 && messages[questionIndex].role !== 'user') questionIndex--;
  return { result: messages[index].result, question: messages[questionIndex]?.content || '', index };
}
