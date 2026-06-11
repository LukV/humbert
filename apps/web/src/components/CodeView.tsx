import { useState } from "react";
import type { Cell, RunSQLRequest } from "../types/cell";
import { apiSend } from "../utils/api";
import { t } from "../locales";
import { consumeSSE } from "../utils/sse";
import { FEATURES } from "../config";
import StageIndicator from "./StageIndicator";

type Tab = "sql" | "chart" | "reasoning";

interface CodeViewProps {
  cell: Cell;
  onCellUpdate: (updated: Cell) => void;
}

export default function CodeView({ cell, onCellUpdate }: CodeViewProps) {
  const [activeTab, setActiveTab] = useState<Tab>("sql");
  const [editedSql, setEditedSql] = useState(cell.sql?.query ?? "");
  const [isRunning, setIsRunning] = useState(false);
  const [runStage, setRunStage] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  const sqlChanged = editedSql.trim() !== (cell.sql?.query ?? "").trim();

  const handleRun = async () => {
    if (!sqlChanged || isRunning) return;
    setIsRunning(true);
    setRunError(null);
    setRunStage("thinking");

    try {
      const body: RunSQLRequest = { cell_id: cell.id, sql: editedSql };
      const response = await apiSend("/api/run-sql", "POST", body);

      if (!response.ok) throw new Error(`Server error: ${response.status}`);

      await consumeSSE(response, {
        onStage: (stage) => setRunStage(stage),
        onCell: (data) => {
          onCellUpdate(data as Cell);
          setRunStage(null);
        },
        onError: (message) => {
          setRunError(message);
          setRunStage(null);
        },
      });
    } catch (err) {
      setRunError(err instanceof Error ? err.message : "Unknown error");
      setRunStage(null);
    } finally {
      setIsRunning(false);
    }
  };

  const tabs: { key: Tab; label: string }[] = [
    { key: "sql", label: t("code.sql") },
    { key: "chart", label: t("code.chart") },
    { key: "reasoning", label: t("code.reasoning") },
  ];

  return (
    <div className="code-block">
      {/* Tab bar */}
      <div className="code-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`code-tab ${activeTab === tab.key ? "active" : ""}`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "sql" &&
        (FEATURES.sqlEdit ? (
          <div>
            <textarea
              value={editedSql}
              onChange={(e) => setEditedSql(e.target.value)}
              disabled={isRunning}
              className="code-textarea"
            />
            <div className="code-actions">
              <button
                onClick={handleRun}
                disabled={!sqlChanged || isRunning}
                className="btn-code-action primary"
              >
                {t("code.run")}
              </button>
              {runStage && <StageIndicator stage={runStage} />}
              {runError && <span className="code-run-error">{runError}</span>}
            </div>
          </div>
        ) : (
          // SQL editing is behind a feature flag until the backend's /api/run-sql
          // (the Refinement pitch) lands — show the compiled query read-only.
          <div className="code-content">{cell.sql?.query ?? "No SQL"}</div>
        ))}

      {activeTab === "chart" && (
        <div className="code-content">
          {cell.chart ? JSON.stringify(cell.chart.spec, null, 2) : "No chart spec"}
        </div>
      )}

      {activeTab === "reasoning" && (
        <div className="code-content code-content--reasoning">
          {cell.metadata.reasoning || "No reasoning available"}
        </div>
      )}
    </div>
  );
}
