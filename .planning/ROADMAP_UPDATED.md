# Updated Roadmap: From 70% Complete to Production Ready

**Updated:** 2026-02-16 (Based on actual codebase state)
**Current Completion:** ~70%
**Remaining Work:** ~30% (8-12 days estimated)
**Target:** Production-ready, multi-environment, fully tested

---

## What's Already Done (Don't Rework)

### ✓ Phase 1-3 Complete (Configuration, Knowledge, Exploration)

- Configuration system (JSON-based, environment-agnostic)
- State management (current/previous/history)
- Action discretization with disjoint filtering
- Knowledge graphs (FalkorDB, per-frame nodes)
- Query system (transition queries, untried actions)
- Episode memory (record/replay)
- Exploration intelligence (try untried actions)
- Repetition intelligence (replay episodes)
- Awareness, monitoring, constraints intelligence

**Status:** USE AS-IS, don't modify

---

## What Needs Fixing (Gaps)

### Gap 1: Path Planning Missing (CRITICAL BLOCKER) 🔴

**Impact:** Blocks Phase 4-5 functionality
**Location:** New file needed: `intelligence/intelligence_planning.py`

**What to build:**
1. `PathfindingIntelligence` class
2. Input: current_state_node, goal_interval, constraints
3. Algorithm: Dijkstra/A* over knowledge graph
4. Output: action_sequence[] or None
5. Constraint validation at each step

**Integration:**
- Add to `system_coordinator_corrected.py`
- Call from `goal_orchestrator.py`
- Use existing query functions

**Estimated Effort:** 2-3 days
**Complexity:** Medium (graph traversal + constraint validation)

**Pseudo-code outline:**
```python
class PathfindingIntelligence:
    def find_path(self, current_state, goal_interval, constraints):
        # 1. Query: what states are in goal_interval?
        goal_states = self.query_goal_states(goal_interval)

        # 2. Use Dijkstra to find shortest path
        path = self.dijkstra(current_state, goal_states, constraints)

        # 3. Validate path respects all constraints
        if self.validate_path(path, constraints):
            return [action for _, action in path]  # Return actions only
        else:
            return None  # Path not found
```

**Success Criteria:**
- ✓ Finds path from current state to goal state
- ✓ Returns action sequence
- ✓ Validates constraints before each action
- ✓ Handles "path not found" gracefully
- ✓ Completes <100ms for normal graphs

---

### Gap 2: Steering Discovery Incomplete ⚠️

**Impact:** System can't learn steering effects
**Location:** `discover_v1.py` line 208 (commented out)

**Problem:** Steering range is [-1.0, +1.0] (symmetric, center=0)
- Gas/brake: [0.0, 1.0] (asymmetric)
- Bouncing algorithm assumes 0-to-max, not -to+

**What to fix:**
1. Adapt bouncing algorithm for symmetric ranges
2. Start from center (0.0), probe both directions
3. Discover min (-1.0) and max (+1.0)
4. Generate bins from min/max

**Estimated Effort:** 1 day
**Complexity:** Low (algorithmic tweak)

**Implementation location:**
```python
# In discover_v1.py or new file: discover_steering.py

def discover_symmetric_action(action_name, center=0.0, range_min=-1.0, range_max=1.0):
    """Discover bins for symmetric action (e.g., steering [-1, 1])"""
    # 1. Start at center (0.0)
    # 2. Probe left: 0.0 → -0.5 → -0.75 → -1.0
    # 3. Probe right: 0.0 → 0.5 → 0.75 → 1.0
    # 4. Measure effect on state
    # 5. Generate bins (low, medium, high for -1 to 1)
```

**Success Criteria:**
- ✓ Discovers steering effects: min, max, mid
- ✓ Creates valid bins for [-1, 1] range
- ✓ Works with existing `ExperimentationIntelligence`
- ✓ Results match gas/brake discovery quality

---

### Gap 3: Experimentation Not Integrated ⚠️

**Impact:** System uses emergency fallback bins (hardcoded)
**Location:** `system_initializer.py` (needs modification)

**Current Flow (Manual):**
```
1. Start system
2. Use emergency bins (config)
3. Manual: python discover_v1.py
4. Manual: update config with discovered bins
5. Restart system
```

