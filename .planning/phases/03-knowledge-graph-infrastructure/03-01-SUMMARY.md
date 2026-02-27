---
phase: 03-knowledge-graph-infrastructure
plan: 01
subsystem: knowledge-graph
tags: [falkordb, cypher, discretization, per-variable-graph, merge-semantics]

# Dependency graph
requires:
  - phase: 02-brain-capacity-micro-processes
    provides: "FrameOrchestrator with execute_one_frame, FrameAction with left/right, KnowledgeManager with FalkorDB backend"
provides:
  - "VariableGraph: single-variable FalkorDB graph with MERGE nodes and CREATE edges"
  - "MultiGraphManager: coordinates N VariableGraph instances for simultaneous per-frame recording"
  - "Inline _discretize() static method (no KnowledgeManager dependency)"
  - "MockFalkorGraph: in-memory Cypher simulation for offline testing"
affects: [03-02-PLAN, 03-03-PLAN, phase-4-exploration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-variable graph isolation via FalkorDB select_graph('kg_{name}')"
    - "MERGE for nodes (no duplicates), CREATE for edges (repeated transitions valid)"
    - "MockFalkorGraph for offline Cypher testing"
    - "Inline _discretize() avoids cross-module instance method dependency"

key-files:
  created:
    - knowledge/variable_graph.py
    - knowledge/multi_graph_manager.py
    - tests/test_variable_graph.py
  modified: []

key-decisions:
  - "Inline _discretize() static method instead of importing from KnowledgeManager (instance method, would fail)"
  - "ActionBin.to_dict() format with 'min'/'max' keys as canonical bin dict format"
  - "Dead-zone actions (bin_id=0, value=0.0) skipped in record_frame (node stays at current value)"
  - "Parameterized Cypher queries ($val) instead of string interpolation (FalkorDB best practice)"

patterns-established:
  - "MockFalkorGraph: reusable in-memory mock for FalkorDB Cypher in offline tests"
  - "VariableGraph per feedback variable, MultiGraphManager as coordinator"
  - "_discretize(value, min_delta, precision=7) as standalone math utility"

# Metrics
duration: 5min
completed: 2026-02-27
---

# Phase 3 Plan 01: Per-Variable Graph Data Model Summary

**VariableGraph with MERGE no-duplicate-node semantics, bin-labeled edges, and MultiGraphManager for simultaneous per-variable recording -- 27 offline tests**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-27T10:26:09Z
- **Completed:** 2026-02-27T10:31:30Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- VariableGraph class manages one FalkorDB graph per feedback variable with MERGE nodes (GRAPH-04) and CREATE edges
- MultiGraphManager coordinates N VariableGraph instances, updates all simultaneously on each frame (GRAPH-06)
- 27 offline tests proving no-duplicate-node semantics, discretization, bin-labeled edges, and multi-graph recording
- No regression in Phase 2 tests (12/12 pass)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create VariableGraph class** - `d8c6afd` (feat)
2. **Task 2: Create MultiGraphManager** - `a50cb91` (feat)
3. **Task 3: Offline tests** - `6d3ec01` (test)

## Files Created/Modified
- `knowledge/variable_graph.py` - Single-variable graph with MERGE nodes, CREATE edges, inline _discretize()
- `knowledge/multi_graph_manager.py` - Multi-graph coordinator with resolve_bin and simultaneous recording
- `tests/test_variable_graph.py` - 27 offline tests with MockFalkorGraph (14 VariableGraph + 13 MultiGraphManager)

## Decisions Made
- Used inline `_discretize()` static method instead of importing from KnowledgeManager (it's an instance method on line 749, import would fail)
- Used parameterized Cypher queries (`$val`) rather than f-string interpolation for FalkorDB best practice
- Dead-zone actions (bin_id=0 with value 0.0) are skipped in record_frame -- the node already represents the current state
- ActionBin.to_dict() format with keys 'min'/'max' is the canonical bin dict format throughout the system

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed MockFalkorGraph edge direction detection**
- **Found during:** Task 3 (tests)
- **Issue:** MockFalkorGraph._handle_match_edges() matched `(from:State` in both FROM and TO queries, always returning FROM edges
- **Fix:** Changed detection to check `from:State{value:` vs `to:State{value:` (which alias has the $val parameter)
- **Files modified:** tests/test_variable_graph.py
- **Verification:** test_get_edges_to now passes (was failing)
- **Committed in:** 6d3ec01 (part of Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 bug in test mock)
**Impact on plan:** Test infrastructure bug, no impact on production code.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- VariableGraph and MultiGraphManager ready for integration with FrameOrchestrator (03-02-PLAN)
- MockFalkorGraph reusable for integration tests
- No blockers for 03-02 or 03-03

## Self-Check: PASSED

All files verified present. All commit hashes verified in git log.

---
*Phase: 03-knowledge-graph-infrastructure*
*Completed: 2026-02-27*
