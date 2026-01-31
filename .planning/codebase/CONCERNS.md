# Codebase Concerns

**Analysis Date:** 2026-01-31

## Tech Debt

### Bin Discovery Still Dependent on Feedback Interpretation

**Issue:** Recent meeting (31-Jan-2026) reveals fundamental flaw in bin discovery methodology. Current implementation in `C:/Users/ateeb/Desktop/tmrl_docker_trainer/intelligence/intelligence_experimentation.py` discovers minimum effective values by detecting feedback changes, but supervisor now clarifies: "We are trying to measure the action through the feedback but it's never gonna be the same."

**Files:**
- `intelligence/intelligence_experimentation.py` (lines 406-512: `record_experiment_result`)
- `core/brain_capacity.py` (no direct bin discovery logic)

**Impact:**
- Bins discovered in noisy environments may not be stable
- Environmental physics (wind, weather, friction) affect feedback differently at different states
- System assumes constant feedback response to actions (violation of physics-aware principle)
- Cannot reliably discover bins in variable environments

**Fix approach:**
- Redesign bin discovery to focus on ACTION CONTROL parameters, not feedback observation
- Use derivative/slope-based detection instead of absolute change threshold
- Implement SNR (signal-to-noise ratio) filtering for feedback noise
- Make discovery method adaptive to environmental variability
- Requires experimental validation with variable conditions

---

### Frame Duration Still Hardcoded in Places

**Issue:** While `control/environment_timing.py` validates timing, fallback values hardcoded throughout codebase contradict Sutton requirement: "Frame interval must be DETERMINED by system, not hardcoded."

**Files:**
- `control/system_initializer.py` (line 336: "default 50ms")
- `control/frame_action_controller.py` (lines 128, 146, 149: fallback 50ms)
- `intelligence/order_discovery.py` (line 625: "test_frames = 15" assumes 50ms)
- `tests/stress_test_falkordb.py` (line 270: "Time budget per frame at 20 FPS = 50ms")

**Impact:**
- If environment runs at different FPS (60, 120, etc.), fallbacks cause frame misalignment
- Actions may be sent between environment frames, causing missed input or double input
- Cannot adapt to dynamic environment frame rate changes

**Fix approach:**
- Remove all hardcoded 50ms/56ms/20FPS constants
- Require timing validation BEFORE any experimentation
- Fail startup if environment timing cannot be measured
- Make all timing-dependent logic use validated dt dynamically

---

### Knowledge Graph Node Duplication Risk Not Fully Tested

**Issue:** Meeting 24-Jan-2026 requires "No node duplication in graphs" - nodes represent states, multiple paths should converge to same node. Current implementation in `knowledge/knowledge_manager.py` uses CREATE (not MERGE) for frame nodes, risking duplicates under concurrent conditions.

**Files:**
- `knowledge/knowledge_manager.py` (lines 161, 200-225: CREATE vs MERGE behavior)
- `core/brain_core.py` (knowledge graph recording logic - not reviewed)

**Impact:**
- Graph bloats with duplicate state nodes if same feedback values occur
- Knowledge graph query accuracy degrades as edges split across duplicates
- "Where have I been?" queries become ambiguous

**Fix approach:**
- Convert all CREATE operations to MERGE with frame_id or discretized state as key
- Add uniqueness constraint on state representation (interval values)
- Implement deduplication cleanup procedure
- Add test to verify MERGE behavior under concurrent writes

---

## Known Bugs

### Disjoint Action Filtering Not Validated Experimentally

**Issue:** System filters gas+brake combinations per config, but never validates that these actions are actually disjoint in practice. What if both can be active in the environment?

**Files:**
- `core/brain_core.py` (DisjointActionValidator - filtering logic)
- `config/system_config_corrected.json` (disjoint declarations)
- Tests: No test of actual disjoint enforcement

**Symptoms:**
- Invalid action combinations sent to environment
- Or valid combinations blocked, limiting exploration

**Trigger:** Run exploration with simultaneous gas+brake to observe actual environment behavior

**Workaround:** Validate disjoint pairs experimentally before filtering

---

### Experimentation Phase Timeout Can Leave System Stuck

**Issue:** `ExperimentationIntelligence.start_experimentation()` in `intelligence/intelligence_experimentation.py` (lines 336-368) can hang if environment stops responding during bin discovery. No timeout implemented for individual action testing.

**Files:**
- `intelligence/intelligence_experimentation.py` (lines 370-404: `get_next_experiment` has no timeout)

