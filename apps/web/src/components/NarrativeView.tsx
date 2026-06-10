import { useEffect, useMemo, useRef } from "react";
import { marked } from "marked";
import type { DataReference } from "../types/cell";

// Configure marked for inline use: no <p> wrapping, no sanitization needed (trusted LLM output)
marked.use({ breaks: true });

interface NarrativeViewProps {
  text: string;
  // Kept for API compatibility; Humbert links figures by value, not by ref.
  dataReferences: DataReference[];
  highlightedDatum?: Record<string, unknown> | null;
}

const NUMBER = /\d[\d.,]*\d|\d/g;

/** Strip a value down to its digits, so "12.345", "12,345" and 12345 all match. */
function digits(value: unknown): string {
  return String(value ?? "").replace(/\D/g, "");
}

/** Wrap every figure in the narrative in a span carrying its digits, so the
 * numbers read as the substance (§4) and can be linked to the chart on hover. */
function emphasizeFigures(text: string): string {
  return text.replace(
    NUMBER,
    (match) => `<span class="narrative__num" data-value="${digits(match)}">${match}</span>`,
  );
}

export default function NarrativeView({ text, highlightedDatum }: NarrativeViewProps) {
  const ref = useRef<HTMLDivElement>(null);
  const html = useMemo(() => marked.parse(emphasizeFigures(text)) as string, [text]);

  // The link between text and chart: when a chart point is hovered, light up the
  // matching figure(s) in the prose. Done imperatively because the narrative is
  // rendered as HTML (markdown), not a React tree.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const live = highlightedDatum
      ? new Set(Object.values(highlightedDatum).map(digits).filter(Boolean))
      : new Set<string>();
    el.querySelectorAll<HTMLElement>(".narrative__num").forEach((span) => {
      const value = span.dataset.value ?? "";
      span.classList.toggle("narrative__num--active", value !== "" && live.has(value));
    });
  }, [highlightedDatum, html]);

  if (!text) return null;

  return (
    <div
      ref={ref}
      className="narrative narrative--markdown"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
