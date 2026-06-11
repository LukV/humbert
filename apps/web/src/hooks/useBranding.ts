import { useEffect, useState } from "react";
import type { ThemeData } from "../types/api";
import { apiGet } from "../utils/api";
import { setLocale, t, useLocale } from "../locales";

function applyThemeCss(data: ThemeData): void {
  if (data.custom_css) {
    // Idempotent by id — StrictMode runs mount effects twice in dev.
    const id = "humbert-theme-css";
    if (!document.getElementById(id)) {
      const link = document.createElement("link");
      link.id = id;
      link.rel = "stylesheet";
      link.href = data.custom_css;
      document.head.appendChild(link);
    }
  }
  const root = document.documentElement;
  for (const [key, value] of Object.entries(data.css_vars)) {
    root.style.setProperty(key, value);
  }
}

/** Load `/api/theme` — app name, locale, skin CSS variables — and subscribe the
 * caller to locale changes, so the UI re-renders into the configured language
 * even when nothing else about the response differs from the defaults. */
export function useBranding(onConnectionError: (message: string | null) => void): string {
  useLocale();
  const [appName, setAppName] = useState("Humbert");

  useEffect(() => {
    apiGet<ThemeData>("/api/theme", { retry: true })
      .then((data) => {
        setAppName(data.app_name);
        setLocale(data.locale);
        applyThemeCss(data);
        onConnectionError(null);
      })
      .catch(() => onConnectionError(t("connection.error")));
  }, [onConnectionError]);

  return appName;
}
