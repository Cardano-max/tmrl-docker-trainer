# Quick Task 16: Fix Excel Probe Display — Verification Probe + Calculation Validation

## What Was Done

Validated ALL 55 midpoint calculations for gas Run 1. Found:
- **43/44 binary search midpoints: EXACTLY CORRECT** (float64 verified)
- **Probe 55: was mislabeled** as BIN SEARCH with formula `mid = (A + B) / 2 = B`
  - Root cause: probe 55 is NOT a midpoint — it's a VERIFICATION probe
  - Binary search stopped at probe 54 (bracket width 1.02e-15 <= precision 1.41e-15)
  - Line 855 in algorithm: `pr_min = probe_fn(self.a_min)` — one final confirmation probe
- **The other LLM's claim of "many errors" was WRONG** — only the display label was incorrect

## Fix Applied

1. Added `search_precision` parameter to `_annotate_probes()`
2. Detect when bracket width <= search_precision → label as "VERIFY" (light green)
3. "How Value Calculated" now shows: "NOT a midpoint! Binary search STOPPED because..."
4. Explains convergence: bracket narrowed from 0.009 to 1.02e-15 (10^13x smaller)
5. Added VERIFY color to legend in Run sheets

## User's MIN/MAX Question Answered

- 0.00196078431372541211 = largest value with NO effect (last D0)
- 0.00196078431372643559 = smallest value WITH effect (returned as MIN)
- MIN = 0.00196078431372643559 (smallest value that turns the action ON)
- MAX = MIN for binary (only one threshold exists)
- Exact threshold is between these two values but can't be narrowed further (float64 limit reached)

## Commits

- `TBD`: fix(quick-16): correct last probe display from BIN SEARCH to VERIFY
