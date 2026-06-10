/** Read a CSS custom property from the document root. SSR-safe — returns
 * `fallback` when `window` is undefined (e.g. SSR, vitest jsdom). Trims the
 * resolved string and returns `fallback` when the var is unset or empty.
 */
export function cssVar(name: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}
