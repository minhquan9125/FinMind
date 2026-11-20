import { primaryRole } from './authRoles.js';
import { PATHS } from '../paths.js';

export function loginDestination(user, from) {
  const admin = primaryRole(user?.roles) === 'admin';
  const pathname = from?.pathname;
  const safe = typeof pathname === 'string' && pathname.startsWith('/') && !pathname.startsWith('//') && !/[\\?#]/.test(pathname);
  const adminPath = safe && (pathname === '/admin' || pathname.startsWith('/admin/'));
  if (admin) return adminPath ? pathname : PATHS.admin;
  if (safe && !adminPath && !['/', '/login', '/register', '/forgot-password', '/reset-password'].includes(pathname)) {
    return pathname + (typeof from.search === 'string' && from.search.startsWith('?') ? from.search : '');
  }
  return PATHS.dashboard;
}
