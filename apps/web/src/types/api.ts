/** Response shapes of the startup endpoints (`/api/healthz`, `/api/theme`,
 * `/api/suggestions`). The cell shapes live in `cell.ts`. */

export interface HealthCheck {
  name: string;
  ok: boolean;
  detail: string;
}

export interface HealthData {
  status: "ok" | "degraded" | "down";
  project: string | null;
  checks: HealthCheck[];
}

export interface ThemeData {
  app_name: string;
  locale: string;
  logo_path: string | null;
  custom_css: string | null;
  css_vars: Record<string, string>;
}

export interface SuggestionsData {
  suggestions: string[];
  generating: boolean;
}
