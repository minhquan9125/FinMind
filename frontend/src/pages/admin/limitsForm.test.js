import test from 'node:test';
import assert from 'node:assert/strict';
import { LIMIT_FIELDS, draftFrom, validateDraft, overridesFrom, isUnchanged, limitsErrorMessage, keyStatusView } from './limitsForm.js';

const bounds = {
  max_input_tokens: { min: 1024, max: 65536 }, max_output_tokens: { min: 256, max: 8192 },
  max_total_tokens: { min: 1024, max: 262144 }, max_generation_calls: { min: 1, max: 50 },
  read_timeout_seconds: { min: 5, max: 600 },
};
const defaults = { max_input_tokens: 16384, max_output_tokens: 2048, max_total_tokens: 65536, max_generation_calls: 20, read_timeout_seconds: 600 };

test('the form covers exactly the five editable fields and starts from the effective values', () => {
  assert.deepEqual(LIMIT_FIELDS.map(f => f.key).sort(), Object.keys(defaults).sort());
  assert.deepEqual(draftFrom(defaults).max_generation_calls, '20');
  assert.equal(draftFrom(undefined).max_input_tokens, '');
});

test('validation reports each bad field and accepts the defaults', () => {
  assert.deepEqual(validateDraft(draftFrom(defaults), bounds), {});
  const bad = validateDraft({ ...draftFrom(defaults), max_generation_calls: '0', read_timeout_seconds: 'abc', max_output_tokens: '1.5' }, bounds);
  assert.match(bad.max_generation_calls, /1–50/);
  assert.equal(bad.read_timeout_seconds, 'Nhập số nguyên');
  assert.equal(bad.max_output_tokens, 'Nhập số nguyên');
});

test('total tokens may not be smaller than output tokens', () => {
  const errors = validateDraft({ ...draftFrom(defaults), max_output_tokens: '4096', max_total_tokens: '2048' }, bounds);
  assert.equal(errors.max_total_tokens, 'Không được nhỏ hơn token đầu ra tối đa');
});

test('only values that differ from the defaults are sent; nothing differing means reset', () => {
  assert.deepEqual(overridesFrom(draftFrom(defaults), defaults), {});
  assert.deepEqual(overridesFrom({ ...draftFrom(defaults), max_generation_calls: ' 8 ' }, defaults), { max_generation_calls: 8 });
});

test('unchanged detection ignores key order', () => {
  assert.equal(isUnchanged({ a: 1, b: 2 }, { b: 2, a: 1 }), true);
  assert.equal(isUnchanged({ a: 1 }, { a: 2 }), false);
  assert.equal(isUnchanged({}, undefined), true);
});

test('error messages are readable and unknown codes fall back', () => {
  assert.match(limitsErrorMessage('LIMITS_CONFIG_CHANGED', 409), /Tải lại/);
  assert.equal(limitsErrorMessage('X', 403), 'Tài khoản không có quyền quản trị.');
  assert.equal(limitsErrorMessage(undefined, 500), 'Không lưu được cấu hình.');
});

test('key status shows state and a human retry time, never key text', () => {
  assert.deepEqual(keyStatusView({ key: 'key 1', state: 'ready', retry_in_seconds: 0 }), { name: 'key 1', label: 'Sẵn sàng', tone: 'success' });
  assert.match(keyStatusView({ key: 'key 2', state: 'quota', retry_in_seconds: 90 }).label, /thử lại sau 2 phút/);
  assert.match(keyStatusView({ key: 'key 3', state: 'invalid', retry_in_seconds: 21600 }).label, /thử lại sau 6 giờ/);
  assert.match(keyStatusView({ key: 'key 4', state: 'quota', retry_in_seconds: 30 }).label, /30 giây/);
  assert.equal(keyStatusView({ state: 'weird' }).tone, 'neutral');
});

