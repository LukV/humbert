# Design language

Concrete visual and interaction rules for Humbert. Where [[003-design-pillars]] sets intent, this doc sets the rules that intent becomes — the things a designer or an LLM can check a screen against. Rules are marked **hard** (do not break without changing this doc) or **open** (a decision still owed, listed again at the end).

Influences, stated plainly so the trade-offs are visible: Tufte (data-ink, words and numbers as one object), accessibility as a floor rather than a finish, Dutch functionalism (grid discipline, typography as structure, plain language, dry wit), and calm that comes from space and restraint rather than from low contrast or a tinted page.

## 1. Epistemic honesty is a visual rule

This sits first because it is the product. **Hard: an uncertain number must never look as confident as a certain one.** Presentation degrades as confidence drops, and that gradient is a design commitment, not only orchestration logic (see [[009-orchestration]]):

- **High** — answer plainly. No caveat furniture. The narrative carries it.
- **Medium** — surface the load-bearing assumption inline and make it correctable (the synonym read: "we read *opkomst* as **bezoeken**", with accept / correct). Accepting raises the score.
- **Low** — a visible caveat, or one clarifying question before answering.
- **Floor** — a refusal, rendered as a calm first-class card, never an error state.

A refusal is a designed output. It states what cannot be answered and why, and offers what is nearby and runnable. It is neutral in tone and colour — see the colour contract.

## 2. Progressive disclosure

**Hard: at rest, a cell is its question, its narrative, and its figure. Nothing else.** Everything else — the query, provenance detail, export, validate, delete — is reached for, not shown. Tools appear on hover; the query unfolds from a quiet affordance; the metadata is one low line. The focus is always the narrative and the figure.

This scales to the notebook itself: a cell collapses to its one-sentence narrative, so a long notebook reads as a scannable column of sentences in serif, and the reader expands only what they care about. An outline rail handles jump-and-orient at length.

## 3. One atom, many views

**Hard: the cell is the only unit; everything else is a view over an ordered list of cells.** The notebook (work view) and the brief (read view) are the same list, filtered and restyled. A number, together with its provenance, looks identical everywhere it appears. Validation, certainty, and lineage live on the atom, so they cannot drift between views.

## 4. Typography

Three registers, each with one job:

- **Source Serif 4** — the narrative, and all read-view prose. The narrative is set in serif because it is a reply, not a readout. This is the single most important visual decision in the product; it is also, for free, the chart's text alternative (see §7).
- **DM Sans** — UI, labels, metadata, eyebrows.
- **JetBrains Mono** — SQL, parameters, snapshot ids.

**Hard: numbers are formatted Dutch** — `1.240`, `48.210`, `0,8 s`. **Hard: no meaningful text below 12px.** Weights are limited to 400 and 500; emphasis is weight or italic, never all-caps shouting (small eyebrow caps excepted, and only as quiet labels).

## 5. Colour — the semantic contract

**Hard. Colour always means the same thing. A colour may not be borrowed for decoration.**

- **Aubergine** (`#4A2D4F` light / lighter in dark) = validation and trust, and nothing else. It appears on the validated stamp and the per-brief provenance mark. Its scarcity is what makes "signed" legible.
- **Amber** = caution. Medium / low certainty, the correctable assumption chip.
- **Neutral (warm grey / ink)** = refusal and absence of an answer. A refusal is calm, not alarmed.
- **Series colours** (FT/Observable muted set) carry data only, and **never include the accent** — if bars were aubergine, "signed" would stop meaning anything.
- **Red is used for nothing.** Wrong is not a state Humbert renders; uncertainty is amber, refusal is neutral, and errors are rare and quiet.

## 6. Charts — Tufte, with a threshold for the camembert

Maximise data-ink. **Hard: no chart borders, no fill backgrounds, no gridlines unless they earn their place; direct labelling over legends; a single baseline over a full axis box.** Beautiful defaults: the first chart must look composed with zero configuration.

Chart type follows the shape of the answer, not a picker:

