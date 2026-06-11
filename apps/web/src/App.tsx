import { useEffect, useRef } from "react";
import { t } from "./locales";
import { useBranding } from "./hooks/useBranding";
import { useHealth } from "./hooks/useHealth";
import { useNotebook } from "./hooks/useNotebook";
import { useTheme } from "./hooks/useTheme";
import CellView from "./components/CellView";
import InputBar from "./components/InputBar";
import ReasoningStream from "./components/ReasoningStream";
import StageIndicator from "./components/StageIndicator";

export default function App() {
  const { theme, toggleTheme } = useTheme();
  const { health, connectionError, setConnectionError } = useHealth();
  const appName = useBranding(setConnectionError);
  const {
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
  } = useNotebook(setConnectionError);

  const resultsScrollRef = useRef<HTMLDivElement>(null);
  const showResults = cells.length > 0 || isProcessing;

  // Scroll to bottom when processing
  useEffect(() => {
    if (isProcessing && resultsScrollRef.current) {
      resultsScrollRef.current.scrollTop = resultsScrollRef.current.scrollHeight;
    }
  }, [cells, currentStage, isProcessing]);

  const isConnected = health?.status === "ok";
  const connectionLabel = health?.project ?? undefined;

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

      {/* Connection / setup error banner. A connection failure (server down)
          takes precedence and offers a reload; a setup error (no API key) is a
          config fix, so it just dismisses. Same component for both. */}
      {(connectionError || setupError) && (
        <div className="connection-error-banner">
          <span>{connectionError ?? setupError}</span>
          <button
            onClick={() => {
              if (connectionError) {
                setConnectionError(null);
                window.location.reload();
              } else {
                setSetupError(null);
              }
            }}
          >
            {connectionError ? t("connection.retry") : t("error.dismiss")}
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
            hasFollowupContext={!!lastCellId}
          />
          {suggestions.length > 0 && (
            <div className="sample-prompts">
              {suggestions.map((s) => (
                <button key={s} className="sample-chip" onClick={() => handleAsk(s)}>
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
                hasFollowupContext={!!lastCellId}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
