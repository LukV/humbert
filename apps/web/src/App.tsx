import { useCallback, useEffect, useRef, useState } from "react";
import type { Cell } from "./types/cell";
import { apiFetch, apiGet } from "./utils/api";
import { consumeSSE } from "./utils/sse";
import { setLocale, t } from "./locales";
import CellView from "./components/CellView";
import InputBar from "./components/InputBar";
import ReasoningStream from "./components/ReasoningStream";
import StageIndicator from "./components/StageIndicator";

interface HealthData {
  ok: boolean;
  connection_name?: string;
  database?: string;
}

interface ThemeData {
  app_name: string;
  locale: string;
  logo_path: string | null;
  custom_css: string | null;
  css_vars: Record<string, string>;
}

interface SuggestionsData {
  suggestions: string[];
  generating: boolean;
}

function pickRandom<T>(arr: T[], n: number): T[] {
  const shuffled = [...arr].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, n);
}

type Theme = "light" | "dark";

function getInitialTheme(): Theme {
  const stored = localStorage.getItem("humbert-theme");
  if (stored === "light" || stored === "dark") return stored;
  if (window.matchMedia("(prefers-color-scheme: dark)").matches) return "dark";
  return "light";
}

function applyThemeCss(data: ThemeData): void {
  if (data.custom_css) {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = data.custom_css;
    document.head.appendChild(link);
  }
  const root = document.documentElement;
  for (const [key, value] of Object.entries(data.css_vars)) {
    root.style.setProperty(key, value);
  }
}

