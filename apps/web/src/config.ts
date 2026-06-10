// Same-origin: the SPA is served by the Python backend in production, and the
// Vite dev server proxies /api to it. An empty base keeps every request relative.
export const API_BASE = "";

// Feature flags for the parts of the Lumen frontend whose backend isn't built
// in Humbert yet. Flip these on as the matching backend pitches land.
export const FEATURES = {
  // The cytoscape pack / semantic-model browser (no /api/pack yet).
  pack: false,
  // Editing a cell's SQL and re-running it (no /api/run-sql yet — Refinement pitch).
  sqlEdit: false,
};
