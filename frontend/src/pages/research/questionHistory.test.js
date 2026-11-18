import test from 'node:test';
import assert from 'node:assert/strict';
import { navigateQuestionHistory as move } from './questionHistory.js';

const messages = [{ role: 'user', content: 'phân tích VCB' },
  { role: 'assistant', content: 'Không phải câu hỏi' },
  { role: 'user', content: 'chủ tịch công ty đó là ai' }];
const base = { messages, scope: 'owner:session', text: 'bản nháp đang viết' };

test('up recalls user questions, down restores unsent draft without mutation', () => {
  const latest = move({ ...base, key: 'ArrowUp' });
  assert.equal(latest.text, messages[2].content);
  const older = move({ ...base, key: 'ArrowUp', text: latest.text, state: latest.state });
  assert.equal(older.text, messages[0].content);
  assert.equal(move({ ...base, key: 'ArrowUp', state: older.state }).text, messages[0].content);
  const newer = move({ ...base, key: 'ArrowDown', state: older.state });
  assert.equal(newer.text, messages[2].content);
  const draft = move({ ...base, key: 'ArrowDown', state: newer.state });
  assert.equal(draft.text, base.text);
  assert.equal(draft.state, null);
  assert.equal(messages.length, 3);
});

test('empty history, other keys and initial down do nothing', () => {
  assert.equal(move({ ...base, key: 'Enter' }), null);
  assert.equal(move({ ...base, key: 'ArrowDown' }), null);
  assert.equal(move({ ...base, messages: [], key: 'ArrowUp' }), null);
});

test('changing account or session cannot recover an old draft', () => {
  const old = move({ ...base, key: 'ArrowUp' });
  for (const scope of ['other:session', 'owner:new-session']) {
    assert.equal(move({ ...base, scope, key: 'ArrowDown', state: old.state }), null);
    const next = move({ ...base, scope, text: '', key: 'ArrowUp', state: old.state });
    assert.equal(next.state.draft, '');
  }
});