**Desired Flow (Automatic):**
```
1. Start system
2. [Check: experimentation_at_startup enabled?]
3. Auto: run ExperimentationCoordinator
4. Auto: discover and update bins
5. Proceed to normal operation
```

**What to fix:**
1. Add `experimentation_at_startup: true/false` to config
2. Add startup check in `system_initializer.py`
3. Call `ExperimentationCoordinator` if enabled
4. Auto-write discovered bins to brain
5. Validate bins, proceed

**Estimated Effort:** 1 day
**Complexity:** Low (orchestration only)

**Implementation outline:**
```python
# In system_initializer.py

if config.get('experimentation', {}).get('enabled_at_startup', False):
    print("Running experimentation phase...")
    coordinator = ExperimentationCoordinator(brain, env)
    discovered_bins = coordinator.discover_all_actions()

    # Update brain with discovered bins
    brain.update_action_bins(discovered_bins)

    print(f"Discovered bins: {discovered_bins}")

# Continue normal operation
```

**Success Criteria:**
- ✓ Config option respected
- ✓ Experimentation runs at startup if enabled
- ✓ Brain bins updated automatically
- ✓ System proceeds to normal operation
- ✓ No manual config editing needed

---

### Gap 4: Multi-Environment Testing ⚠️

**Impact:** Don't know if code truly works on other environments
**Status:** TrackMania ✓, Drone ⚠, Robot ⚠, Healthcare ⚠

**What to test:**
1. Drone (simulated) with different actions/feedbacks
2. Robot (simulated) with 2D navigation
3. Verify same code works with only config changes

**Test configs to create:**
```json
# configs/drone_test_config.json
{
    "environment": "generic",
    "actions": ["pitch", "roll", "yaw", "throttle"],
    "feedbacks": ["altitude", "velocity", "orientation_x/y/z"],
    "episode": {"max_frames": 5000}
}

# configs/robot_test_config.json
{
    "environment": "generic",
    "actions": ["forward", "turn"],
    "feedbacks": ["position_x", "position_y", "angle"],
    "episode": {"max_frames": 3000}
}
```

**Estimated Effort:** 2-3 days
**Complexity:** Medium (test environment setup)

**Success Criteria:**
- ✓ Drone config works with same code
- ✓ Robot config works with same code
- ✓ Graphs populate correctly
- ✓ Queries work identically
- ✓ No hardcoding differences needed

---

### Gap 5: Comprehensive Testing Suite ⚠️

**Impact:** Don't have confidence in all code paths
**Current:** Limited tests, mostly manual
**Needed:** Automated test suite

**Test files to create:**
```
tests/
├── test_config_system.py          # Config loading, validation
├── test_state_manager.py          # State tracking
├── test_action_discretizer.py     # Bin creation, combinations
├── test_knowledge_manager.py      # Graph operations, queries
├── test_query_system.py           # All query functions
├── test_intelligence_modules.py   # Each intelligence module
├── test_constraints.py            # Hard/soft constraint validation
├── test_pathfinding.py            # Once pathfinding implemented
├── test_experimentation.py        # Bin discovery
├── test_integration_e2e.py        # End-to-end scenarios
└── test_multi_environment.py      # Cross-environment
```

**Estimated Effort:** 2-3 days
**Complexity:** Low (straightforward test writing)

**Success Criteria:**
- ✓ 50+ automated tests
- ✓ All tests pass
- ✓ >80% code coverage
- ✓ CI/CD ready (if needed)

---

## Updated Work Phases

### Immediate (Next 1-2 Days): Fix Critical Gaps

#### Phase A: Path Planning Implementation 🔴 CRITICAL

**Deliverable:** `intelligence_planning.py` with pathfinding
- Dijkstra/A* algorithm over knowledge graph
- Constraint validation per action
- Graceful "path not found" handling
- Integration into system coordinator

**Success:** Can plan multi-step sequences

**Then:** Unlock Phase 4-5 requirements

---

#### Phase B: Steering Discovery & Experimentation Integration (1 Day)

**Deliverables:**
1. Symmetric bouncing algorithm for steering
2. Experimentation auto-integration at startup

**Success:** System auto-discovers all action bins on startup

---

### Near-Term (Days 3-5): Multi-Environment Validation

#### Phase C: Cross-Environment Testing (2-3 Days)

**Deliverables:**
1. Drone test config + validation
2. Robot test config + validation
3. Verification report (same code, 3 environments)

