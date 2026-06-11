import { Component, type ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { VegaLite } from "react-vega";

import { cssVar } from "../utils/cssVar";
import { getLocaleTag } from "../locales";

type Theme = "light" | "dark";

interface ChartRendererProps {
  spec: Record<string, unknown>;
  data: Record<string, unknown>[];
  theme: Theme;
  onHoverData?: (datum: Record<string, unknown> | null) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: string;
}

class ChartErrorBoundary extends Component<
  { children: ReactNode },
  ErrorBoundaryState
> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false, error: "" };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error: error.message };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="chart-error">
          Chart rendering error: {this.state.error}
        </div>
      );
    }
    return this.props.children;
  }
}

// Light → dark color remapping for chart-emitted literal hexes. Vega specs
// occasionally encode palette colors inline (e.g. `value: "#4A2D4F"` in a
// layered chart). Keep the literal map: these are *data* values, not theme
// tokens, and remapping by CSS var would require a structural change in how
// charts are authored.
const DARK_COLOR_MAP: Record<string, string> = {
  "#4A2D4F": "#9B7BA0",
  "#C2876E": "#D4A08A",
  "#6B8F8A": "#7FABA5",
  "#B8A44C": "#D4C46E",
  "#8C7B6B": "#A99888",
  "#A3667E": "#C08A9E",
};

// The dark-mode fallback for the built-in skin: the default series palette,
// lightened for the dark background. A custom skin supplies its own via
// `--chart-palette` (see `categoryRange`).
const DARK_PALETTE = ["#9B7BA0", "#D4A08A", "#7FABA5", "#D4C46E", "#A99888", "#C08A9E"];

// The `--chart-palette` value the backend emits for the built-in skin
// (humbert.theme.theme_to_css_vars of the defaults). When the active skin's
// palette equals this, we leave the hand-tuned per-mode defaults in place — the
// spec's own series colors in light, DARK_PALETTE in dark — so the default look
// is unchanged. Keep in sync with humbert/theme.py's ThemeColors defaults.
const DEFAULT_CHART_PALETTE = "#4A2D4F,#C2876E,#6B8F8A,#B8A44C,#8C7B6B,#A3667E";

/** The active skin's chart palette from `--chart-palette`, or null when it's the
 * built-in default (so the tuned per-mode palettes stand). */
function customPalette(): string[] | null {
  const raw = cssVar("--chart-palette", "");
  if (!raw || raw === DEFAULT_CHART_PALETTE) return null;
  return raw.split(",").map((c) => c.trim()).filter(Boolean);
}

/** The category color range to inject, or [] to leave the spec's colors alone.
 * The default skin keeps its defaults; a custom skin overrides both modes — in
 * dark, known default colors are remapped for contrast and brand colors pass
 * through (the skin author owns dark-mode legibility). */
function categoryRange(theme: Theme): string[] {
  const custom = customPalette();
  if (theme === "dark") {
    return (custom ?? DARK_PALETTE).map((c) => DARK_COLOR_MAP[c.toUpperCase()] ?? c);
  }
  return custom ?? [];
}

/** Merge a category color range into a spec's Vega-Lite config. */
function withCategoryRange(
  spec: Record<string, unknown>,
  category: string[],
): Record<string, unknown> {
  const s = { ...spec };
  const config = { ...(s.config as Record<string, unknown> ?? {}) };
  config.range = { ...(config.range as Record<string, unknown> ?? {}), category };
  s.config = config;
  return s;
}

// Axis/legend/title overrides read live from CSS so they track theme tokens
// instead of duplicating them. Vega-Lite has its own theme system separate
// from CSS, so we still inject these values into the spec — but they come
// from the same source of truth as the rest of the UI.
function darkAxisOverrides() {
  return {
    gridColor: cssVar("--border", "rgba(232,229,223,0.08)"),
    domainColor: cssVar("--border-strong", "#4A4843"),
    tickColor: cssVar("--border-strong", "#4A4843"),
    labelColor: cssVar("--text-secondary", "#9A9590"),
    titleColor: cssVar("--text-secondary", "#9A9590"),
  };
}

function darkLegendOverrides() {
  return {
    labelColor: cssVar("--text-secondary", "#9A9590"),
    titleColor: cssVar("--text-secondary", "#9A9590"),
  };
}

function darkTitleOverrides() {
  return {
    color: cssVar("--text-primary", "#E8E5DF"),
  };
}

/** Remap hardcoded color values in encoding objects for dark mode. */
function remapEncoding(encoding: Record<string, unknown>): Record<string, unknown> {
  const result = { ...encoding };
  for (const [key, val] of Object.entries(result)) {
    if (val && typeof val === "object" && !Array.isArray(val)) {
      const enc = val as Record<string, unknown>;
      if (typeof enc.value === "string" && enc.value in DARK_COLOR_MAP) {
        result[key] = { ...enc, value: DARK_COLOR_MAP[enc.value] };
      }
    }
  }
  return result;
}

