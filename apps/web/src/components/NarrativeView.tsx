import { useEffect, useMemo, useRef } from "react";
import { marked } from "marked";
import DOMPurify from "dompurify";
import type { DataReference } from "../types/cell";

// Configure marked for inline use: no <p> wrapping. The output is sanitized
// before injection — the narrative is LLM prose over user-loaded data, so a
// hostile string in the data could otherwise become markup in our origin.
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

/** Wrap every figure in a span carrying its digits, so the numbers read as the
 * substance (§4) and can be linked to the chart on hover. Runs on the parsed
 * HTML's text nodes — running it on the raw markdown would corrupt numeric
 * syntax (the `1` in an ordered list, digits inside code spans or URLs). */
function emphasizeFigures(html: string): string {
  const template = document.createElement("template");
  template.innerHTML = html;
  const walker = document.createTreeWalker(template.content, NodeFilter.SHOW_TEXT, {
    acceptNode: (node) =>
      node.parentElement?.closest("code, pre, a")
        ? NodeFilter.FILTER_REJECT
        : NodeFilter.FILTER_ACCEPT,
  });
  const textNodes: Text[] = [];
  let current: Node | null;
  while ((current = walker.nextNode())) textNodes.push(current as Text);

  for (const node of textNodes) {
    const text = node.nodeValue ?? "";
    const matches = [...text.matchAll(NUMBER)];
    if (!matches.length) continue;
    const fragment = document.createDocumentFragment();
    let last = 0;
    for (const match of matches) {
      const start = match.index;
      if (start > last) fragment.append(text.slice(last, start));
      const span = document.createElement("span");
      span.className = "narrative__num";
      span.dataset.value = digits(match[0]);
      span.textContent = match[0];
      fragment.append(span);
      last = start + match[0].length;
    }
    if (last < text.length) fragment.append(text.slice(last));
    node.replaceWith(fragment);
  }
  return template.innerHTML;
}

export default function NarrativeView({ text, highlightedDatum }: NarrativeViewProps) {
  const ref = useRef<HTMLDivElement>(null);
  const html = useMemo(
    () => emphasizeFigures(DOMPurify.sanitize(marked.parse(text) as string)),
    [text],
  );

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
