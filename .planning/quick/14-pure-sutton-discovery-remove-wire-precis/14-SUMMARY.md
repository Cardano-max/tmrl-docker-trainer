---
phase: quick
plan: 14
subsystem: intelligence/experimentation
tags: [sutton-algorithm, binary-detection, discovery, refactor]
dependency-graph:
  requires: [quick-12, quick-11]
  provides: [pure-sutton-discovery, combined-bracket-binary-detection]
  affects: [test_phase_a_tmnf.py, run_5_pure_sutton.py]
tech-stack:
  patterns: [single-algorithm-discovery, combined-bracket, nature-by-sweep]
key-files:
  created:
    - run_5_pure_sutton.py
  modified:
    - intelligence/intelligence_experimentation.py
    - test_phase_a_tmnf.py
decisions:
  - "Single exponential sweep discovers binary/analog nature organically -- no pre-classification step"
  - "Combined bracket (saturated->D0 directly) means MAX=MIN for binary actions"
  - "wire_precision parameter kept in signature for backward compat but ignored internally"
  - "detect_action_nature() and _run_binary_discovery() preserved as deprecated (not deleted)"
  - "Binary search uses _binary_search_min on combined bracket since we want smallest value with effect"
metrics:
  duration: 4min
  completed: 2026-03-04
---

# Quick Task 14: Pure Sutton Discovery -- Single Algorithm Summary

Rewrote run_discovery() from two-stage model to pure Sutton single algorithm that discovers action nature organically during the exponential sweep.

## What Changed

### Before (Two-Stage Model)
1. `detect_action_nature()` -- pre-classifies binary vs analog by probing multiple magnitudes
2. If binary -> `_run_binary_discovery()` (hardcodes MAX=1.0, binary searches MIN separately)
3. If analog -> exponential sweep + binary search for MAX and MIN

### After (Pure Sutton Single Algorithm)
1. Measure D0 = probe_fn(0.0) inline
2. Exponential sweep from 1e6 downward -- single pass discovers everything:
   - **BINARY**: delta goes saturated -> D0 directly (one transition, combined bracket)
   - **ANALOG**: delta goes saturated -> intermediate -> D0 (two transitions, separate brackets)
3. Binary search the bracket(s)
4. If combined bracket: MAX = MIN = threshold (binary action, 1 effective bin)
5. Nature inferred from sweep behavior, not pre-classified

### Key Insight
For binary actions in the pure algorithm, when delta changes from saturated and goes DIRECTLY to D0 (skipping intermediate values), the MAX bracket and MIN bracket are THE SAME. Binary search on this shared bracket gives MAX = MIN = the activation threshold.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Rewrite run_discovery() as pure Sutton single algorithm | ae8c345 | intelligence/intelligence_experimentation.py |
| 2 | Remove wire_precision from discovery call in test_phase_a_tmnf | b0efab2 | test_phase_a_tmnf.py |
| 3 | Create 5-run pure Sutton validation script | 94ca77c | run_5_pure_sutton.py |

## Verification

### Offline Mock Tests (3/3 PASS)
1. **Binary action**: Correctly detects combined bracket, finds MAX = MIN = threshold (~0.002)
2. **Analog action**: Correctly finds separate MAX and MIN brackets, binary searches each
3. **No-effect action**: Correctly returns (None, None) with nature='none'

### Live Validation
- `run_5_pure_sutton.py` created and ready to run against TMNF
- Requires TMInterface 2.x with AgenticBridge.as plugin
- User does not have TMNF running currently -- script is ready-to-run

## Deviations from Plan

None -- plan executed exactly as written.

## Files

| File | Action | Description |
|------|--------|-------------|
| intelligence/intelligence_experimentation.py | MODIFIED | Rewrote run_discovery() -- single algorithm, no pre-classification |
| test_phase_a_tmnf.py | MODIFIED | Removed wire_precision from disc.run_discovery() call |
| run_5_pure_sutton.py | CREATED | 5-run validation script (JSON + terminal, no Excel dependency) |

## Self-Check: PASSED

All 3 files verified present. All 3 commits verified in git log.
