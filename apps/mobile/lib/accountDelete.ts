/** Sessions are purged first on the server — a 401/404 here means the wipe already started. */
export function isAccountDeleteComplete(error: unknown): boolean {
  if (typeof error !== "object" || error === null || !("status" in error)) {
    return false;
  }
  const status = error.status;
  return status === 401 || status === 404;
}
