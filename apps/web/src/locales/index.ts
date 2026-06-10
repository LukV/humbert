import en from "./en.json";
import nl from "./nl.json";

const locales: Record<string, Record<string, string>> = { en, nl };

let currentLocale = "en";

export function setLocale(locale: string) {
  currentLocale = locale in locales ? locale : "en";
}

/** Return the active locale tag in BCP-47 form, suitable for Intl APIs
 * (number/date formatting). Maps Lumen's short codes onto canonical tags. */
export function getLocaleTag(): string {
  return currentLocale === "nl" ? "nl-NL" : "en-US";
}

/**
 * Look up a translation by key. Optional `params` substitute `{name}`
 * placeholders in the resolved string (`t("pack.ghost.description.one",
 * { n: 3 })` substitutes `{n}` with `3`). Falls through to English, then
 * the raw key if nothing matches.
 */
export function t(key: string, params?: Record<string, string | number>): string {
  const raw = locales[currentLocale]?.[key] ?? locales.en[key] ?? key;
  if (!params) return raw;
  return raw.replace(/\{(\w+)\}/g, (_, name: string) =>
    name in params ? String(params[name]) : `{${name}}`,
  );
}
