---
phase: quick-11
plan: 01
subsystem: intelligence, adapters
tags: [wire-precision, uint8-quantization, sutton-compliance, binary-search, nature-detection]

# Dependency graph
requires:
  - phase: quick-9
    provides: two-stage binary/analog discovery model
  - phase: quick-10
    provides: 5-run validation proving binary discovery works
provides:
  - "TMNFAdapter.get_wire_precision() API returning wire format metadata for all 5 channels"
  - "Faithful uint8 quantization replacing hardcoded > 0.0 threshold"
  - "Wire-precision-derived nature detection probes (not hardcoded)"
  - "MIN binary search floor at wire step boundary (1/255 for uint8)"
  - "--from-zero flag for zero-speed discovery"
  - "6 offline verification tests proving precision-first correctness"
affects: [phase-a-discovery, adapters, intelligence-experimentation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wire precision metadata API on adapter layer"
    - "Probe values derived from wire format, not hardcoded"
    - "Binary search bounded by wire resolution, not float epsilon"

key-files:
  created:
    - test_precision_discovery.py
  modified:
    - adapters/tmnf_adapter.py
    - intelligence/intelligence_experimentation.py
    - test_phase_a_tmnf.py

key-decisions:
  - "Faithful uint8 quantization: round(val * 255) instead of hardcoded > 0.0 threshold"
  - "Wire precision is pure data (no TCP needed) -- adapter always knows its wire format"
  - "Nature detection appends probes to self.probes for internal consistency (bug fix)"
  - "Wire step floor uses max(search_precision, wire_step) then restores original after binary search"

patterns-established:
  - "Adapter reports wire precision, algorithm derives probes from it (Sutton: 'first find the system's precision')"
  - "detect_action_nature stores self._nature_probes for reuse by _run_binary_discovery"

# Metrics
duration: 8min
completed: 2026-03-03
---

# Quick Task 11: Precision-First Discovery Rewrite Summary

**Wire-precision-aware discovery: adapter reports uint8/int32 wire format, nature detection derives probes from it, MIN search stops at wire boundary (~1/255 = 0.00392), faithful quantization replaces hardcoded > 0.0**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-03T17:05:32Z
- **Completed:** 2026-03-03T17:13:06Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- TMNFAdapter.get_wire_precision() returns wire format metadata for all 5 channels (gas/brake/left/right: uint8, steering: int32)
- Faithful uint8 quantization: gas=0.004 maps to uint8(1) (ON), gas=0.001 maps to uint8(0) (OFF) -- real boundary at ~1/255
- Nature detection derives probe values from wire precision when available (Sutton: "first find the system's precision")
- Binary MIN search bounded by wire step (1/255 for uint8, not grinding to 9.77e-16)
- --from-zero flag allows discovery from zero speed (skip MIN_PROBE_SPEED acceleration)
- 6 offline verification tests all PASS without TMNF running

## Task Commits

Each task was committed atomically:

1. **Task 1: Adapter wire precision API + faithful uint8 quantization** - `8068304` (feat)
2. **Task 2: Wire-precision-aware nature detection + MIN search + zero-speed option** - `471f905` (feat)
3. **Task 3: Offline verification script + probe tracking bug fix** - `ec65210` (feat)

**Plan metadata:** [pending] (docs: complete plan)

## Files Created/Modified
- `adapters/tmnf_adapter.py` - Added get_wire_precision() method, changed gas/brake/left/right from `1 if val > 0.0` to `round(val * 255)` faithful quantization
- `intelligence/intelligence_experimentation.py` - detect_action_nature accepts wire_precision, derives probes from it; _run_binary_discovery respects wire_step floor; run_discovery passes wire_precision through chain; detect_action_nature now appends probes to self.probes
- `test_phase_a_tmnf.py` - Plumbs wire_precision from adapter to discovery, adds --from-zero flag, save_results includes wire_precision in JSON
- `test_precision_discovery.py` - New: 6 offline tests validating all 3 fixes

## Decisions Made
- **Faithful uint8 quantization** (`round(val * 255)`) chosen over alternatives like truncation or ceiling -- round() gives the most balanced boundary placement (threshold at ~0.00196, exactly between uint8 values 0 and 1)
- **Wire precision is pure data** -- get_wire_precision() needs no TCP connection, just reports the known wire format from the AgenticBridge.as protocol spec
- **Probe derivation uses powers of 10** down to float_step -- matches Sutton's "0.1, 0.01, 0.001" pattern from transcripts
- **Wire step floor**: `max(search_precision, wire_step)` ensures the larger of the two stops the binary search; original precision restored after search completes

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] detect_action_nature() did not append probes to self.probes**
- **Found during:** Task 3 (offline verification script)
- **Issue:** `_run_binary_discovery()` searched `self.probes` for nature detection results, but `detect_action_nature()` never added them -- it relied on the external `probe_fn` (make_probe_fn) to do it. Mock probe functions without this behavior caused "no active probes found" failure.
- **Fix:** Added `self.probes.append(pr)` for D0 and nature probes inside `detect_action_nature()`, with `if pr not in self.probes` guard to avoid double-counting when external probe_fn also appends.
- **Files modified:** intelligence/intelligence_experimentation.py
- **Verification:** All 6 offline tests pass, including binary discovery finding MIN at wire_step (0.00392) not 1.0
- **Committed in:** ec65210 (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Essential for correctness -- without this fix, binary discovery could not find nature probes in its own probe list when using mock/simple probe functions.

## Issues Encountered
None beyond the deviation documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Wire precision infrastructure ready for any adapter (not TMNF-specific pattern)
- Live validation with TMNF can use `python test_phase_a_tmnf.py` to see MIN discovered at ~0.00392 instead of near-zero
- --from-zero flag enables testing gas/brake discovery from standstill

## Self-Check: PASSED

All 4 files verified present. All 3 task commits verified in git log.

---
*Quick Task: 11*
*Completed: 2026-03-03*
