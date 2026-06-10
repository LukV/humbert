/** Tiny HTTP client over fetch.
 *
 * `apiFetch` returns the raw Response so callers can branch on status (the
 * 404-vs-200 split for /api/pack, the streaming SSE responses) without losing
 * the body. `apiGet<T>` is the convenience shorthand for the 90% case: GET
 * + 2xx → JSON.
 *
 * Retry is opt-in (`retry: true`) so the SSE endpoints and DELETE/POST
 * mutations don't accidentally re-fire on transient flakes. App-startup calls
 * use `retry: true` to ride out the race between `lumen start` opening the
 * browser and uvicorn binding the port.
 */

import { API_BASE } from "../config";
import { fetchWithRetry } from "./fetchWithRetry";

type ApiInit = RequestInit & { retry?: boolean };

export async function apiFetch(path: string, init: ApiInit = {}): Promise<Response> {
  const { retry, ...rest } = init;
  const url = `${API_BASE}${path}`;
  return retry ? fetchWithRetry(url, rest) : fetch(url, rest);
}

export async function apiGet<T>(path: string, opts: { retry?: boolean } = {}): Promise<T> {
  const res = await apiFetch(path, { retry: opts.retry });
  if (!res.ok) {
    throw new Error(`GET ${path} failed: ${res.status}`);
  }
  return (await res.json()) as T;
}

export async function apiSend(
  path: string,
  method: "POST" | "PATCH" | "DELETE",
  body?: unknown,
): Promise<Response> {
  return apiFetch(path, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}
