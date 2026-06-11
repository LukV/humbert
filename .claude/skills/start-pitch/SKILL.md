---
name: start-pitch
description: Move a pitch from slot/draft/ready to in-cycle. First co-writes the technical shaping of the pitch (this is the real work of "starting"), then on Luk's OK flips frontmatter and the In Cycle.md "Currently" section. Use when Luk says "start <pitch-name>", "let's pick up <pitch-name>", or "I'll work on <pitch-name>", or when a pitch needs to move from slot/draft/ready to in-cycle.
---

# start-pitch

Starting a pitch is not a state flip — it's the technical analysis. Pitches here are written by the dev team (Luk + Claude Code) inside the repo, where the code is, because the shaping is more technical than functional. So this skill has two phases: **shape** (co-write the technical pitch, get OK) then **apply** (move to in-cycle, begin).

## Vault / repo paths

- Pitch notes: `../../docs/planning/pitches/<name>.md`
- Pitch template: `../../docs/planning/pitches/_template.md`
- Block notes: `../../docs/planning/blocks/<nn>-<block>.md`
- In Cycle: `../../docs/planning/In Cycle.md`
- Architecture: `../../docs/architecture/001-stack-decisions.md`

(Paths are relative to this skill's dir; adjust if Humbert's repo layout differs.)

## Phase 1 — shape (the technical analysis)

1. **Identify the pitch.** If the name isn't obvious from Luk's request, list `pitches/` and the block slots and ask. Don't guess.

2. **Read what exists.** Three cases:
   - **Ready** (`status: ready`, pitch file exists) — sketch is concrete; go light on shaping, confirm it still holds, move to Phase 2.
   - **Draft** (`status: draft`) — finish the technical shaping with Luk: tighten the sketch, the cut line, out-of-scope, risks.
   - **Slot only** (a line on a block note, no file) — create the file from `_template.md` and co-write it now. This is the common case.

3. **Do the analysis.** Work the problem against the real code and the design notes: the technical sketch, the **cut line** (the smallest version still worth shipping), what's explicitly **out of scope**, and the risks. Pull surrounding context from the block note and the relevant `product-design/` notes.

4. **Touch architecture only alongside the pitch.** If the analysis lands a real stack decision (a framework choice, an execution-path call), record it in `001-stack-decisions.md` — but only the decision this pitch forces, in that note. Don't wander the architecture; don't duplicate it into the pitch.

5. **Get the OK.** Present the shaped pitch (and any architecture edit) and wait for Luk's go-ahead before applying. The shaping is the thing Luk is reviewing — not just the green light to code.

## Phase 2 — apply

6. **Update the pitch frontmatter.** Set `status: in-cycle`. Add `started: YYYY-MM-DD` (today; `date +%Y-%m-%d`). Leave `appetite` (the coarse small/medium/chunky tag) and `created` unchanged.

7. **Update `In Cycle.md` "Currently" section.** Replace the body with: