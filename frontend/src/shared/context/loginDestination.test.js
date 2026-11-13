import test from 'node:test';
import assert from 'node:assert/strict';
import { loginDestination } from './loginDestination.js';

test('server admin grant returns to administration despite stale dashboard destination', () => {
  const admin = { email: 'member@example.test', roles: ['RESEARCHER', 'ADMINISTRATOR'] };
  assert.equal(loginDestination(admin, { pathname: '/dashboard' }), '/admin');
  assert.equal(loginDestination(admin), '/admin');
  assert.equal(loginDestination(admin, { pathname: '/admin/ingestion' }), '/admin/ingestion');
});

test('email and stale UI role cannot select admin destination for a researcher', () => {
  const user = { email: 'admin@example.test', role: 'admin', roles: ['RESEARCHER'] };
  assert.equal(loginDestination(user, { pathname: '/admin/ingestion' }), '/dashboard');
  assert.equal(loginDestination(user, { pathname: '/research', search: '?company=FPT' }), '/research?company=FPT');
  for (const pathname of ['//external.test', '/\\external.test', '/login']) assert.equal(loginDestination(user, { pathname }), '/dashboard');
});
