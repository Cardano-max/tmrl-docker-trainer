---
phase: 01-system-initialization
plan: 01
subsystem: config
tags: [tmnf, tminterface, validation, config, prior-knowledge, json, glob]

# Dependency graph
requires: []
provides:
  - TMNF system config with frame_duration_ms=10, binary gas/brake, analog steering, no pre-populated bins
  - ConfigValidator updated to accept TMNF configs (bins optional, environment.timing required)
  - PriorKnowledgeManager for disk-based bin discovery result detection and loading
affects:
  - 01-02 (SystemInitializer uses ConfigValidator and PriorKnowledgeManager)
  - All phases that load config or check prior knowledge

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Config-driven frame_duration_ms (not hard-coded) -- Sutton Jan 24 requirement
    - Bins are discovered at runtime, never pre-configured -- Sutton REQ-20
    - Prior knowledge = disk-based JSON files in Phase 1 (FalkorDB in Phase 3+)

key-files:
  created:
    - config/tmnf_config.json
    - knowledge/prior_knowledge.py
  modified:
    - utils/validators.py
    - knowledge/__init__.py

key-decisions:
  - "Bins are optional in ConfigValidator -- bins are discovered at runtime by Phase A (Sutton REQ-20), not configured"
  - "system_config key removed from required_top_level -- it is a TM2020/FalkorDB concern (Phase 3), not needed for TMNF Phase 1"
  - "environment.timing.frame_duration_ms is now required by validator -- enforces INIT-06 (Sutton Jan 24: configured not hard-coded)"
  - "Prior knowledge in Phase 1 = disk-based JSON files matching tmnf_phase_a_results_*.json; FalkorDB check deferred to Phase 3+"

patterns-established:
  - "Config validation pattern: validate_config() for all configs, validate_tmnf_config() for TMNF-specific checks"
  - "Prior knowledge pattern: PriorKnowledgeManager.has_prior_knowledge() check before running Phase A experimentation"

# Metrics
duration: 4min
completed: 2026-02-26
---

# Phase 1 Plan 01: Config Foundation and Prior Knowledge Summary

**TMNF config with 10ms tick rate, updated ConfigValidator that accepts bin-free actions, and PriorKnowledgeManager detecting saved bin discovery JSON files on disk**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-02-26T01:56:00Z
- **Completed:** 2026-02-26T01:59:25Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Created `config/tmnf_config.json` with TMNF-specific settings (10ms tick, binary gas/brake, analog steering, no pre-populated bins, TCP port 8476)
- Updated `ConfigValidator` to accept TMNF configs where actions have no `bins` (bins discovered at runtime), added required `environment.timing.frame_duration_ms` enforcement, maintained backward compatibility for TM2020 configs
- Created `PriorKnowledgeManager` in `knowledge/prior_knowledge.py` with disk-based prior knowledge detection, loading, extraction, and saving

## Task Commits

Each task was committed atomically:

1. **Task 1: Create TMNF config and update validator** - `e7283a1` (feat)
2. **Task 2: Implement prior knowledge detection from disk** - `b3e0f9f` (feat)
3. **Deviation: Export PriorKnowledgeManager from knowledge package** - `f1543d2` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified
- `config/tmnf_config.json` - TMNF system config (frame_duration_ms=10, binary/analog actions, TCP port 8476, no pre-populated bins)
- `utils/validators.py` - ConfigValidator updated: bins optional, environment.timing required, system_config conditional, new validate_tmnf_config() and _validate_environment()
- `knowledge/prior_knowledge.py` - PriorKnowledgeManager: disk-based prior knowledge detection/loading from tmnf_phase_a_results_*.json files
- `knowledge/__init__.py` - Exports PriorKnowledgeManager from the knowledge package

## Decisions Made
- **Bins optional in validator:** Bins are discovered at runtime by Phase A (Sutton REQ-20). Pre-configuring bins in the config file would violate Sutton's requirement that bins are acquired knowledge, not prior knowledge.
- **system_config removed from required keys:** The `system_config` section contains FalkorDB/database configuration which is a Phase 3 concern. TMNF Phase 1 does not need a database.
- **frame_duration_ms is required:** Sutton Jan 24 said frame duration must be configured, not hard-coded. The validator now enforces this exists as `environment.timing.frame_duration_ms`.
- **Prior knowledge = JSON files for Phase 1:** FalkorDB graph checking is deferred to Phase 3. For now, prior knowledge is the JSON result files from test_phase_a_tmnf.py.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added PriorKnowledgeManager to knowledge package exports**
- **Found during:** Task 2 (after creating knowledge/prior_knowledge.py)
- **Issue:** New class not exported from knowledge/__init__.py, making `from knowledge import PriorKnowledgeManager` fail
- **Fix:** Added import and __all__ entry in knowledge/__init__.py
- **Files modified:** knowledge/__init__.py
- **Verification:** `python -c "from knowledge import PriorKnowledgeManager; print('ok')"` passes
- **Committed in:** f1543d2 (separate commit after Task 2)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Auto-fix necessary for package usability. No scope creep.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- INIT-01 partially met: ConfigValidator catches missing required fields (frame_duration_ms, actions, feedbacks, environment), rejects bad configs
- INIT-02 partially met: PriorKnowledgeManager detects saved bin results on disk
- INIT-06 met: frame_duration_ms=10 in TMNF config, validator enforces its presence
- Plan 02 (SystemInitializer) can now use ConfigValidator.validate_config() and PriorKnowledgeManager.has_prior_knowledge()

---
*Phase: 01-system-initialization*
*Completed: 2026-02-26*