/** Deep-merge dark-mode config overrides into a Vega-Lite spec. */
function applyDarkTheme(spec: Record<string, unknown>): Record<string, unknown> {
  const s = { ...spec };

  // Merge config overrides
  const config = { ...(s.config as Record<string, unknown> ?? {}) };
  const axis = { ...(config.axis as Record<string, unknown> ?? {}), ...darkAxisOverrides() };
  const legend = { ...(config.legend as Record<string, unknown> ?? {}), ...darkLegendOverrides() };
  const title = { ...(config.title as Record<string, unknown> ?? {}), ...darkTitleOverrides() };
  config.axis = axis;
  config.legend = legend;
  config.title = title;
  s.config = config;

  // Remap hardcoded color values in top-level encoding
  if (s.encoding && typeof s.encoding === "object") {
    s.encoding = remapEncoding(s.encoding as Record<string, unknown>);
  }

  // Remap in layers
  if (Array.isArray(s.layer)) {
    s.layer = (s.layer as Record<string, unknown>[]).map((layer) => {
      if (layer.encoding && typeof layer.encoding === "object") {
        return { ...layer, encoding: remapEncoding(layer.encoding as Record<string, unknown>) };
      }
      return layer;
    });
  }

  return s;
}

/** A single-value answer ("one big number", §6) — a text mark with no x/y.
 * Returns the numeric value when the spec is that shape, else null. */
function bigNumberValue(
  spec: Record<string, unknown>,
  data: Record<string, unknown>[],
): number | null {
  const enc = spec.encoding as Record<string, { field?: string }> | undefined;
  if (!enc || !enc.text || enc.x || enc.y) return null;
  const field = enc.text.field;
  if (!field) return null;
  const rows = data.length ? data : ((spec.data as { values?: Record<string, unknown>[] })?.values ?? []);
  const value = rows[0]?.[field];
  return typeof value === "number" ? value : null;
}

export default function ChartRenderer({
  spec,
  data,
  theme,
  onHoverData,
}: ChartRendererProps) {
  // A single big number is typography, not a chart — render it as styled,
  // locale-formatted HTML (§4/§6) rather than a Vega text mark on a canvas.
  const bigNumber = useMemo(() => bigNumberValue(spec, data), [spec, data]);
  const [renderError, setRenderError] = useState(false);

  // Hover-linking is only wired for single-view specs. A point selection on a
  // layered spec (our bar = bar + labels, the multi-line) compiles into every
  // layer and Vega throws "Duplicate signal name"; and a dangling signalListener
  // for a signal the spec never declares throws too. So the param and the
  // listener must be gated by exactly the same condition.
  const hoverEnabled = !!onHoverData && !Array.isArray(spec.layer);

  // Inject data, hover selection, and theme overrides into spec. Humbert's
  // chart specs already carry their own (capped, number-coerced) data, so only
  // inject the result rows when the spec doesn't bring its own.
  const fullSpec = useMemo(() => {
    let s: Record<string, unknown> = spec.data
      ? { ...spec }
      : { ...spec, data: { values: data } };

    // Apply dark theme overrides
    if (theme === "dark") {
      s = applyDarkTheme(s);
    }

    // The active skin's palette drives the category color range. A no-op for the
    // default skin (its tuned per-mode palettes stand); a custom skin overrides.
    const category = categoryRange(theme);
    if (category.length) {
      s = withCategoryRange(s, category);
    }

    if (hoverEnabled) {
      const existingParams = (s.params as unknown[]) ?? [];
      s.params = [
        ...existingParams,
        {
          name: "hover",
          select: { type: "point", on: "pointerover", clear: "pointerout" },
        },
      ];
    }
    return s;
  }, [spec, data, theme, hoverEnabled]);

  // A fresh spec gets a fresh chance to render.
  useEffect(() => setRenderError(false), [fullSpec]);

  const handleHoverSignal = useCallback(
    (_name: string, value: unknown) => {
      if (!onHoverData) return;
      // Vega selection signal value is an object with the selected datum fields
      if (value && typeof value === "object" && !Array.isArray(value)) {
        const obj = value as Record<string, unknown>;
        // Empty object means no selection (pointerout)
        if (Object.keys(obj).length === 0) {
          onHoverData(null);
        } else {
          onHoverData(obj);
        }
      } else {
        onHoverData(null);
      }
    },
    [onHoverData]
  );

  const signalListeners = useMemo(() => {
    if (!hoverEnabled) return undefined;
    return { hover: handleHoverSignal };
  }, [hoverEnabled, handleHoverSignal]);

  if (bigNumber !== null) {
    return (
      <div className="big-number">
        {new Intl.NumberFormat(getLocaleTag()).format(bigNumber)}
      </div>
    );
  }

  // If Vega can't render this spec, fall back silently — the narrative below
  // carries the figures (§7), so a chart failure is never a dead end.
  if (renderError) return null;

  return (
    <ChartErrorBoundary>
      <div className="chart-container">
        <VegaLite
          spec={fullSpec as never}
          actions={false}
          style={{ width: "100%" }}
          signalListeners={signalListeners}
          onError={(err) => {
            console.warn("[chart] render failed:", err);
            setRenderError(true);
          }}
        />
      </div>
    </ChartErrorBoundary>
  );
}