**Success:** Prove environment-agnostic architecture works

---

### Short-Term (Days 6-8): Robustness

#### Phase D: Comprehensive Test Suite (2-3 Days)

**Deliverables:**
1. 50+ automated tests covering all layers
2. >80% code coverage
3. CI/CD ready

**Success:** Production-grade test coverage

---

## Revised Timeline

| Phase | Work | Days | Status |
|-------|------|------|--------|
| **A** | Path Planning | 2-3 | 🔴 CRITICAL |
| **B** | Steering + Experimentation | 1 | ⚠️ Important |
| **C** | Multi-Environment Testing | 2-3 | ⚠️ Important |
| **D** | Test Suite | 2-3 | ✓ Good to have |
| **Total** | Complete System | **8-12 days** | Ready for research |

---

## What NOT to Touch (Already Done Right)

### ✓ Do NOT Rewrite:
1. Core Brain Capacity modules (solid)
2. Knowledge graphs (FalkorDB working)
3. Query system (correct implementation)
4. Configuration system (environment-agnostic)
5. Intelligence modules (Awareness, Repeat, Explore, etc.)
6. Environment adapters (truly generic)

### ✓ Preserve During Work:
- Existing test files (don't break them)
- FalkorDB setup (working, optimized)
- Module structure (clean separation of concerns)
- Disjoint action filtering (good feature)
- Per-frame node design (works well)

---

## Deliverables Checklist

### Phase A: Path Planning (2-3 days)

- [ ] `intelligence/intelligence_planning.py` created
- [ ] `PathfindingIntelligence` class with Dijkstra/A*
- [ ] Goal interval querying
- [ ] Constraint validation per action
- [ ] "Path not found" handling
- [ ] <100ms query performance
- [ ] Integration into `system_coordinator_corrected.py`
- [ ] Integration into `goal_orchestrator.py`
- [ ] Basic tests passing

### Phase B: Steering & Integration (1 day)

- [ ] Symmetric bouncing algorithm implemented
- [ ] `discover_steering()` function working
- [ ] Experimentation config option added
- [ ] Auto-startup integration working
- [ ] Bins auto-updated in brain
- [ ] No manual config editing needed

### Phase C: Multi-Environment (2-3 days)

- [ ] Drone config created and tested
- [ ] Robot config created and tested
- [ ] Same code verified on 3+ environments
- [ ] Cross-environment validation report written

### Phase D: Test Suite (2-3 days)

- [ ] 50+ automated tests
- [ ] All tests passing
- [ ] Coverage report >80%
- [ ] CI/CD ready

---

## Final Success Criteria (Production Ready)

✓ **Phase 1-3 Complete** (Configuration, Knowledge, Exploration)
✓ **Phase 4-5 Working** (Planning, Hierarchical)
✓ **Phase 6 Hardened** (Safety, Performance, Production)
✓ **Phase 7 Validated** (Multi-environment tested)

**System is PRODUCTION-READY when:**
1. All gaps fixed
2. Multi-environment tested
3. Test suite passing (>80% coverage)
4. Documentation updated
5. Ready for research publication/deployment

---

## Risk Mitigation

### Risk 1: Pathfinding Performance
- **Mitigation:** Use heuristic (A*), not just Dijkstra
- **Mitigation:** Graph pruning if >100K nodes
- **Mitigation:** Test with largest graphs from TrackMania

### Risk 2: Steering Discovery Fails
- **Mitigation:** Fall back to manual steering values
- **Mitigation:** Validate discovered bins before using

### Risk 3: Multi-Environment Config Issues
- **Mitigation:** Start with minimal configs (2 actions, 2 feedbacks)
- **Mitigation:** Validate each environment separately

### Risk 4: Test Suite Maintenance
- **Mitigation:** Keep tests simple, focused
- **Mitigation:** Mark sensitive tests (FalkorDB dependent)

---

## Next Immediate Action

**Start with Phase A: Path Planning**

1. Read: `intelligence/intelligence_repeat.py` (similar structure)
2. Create: `intelligence/intelligence_planning.py`
3. Implement: Dijkstra/A* over knowledge graph
4. Test: Manual verification with simple examples
5. Integrate: Add to `system_coordinator_corrected.py`

**Estimated:** 2-3 days of focused work

---

*Roadmap updated: 2026-02-16*
*Based on 70% implementation analysis*