**Symptoms:**
- System waits forever for feedback after sending experimental action
- User sees no progress
- Must force-kill process

**Trigger:** Environment disconnects during experimentation phase

**Workaround:** Set OS-level timeout or kill process manually

---

### Goal Orchestrator Not Fully Integrated

**Issue:** Meeting requirements include goal-driven orchestration, but `control/goal_orchestrator.py` (line 256) has TODO comment: "Query knowledge graphs for path to target" - core path-finding not implemented.

**Files:**
- `control/goal_orchestrator.py` (lines 256, goal execution)

**Impact:** Goals cannot be executed because system cannot query knowledge graph to find path from current state to goal state

---

## Security Considerations

### Environment Adapter Trust Boundary Not Enforced

**Issue:** System trusts environment telemetry without validation. Malformed or adversarial data from TrackMania TCP socket could crash system or cause invalid state transitions.

**Files:**
- `adapters/tmrl_live_adapter.py` (lines ~120: struct.unpack without error handling)

**Risk:** TCP packet corruption causes system crash

**Current mitigation:** Basic try/catch in adapter

**Recommendations:**
- Add checksum/CRC validation to telemetry packets
- Implement packet format version negotiation
- Validate all feedback values are in expected ranges
- Add rate limiting to socket reads

---

## Performance Bottlenecks

### Knowledge Graph Query Performance Under Load

**Issue:** Meeting 24-Jan-2026 requires stress testing: "nodes/sec, edges/sec, query/sec" and "find throughput limits." Current tests in `tests/stress_test_falkordb.py` measure throughput, but real-time constraint is critical.

**Files:**
- `tests/stress_test_falkordb.py` (benchmark logic exists, but results not integrated into system)
- System makes zero performance adjustments based on test results

**Problem:**
- At 60 FPS with multiple feedbacks, system may exceed FalkorDB throughput
- Graph queries for "untried actions" could become slow under high load
- System has no fallback for degraded performance

**Improvement path:**
- Run stress test before initialization to determine safe FPS
- Implement graph query caching for frequently accessed states
- Add async graph operations to prevent blocking main loop
- Dynamically reduce number of tracked feedbacks if throughput degrades

---

### Experimentation Phase Inefficiency

**Issue:** Bin discovery in `intelligence/intelligence_experimentation.py` increments by `min_step = 0.01` (line 313), requiring ~100 iterations to discover min value. In variable environments, this is unreliable and slow.

**Files:**
- `intelligence/intelligence_experimentation.py` (lines 313, 450-459: linear increment loop)

**Problem:**
- Fixed-size steps don't account for variable response times
- No exponential backoff / binary search
- Meeting 24-Jan-2026 mentioned "order of magnitude discovery" but implementation still linear

**Improvement path:**
- Implement exponential search (0.01 → 0.1 → 0.3 → 0.6 → binary refine)
- Reduce iterations from ~100 to ~15-20
- Adapt step size based on environment response time

---

## Fragile Areas

### Timing Synchronization Logic

**Files:**
- `control/environment_timing.py` (timing validation)
- `control/frame_action_controller.py` (action sending cadence)
- `intelligence/intelligence_experimentation.py` (wait_fn callback)

**Why fragile:**
- System's concept of "a frame" depends entirely on environment definition
- If environment changes FPS mid-session, system may desynchronize
- No continuous re-validation of timing assumptions
- Meeting 31-Jan-2026 shows deep confusion about frame alignment

**Safe modification:**
- Always measure environment timing at start
- Validate timing every N seconds during operation
- Use measured dt for ALL timing calculations, never config
- Add telemetry logging of frame-action alignment

**Test coverage:**
- No test of environment FPS change mid-session
- No test of action misalignment detection
- No test of timing drift recovery

---

### Experimentation Coordinator Callback Architecture

**Files:**
- `intelligence/intelligence_experimentation.py` (lines 666-726: ExperimentationCoordinator)

**Why fragile:**
- Requires 4 separate callback functions (send_action, get_feedbacks, wait, reset)
- No error handling if callbacks return None or raise exceptions
- No timeout handling if callbacks block
- Coupling between experimentation logic and environment interaction

**Safe modification:**
- Add wrapper class to validate callback return values
- Implement timeout decorators on callbacks
- Add retry logic for transient failures
- Test with callback failures

**Test coverage:**
- No test of callback exceptions
- No test of callback timeouts
- No test of environment disconnect during experimentation

---

## Scaling Limits

### FalkorDB Node/Edge Throughput at High FPS

**Current capacity:** Not measured in production

