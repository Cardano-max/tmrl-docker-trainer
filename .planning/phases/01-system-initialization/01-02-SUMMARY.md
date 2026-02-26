---
phase: 01-system-initialization
plan: 02
subsystem: control
tags: [tmnf, system-init, adapter-agnostic, prior-knowledge, experimentation, pytest]

# Dependency graph
requires:
  - phase: 01-01
    provides: "config/tmnf_config.json, ConfigValidator (bins optional, frame_duration_ms required), PriorKnowledgeManager"
provides:
  - Rewritten SystemInitializer: TMNF/adapter-agnostic startup sequence with 5 stages
  - InitializationResult now includes frame_duration_ms field
  - 9-test offline integration test suite covering all 6 INIT requirements
affects:
  - 01-03 (SystemInitializer is the entry point for system startup; next plan wires it to live TMNF)
  - All phases that call SystemInitializer.initialize()

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Adapter injection pattern: pass adapter to SystemInitializer constructor for offline/test use
    - Stage-based init: each stage independently tracked in stages dict, fail-fast on errors
    - Defer adapter connection: only connect when bin discovery is actually needed (no connection when prior knowledge found)
    - wait_fn fallback: use adapter.wait_one_tick() if available (TMNF TCP sync), else time.sleep

key-files:
  created:
    - tests/test_system_init.py
  modified:
    - control/system_initializer.py
    - __init__.py

key-decisions:
  - "Validate config before checking prior knowledge: need frame_duration_ms from config even when prior knowledge exists, so validation runs first"
  - "Adapter injection via constructor: allows tests to pass MockAdapter without touching the config-based adapter creation path"
  - "wait_fn uses getattr(adapter, 'wait_one_tick', lambda: time.sleep(...)): TMNF adapter needs TCP-sync tick, non-TMNF adapters fall back to time.sleep"
  - "INIT-03 test mocks ExperimentationCoordinator class not method: instance.intelligence is an instance attribute, patching the class is the correct approach"

patterns-established:
  - "SystemInitializer constructor pattern: SystemInitializer(config_path=..., adapter=...) where adapter=None means auto-create from config"
  - "Test helper pattern: make_test_config(tmp_path) + make_fake_prior_knowledge(tmp_path) for all system init offline tests"

# Metrics
duration: 5min
completed: 2026-02-26
---

# Phase 1 Plan 02: SystemInitializer Rewrite Summary

**Adapter-agnostic SystemInitializer with 5-stage startup sequence (load config, validate, check prior knowledge, connect adapter, acquire bins) and 9-test offline pytest suite covering all 6 INIT requirements**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-02-26T02:01:52Z
- **Completed:** 2026-02-26T02:06:16Z
- **Tasks:** 2
- **Files modified:** 3 (+ 1 created)

## Accomplishments
- Rewrote `control/system_initializer.py`: removed all TM2020-specific code (TMRLLiveAdapter, vgamepad, FalkorDB), wired to ConfigValidator and PriorKnowledgeManager from plan 01, added adapter injection, added `frame_duration_ms` to `InitializationResult`
- Created `tests/test_system_init.py` with 9 offline tests covering INIT-01 through INIT-06, all passing without game/FalkorDB
- Fixed stale `__init__.py` that imported non-existent classes and blocked pytest collection

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite SystemInitializer** - `0994d16` (feat)
2. **Task 2: Offline integration tests** - `d4e3f6d` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified
- `control/system_initializer.py` - Complete rewrite: TMNF/adapter-agnostic, 5-stage init, frame_duration_ms in result
- `tests/test_system_init.py` - 9 offline tests covering all INIT requirements
- `__init__.py` - Fixed stale imports that blocked pytest collection

## Decisions Made
- **Validate config before prior knowledge check:** Although Sutton says "when there is previous knowledge no need to validate anything", we still need `frame_duration_ms` from config. We run `ConfigValidator.validate_config()` first (enforces INIT-01 and INIT-06), then check prior knowledge. This is the cleanest interpretation: validation catches unparseable configs, prior knowledge check decides whether to run experimentation.
- **Adapter injection pattern:** Constructor accepts optional `adapter` param. When `None`, `_connect_adapter()` auto-creates `TMNFAdapter` from config. When set, uses it directly. This enables offline tests with `MockAdapter` without changing any logic paths.
- **wait_fn via getattr:** `getattr(adapter, 'wait_one_tick', lambda: time.sleep(...))` -- TMNF adapter has `wait_one_tick()` that sends the TCP "advance" command to TMInterface; using `time.sleep` instead would desync from the game tick. For mock/non-TMNF adapters, falls back to `time.sleep`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed stale top-level __init__.py blocking pytest collection**
- **Found during:** Task 2 (first test run)
- **Issue:** `__init__.py` imported `KnowledgeGraphV2`, `BrainArchitecture`, `SystemCoordinatorCorrected`, etc. -- all non-existent in current codebase. pytest failed at collection with `ImportError`.
- **Fix:** Replaced content with minimal version-only `__init__.py`
- **Files modified:** `__init__.py`
- **Verification:** `python -m pytest tests/test_system_init.py -v` collected and ran all 9 tests
- **Committed in:** `d4e3f6d` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Auto-fix required for pytest to collect any tests. No scope creep -- the stale `__init__.py` was a leftover from an old architecture that no longer exists.

## Issues Encountered
- INIT-03 test: patching `ExperimentationCoordinator.intelligence` as a class attribute failed because `intelligence` is an instance variable (set in `__init__`). Fixed by patching the entire class with a `MagicMock()` instance whose `.intelligence.discovery_results` is pre-set.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 6 INIT requirements verified by offline test suite
- SystemInitializer ready for wiring to live TMNF in plan 03
- INIT-01: system refuses bad/missing config (test_init_rejects_missing_config_file + test_init_rejects_invalid_config)
- INIT-02: detects prior knowledge (test_init_loads_prior_knowledge)
- INIT-03: runs discovery when no prior knowledge (test_init_runs_discovery_without_prior)
- INIT-04: skips experimentation with prior knowledge (test_init_skips_experimentation_with_prior)
- INIT-05: prints status at each stage (test_init_prints_status_messages)
- INIT-06: frame_duration_ms from config (test_init_frame_duration_from_config)

---
*Phase: 01-system-initialization*
*Completed: 2026-02-26*

## Self-Check: PASSED

- FOUND: control/system_initializer.py
- FOUND: tests/test_system_init.py
- FOUND: .planning/phases/01-system-initialization/01-02-SUMMARY.md
- FOUND commit: 0994d16 (Task 1)
- FOUND commit: d4e3f6d (Task 2)
- All 9 tests pass: `python -m pytest tests/test_system_init.py -v`
