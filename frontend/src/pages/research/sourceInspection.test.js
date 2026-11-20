import { test } from 'node:test';
import assert from 'node:assert/strict';
import { sourceInspection } from './sourceInspection.js';

const first = { citations: [{ citation_number: 1, title: 'FPT 2024' }] };
const second = { citations: [{ citation_number: 1, title: 'VCB 2025' }] };
const snapshot = { session_id: 'session-a', messages: [
  { role: 'user', content: 'FPT năm 2024' }, { role: 'assistant', result: first },
  { role: 'user', content: 'VCB năm 2025' }, { role: 'assistant', result: second },
  { role: 'user', content: 'Câu hỏi đang đợi trả lời' },
] };

test('opening an older answer retains that answer and its own question', () => {
  const view = sourceInspection(snapshot, { owner: 'user-a', session: 'session-a', index: 1 }, 'user-a');
  assert.equal(view.result, first);
  assert.equal(view.question, 'FPT năm 2024');
  assert.equal(view.index, 1);
});

test('default inspection pairs the latest answer with its question, not a pending question', () => {
  const view = sourceInspection(snapshot, null, 'user-a');
  assert.equal(view.result, second);
  assert.equal(view.question, 'VCB năm 2025');
});

test('switching account or conversation discards the old selection', () => {
  for (const selection of [
    { owner: 'other-user', session: 'session-a', index: 1 },
    { owner: 'user-a', session: 'old-session', index: 1 },
  ]) assert.equal(sourceInspection(snapshot, selection, 'user-a').result, second);
});

test('invalid selections and empty sessions never display an unrelated source', () => {
  for (const index of [-1, 0, 99, '1']) {
    assert.equal(sourceInspection(snapshot, { owner: 'user-a', session: 'session-a', index }, 'user-a').result, second);
  }
  assert.equal(sourceInspection(null, null, 'user-a').result, null);
  assert.equal(sourceInspection(snapshot, null, null).result, null);
});
