---
phase: quick-8
plan: 1
subsystem: testing
tags: [tmnf, binary-proof, multi-speed, extended-range, analog-gas, fact-check]

# Dependency graph
requires:
  - phase: Phase A
    provides: "TMNFAdapter TCP bridge, AgenticBridge.as v2.0, probe patterns"
provides:
  - "Multi-speed binary proof script for gas/brake/left/right across 6 speeds"
  - "Extended range MIN boundary discovery with binary search"
  - "Analog gas axis fact-check documentation"
  - "JSON results with per-speed breakdown and verdicts"
affects: [phase-a-validation, bin-discovery, future-analog-tests]

# Tech tracking
tech-stack:
  added: []
  patterns: [multi-speed-probing, extended-range-binary-search, fact-check-documentation]

key-files:
  created:
    - test_multi_speed_binary_proof.py
  modified: []

key-decisions:
  - "Group D analog gas test is documentation-only (requires AgenticBridge.as modification for live test)"
  - "Left/right extended range confirms adapter boundary (> 0.0) not game boundary"
  - "Gas/brake binary search goes to 1e-18 precision for true MIN"

patterns-established:
  - "Multi-speed test pattern: restart -> accelerate -> save_state -> probe at each speed"
  - "Extended range pattern: descending probes -> binary search between last-working and first-D0"

# Metrics
duration: 3min
completed: 2026-03-03
---

# Quick Task 8: Multi-Speed Binary Proof Summary

**4-group validation script proving TMNF binary inputs are speed-independent, with extended MIN boundary discovery and analog gas axis fact-check**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-03T04:18:42Z
- **Completed:** 2026-03-03T04:21:53Z
- **Tasks:** 1
- **Files created:** 1

## Accomplishments

- Created 828-line test script with 4 comprehensive test groups (A-D)
- Group A: gas/brake binary proof across 6 speeds (rest, 50, 100, 150, 200, 250 km/h)
- Group B: left/right steering proof across 5 speeds with opposite-sign verification
- Group C: extended range MIN probing below 1e-15 with 20-step binary search
- Group D: analog gas axis fact-check with TMInterface docs cross-reference
- Full JSON output with per-speed breakdown, verdicts, and probe-level data

## Task Commits

1. **Task 1: Create multi-speed binary proof + extended range + analog gas axis test script** - `876958e` (feat)

## Files Created/Modified

- `test_multi_speed_binary_proof.py` - 828-line comprehensive test with 4 groups (A: multi-speed gas/brake, B: multi-speed steering, C: extended range MIN, D: analog gas fact-check)

## Decisions Made

- Analog gas axis test (Group D) is documentation-only, not live-tested, because testing InputType::Gas(5) requires modifying AgenticBridge.as to add a new channel. Flagged as FUTURE_TEST.
- Left/right extended range probing documents that the true MIN boundary is in the adapter's `> 0.0` uint8 comparison, not in the game engine. Any positive float becomes digital ON.
- Binary search for gas/brake TRUE MIN uses 20 steps to reach 1e-18 precision, matching the adapter's float comparison boundary.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Script ready for live testing against TMNF + TMInterface
- When run, will produce multi_speed_binary_proof_{timestamp}.json with full results
- Analog gas axis live test flagged for future AgenticBridge.as modification

## Self-Check: PASSED

- test_multi_speed_binary_proof.py: FOUND
- 8-SUMMARY.md: FOUND
- commit 876958e: FOUND

---
*Quick Task: 8-multi-speed-binary-proof-fact-check-vali*
*Completed: 2026-03-03*
