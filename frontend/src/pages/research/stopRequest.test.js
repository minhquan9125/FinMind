import { test } from 'node:test';
import assert from 'node:assert/strict';
import { stopRequest } from './stopRequest.js';

test('Stop cancels the click default action before aborting the old request', () => {
  const click = new Event('click', { cancelable: true });
  const request = new AbortController();
  request.signal.addEventListener('abort', () => assert.equal(click.defaultPrevented, true));
  stopRequest(click, request);
  assert.equal(request.signal.aborted, true);
  assert.equal(click.defaultPrevented, true);
  // A subsequent question owns a fresh controller and is not cancelled.
  const next = new AbortController();
  assert.equal(next.signal.aborted, false);
});

test('a late Stop click still cannot submit the form after the request completes', () => {
  const click = new Event('click', { cancelable: true });
  stopRequest(click, null);
  assert.equal(click.defaultPrevented, true);
});
