// UI navigation only; API authorization always uses current server-side grants.
export function primaryRole(roles) {
  return Array.isArray(roles) && roles.some(role => String(role).toUpperCase() === "ADMINISTRATOR") ? "admin" : "user";
}

export function normalizeAuthUser(user) {
  return user ? { ...user, role: primaryRole(user.roles) } : null;
}