test('key form errors are specific and never contain the key', async () => {
  const { validateKeyForm } = await import('./limitsForm.js');
  const good = 'AIza' + 'A'.repeat(35);
  assert.deepEqual(validateKeyForm({ label: 'Khóa của Huyền', key: good }), {});
  assert.deepEqual(validateKeyForm({ label: ' ', key: '' }), { label: 'Đặt tên gợi nhớ, tối đa 60 ký tự', key: 'Khóa Gemini bắt đầu bằng AIza hoặc AQ. và không có khoảng trắng bên trong' });
  assert.ok(validateKeyForm({ label: 'x', key: 'sk-' + 'x'.repeat(40) }).key);
  assert.ok(validateKeyForm({ label: 'x', key: 'AIza' + 'A'.repeat(10) + ' ' + 'A'.repeat(25) }).key);
  assert.ok(validateKeyForm({ label: 'x'.repeat(61), key: good }).label);
  const newShape = 'AQ.' + 'x'.repeat(8) + '_' + 'Y'.repeat(20) + '-' + 'z'.repeat(18);   // newer Google key shape
  assert.deepEqual(validateKeyForm({ label: 'Khóa mới', key: newShape }), {});
  assert.deepEqual(validateKeyForm({ label: 'x', key: ` ${newShape}
` }), {});
  for (const bad of ['AQ' + 'x'.repeat(40), 'AQ. short', 'AQ.' + 'x'.repeat(10) + ' ' + 'y'.repeat(25), 'AX.' + 'x'.repeat(40)]) {
    assert.ok(validateKeyForm({ label: 'x', key: bad }).key, bad);
  }
  assert.deepEqual(validateKeyForm(), { label: 'Đặt tên gợi nhớ, tối đa 60 ký tự', key: 'Khóa Gemini bắt đầu bằng AIza hoặc AQ. và không có khoảng trắng bên trong' });
  assert.ok(!JSON.stringify(validateKeyForm({ label: 'x', key: 'AIza-secret-wrong!' + 'Z'.repeat(40) })).includes('Z'.repeat(10)));
});

test('key error codes map to readable text and the disabled store explains how to enable it', async () => {
  const { keyErrorMessage } = await import('./limitsForm.js');
  assert.match(keyErrorMessage('KEY_REJECTED', 409), /Google từ chối/);
  assert.match(keyErrorMessage('KEY_STORE_DISABLED', 503), /GEMINI_KEYS_SECRET/);
  assert.match(keyErrorMessage('KEY_DUPLICATE', 409), /đã có/);
  assert.equal(keyErrorMessage('X', 403), 'Tài khoản không có quyền quản trị.');
  assert.equal(keyErrorMessage(undefined, 500), 'Không thực hiện được.');
});

test('add result and test result notes reflect what Google said and whether a restart is needed', async () => {
  const { addResultNote, testResultLabel } = await import('./limitsForm.js');
  assert.match(addResultNote({ verification: 'OK', restart_needed: false }), /Google chấp nhận khóa\. Có hiệu lực ngay/);
  assert.match(addResultNote({ verification: 'QUOTA', restart_needed: false }), /hết hạn mức/);
  assert.match(addResultNote({ verification: 'UNAVAILABLE', restart_needed: false }), /vẫn được lưu/);
  assert.match(addResultNote({ verification: 'OK', restart_needed: true }), /khởi động lại backend một lần/);
  assert.equal(addResultNote(null), 'Đã lưu khóa. Có hiệu lực ngay, không cần khởi động lại.');
  assert.equal(testResultLabel('INVALID'), 'Google từ chối khóa này.'); assert.equal(testResultLabel('?'), 'Không rõ.');
});

test('a managed key shows only its label, last four characters and an honest state', async () => {
  const { managedKeyView } = await import('./limitsForm.js');
  const base = { id: 'i', label: 'Huyền', last4: 'AAAA', enabled: true, verified: true, readable: true };
  assert.deepEqual(managedKeyView(base), { id: 'i', name: 'Huyền', tail: '…AAAA', label: 'Đã kiểm tra', tone: 'success' });
  assert.equal(managedKeyView({ ...base, verified: false }).label, 'Chưa kiểm tra');
  assert.equal(managedKeyView({ ...base, enabled: false }).label, 'Đang tắt');
  assert.equal(managedKeyView({ ...base, readable: false }).tone, 'error');
  assert.ok(!JSON.stringify(managedKeyView(base)).includes('AIza'));
});

test('an .env key shows only its number, last four characters and whether it is in use', async () => {
  const { envKeyView, keyErrorMessage } = await import('./limitsForm.js');
  const item = { id: 'abc123', position: 1, last4: 'ZZZZ', enabled: true };
  assert.deepEqual(envKeyView(item), { id: 'abc123', name: 'Khóa .env #1', tail: '…ZZZZ', label: 'Đang dùng', tone: 'success' });
  assert.deepEqual(envKeyView({ ...item, enabled: false }), { id: 'abc123', name: 'Khóa .env #1', tail: '…ZZZZ', label: 'Đang tắt', tone: 'neutral' });
  assert.match(keyErrorMessage('KEY_LAST_ACTIVE', 409), /khóa cuối cùng/);
});