**Limit:** Stress test `tests/stress_test_falkordb.py` shows potential issues at:
- 60 FPS with 5+ feedbacks = ~300 nodes/sec, ~300 edges/sec
- Query latency under load not characterized

**Scaling path:**
- Graph query caching (most states queried repeatedly)
- Async graph writes (decouple recording from action loop)
- Graph sharding by feedback type (already supported, not optimized)
- Consider read-replica for query-heavy operations

---

### Memory Usage of Knowledge Graphs

**Issue:** System stores one node per frame indefinitely. After 1 hour at 60 FPS = 216,000 nodes. With 5 feedbacks = 1.08M nodes total.

**Files:**
- Knowledge storage: `knowledge/knowledge_manager.py`, FalkorDB persistence

**Limit:** Unknown

**Scaling path:**
- Implement graph pruning: keep only last N frames + important state landmarks
- Compress old transitions into statistical summaries
- Archive old knowledge to disk, keep hot set in memory
- Test maximum sustainable graph size

---

## Dependencies at Risk

### FalkorDB Library Usage

**Risk:** FalkorDB is young graph database. Risk of:
- API breaking changes (currently using `select_graph()` - may not be stable)
- Performance regressions
- Limited query optimization

**Impact:** If FalkorDB becomes unreliable, entire knowledge persistence is broken

**Migration plan:**
- If needed, abstract graph interface via wrapper
- Support fallback to RocksDB or LevelDB (key-value store)
- Document graph schema for other implementations

---

### vgamepad Virtual Controller Dependency

**Risk:** ViGEmBus driver dependency on Windows. If driver updates or becomes unsupported:
- System cannot send actions to TrackMania
- No fallback control method

**Impact:** System completely non-functional

**Migration plan:**
- If ViGEmBus fails, implement TCP-based action protocol (environment listens on port)
- Add action logging to file (can be replayed)
- Support keyboard input simulation fallback

---

## Missing Critical Features

### State Space Exploration Not Exhaustive

**Issue:** System can only explore state space reachable from current position. If environment has unreachable regions, system never learns them.

**Problem:** Meeting requirements don't address exploration boundaries. "All reachable states explored" is explicitly rejected, but system has no concept of exploration frontier.

**Blocks:** Cannot know when exploration is "complete"

---

### Episode Replay Capability Not Implemented

**Issue:** Meeting requirements include "Episode 4337, repeat that one" but system has no replay mechanism.

**Files:** Mentioned in `docs/system_architecture.md` (line 182) as future work, not implemented

**Blocks:** Cannot validate repeated actions produce same results

---

### MPC (Model Predictive Control) Deferred

**Issue:** Supervisor explicitly asked to defer MPC implementation until three-state architecture is solid. Currently, system has no predictive planning capability.

**Files:** `docs/system_architecture.md` (line 532: "[ ] MPC Implementation")

**Impact:** System cannot look ahead; only reacts to immediate state

---

## Test Coverage Gaps

### No Test of Disjoint Action Enforcement Under Concurrent Actions

**What's not tested:**
- Can system block invalid combinations (gas+brake) in real environment?
- Does discretizer correctly catch disjoint violations?

