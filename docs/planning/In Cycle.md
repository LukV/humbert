---
project: humbert
type: planning-index
status: active
updated: 2026-06-10
current_pitch: none
---
# In Cycle

What's being built right now. Usually one pitch. Occasionally two, if they're small and unrelated.

## Currently

*Nothing in cycle yet.*

See [[#On deck]] for the next pickup.

## On deck

After Beautiful defaults, block 2 continues with **Refinement** and **Validation**; **Tier 2 — governed fallback** stays parked. See [[blocks/02-notebook-and-orchestration]].

## How a pitch enters and leaves this page

**Enters** — when work actually starts. Run skill `start-pitch`, which:

1. Updates the pitch note frontmatter (or adds one from [[pitches/_template]]): `status: in-cycle`, `started: YYYY-MM-DD`.
2. Replaces the "Currently" section above with the pitch summary (see template below).

**Leaves** — when it ships, runs past its cut line, or is dropped. Run skill `ship-pitch`, which:

1. Updates the pitch frontmatter: `status: shipped | dropped`, `ended: YYYY-MM-DD`.
2. Fills in the "What actually happened" section at the bottom of the pitch.
3. Moves the file to `pitches/shipped/` (dropped pitches stay in `pitches/`).
4. Clears this page back to "Nothing in cycle yet" or picks the next one.
5. On ship (not drop): release via the repo's `CHANGELOG` flow.

## When a pitch is in cycle, the section looks like this

```
## Currently

### [[pitches/some-pitch]] — chunky

Started 2026-06-08.

One paragraph reminding the reader what this is and what the cut line is.

**Cut line:** the smallest version still worth shipping — written at the start.

**Status notes** *(optional, short, dated):*
- 2026-06-08 — started. Connection shape decided.
```

Status notes are not a daily log. They record *judgment calls* — moments where direction shifted or a risk surfaced. The kind of thing future-you would want to find later.