export default function App() {
  const [cells, setCells] = useState<Cell[]>([]);
  const [currentStage, setCurrentStage] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [health, setHealth] = useState<HealthData | null>(null);
  const [theme, setTheme] = useState<Theme>(getInitialTheme);
  const [reasoningText, setReasoningText] = useState("");
  const [appName, setAppName] = useState("Humbert");
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const resultsScrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  // Read inside setInterval to avoid recreating the timer every time the
  // banner toggles. Mirrors `connectionError` state.
  const connectionErrorRef = useRef<string | null>(null);
  connectionErrorRef.current = connectionError;

  const lastCellId = cells.length > 0 ? cells[cells.length - 1].id : null;
  const showResults = cells.length > 0 || isProcessing;

  // Apply theme to document
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("humbert-theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "light" ? "dark" : "light"));
  };

  // --- Initial load: four independent fetches, each isolated so a slow or
  // failing endpoint can't block the others. `retry: true` rides out the
  // race between `humbert start` opening the browser and uvicorn binding.
  useEffect(() => {
    const loadNotebook = () =>
      apiGet<Cell[]>("/api/notebook", { retry: true })
        .then((data) => {
          setCells(data);
          setConnectionError(null);
        })
        .catch(() => setConnectionError(t("connection.error")));

    const loadSuggestions = () =>
      apiGet<SuggestionsData>("/api/suggestions", { retry: true })
        .then((data) => {
          if (data.suggestions.length > 0) {
            setSuggestions(pickRandom(data.suggestions, 5));
          }
        })
        .catch(() => console.warn("Failed to fetch suggestions"));

    const loadHealth = () =>
      apiGet<HealthData>("/api/health", { retry: true })
        .then((data) => {
          setHealth(data);
          if (data.ok) setConnectionError(null);
        })
        .catch(() => {
          setHealth(null);
          setConnectionError(t("connection.error"));
        });

    const loadTheme = () =>
      apiGet<ThemeData>("/api/theme", { retry: true })
        .then((data) => {
          setAppName(data.app_name);
          setLocale(data.locale);
          applyThemeCss(data);
          setConnectionError(null);
        })
        .catch(() => setConnectionError(t("connection.error")));

    void loadNotebook();
    void loadSuggestions();
    void loadHealth();
    void loadTheme();
  }, []);

  // Health polling — fast (2s) while disconnected so the banner clears
  // quickly once the server is up; slow (30s) on the steady-state path.
  // Reads `connectionError` via ref so banner-toggle doesn't recreate the
  // timer; cadence is picked when the timer starts.
  useEffect(() => {
    const intervalMs = connectionError ? 2_000 : 30_000;
    const interval = setInterval(() => {
      apiGet<HealthData>("/api/health")
        .then((data) => {
          setHealth(data);
          if (data.ok && connectionErrorRef.current) {
            setConnectionError(null);
          }
        })
        .catch(() => {
          setHealth(null);
          setConnectionError(t("connection.error"));
        });
    }, intervalMs);
    return () => clearInterval(interval);
  }, [connectionError]);

  // Scroll to bottom when processing
  useEffect(() => {
    if (isProcessing && resultsScrollRef.current) {
      resultsScrollRef.current.scrollTop = resultsScrollRef.current.scrollHeight;
    }
  }, [cells, currentStage, isProcessing]);

  const handleCellUpdate = (updated: Cell) => {
    setCells((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
  };

  const handleCellDelete = async (cellId: string) => {
    try {
      await apiFetch(`/api/cells/${cellId}`, { method: "DELETE" });
      setCells((prev) => prev.filter((c) => c.id !== cellId));
    } catch {
      /* ignore */
    }
  };

  // Abort active SSE stream on unmount
  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  const handleAsk = useCallback(
    async (question: string) => {
      // Abort any in-flight request
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setIsProcessing(true);
      setError(null);
      setCurrentStage("thinking");
      setReasoningText("");

      try {
        const body: { question: string; parent_cell_id?: string } = { question };
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
          throw new Error(message);
        }

        await consumeSSE(
          response,
          {
            onStage: (stage) => setCurrentStage(stage),
            onCell: (data) => {
              setCells((prev) => [...prev, data as Cell]);
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
        setError(err instanceof Error ? err.message : "Unknown error");
        setCurrentStage(null);
      } finally {
        setIsProcessing(false);
      }
    },
    [lastCellId],
  );

  const isConnected = health?.ok === true;
  const connectionLabel = health?.database || health?.connection_name;

  return (
    <div className="app">
      {/* Topbar */}
      <header className="topbar">
        <div className="topbar-left">
          {/* The Humbert mark: four bars, outline only (docs/assets Humbert-Icon → mk-barsline). */}
          <svg
            className="topbar-logo"
            width="18"
            height="18"
            viewBox="0 0 24 24"
            aria-hidden
          >
            <g fill="none" stroke="var(--logo-fill)" strokeWidth="1.6">
              <rect x="2.7" y="14.2" width="3.2" height="7.1" rx="0.9" />
              <rect x="7.8" y="9.4" width="3.2" height="11.9" rx="0.9" />
              <rect x="12.9" y="11.2" width="3.2" height="10.1" rx="0.9" />
              <rect x="18" y="5.6" width="3.2" height="15.7" rx="0.9" />
            </g>
          </svg>
          <span className="topbar-wordmark">{appName}</span>
        </div>
        <div className="topbar-right">
          {health !== null && (
            <div className="conn-indicator">
              <span
                className={`conn-dot ${isConnected ? "conn-dot--connected" : "conn-dot--disconnected"}`}
              />
              {isConnected ? connectionLabel || "Connected" : "Not connected"}
            </div>
          )}
          <button
            className="theme-toggle"
            onClick={toggleTheme}
            title="Toggle theme"
            aria-label="Toggle theme"
          >
            {theme === "light" ? (
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <path
                  d="M13.5 9.2A5.5 5.5 0 016.8 2.5 6 6 0 1013.5 9.2z"
                  stroke="currentColor"
                  strokeWidth="1.3"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            ) : (
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="3" stroke="currentColor" strokeWidth="1.3" />
                <path
                  d="M8 1.5v1.5M8 13v1.5M1.5 8H3M13 8h1.5M3.4 3.4l1 1M11.6 11.6l1 1M3.4 12.6l1-1M11.6 4.4l1-1"
                  stroke="currentColor"
                  strokeWidth="1.2"
                  strokeLinecap="round"
                />
              </svg>
            )}
          </button>
        </div>
      </header>

      {/* Connection error banner */}
      {connectionError && (
        <div className="connection-error-banner">
          <span>{connectionError}</span>
          <button
            onClick={() => {
              setConnectionError(null);
              window.location.reload();
            }}
          >
            {t("connection.retry")}
          </button>
        </div>
      )}

      {/* Empty state (hero view) */}
      {!showResults && (
        <div className="view-empty">
          <h1 className="hero-title" style={{ whiteSpace: "pre-line" }}>
            {t("hero.title")}
          </h1>
          <p className="hero-sub">{t("hero.subtitle")}</p>
          <InputBar
            variant="hero"
            onAsk={handleAsk}
            disabled={isProcessing || !!connectionError}
            parentCellId={lastCellId}
          />
          {suggestions.length > 0 && (
            <div className="sample-prompts">
              {suggestions.map((s, i) => (
                <button key={i} className="sample-chip" onClick={() => handleAsk(s)}>
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Results state */}
      {showResults && (
        <div className="view-results">
          <div className="results-scroll" ref={resultsScrollRef}>
            <div className="results-inner">
              {cells.map((cell) => (
                <CellView
                  key={cell.id}
                  cell={cell}
                  theme={theme}
                  onCellUpdate={handleCellUpdate}
                  onCellDelete={handleCellDelete}
                  onAsk={handleAsk}
                />
              ))}

              {currentStage && <StageIndicator stage={currentStage} />}

              {reasoningText && isProcessing && (
                <ReasoningStream text={reasoningText} isStreaming={!!currentStage} />
              )}

              {error && (
                <div className="app-error">
                  <span className="app-error__text">{error}</span>
                  <button
                    className="app-error__dismiss"
                    onClick={() => setError(null)}
                    aria-label="Dismiss error"
                  >
                    &times;
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Bottom input bar */}
          <div className="bottom-input-bar">
            <div className="bottom-input-inner">
              <InputBar
                variant="compact"
                onAsk={handleAsk}
                disabled={isProcessing || !!connectionError}
                parentCellId={lastCellId}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