- single value → one big number
- part-to-whole, **2–3 categories → camembert (pie)** — at low cardinality a pie reads "share of a whole" faster than a bar; this is on merit, the name is just the wink
- part-to-whole, **4+ categories → sorted bar** (or stacked bar if the total also matters)
- comparison across categories → sorted horizontal bar
- trend over time → line
- comparison across a dimension (gemeente, year) → **small multiples** of one small chart, never one busy combined chart
- no clear shape, or a single fact → **no chart**; the narrative stands alone

At notebook scale, a collapsed cell may carry an inline **sparkline** beside its sentence, so the scan carries shape and not only text (Tufte's dataword).

## 7. Accessibility is a floor, not a finish

This is where "calm, not creamy" actually bites: **muted-for-calm and load-bearing are mutually exclusive.** If text means something, it clears contrast; if it is truly decorative (a hairline, an inactive dot), it may be faint.

**Hard rules:**

- Body and any load-bearing label: contrast ≥ **4.5:1**. (The current tertiary ink `#A39B90` on paper fails this — fine for hairlines and dots, not for metadata anyone needs to read.)
- Large text (≥18px) and graphical/UI objects: ≥ **3:1**.
- **Never encode meaning in colour alone.** The certainty dot needs a shape or letter alongside it; the series palette needs direct labels, not colour-keyed legends.
- Minimum meaningful type size 12px (§4).
- Visible focus rings; full keyboard paths for chips, toggles, expand/collapse.
- Respect `prefers-reduced-motion`, including the collapse-on-new-answer behaviour.

**The serif narrative is the chart's text alternative.** A screen reader receives "48.210 jongeren, 9% meer dan in 2024" as a real sentence, not "chart, four bars." Most tools bolt this on; Humbert gets it from its core shape, and it must never be dropped.

## 8. Dutch design influence

Three concrete things, plus a fourth on voice:

- **Grid discipline.** A real baseline and column grid sits under the editorial calm — Crouwel-rational, not loose. Calm is structured, not vague.
- **Typography as structure.** Hierarchy is carried by type and space, not by boxes, rules, or card chrome. Cells are borderless, separated by whitespace and a hairline.
- **Plain language.** Short, active, direct, no hype — the throughline of the NL Design System and the [[006-honest-uncertainty]] tone. The interface explains; it does not sell.
- **Dry wit lives in naming and defaults, not in copy.** The DuckDB principle: a serious tool can have a light name. "Camembert" and the like are allowed as names and as well-chosen defaults; the interface voice itself never jokes.

## 9. Motion restraint

**Hard: motion is minimal, purposeful, and reduced-motion-aware.** Transitions clarify a change (a drawer opening, a cell collapsing); nothing moves for delight alone. Calm extends to how things move.

## 10. Durable, plain artifacts

A brief is static HTML: printable, archivable, no lock-in, permalink = file path. **Hard: a brief ships with a real print stylesheet** — Tufte and Dutch functionalism agree that a thing worth publishing is worth printing well. Versions are plain (`v2` → `v3` on a new snapshot); access is where you put the file.

## Open questions

1. **Warm vs de-creamed paper — open.** The current palette is warm (paper `#FBFAF7`, warm greys). The concern is over-creaming: warmth washed across the whole surface rather than reserved for the accent. The candidate is a near-neutral paper (~`#F8F8F6`) with inks carrying only a faint warm cast, and warmth reserved for the aubergine accent plus at most one warm neutral. **This is decided by overall aesthetic consistency, not by fiat — resolve via a side-by-side, judging which holds together with the serif, the accent, and the chart palette across cell / notebook / brief.** Whatever wins must still pass §7.
2. **Provenance placement** (from [[002-product-forms]]) — per-brief single stamp (calm, assumes one signer + one snapshot) vs per-figure (honest when a brief mixes snapshots). Currently leaning per-brief with per-figure fallback.
3. **Question placement in the brief** — quiet caption under each figure (current) vs an appendix for heavily-cited notas.

## Settled here

- Camembert is a rule with a threshold (2–3 slices), not an exception to rigour, and not only a joke.
- Colour is a fixed semantic contract (§5); red carries nothing.
- Muted is allowed only where nothing load-bearing depends on it (§7).
