# Roadmap: v1.0 Full Sutton Pipeline

## Overview

Implement the complete intelligent agent architecture specified across 6 Dr. Sutton meeting transcripts -- from system initialization and brain capacity micro-processes through knowledge graphs, exploration, planning, and hierarchical intelligence -- running on TMNF with deterministic rewind. Phase A (bin discovery) is already complete; this roadmap covers the 49 remaining requirements that build the full pipeline on top of that foundation.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: System Initialization** - Config validation, prior knowledge loading, auto bin discovery on startup
- [x] **Phase 2: Brain Capacity Micro-Processes** - Send/perform/record action, receive/collect/record feedback, query graph, compare state
- [x] **Phase 3: Knowledge Graph Infrastructure** - Per-variable graphs with no-duplicate nodes, per-frame recording, multiplicity testing
- [ ] **Phase 4: Exploration and Awareness** - Untried action discovery, depth-first search, episode loop, repetition, state comparison
- [ ] **Phase 5: Planning / MPC** - Goal intervals, pathfinding through graph, multi-frame chaining, dynamic timestep, constraints
- [ ] **Phase 6: Hierarchical Intelligence** - Goal composition, decomposition, multi-level planning, inter-level communication

## Phase Details

### Phase 1: System Initialization
**Goal**: System boots correctly -- validates config, detects prior knowledge, runs bin discovery if needed, and reports status before any intelligence begins
**Depends on**: Phase A complete (bin discovery algorithm exists)
**Requirements**: INIT-01, INIT-02, INIT-03, INIT-04, INIT-05, INIT-06
**Success Criteria** (what must be TRUE):
  1. System refuses to start if config is invalid or incomplete (validation catches bad configs)
  2. System detects existing knowledge graphs on disk and loads them without re-running experimentation
  3. System automatically runs bin discovery when no prior knowledge exists, then proceeds
  4. System prints clear status messages at each startup stage (validation, bins, graphs, ready)
  5. Frame duration is read from environment config, never hardcoded
**Plans**: 2 plans

Plans:
- [x] 01-01-PLAN.md -- TMNF config, validator update, prior knowledge detection
- [x] 01-02-PLAN.md -- SystemInitializer rewrite + offline integration tests

### Phase 2: Brain Capacity Micro-Processes
**Goal**: The six micro-processes from Jan 9 meeting work as small, generic, composable building blocks that intelligence modules orchestrate
**Depends on**: Phase 1 (system initialized, config loaded, bins available)
**Requirements**: BRAIN-01, BRAIN-02, BRAIN-03, BRAIN-04, BRAIN-05, BRAIN-06, BRAIN-07, BRAIN-08, BRAIN-09, BRAIN-10
**Success Criteria** (what must be TRUE):
  1. System sends an action to TMNF and the environment executes it for exactly one frame
  2. System receives feedback (all state variables) from TMNF after each frame
  3. System records every action sent and every feedback received (retrievable history)
  4. System queries the knowledge graph for any node, edge, or relationship and gets correct results
  5. Each micro-process is a standalone function that intelligence modules compose (not monolithic)
**Plans**: 2 plans

Plans:
- [x] 02-01-PLAN.md -- FrameOrchestrator + FrameAction left/right + 12 unit tests
- [x] 02-02-PLAN.md -- Live per-frame graph recording test for Friday demo

### Phase 3: Knowledge Graph Infrastructure
**Goal**: Per-variable knowledge graphs populate correctly with state-action transitions, enforce no-duplicate-node semantics, and support per-frame simultaneous recording across all variables
**Depends on**: Phase 2 (micro-processes can send/receive/record)
**Requirements**: GRAPH-01, GRAPH-02, GRAPH-03, GRAPH-04, GRAPH-05, GRAPH-06, GRAPH-07, GRAPH-08, GRAPH-09, GRAPH-10, GRAPH-11, GRAPH-12
**Success Criteria** (what must be TRUE):
  1. Each feedback variable has its own graph, and all graphs update simultaneously on every frame
  2. Returning to a previously visited state reuses the existing node (no duplicate nodes ever created)
  3. Graph stores action bins as edge labels (not raw continuous values), and same node reachable via different actions shows multiple edges
  4. Multiplicity testing validates intermediate action values between MIN and MAX experimentally (not assumed linear)
  5. State resolution matches system precision from bin discovery -- unreachable states have no nodes
**Plans**: 3 plans

Plans:
- [x] 03-01-PLAN.md -- Per-variable graph data model (VariableGraph + MultiGraphManager + offline tests)
- [x] 03-02-PLAN.md -- Integration wiring (FrameOrchestrator + config + integration tests)
- [x] 03-03-PLAN.md -- Multiplicity testing (intermediate action validation + offline tests)

