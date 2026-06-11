/**
 * Fetch wrapper that retries on network failure (the only failure mode that
 * indicates the server isn't reachable yet). Non-2xx responses are returned
 * as-is — the caller decides whether to treat them as errors.
 *
 * Used on app mount so a slow server start (browser opens before uvicorn is
 * listening on POST-able endpoints) doesn't immediately surface the
 * "Unable to connect" banner. The total wait at defaults is
 * 400 + 800 + 1600 + 3200 = 6s before the catch fires.
 */
export async function fetchWithRetry(
  input: RequestInfo | URL,
  init?: RequestInit,
  opts?: { attempts?: number; baseDelayMs?: number },
): Promise<Response> {
  const attempts = opts?.attempts ?? 5;
  const baseDelayMs = opts?.baseDelayMs ?? 400;
  let lastError: unknown;
  for (let i = 0; i < attempts; i++) {
    try {
      return await fetch(input, init);
    } catch (err) {
      // An abort is the caller's decision, not a flaky server — never retry it.
      if (err instanceof DOMException && err.name === "AbortError") throw err;
      lastError = err;
      if (i < attempts - 1) {
        await new Promise((resolve) =>
          setTimeout(resolve, baseDelayMs * Math.pow(2, i)),
        );
      }
    }
  }
  throw lastError;
}
