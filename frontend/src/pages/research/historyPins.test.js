import { test } from 'node:test';
import assert from 'node:assert/strict';
import { historyPinsKey, loadHistoryPins, toggleHistoryPin, sortPinnedHistory } from './historyPins.js';

function memory() {
  const values = new Map();
  return { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) };
}

test('pins survive reload, are isolated by account, and can be removed', () => {
  const storage = memory();
  assert.deepEqual(toggleHistoryPin('a', 'session-1', storage).ids, ['session-1']);
  assert.deepEqual(loadHistoryPins('a', storage).ids, ['session-1']);
  assert.deepEqual(loadHistoryPins('b', storage).ids, []);
  toggleHistoryPin('b', 'session-2', storage);
  assert.deepEqual(toggleHistoryPin('a', 'session-1', storage).ids, []);
  assert.deepEqual(loadHistoryPins('b', storage).ids, ['session-2']);
  assert.deepEqual(loadHistoryPins(null, storage).ids, []);
});

test('pin sorting retains server order within groups without mutating history', () => {
  const items = ['a', 'b', 'c', 'd'].map(session_id => ({ session_id }));
  assert.deepEqual(sortPinnedHistory(items, ['d', 'b', 'missing']).map(item => item.session_id), ['b', 'd', 'a', 'c']);
  assert.deepEqual(items.map(item => item.session_id), ['a', 'b', 'c', 'd']);
});

test('storage data is normalized and malformed JSON is reported without overwriting it', () => {
  const storage = memory();
  storage.setItem(historyPinsKey('a'), JSON.stringify(['one', '', null, 'one', 2]));
  assert.deepEqual(loadHistoryPins('a', storage).ids, ['one']);
  storage.setItem(historyPinsKey('a'), '{broken');
  assert.ok(toggleHistoryPin('a', 'two', storage).error);
  assert.equal(storage.getItem(historyPinsKey('a')), '{broken');
});

test('blocked reads and failed writes report failure instead of showing an unsaved pin', () => {
  assert.ok(loadHistoryPins('a', { getItem() { throw Error('blocked'); } }).error);
  const storage = { getItem: () => '["old"]', setItem() { throw Error('quota'); } };
  const result = toggleHistoryPin('a', 'new', storage);
  assert.ok(result.error);
  assert.deepEqual(result.ids, ['old']);
});

test('toggling reads current persisted pins to preserve changes from another tab', () => {
  const storage = memory();
  toggleHistoryPin('a', 'one', storage);
  toggleHistoryPin('a', 'two', storage);
  assert.deepEqual(loadHistoryPins('a', storage).ids, ['one', 'two']);
});
