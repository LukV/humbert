import { useSyncExternalStore } from "react";
import en from "./en.json";
import nl from "./nl.json";

const locales: Record<string, Record<string, string>> = { en, nl };

// The locale lives in module state so `t()` stays a plain function, but React
// can't see module state — components that render translated strings subscribe
// via `useLocale()` so a locale change (the /api/theme response) re-renders them.
let currentLocale = "en";
let version = 0;
const listeners = new Set<() => void>();

export function setLocale(locale: string) {
  const next = locale in locales ? locale : "en";
  if (next === currentLocale) return;
  currentLocale = next;
  version += 1;
  listeners.forEach((notify) => notify());
}

/** Subscribe this component to locale changes. Returns a value that changes
 * with the locale so `useSyncExternalStore` triggers a re-render. */
export function useLocale(): number {
  return useSyncExternalStore(subscribe, () => version);
}

function subscribe(notify: () => void): () => void {
  listeners.add(notify);
  return () => listeners.delete(notify);
}

/** Return the active locale tag in BCP-47 form, suitable for Intl APIs
 * (number/date formatting). */
export function getLocaleTag(): string {
  return currentLocale === "nl" ? "nl-NL" : "en-US";
}

/**
 * Look up a translation by key. Optional `params` substitute `{name}`
 * placeholders in the resolved string. Falls through to English, then the
 * raw key if nothing matches.
 */
export function t(key: string, params?: Record<string, string | number>): string {
  const raw = locales[currentLocale]?.[key] ?? locales.en[key] ?? key;
  if (!params) return raw;
  return raw.replace(/\{(\w+)\}/g, (_, name: string) =>
    name in params ? String(params[name]) : `{${name}}`,
  );
}
