import test from 'node:test';
import assert from 'node:assert/strict';
import { clarificationChoices } from './clarificationView.js';

test('shows actionable natural-language choices while clarification is pending or stalled', () => {
  const option = { id: '1', label: 'Tổng nợ phải trả', reply: 'Tổng nợ phải trả', description: 'Toàn bộ nợ.' };
  for (const status of ['ASK_CLARIFICATION', 'CLARIFICATION_STALLED']) {
    assert.deepEqual(clarificationChoices({ status, clarification_options: [option] }), [option]);
  }
  assert.deepEqual(clarificationChoices({ status: 'EVIDENCE_READY', clarification_options: [option] }), []);
});

test('drops malformed, duplicate or empty choices without mutating the server response', () => {
  const choices = [{ id: '1', label: 'Nợ', reply: 'Nợ' }, { id: '1', label: 'Khác', reply: 'Khác' },
    { id: '2', label: '', reply: 'x' }, null, { id: '3', label: 'x', reply: 'x'.repeat(201) }];
  assert.equal(clarificationChoices({ status: 'ASK_CLARIFICATION', clarification_options: choices }).length, 1);
  assert.equal(choices.length, 5);
  assert.deepEqual(clarificationChoices(null), []);
});
