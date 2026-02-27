---
phase: 02-brain-capacity-micro-processes
plan: 01
subsystem: core
tags: [frame-orchestrator, micro-processes, sutton, knowledge-graph, falkordb]

# Dependency graph
requires:
  - phase: 01-system-initialization
    provides: "SystemInitializer, TMNFAdapter, KnowledgeManager"
provides:
  - "FrameOrchestrator: atomic 6-micro-process per-frame execution"
  - "FrameAction with left/right fields for TMNF 4-input model"
  - "BRAIN-07: query_frame() (history + graph fallback)"
  - "BRAIN-08: initialize_graph() (optional FalkorDB connection)"
  - "BRAIN-09: compare_to_known() (expected vs actual deltas)"
affects: [02-brain-capacity-micro-processes, 03-intelligence-layer]

# Tech tracking
tech-stack:
  added: []
  patterns: ["adapter-agnostic orchestrator", "in-memory-first with optional graph persistence", "MockAdapter for offline testing"]

key-files:
  created:
    - core/frame_orchestrator.py
    - tests/test_frame_orchestrator.py
  modified:
    - knowledge/knowledge_manager.py

key-decisions:
  - "In-memory history always works; FalkorDB is optional overlay (no hard dependency)"
  - "FrameAction gets left/right fields for TMNF 4-binary-input model (Phase A proven)"
  - "Orchestrator imports only logging+typing (adapter-agnostic, no TMNF imports)"

patterns-established:
  - "MockAdapter pattern: offline tests simulate adapter with send_action_dict/wait_one_tick/get_feedbacks"
  - "Capacity-only modules: no intelligence logic in orchestrator, just raw operations"

# Metrics
duration: 3min
completed: 2026-02-27
---

# Phase 2 Plan 01: Frame-Sync Micro-Process Orchestrator Summary

**FrameOrchestrator implementing Sutton's 6 micro-processes with in-memory history, optional FalkorDB, and adapter-agnostic design**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-27T09:46:05Z
- **Completed:** 2026-02-27T09:49:13Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- FrameOrchestrator.execute_one_frame() calls all 6 micro-processes in correct Sutton order (feedback-before, send, tick, feedback-after, record)
- FrameAction dataclass extended with left/right for TMNF's 4 binary inputs (gas, brake, left, right)
- All 12 offline tests pass with MockAdapter -- no TMNF/TMInterface/FalkorDB needed
- BRAIN-07/08/09 capacities implemented: query_frame, initialize_graph, compare_to_known

## Task Commits

Each task was committed atomically:

1. **Task 1: Update FrameAction dataclass for 4 TMNF actions** - `fa79ab6` (feat)
2. **Task 2: Create core/frame_orchestrator.py** - `a04f205` (feat)
3. **Task 3: Create tests/test_frame_orchestrator.py** - `4585acf` (test)

## Files Created/Modified
- `core/frame_orchestrator.py` - FrameOrchestrator class: 6 micro-processes, query_frame, compare_to_known, initialize_graph
- `tests/test_frame_orchestrator.py` - 12 offline unit tests with MockAdapter
- `knowledge/knowledge_manager.py` - FrameAction gets left/right fields; Cypher queries updated for 5-field actions

## Decisions Made
- In-memory history always works; FalkorDB is optional overlay -- no hard dependency on graph database
- FrameAction gets left/right fields matching TMNF's 4-binary-input model (Phase A proven: gas, brake, left, right are all binary)
- Orchestrator imports only logging+typing -- completely adapter-agnostic (no TMNFAdapter imports)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- FrameOrchestrator ready for intelligence modules to compose (exploration, awareness, repetition)
- MockAdapter pattern established for all future offline tests
- Knowledge graph recording works if FalkorDB available, gracefully degrades to in-memory otherwise

## Self-Check: PASSED

All 4 files verified present. All 3 task commits verified in git log.

---
*Phase: 02-brain-capacity-micro-processes*
*Completed: 2026-02-27*
