---
phase: quick-10
plan: 01
subsystem: testing
tags: [two-stage-discovery, binary-detection, validation, tmnf, tminterface, sutton-compliance]

# Dependency graph
requires:
  - phase: quick-9
    provides: two-stage discovery model (detect_action_nature + binary/analog path)
  - phase: quick-8
    provides: multi_speed_binary_proof_20260303_092924.json cross-reference data
provides:
  - 5-run two-stage validation script (run_5_two_stage_validation.py)
  - Cross-run determinism verification for two-stage model
  - Sutton compliance validation with terminal report + JSON output
affects: [phase-a-validation, bin-discovery]

# Tech tracking
tech-stack:
  added: []
  patterns: [function-reuse-from-test_phase_a_tmnf, validation-engine-with-verdicts]

key-files:
  created:
    - run_5_two_stage_validation.py
  modified: []

key-decisions:
  - "Reuse all discovery functions from test_phase_a_tmnf.py (no code duplication)"
  - "No Excel/openpyxl dependency -- JSON + terminal report only"
  - "Cross-reference with multi_speed_binary_proof is optional (--no-cross-ref flag)"

patterns-established:
  - "Validation engine pattern: per-run checks + cross-run stability + Sutton compliance + cross-reference"
  - "Terminal report with structured sections (environment, per-run, stability, compliance, cross-ref, overall)"

# Metrics
duration: 3min
completed: 2026-03-03
---

# Quick Task 10: 5-Run Two-Stage Validation Summary

**5-run validation script for two-stage discovery model with cross-run determinism checks, Sutton compliance validation, and multi-speed binary proof cross-reference**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-03T16:27:27Z
- **Completed:** 2026-03-03T16:31:18Z
- **Tasks:** 1/2 (Task 2 is checkpoint:human-verify requiring live TMNF)
- **Files created:** 1

## Accomplishments
- Created `run_5_two_stage_validation.py` (702 lines) that reuses `measure_frame_duration`, `measure_system_precision`, `run_discovery_tmnf` from `test_phase_a_tmnf.py`
- Validation engine checks 18+ criteria: per-run nature/MAX/bins/D0/MIN/probes, cross-run stability (6 fields x 4 actions), Sutton compliance (6 checks), and cross-reference with multi-speed binary proof
- Terminal report with 6 sections: environment, per-run results, cross-run stability, per-run verdicts, Sutton compliance, cross-reference, overall score
- JSON output with full run data, validation verdicts, and cross-reference comparison

## Task Commits

Each task was committed atomically:

1. **Task 1: Create run_5_two_stage_validation.py** - `77d9ef4` (feat)
2. **Task 2: Live TMNF validation** - checkpoint:human-verify (awaiting live test)

**Plan metadata:** (this summary commit)

## Files Created
- `run_5_two_stage_validation.py` - 5-run two-stage validation script with validation engine, terminal report, and JSON output

## Decisions Made
- Reuse all discovery functions from `test_phase_a_tmnf.py` (no code duplication) -- as specified in plan
- No Excel/openpyxl dependency -- JSON + terminal report only (deliberate departure from old `run_5_discovery_validation.py`)
- Cross-reference with multi_speed_binary_proof is optional via `--no-cross-ref` flag for environments where the JSON file is not available

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Steps

Task 2 (checkpoint:human-verify) requires live testing against TMNF:
1. TMNF running with TMInterface 2.x and AgenticBridge.as loaded
2. Start a race (countdown finished)
3. Run: `python run_5_two_stage_validation.py --speed 5.0`
4. Verify all 5 runs produce consistent BINARY results with all validation checks PASS
5. Check JSON output file for complete results

---
*Phase: quick-10*
*Completed: 2026-03-03*
