import type { Cell } from "../types/cell";

/** Parse SSE events from a fetch Response and dispatch to handlers. */
export interface SSEHandlers {
  onStage?: (stage: string) => void;
  onCell?: (cell: Cell) => void;
  onError?: (message: string) => void;
  onReasoning?: (text: string) => void;
  onRefusal?: (data: unknown) => void;
}

const INACTIVITY_TIMEOUT_MS = 60_000;

export async function consumeSSE(
  response: Response,
  handlers: SSEHandlers,
  signal?: AbortSignal
): Promise<void> {
  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";
  let eventType = "";
  let eventData = "";

  let inactivityTimer: ReturnType<typeof setTimeout> | null = null;

  const clearInactivityTimer = () => {
    if (inactivityTimer !== null) {
      clearTimeout(inactivityTimer);
      inactivityTimer = null;
    }
  };

  const resetInactivityTimer = () => {
    clearInactivityTimer();
    inactivityTimer = setTimeout(() => {
      handlers.onError?.("Connection timed out — please retry");
      reader.cancel().catch(() => {});
    }, INACTIVITY_TIMEOUT_MS);
  };

  const dispatch = () => {
    if (eventType && eventData) {
      try {
        const data: unknown = JSON.parse(eventData);
        if (eventType === "stage") {
          handlers.onStage?.((data as { stage: string }).stage);
        } else if (eventType === "cell") {
          // The one place the wire payload is trusted as a Cell.
          handlers.onCell?.(data as Cell);
        } else if (eventType === "error") {
          handlers.onError?.((data as { message: string }).message);
        } else if (eventType === "refusal") {
          handlers.onRefusal?.(data);
        } else if (eventType === "reasoning") {
          handlers.onReasoning?.((data as { text: string }).text);
        }
      } catch (e) {
        console.error("[SSE] parse error:", e, eventData);
      }
    }
    eventType = "";
    eventData = "";
  };

  const processLine = (rawLine: string) => {
    const line = rawLine.replace(/\r$/, "");
    if (line.startsWith("event:")) {
      eventType = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      // Per the SSE spec, consecutive data: lines join with a newline.
      const chunk = line.slice(5).trimStart();
      eventData = eventData ? `${eventData}\n${chunk}` : chunk;
    } else if (line === "") {
      dispatch();
    }
  };

  try {
    resetInactivityTimer();

    while (true) {
      if (signal?.aborted) break;

      const { done, value } = await reader.read();
      if (done) break;

      resetInactivityTimer();

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      lines.forEach(processLine);
    }

    // Flush: a stream that ends without a trailing blank line still carries
    // its last event (typically the cell) — don't drop it.
    buffer += decoder.decode();
    if (buffer) buffer.split("\n").forEach(processLine);
    dispatch();
  } catch (err) {
    // AbortError is expected when the signal is aborted
    if (err instanceof DOMException && err.name === "AbortError") return;
    throw err;
  } finally {
    clearInactivityTimer();
    reader.releaseLock();
  }
}
