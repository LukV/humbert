import { Suspense, lazy, memo, useState } from "react";
import type { Cell } from "../types/cell";
import { apiSend } from "../utils/api";
import { t, useLocale } from "../locales";
import CodeView from "./CodeView";
import FeedbackControls from "./FeedbackControls";
import NarrativeView from "./NarrativeView";

// The chart stack (vega + vega-lite) dwarfs the rest of the bundle; loading it
// lazily keeps the hero view light and splits vega into its own chunk.
const ChartRenderer = lazy(() => import("./ChartRenderer"));

interface CellViewProps {
  cell: Cell;
  theme: "light" | "dark";
  onCellUpdate: (updated: Cell) => void;
  onCellDelete: (cellId: string) => void;
  onAsk: (question: string) => void;
}

// Memoized so the streaming reasoning text (which re-renders App per SSE
// chunk) doesn't re-render every settled cell in the notebook.
export default memo(function CellView({
  cell,
  theme,
  onCellUpdate,
  onCellDelete,
  onAsk,
}: CellViewProps) {
  useLocale();
  const [showCode, setShowCode] = useState(false);
  const [hoveredDatum, setHoveredDatum] = useState<Record<string, unknown> | null>(null);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");

  const hasErrors = cell.result?.diagnostics?.some(
    (d) => d.severity === "error"
  );
  const hasData = cell.result && cell.result.data.length > 0;
  const emptyResult =
    cell.result && cell.result.row_count === 0 && !hasErrors;

  const displayTitle = cell.title || cell.question;

  const startEditing = () => {
    setTitleDraft(displayTitle);
    setEditingTitle(true);
  };

  const commitTitle = async () => {
    setEditingTitle(false);
    const newTitle = titleDraft.trim();
    if (newTitle === cell.question) {
      // Reset to default (empty title means use question)
      if (cell.title === "") return;
      try {
        await apiSend(`/api/cells/${cell.id}`, "PATCH", { title: "" });
        onCellUpdate({ ...cell, title: "" });
      } catch { /* ignore */ }
      return;
    }
    if (newTitle && newTitle !== cell.title) {
      try {
        await apiSend(`/api/cells/${cell.id}`, "PATCH", { title: newTitle });
        onCellUpdate({ ...cell, title: newTitle });
      } catch { /* ignore */ }
    }
  };

  const cancelEditing = () => {
    setEditingTitle(false);
  };

  const handleTitleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      commitTitle();
    } else if (e.key === "Escape") {
      cancelEditing();
    }
  };

  const isExplanation = cell.cell_type === "explanation";
  const refusal = cell.refusal;

  return (
    <div className={`cell ${isExplanation ? "cell--explanation" : ""}`}>
      {/* Cell body */}
      <div className="cell-body">
        {/* Title header */}
        <div className="cell__header">
          {editingTitle ? (
            <input
              autoFocus
              onFocus={(e) => e.currentTarget.select()}
              className="cell__title-input"
              value={titleDraft}
              onChange={(e) => setTitleDraft(e.target.value)}
              onBlur={commitTitle}
              onKeyDown={handleTitleKeyDown}
            />
          ) : (
            <h3
              className="cell__question"
              onDoubleClick={startEditing}
              title="Double-click to edit title"
            >
              {displayTitle}
            </h3>
          )}
          {cell.sql?.edited_by_user && (
            <span className="cell__badge">{t("cell.edited")}</span>
          )}
          <button
            className="cell__delete-btn"
            onClick={() => onCellDelete(cell.id)}
            aria-label="Remove cell"
          >
            &times;
          </button>
        </div>

        {/* Refused: a recognised "no answer" state — not an error */}
        {refusal && (
          <div className="cell-refusal">
            <div className="cell-refusal__status">
              {t(
                refusal.category === "unsupported_question"
                  ? "refusal.unsupported"
                  : refusal.category === "access_denied"
                    ? "refusal.access_denied"
                    : "refusal.insufficient"
              )}
            </div>
            <p className="cell-refusal__detail">{refusal.reason.detail}</p>
            {refusal.reason.suggestion && (
              <button
                className="cell-refusal__suggestion"
                onClick={() => onAsk(refusal.reason.suggestion!)}
              >
                {refusal.reason.suggestion}
              </button>
            )}
          </div>
        )}

        {/* Analysis-only: error, empty, chart */}
        {!isExplanation && hasErrors && (
          <div className="error-banner">
            <div className="error-banner__content">
              {cell.result?.diagnostics
                ?.filter((d) => d.severity === "error")
                .map((d, i) => (
                  <div key={i}>
                    {d.message}
                    {d.hint && (
                      <span className="error-banner__hint">Hint: {d.hint}</span>
                    )}
                  </div>
                ))}
            </div>
          </div>
        )}

        {!isExplanation && emptyResult && (
          <div className="cell__empty-results">
            Query returned no results. Try broadening your filters.
          </div>
        )}

        {!isExplanation && cell.chart && hasData && (
          <div className="cell__chart">
            <Suspense fallback={<div className="chart-container" />}>
              <ChartRenderer
                spec={cell.chart.spec}
                data={cell.result!.data}
                theme={theme}
                onHoverData={setHoveredDatum}
              />
            </Suspense>
          </div>
        )}

        {/* Narrative */}
        {cell.narrative && (
          <div className="cell-insight">
            <NarrativeView
              text={cell.narrative.text}
              dataReferences={cell.narrative.data_references}
              highlightedDatum={hoveredDatum}
            />
          </div>
        )}

      </div>

      {/* Footer strip (analysis only) */}
      {!isExplanation && cell.sql && (
        <div className="cell-footer">
          <div className="cell-footer-left">
            <button
              className="cell-link"
              onClick={() => setShowCode(!showCode)}
            >
              <span className={`arrow ${showCode ? "open" : ""}`}>&#9656;</span>
              {showCode ? "Hide code" : t("cell.code")}
            </button>
          </div>
          <div className="cell-meta-strip">
            {cell.result && (
              <>
                <span>{cell.result.row_count} {t("cell.rows")}</span>
                <span className="sep" />
                <span>{cell.result.execution_time_ms}ms</span>
              </>
            )}
            {cell.metadata.model && (
              <>
                {cell.result && <span className="sep" />}
                <span>{cell.metadata.model}</span>
              </>
            )}
          </div>
          <FeedbackControls cellId={cell.id} />
        </div>
      )}

      {/* Footer strip (refused cells) — model + feedback; over-refusal is
          exactly the failure mode we want users to flag */}
      {refusal && (
        <div className="cell-footer">
          <div className="cell-footer-left" />
          <div className="cell-meta-strip">
            {cell.metadata.model && <span>{cell.metadata.model}</span>}
          </div>
          <FeedbackControls cellId={cell.id} />
        </div>
      )}

      {/* Code drawer (analysis only) — mounted only when open, so a closed
          drawer costs nothing; keyed by the SQL so an updated cell resets it. */}
      {!isExplanation && cell.sql && (
        <div className={`code-drawer ${showCode ? "open" : ""}`}>
          {showCode && (
            <CodeView key={cell.sql.query} cell={cell} onCellUpdate={onCellUpdate} />
          )}
        </div>
      )}
    </div>
  );
});