**Files:**
- `core/brain_core.py` (DisjointActionValidator - tested only in isolation, not integrated)
- Tests: `tests/live_system_validator.py` (doesn't test disjoint enforcement)

**Risk:** Silent failure where invalid combinations are sent to environment

**Priority:** High

---

### No Test of Timing Validation Integration

**What's not tested:**
- Does system startup fail if timing validation fails?
- Does timing mismatch block initialization?
- What happens if environment FPS changes mid-session?

**Files:**
- `control/environment_timing.py` (validator exists but not integrated into initialization)
- `control/system_initializer.py` (timing_validation stage exists but untested)

**Risk:** System runs with wrong frame timing, actions misaligned

**Priority:** High

---

### No Test of Knowledge Persistence Across Sessions

**What's not tested:**
- Can system load previous knowledge and skip bin discovery?
- Does "Do you want to use it?" prompt work correctly?
- Are graphs properly restored from FalkorDB?

**Files:**
- `control/system_initializer.py` (prior knowledge check - partially tested)
- `knowledge/knowledge_manager.py` (persistence - not tested)

**Risk:** System skips critical initialization or loses knowledge

**Priority:** Medium

---

### No Test of Experimentation Failure Modes

**What's not tested:**
- Environment becomes unresponsive during bin discovery
- Feedback values stuck at constant (min discovery hangs)
- Callback timeout handling

**Files:**
- `intelligence/intelligence_experimentation.py` (no timeout logic)

**Risk:** System hangs indefinitely

**Priority:** High

---

### No Test of Stress Conditions

**What's not tested:**
- System behavior under graph load (stress test exists but not integrated)
- Action sending cadence under CPU load
- Knowledge graph query latency degradation

**Files:**
- `tests/stress_test_falkordb.py` (standalone, not integrated)

**Risk:** Unknown failure mode in production

**Priority:** Medium

---

## Architectural Concerns

### Three-State Architecture Implementation Incomplete

**Issue:** Meeting requirements define three states (Internal, Environment, Sensorial), but implementation doesn't clearly separate them.

**Files:**
- `core/brain_core.py` - doesn't explicitly represent Internal vs Environment vs Sensorial state
- `core/state_manager.py` - unclear what state it manages

**Impact:** Cannot validate "awareness" properly - comparison of predicted (internal) vs actual (environment) is implicit

**Fix:** Create explicit StateVector class with three components, use throughout

---

### Goal Orchestration Not Wired

**Issue:** Meeting requires "Goal is an orchestrator, all capacities used to achieve this" but goal_orchestrator.py is isolated from main system flow.

**Files:**
- `control/goal_orchestrator.py` (lines 256: unimplemented)
- `run_order_system.py` (doesn't use goal orchestrator)
- No integration point in main system flow

**Impact:** Goals cannot be executed

---

### Awareness Intelligence Not Fully Validated

**Issue:** Awareness comparison logic exists but never tested against real environment discrepancies.

**Files:**
- `intelligence/intelligence_awareness.py` (line 218: logging logic exists)

**Problem:** System claims to compare prediction vs reality but no evidence it works in practice

---

## Requirements-Implementation Gaps

### From 24-Jan-2026 Meeting (MEET_REQ.TXT)

| Requirement | Status | Notes |
|-----------|--------|-------|
| REQ-001: Frame timing from environment, not hardcoded | ⚠️ Partial | Timing validator exists but fallbacks still hardcoded |
| REQ-002: Initialization pipeline with validation | ✓ Implemented | system_initializer.py structure in place |
| REQ-003: Bin acquisition mandatory before recording | ✓ Implemented | experimentation_intelligence.py enforces this |
| REQ-005: Randomized test harness for bin discovery | ✗ Missing | No test generates random min/max to validate algorithm |
| REQ-006: No node duplication in graphs | ⚠️ Partial | CREATE used, not MERGE - risk remains |
| REQ-007: Graph recording stress tested | ✗ Not integrated | stress_test_falkordb.py exists but results unused |
| REQ-008: Separate capacity from intelligence | ✓ Implemented | brain_capacity.py and intelligence modules separate |

**Priority fixes:** REQ-005, REQ-006, REQ-007

---

### From 31-Jan-2026 Meeting (meeting_transcript_31Jan2026.txt)

| Requirement | Status | Notes |
|-----------|--------|-------|
| Bin discovery focus on ACTION, not feedback | ✗ Missing | Current implementation measures feedback change |
| SNR filtering for noisy feedback | ✗ Missing | No noise filtering implemented |
| Derivative-based bin detection | ✗ Missing | Only absolute change threshold |
| Frame-based action control | ⚠️ Partial | logic exists but timing validation incomplete |
| Minimum value per frame capability | ✗ Unclear | Implementation doesn't expose this |

**Critical gaps:** Bin discovery needs fundamental redesign

---

## Summary by Severity

### Critical (Blocks Core Functionality)

1. Bin discovery flawed - focuses on feedback instead of action control
2. Goal orchestrator unimplemented - goals cannot execute
3. Frame timing validation not integrated - actions may misalign
4. Node duplication risk in graphs - knowledge integrity compromised

### High (Degrades Quality)

5. No timeout handling in experimentation - can hang system
6. Knowledge graph performance not validated - unknown scaling limits
7. Awareness intelligence unvalidated - comparison logic untested
8. Disjoint filtering not tested in practice - may allow invalid actions

### Medium (Future Issues)

9. Episode replay not implemented - cannot repeat experiments
10. MPC deferred but not planned - no predictive capability
11. Memory usage of graphs unbounded - will cause bloat
12. Experimentation efficiency poor - linear search inefficient

### Low (Technical Debt)

13. Code has isolated TODOs - goal_orchestrator has unimplemented feature
14. Hardcoded constants scattered - violates Sutton's principle
15. Test coverage gaps in multiple areas
16. Dependency risks with FalkorDB and vgamepad

---

*Concerns analysis: 2026-01-31*
