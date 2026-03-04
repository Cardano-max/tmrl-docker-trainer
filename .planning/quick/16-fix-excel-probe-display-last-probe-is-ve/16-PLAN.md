# Quick Task 16: Fix Excel Probe Display — Verification Probe + Calculation Validation

## Problem

User asked another LLM to verify the midpoint calculations in the Run sheets.
That LLM claimed "many calculation errors". Investigation revealed:

1. **43 out of 44 binary search midpoints are EXACTLY correct** (verified with float64 math)
2. **Probe 55 (last probe) was mislabeled** as "BIN SEARCH" with a midpoint formula.
   It's actually a VERIFICATION probe — the binary search already stopped because
   bracket width (1.02e-15) <= search_precision (1.41e-15).
   The code then probes `a_min` one more time to record delta_at_min (line 855).
3. The other LLM's claim of "many errors" was wrong — only the last probe was mislabeled.

## User's MIN/MAX Question

User asked: "shouldn't 0.00196078431372541211 be MIN and 0.00196078431372643559 be MAX?"

Answer: Close but inverted.
- 0.00196078431372541211 = largest value with NO effect (below threshold)
- 0.00196078431372643559 = smallest value WITH effect (above threshold)
- MIN = smallest value that produces an effect = 0.00196078431372643559
- For binary: MAX = MIN = same value (there's only ON or OFF)
- The exact threshold is between these two, but we can't narrow further (float64 limit)

## Fix

1. Add search_precision parameter to _annotate_probes()
2. Detect when bracket_width <= search_precision → remaining probes are VERIFY not BIN SEARCH
3. New VERIFY phase with light green color and correct explanation
4. Show "NOT a midpoint!" in How Value Calculated column
5. Explain convergence in plain English
