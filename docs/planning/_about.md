---
project: humbert
type: planning-system
status: active
updated: 2026-06-07
---
# About this folder

The implementation plan for Humbert. **Self-contained.** Anything promised in the design notes ([[../product-design/001-problem-and-stakeholders]] through [[../product-design/010-design-language]]) but not yet built lives here as a pitch or a slot on a block.

Architecture and stack decisions are documented separately in [[../architecture/001-stack-decisions]]. Read that first if you're starting fresh — it explains *what* we're building with (Python backend, React/TypeScript/Tailwind frontend, dbt + MetricFlow, local-first), before this folder explains *what we're building, in what order*.

Modeled after the Lumen and Runtime planning surfaces — Shape Up with blocks as the top navigation, a pitch lifecycle, and no fixed cycles. Two deliberate departures: appetite no longer carries the scope (see [[#Scope, not appetite]]), and there's no Sequencing or Released note (the block order lives in [[Betting Table]]; the "what shipped" view is `pitches/shipped/`).

## Files

- [[Betting Table]] — index of blocks, in execution order. The top-level navigation.
- [[In Cycle]] — what's being built right now. Usually one pitch.
- `blocks/` — one note per block. Each block carries its framing, open design items, pitches, and dependencies.
- `pitches/` — one note per pitch that's been written up. `_template.md` is the starting point. `shipped/` is the record of what's done — the day-to-day release view. Most slots on a block note never need a full pitch file — the slot framing is enough.

## What's a pitch, what's not

A **pitch** is implementation work that benefits from being framed before being done. Problem, scope, sketch, cut line, risks. Sized so the dev team — Luk plus Claude Code — can hold the whole shape in their head and ship something coherent.

A pitch is **not**:

- A design decision still in motion. Those go back into the product-design notes or get logged as an open item inside the relevant block.
- A five-minute job (typo fix, copy tweak, colour adjustment). Just do them.
- A "feature idea" with no concrete shape. Either frame it as a pitch or leave it as an open design item.
- An architecture decision. Those live in [[../architecture/001-stack-decisions]].

## Pitch lifecycle

1. **Slot on a block note.** One line under a block. Not a pitch yet — a placeholder for one.
2. **Draft.** A note in `pitches/` with `status: draft`. Problem and cut line captured.
3. **Ready.** `status: ready`, linked from the block. Sketch concrete enough to start tomorrow.
4. **In cycle.** `status: in-cycle`. Listed on [[In Cycle]].
5. **Shipped.** `status: shipped`, moved to `pitches/shipped/`. `shipped_on:` date and a one-paragraph "what actually happened".
6. **Dropped.** `status: dropped`. Stays in `pitches/` with a note on *why*.

Write the pitch note when the slot's framing isn't enough to start, when the risks deserve explicit calling-out, or when the shape needs designing before building. Otherwise the block-level slot carries enough.

## Scope, not appetite

Under vibe coding, time-appetite stopped saying much — Claude Code can produce a week of old work in an evening, so a clock is the wrong cap. Humbert controls scope two ways instead:

- **Out of scope** — the binding control. Each pitch names what it will deliberately *not* do, so temptations stay out.
- **The cut line** — one sentence per pitch: the smallest version still worth shipping. Build to the cut line first; everything above it is a bonus, not a commitment.

Appetite survives only as a coarse ambition tag — **small / medium / chunky** — a rough signal of weight, never an estimate. If a pitch overflows, the response is to cut back to the cut line or drop it, never to quietly grow it.

There's no fixed cycle length. A new pitch starts when the previous one ends.

## What lives where

- **The why** — design notes ([[../product-design/001-problem-and-stakeholders]] through `010-design-language`).
- **The how (stack-level)** — [[../architecture/001-stack-decisions]].
- **The strategy and the work** — this folder.
- **The how (pitch-level)** — figured out during the cycle, captured in commit messages and (if worth keeping) a session note.
- **Tone** — [[../_context]].

## Working with Claude Code

Pitches are written **by the dev team — Luk and Claude Code together**. That means framing *and* solution design: the pitch is where the shape of the answer gets worked out, not just a ticket handed down to be executed. Claude is a co-designer inside the frame, not a code generator after it.

What the pitch still pins down is the *edges*, not the solution: what's out of scope, and the cut line. Inside those edges, the design is open and collaborative. When starting a pitch, pull in:
1. [[../architecture/001-stack-decisions]] — the stack and the *why*.
2. The pitch note itself.
3. The block note (for surrounding context).
4. The relevant product-design note(s).

If the work wants to grow past the cut line or out of scope, that's a conversation — extend the pitch, defer it to another slot, or drop it — not a silent expansion. Two skills run the boundaries of a cycle: `start-pitch` (enter) and `ship-pitch` (leave), ported from the Runtime repo.

## When in doubt

If something doesn't fit a pitch — a copy tweak, a one-line bug fix — just do it. Pitches are for work that earns being framed first. If something *would* be a pitch but the design isn't settled, push it back to the design notes.