### Phase 4: Exploration and Awareness
**Goal**: System systematically explores untried actions at each state node, records results across all graphs, replays successful trajectories, and detects discrepancies between environment state and internal graph state
**Depends on**: Phase 3 (knowledge graphs exist and can be populated/queried)
**Requirements**: EXPLORE-01, EXPLORE-02, EXPLORE-03, EXPLORE-04, EXPLORE-05, EXPLORE-06, AWARE-01, AWARE-02, AWARE-03
**Success Criteria** (what must be TRUE):
  1. At any state node, system identifies which action combinations have been tried and which remain untried
  2. System performs untried actions depth-first and records results in all graphs simultaneously
  3. System runs exploration episodes (start, explore, end) and saves trajectories that accumulate knowledge across episodes
  4. System replays a successful trajectory from a previous episode and detects when state diverges from expectation
  5. System compares environment-reported state against graph-predicted state and flags discrepancies
**Plans**: TBD

Plans:
- [ ] 04-01: TBD
- [ ] 04-02: TBD
- [ ] 04-03: TBD

### Phase 5: Planning / MPC
**Goal**: System finds paths through the knowledge graph to reach goal intervals, chains multi-frame sequences when targets are unreachable in one frame, and adjusts planning frequency dynamically
**Depends on**: Phase 4 (graphs populated through exploration, awareness operational)
**Requirements**: PLAN-01, PLAN-02, PLAN-03, PLAN-04, PLAN-05, PLAN-06, PLAN-07
**Success Criteria** (what must be TRUE):
  1. User specifies a goal as an interval on a state variable (e.g., speed 45-55) and system accepts it
  2. System finds an action sequence through the knowledge graph that reaches the goal interval
  3. When target is unreachable in one frame, system chains multiple frames and knows what's achievable per frame from MIN/MAX/bins
  4. Planning frequency increases automatically when system is closer to constraint boundaries
  5. System returns graceful failure ("path not found") when no sequence exists, and never violates constraint intervals during planning
**Plans**: TBD

Plans:
- [ ] 05-01: TBD
- [ ] 05-02: TBD

### Phase 6: Hierarchical Intelligence
**Goal**: System composes multiple goals across variables, decomposes complex goals into achievable subgoals, and plans at multiple hierarchical levels with bidirectional information flow
**Depends on**: Phase 5 (single-variable planning works)
**Requirements**: HIER-01, HIER-02, HIER-03, HIER-04, HIER-05
**Success Criteria** (what must be TRUE):
  1. System accepts compound goals (AND logic across multiple variables: position 50-60 AND speed 45-55 AND distance > 5m)
  2. Complex goals decompose into subgoals that the Phase 5 planner can each solve independently
  3. Multi-level planning operates where Level N aggregates Level N-1 entities (vacuum robot analogy works)
  4. Information flows bidirectionally: Level N sends commands down, Level N-1 sends state up
  5. System stops safely if no path satisfies all constraint layers simultaneously
**Plans**: TBD

Plans:
- [ ] 06-01: TBD
- [ ] 06-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6

| Phase | Plans Complete | Status | Completed |
|-------|---------------|--------|-----------|
| 1. System Initialization | 2/2 | ✓ Complete | 2026-02-26 |
| 2. Brain Capacity Micro-Processes | 2/2 | ✓ Complete | 2026-02-27 |
| 3. Knowledge Graph Infrastructure | 3/3 | ✓ Complete | 2026-02-27 |
| 4. Exploration and Awareness | 0/TBD | Not started | - |
| 5. Planning / MPC | 0/TBD | Not started | - |
| 6. Hierarchical Intelligence | 0/TBD | Not started | - |

---

## Coverage

**49/49 requirements mapped (100%)**

| Category | Requirements | Phase | Count |
|----------|-------------|-------|-------|
| INIT | INIT-01 to INIT-06 | Phase 1 | 6 |
| BRAIN | BRAIN-01 to BRAIN-10 | Phase 2 | 10 |
| GRAPH | GRAPH-01 to GRAPH-12 | Phase 3 | 12 |
| EXPLORE | EXPLORE-01 to EXPLORE-06 | Phase 4 | 6 |
| AWARE | AWARE-01 to AWARE-03 | Phase 4 | 3 |
| PLAN | PLAN-01 to PLAN-07 | Phase 5 | 7 |
| HIER | HIER-01 to HIER-05 | Phase 6 | 5 |

No orphaned requirements. No duplicates.

---

## Dependency Chain

```
Phase A (DONE) --> Phase 1 (INIT) --> Phase 2 (BRAIN) --> Phase 3 (GRAPH)
                                                              |
                                                              v
                   Phase 6 (HIER) <-- Phase 5 (PLAN) <-- Phase 4 (EXPLORE+AWARE)
```

Each phase produces testable, runnable code. Each phase builds on the previous.

---

*Roadmap created: 2026-02-26*
*Milestone: v1.0 Full Sutton Pipeline*
*Source: 49 requirements from 6 Sutton meeting transcripts*
