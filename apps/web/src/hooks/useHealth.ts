import { useEffect, useRef, useState } from "react";
import type { HealthData } from "../types/api";
import { apiGet } from "../utils/api";
import { t } from "../locales";

/** Backend health: one fetch on mount (with retry, riding out the race between
 * `humbert start` opening the browser and uvicorn binding), then polling.
 *
 * `setConnectionError` is shared with the other startup fetches so any of them
 * can raise or clear the banner.
 */
export function useHealth() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  // Read inside setInterval to avoid recreating the timer every time the
  // banner toggles. Mirrors `connectionError` state.
  const connectionErrorRef = useRef<string | null>(null);
  connectionErrorRef.current = connectionError;

  useEffect(() => {
    apiGet<HealthData>("/api/healthz", { retry: true })
      .then((data) => {
        setHealth(data);
        if (data.status === "ok") setConnectionError(null);
      })
      .catch(() => {
        setHealth(null);
        setConnectionError(t("connection.error"));
      });
  }, []);

  // Health polling — fast (2s) while disconnected so the banner clears
  // quickly once the server is up; slow (30s) on the steady-state path.
  // Reads `connectionError` via ref so banner-toggle doesn't recreate the
  // timer; cadence is picked when the timer starts.
  useEffect(() => {
    const intervalMs = connectionError ? 2_000 : 30_000;
    const interval = setInterval(() => {
      apiGet<HealthData>("/api/healthz")
        .then((data) => {
          setHealth(data);
          if (data.status === "ok" && connectionErrorRef.current) {
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

  return { health, connectionError, setConnectionError };
}
