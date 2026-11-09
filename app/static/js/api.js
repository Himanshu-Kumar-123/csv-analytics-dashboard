// Small fetch wrapper: adds the CSRF header, parses JSON and normalises errors.
const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content ?? "";

export class ApiError extends Error {
  constructor(message, { status = 0, code = "error", details = null } = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function parseError(response) {
  try {
    const body = await response.json();
    if (body && body.error) {
      return new ApiError(body.error.message, { status: response.status, code: body.error.code, details: body.error.details });
    }
  } catch { /* non-JSON error body */ }
  return new ApiError(`Request failed (${response.status})`, { status: response.status });
}

export async function apiFetch(url, { method = "GET", body, json, headers = {} } = {}) {
  const init = { method, headers: { Accept: "application/json", ...headers }, credentials: "same-origin" };
  if (method !== "GET" && method !== "HEAD") init.headers["X-CSRFToken"] = csrfToken;
  if (json !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(json);
  } else if (body !== undefined) {
    init.body = body;
  }
  let response;
  try {
    response = await fetch(url, init);
  } catch {
    throw new ApiError("Network error: could not reach the server.");
  }
  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return null;
  return response.json();
}

export function withQuery(url, params = {}) {
  const u = new URL(url, window.location.origin);
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    u.searchParams.set(key, typeof value === "object" ? JSON.stringify(value) : String(value));
  }
  return u.pathname + u.search;
}

export function getCsrfToken() {
  return csrfToken;
}
