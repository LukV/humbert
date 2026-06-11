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

interface ErrorBoundaryProps {
  spec: unknown;
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: string;
  spec: unknown;
}

class ChartErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: "", spec: props.spec };
  }

  // A new spec gets a fresh chance to render — without this, one crash
  // would blank the chart forever, even after a valid update arrives.
  static getDerivedStateFromProps(
    props: ErrorBoundaryProps,
    state: ErrorBoundaryState,
  ): Partial<ErrorBoundaryState> | null {
    if (props.spec !== state.spec) {
      return { spec: props.spec, hasError: false, error: "" };
    }
    return null;
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
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

// Marks that *carry data* — the ones a skin's palette recolors. Text marks
// (value labels, the big number) stay ink, never brand colour (§5/§7).
const DATA_MARKS = new Set(["line", "point", "bar", "area", "circle", "square"]);

/** The active skin's series colours, dark-adjusted, or null for the built-in
 * skin (whose §5-tuned `_SERIES` must stand, so we leave its specs alone). */
function skinSeries(theme: Theme): string[] | null {
  const custom = customPalette();
  if (!custom) return null;
  return theme === "dark"
    ? custom.map((c) => DARK_COLOR_MAP[c.toUpperCase()] ?? c)
    : custom;
}

/** Lighten `#rrggbb` toward white by `factor` (0–1) — mirrors the backend's
 * `_lighten_hex`, used to derive a ramp's light end from a brand colour. */
function lighten(hex: string, factor: number): string {
  const raw = hex.replace(/^#/, "");
  if (raw.length !== 6) return hex;
  const channels = [0, 2, 4].map((i) => parseInt(raw.slice(i, i + 2), 16));
  const out = channels.map((c) => Math.min(255, Math.round(c + (255 - c) * factor)));
  return "#" + out.map((c) => c.toString(16).padStart(2, "0")).join("");
}

/** Replace a hardcoded `scale.range` on a color encoding with the skin palette:
 * the full set for a categorical encoding, a light→brand ramp for a quantitative
 * one (the ranked-bar shading). Leaves encodings without a baked range alone. */
function recolorEncoding(
  encoding: Record<string, unknown>,
  palette: string[],
  ramp: string[],
): Record<string, unknown> {
  const color = encoding.color as Record<string, unknown> | undefined;
  if (!color || typeof color !== "object" || Array.isArray(color)) return encoding;
  const scale = color.scale as Record<string, unknown> | undefined;
  if (!scale || !Array.isArray(scale.range)) return encoding;
  const range = color.type === "quantitative" ? ramp : palette;
  return { ...encoding, color: { ...color, scale: { ...scale, range } } };
}

/** Repaint a single-colour data mark (line, scatter point) with the skin's
 * lead colour. Text marks and marks that colour via an encoding pass through. */
function recolorMark(mark: unknown, palette: string[]): unknown {
  if (!mark || typeof mark !== "object" || Array.isArray(mark)) return mark;
  const m = mark as Record<string, unknown>;
  if (typeof m.type === "string" && DATA_MARKS.has(m.type) && typeof m.color === "string") {
    return { ...m, color: palette[0] };
  }
  return mark;
}

/** Push a custom skin's palette into a spec's baked-in colours. The backend
 * authors charts in the default palette — explicit per-encoding `scale.range`s
 * and single mark colours that shadow `config.range.category` — so a custom
 * skin only reaches the marks here. A no-op for the built-in skin. */
function applySkinColors(
  spec: Record<string, unknown>,
  palette: string[],
): Record<string, unknown> {
  if (!palette.length) return spec;
  const ramp = [lighten(palette[0], 0.55), palette[0]];
  const s = { ...spec };
  if (s.mark) s.mark = recolorMark(s.mark, palette);
  if (s.encoding && typeof s.encoding === "object") {
    s.encoding = recolorEncoding(s.encoding as Record<string, unknown>, palette, ramp);
  }
  if (Array.isArray(s.layer)) {
    s.layer = (s.layer as Record<string, unknown>[]).map((layer) => {
      const l = { ...layer };
      if (l.mark) l.mark = recolorMark(l.mark, palette);
      if (l.encoding && typeof l.encoding === "object") {
        l.encoding = recolorEncoding(l.encoding as Record<string, unknown>, palette, ramp);
      }
      return l;
    });
  }
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

    // …and its baked-in series ranges and single mark colours, which the
    // category range alone can't reach. Custom skins only; default skin stands.
    const series = skinSeries(theme);
    if (series) {
      s = applySkinColors(s, series);
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
    <ChartErrorBoundary spec={fullSpec}>
      <div className="chart-container">
        <VegaLite
          // react-vega types want its own VisualizationSpec; our spec is a
          // plain Record built by the backend, so cast at this one boundary.
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
