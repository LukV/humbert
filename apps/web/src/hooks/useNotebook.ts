import { useCallback, useEffect, useRef, useState } from "react";
import type { AskRequest, Cell } from "../types/cell";
import type { SuggestionsData } from "../types/api";
import { apiFetch, apiGet } from "../utils/api";
import { consumeSSE } from "../utils/sse";
import { t } from "../locales";

/** Fisher–Yates shuffle, then take the first n. */
function pickRandom<T>(arr: T[], n: number): T[] {
  const shuffled = [...arr];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled.slice(0, n);
}

/** The notebook: its cells, the suggestion chips, and the ask/SSE pipeline. */
export function useNotebook(onConnectionError: (message: string | null) => void) {
  const [cells, setCells] = useState<Cell[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [currentStage, setCurrentStage] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [reasoningText, setReasoningText] = useState("");
  const [error, setError] = useState<string | null>(null);
  // A setup problem returned by /api/ask (no connection / no API key). Shown in
  // the same under-header banner as a connection failure, not the inline cell
  // error — it's a configuration issue, not a bad answer.
  const [setupError, setSetupError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const lastCellId = cells.length > 0 ? cells[cells.length - 1].id : null;

  // Initial load: two independent fetches, each isolated so a slow or failing
  // endpoint can't block the other. `retry: true` rides out the race between
  // `humbert start` opening the browser and uvicorn binding.
  useEffect(() => {
    apiGet<Cell[]>("/api/notebook", { retry: true })
      .then((data) => {
        setCells(data);
        onConnectionError(null);
      })
      .catch(() => onConnectionError(t("connection.error")));

    apiGet<SuggestionsData>("/api/suggestions", { retry: true })
      .then((data) => {
        if (data.suggestions.length > 0) {
          setSuggestions(pickRandom(data.suggestions, 5));
        }
      })
      .catch(() => console.warn("Failed to fetch suggestions"));
  }, [onConnectionError]);

  // Abort active SSE stream on unmount
  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  const handleCellUpdate = useCallback((updated: Cell) => {
    setCells((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
  }, []);

  const handleCellDelete = useCallback(async (cellId: string) => {
    try {
      await apiFetch(`/api/cells/${cellId}`, { method: "DELETE" });
      setCells((prev) => prev.filter((c) => c.id !== cellId));
    } catch {
      /* ignore */
    }
  }, []);

  const handleAsk = useCallback(
    async (question: string) => {
      // Abort any in-flight request
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setIsProcessing(true);
      setError(null);
      setSetupError(null);
      setCurrentStage("thinking");
      setReasoningText("");

      try {
        const body: AskRequest = { question };
        if (lastCellId) {
          body.parent_cell_id = lastCellId;
        }

        const response = await apiFetch("/api/ask", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: controller.signal,
        });

        if (!response.ok) {
          // A setup problem (no connection / no API key) comes back as JSON.
          let message = `Server error: ${response.status}`;
          try {
            const data = (await response.json()) as { error?: string };
            if (data.error) message = data.error;
          } catch {
            /* not JSON — keep the status message */
          }
          // 400 is a configuration problem, not a failed answer: surface it in
          // the header banner (same component as a connection failure) and stop.
          if (response.status === 400) {
            setSetupError(message);
            return;
          }
          throw new Error(message);
        }

        await consumeSSE(
          response,
          {
            onStage: (stage) => setCurrentStage(stage),
            onCell: (cell) => {
              setCells((prev) => [...prev, cell]);
              setCurrentStage(null);
              setReasoningText("");
            },
            onError: (message) => {
              setError(message);
              setCurrentStage(null);
            },
            onRefusal: () => {
              // A refusal is not an error — the refused cell arrives via onCell.
              setCurrentStage(null);
              setReasoningText("");
            },
            onReasoning: (text) => setReasoningText((prev) => prev + text),
          },
          controller.signal,
        );
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        if (abortRef.current === controller) {
          setError(err instanceof Error ? err.message : "Unknown error");
          setCurrentStage(null);
        }
      } finally {
        // Only the live request may clear the shared state — when a new ask
        // replaces this one, this teardown must not switch off its indicator.
        if (abortRef.current === controller) {
          setIsProcessing(false);
        }
      }
    },
    [lastCellId],
  );

  return {
    cells,
    suggestions,
    currentStage,
    isProcessing,
    reasoningText,
    error,
    setError,
    setupError,
    setSetupError,
    lastCellId,
    handleAsk,
    handleCellUpdate,
    handleCellDelete,
  };
}
