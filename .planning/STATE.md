# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-26)

**Core value:** Enable safe, goal-based autonomous learning that scales hierarchically
**Current focus:** Phase 2 complete -- ready for Phase 3 (Intelligence Modules)

## Current Position

Phase: 2 of 6 (Brain Capacity Micro-Processes) -- COMPLETE
Plan: 2/2 complete
Status: Phase 2 complete, ready for Phase 3
Last activity: 2026-02-27 -- 02-02 Live Per-Frame Graph Recording Test complete (25 frames, 4 phases)

Progress: [███░░░░░░░] 33%

## Performance Metrics

**Velocity:**
- Total plans completed: 4
- Average duration: 3.8 min
- Total execution time: 0.25 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-system-initialization | 2 | 9min | 4.5min |
| 02-brain-capacity-micro-processes | 2 | 6min | 3min |

**Recent Trend:**
- Last 5 plans: 01-01 (4min), 01-02 (5min), 02-01 (3min), 02-02 (3min)
- Trend: accelerating

*Updated after each plan completion*

## Accumulated Context

### Phase A: Bin Discovery (COMPLETE)

**What shipped:**
- Sutton's 4-step bin discovery algorithm (FrameBinDiscovery)
- Precision discovery via binary search (measure_precision)
- TMNF + TMInterface TCP bridge (SuttonBridge.as + tmnf_adapter.py)
- Gas: 2 bins (binary), Brake: 2 bins (binary), Steering: 201 bins (precision-discovered)
- 9/9 live rubrics, 12/12 offline tests, stable 3/3 runs
- REQ-01 through REQ-25 validated

### Phase 1 Plan 01: Config Foundation (COMPLETE)

**What shipped:**
- config/tmnf_config.json (frame_duration_ms=10, binary gas/brake, analog steering, no pre-populated bins)
- utils/validators.py updated (bins optional, environment.timing required, system_config conditional)
- knowledge/prior_knowledge.py (PriorKnowledgeManager: disk-based JSON result detection/loading)

### Phase 1 Plan 02: SystemInitializer (COMPLETE)

**What shipped:**
- control/system_initializer.py rewritten: adapter-agnostic, 5-stage sequence, frame_duration_ms in result
- tests/test_system_init.py: 9 offline tests, all passing, covers INIT-01 through INIT-06
- __init__.py fixed (was importing non-existent classes, blocking pytest)

### Phase 2 Plan 01: Frame-Sync Micro-Process Orchestrator (COMPLETE)

**What shipped:**
- core/frame_orchestrator.py: FrameOrchestrator with all 6 Sutton micro-processes
- FrameAction dataclass updated with left/right for TMNF 4-input model
- BRAIN-07 (query_frame), BRAIN-08 (initialize_graph), BRAIN-09 (compare_to_known)
- tests/test_frame_orchestrator.py: 12 offline tests with MockAdapter, all passing
- In-memory history always works; FalkorDB optional overlay

### Phase 2 Plan 02: Live Per-Frame Graph Recording Test (COMPLETE)

**What shipped:**
- tests/test_live_graph_recording.py: end-to-end live test with TMNF + FalkorDB
- 4-phase recording: gas(10) + brake(5) + D0(5) + left+gas(5) = 25 frames
- Graph edge verification: left/right properties in Cypher confirmed
- --no-graph fallback for in-memory-only mode
- Summary table with per-frame speed/yaw and graph query examples
- Friday meeting demo-ready script

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Phase A]: TMNF + TMInterface for deterministic rewind (pure Sutton compliance)
- [Phase A]: Three-layer architecture (Brain -> Knowledge -> Intelligence) locked
- [Phase A]: Config-driven, env-agnostic design locked
- [Phase A]: Goal/constraint-based planning, not reward-based
- [01-01]: Bins are optional in ConfigValidator -- bins are discovered at runtime by Phase A (Sutton REQ-20), not configured
- [01-01]: system_config key removed from required_top_level -- TM2020/FalkorDB concern (Phase 3), not needed for TMNF Phase 1
- [01-01]: environment.timing.frame_duration_ms is now required by validator -- enforces INIT-06 (Sutton Jan 24)
- [01-01]: Prior knowledge in Phase 1 = disk-based JSON files (tmnf_phase_a_results_*.json); FalkorDB check deferred to Phase 3+
- [01-02]: Validate config before prior knowledge check -- need frame_duration_ms even when prior knowledge exists
- [01-02]: Adapter injection via constructor -- allows offline tests with MockAdapter without changing init logic
- [01-02]: wait_fn via getattr(adapter, wait_one_tick, fallback) -- TMNF TCP sync vs time.sleep for non-TMNF adapters
- [02-01]: In-memory history always works; FalkorDB is optional overlay (no hard dependency)
- [02-01]: FrameAction gets left/right fields for TMNF 4-binary-input model (Phase A proven)
- [02-01]: Orchestrator imports only logging+typing (adapter-agnostic, no TMNF imports)
- [02-02]: All 3 tasks integrated into single script (plan specified tasks 2+3 are part of task 1)
- [02-02]: 4-phase recording pattern: gas(10) + brake(5) + D0(5) + left+gas(5) = 25 frames
- [02-02]: --no-graph CLI flag plus graceful fallback on FalkorDB connection failure

### Pending Todos

None.

### Blockers/Concerns

None.

## Session Continuity

Last session: 2026-02-27
Stopped at: Completed 02-02-PLAN.md (Live Per-Frame Graph Recording Test) -- Phase 2 complete
Resume file: None
