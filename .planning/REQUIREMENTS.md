# Requirements: Intelligent Agent Architecture (MPC-RL Hybrid)

**Defined:** 2026-02-16 (Deep transcription analysis)
**Core Value:** Enable safe, goal-based autonomous learning that scales hierarchically

---

## v1 Requirements (Foundation: Brain Capacity + Knowledge Acquisition)

### Configuration System

- [ ] **CONFIG-01**: System reads JSON configuration file defining action names, action bin ranges, action constraints
- [ ] **CONFIG-02**: System reads JSON configuration file defining environment feedback types (position, velocity, etc.) and their units
- [ ] **CONFIG-03**: System validates configuration completeness (all required fields present, no contradictions)
- [ ] **CONFIG-04**: System is environment-agnostic (same code runs with different configs for TrackMania/drone/robot)
- [ ] **CONFIG-05**: Configuration defines hard vs soft constraints for each action

### State Management

- [ ] **STATE-01**: System tracks current state as dictionary of all feedback values at current frame
- [ ] **STATE-02**: System maintains previous state pointer (for detecting discontinuities)
- [ ] **STATE-03**: System maintains history buffer (last 100 states minimum)
- [ ] **STATE-04**: System records state timestamp (both environment frame and system clock)
- [ ] **STATE-05**: System detects state discontinuities (e.g., robot teleported between episodes)
- [ ] **STATE-06**: State vector can be converted to hash for fast comparison

### Action Discretization

- [ ] **ACTION-01**: System reads continuous action ranges from config and creates discrete bins (e.g., gas: 0-1 → low/medium/high)
- [ ] **ACTION-02**: System generates all possible action combinations (e.g., gas+left, brake+right)
- [ ] **ACTION-03**: System enforces action constraints (e.g., cannot accelerate > 100 km/h)
- [ ] **ACTION-04**: System differentiates hard constraints (system stops) vs soft constraints (warning)
- [ ] **ACTION-05**: System represents discrete actions by name, not index (human-readable graph edges)

### Knowledge Graph Foundation

- [ ] **GRAPH-01**: For each state variable (position, velocity, etc.), system creates empty graph at initialization
- [ ] **GRAPH-02**: Graph nodes represent state intervals (e.g., position node = "40-45 meters")
- [ ] **GRAPH-03**: Graph edges represent state transitions via specific actions
- [ ] **GRAPH-04**: Graph edges are labeled with action names and bins (e.g., "gas→high", "brake→medium")
- [ ] **GRAPH-05**: System stores graph nodes as: [min_value, max_value, properties_dict]
- [ ] **GRAPH-06**: System stores graph edges as: [from_node_id, to_node_id, action_name, action_bin, timestamp]

### State Recording During Episodes

- [ ] **RECORD-01**: At each frame, system observes all state variable values from environment
- [ ] **RECORD-02**: For each state variable, system queries knowledge graph: "Is there a node for this value?"
- [ ] **RECORD-03**: If node exists, system records transition: previous_state → current_state via action
- [ ] **RECORD-04**: If node doesn't exist, system creates new node with interval and records transition
- [ ] **RECORD-05**: All edges are labeled with the action that caused the transition (from config)
- [ ] **RECORD-06**: System handles simultaneous multi-variable transitions (e.g., gas affects both velocity AND position)
- [ ] **RECORD-07**: Episode data is persisted after episode ends (not lost on restart)

### Knowledge Graph Querying

- [ ] **QUERY-01**: System can retrieve node given state value (e.g., "Is position 42.5 in a known node?")
- [ ] **QUERY-02**: System can list all edges from a node (all tried actions)
- [ ] **QUERY-03**: System can list all edges not yet tried from a node
- [ ] **QUERY-04**: System can retrieve transition history for a state (which actions led here)
- [ ] **QUERY-05**: Query operations complete in <100ms (performance requirement)

### Data Input vs Data Knowledge

- [ ] **KNOWLEDGE-01**: System distinguishes data inputs (raw sensor values) from derived knowledge (position→velocity via math)
- [ ] **KNOWLEDGE-02**: System can deduce velocity from position + time without separate graph
- [ ] **KNOWLEDGE-03**: System can deduce acceleration from velocity + time without separate graph
- [ ] **KNOWLEDGE-04**: User specifies which variables are inputs vs derived (reduces graph explosion)

### Multi-Episode Memory

- [ ] **MEMORY-01**: System retains all knowledge graphs across episodes
- [ ] **MEMORY-02**: System can replay previous episode exactly (given episode ID)
- [ ] **MEMORY-03**: System can extract successful trajectories from past episodes
- [ ] **MEMORY-04**: Old episodes can be archived/compressed (configurable retention)

---

## v2 Requirements (Intelligence Layer: Planning, Exploration, Hierarchical Control)

### Exploration Intelligence

- [ ] **EXPLORE-01**: System identifies untried actions at a given state node
- [ ] **EXPLORE-02**: System performs depth-first search: try untried actions before moving to new nodes
- [ ] **EXPLORE-03**: System tracks which actions have been tried (combination count matching max combinations)
- [ ] **EXPLORE-04**: System handles n-ary action combinations (not just pairwise)

### Planning Intelligence

- [ ] **PLAN-01**: User specifies goal as interval (e.g., position 50-60, velocity 20-30)
- [ ] **PLAN-02**: System finds path through graph from current node to goal node
- [ ] **PLAN-03**: System returns sequence of actions to reach goal
- [ ] **PLAN-04**: System validates path satisfies all constraints (hard/soft)
- [ ] **PLAN-05**: System handles "path not found" gracefully (returns safe fallback action or stops)

### Dynamic Constraint Intervals

- [ ] **DCONST-01**: System defines interval for each goal (e.g., position must be 50-60)
- [ ] **DCONST-02**: System calculates distance from current state to interval
- [ ] **DCONST-03**: System adjusts planning frequency (timestep) based on distance-to-goal
- [ ] **DCONST-04**: Closer to boundary = faster replanning (higher frequency)

### Hierarchical Goal Composition

- [ ] **HIER-01**: System composes multiple constraints: goal_1 ∩ goal_2 ∩ goal_3 = compound goal
- [ ] **HIER-02**: System decomposes compound goal into subgoals
- [ ] **HIER-03**: System plans at multiple levels (move to position THEN adjust velocity)
- [ ] **HIER-04**: Each level respects constraints of parent level

### Repetition Intelligence (Copy Last Episode)

- [ ] **REPEAT-01**: System can extract successful trajectory from previous episode
- [ ] **REPEAT-02**: System replays trajectory by following same action sequence
- [ ] **REPEAT-03**: If state is unknown, system flags and explores

---

## v3 Requirements (Safety, Production Hardening)

### Safety Constraints

- [ ] **SAFETY-01**: Hard constraints are never violated (system stops if violated)
- [ ] **SAFETY-02**: Soft constraints trigger warnings but allow action
- [ ] **SAFETY-03**: Graceful failure: if no valid action, system defaults to safe state
- [ ] **SAFETY-04**: Real-world mode differs from simulation (learning constraints are stricter in real world)

### Performance & Scalability

- [ ] **PERF-01**: System handles 100+ independent state variables
- [ ] **PERF-02**: System handles 1000+ action combinations
- [ ] **PERF-03**: Query response <100ms for any operation
- [ ] **PERF-04**: Memory usage bounded (configurable history retention)

### Production Features

- [ ] **PROD-01**: Comprehensive logging of all state-action transitions
- [ ] **PROD-02**: System can export graphs for analysis/visualization
- [ ] **PROD-03**: System can import pre-trained graphs
- [ ] **PROD-04**: Monitoring/health checks for graph integrity
- [ ] **PROD-05**: Rollback capability (revert to previous graph state)

---

## Out of Scope

| Feature | Reason |
|---------|--------|
| Neural network training during execution | Knowledge graphs are explicit, not learned models |
| Reward functions (traditional RL) | Goal/constraint-based system, not reward-based |
| Multi-agent coordination | Single-agent focus for foundation layer |
| Real-time GPU acceleration | CPU-first, can optimize later |
| Automatic action/feedback discovery | User specifies in config (safety-critical) |

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CONFIG-01 | Phase 1 | Pending |
| CONFIG-02 | Phase 1 | Pending |
| CONFIG-03 | Phase 1 | Pending |
| CONFIG-04 | Phase 1 | Pending |
| CONFIG-05 | Phase 1 | Pending |
| STATE-01 | Phase 1 | Pending |
| STATE-02 | Phase 1 | Pending |
| STATE-03 | Phase 1 | Pending |
| STATE-04 | Phase 1 | Pending |
| STATE-05 | Phase 1 | Pending |
| STATE-06 | Phase 1 | Pending |
| ACTION-01 | Phase 1 | Pending |
| ACTION-02 | Phase 1 | Pending |
| ACTION-03 | Phase 1 | Pending |
| ACTION-04 | Phase 1 | Pending |
| ACTION-05 | Phase 1 | Pending |
| GRAPH-01 | Phase 2 | Pending |
| GRAPH-02 | Phase 2 | Pending |
| GRAPH-03 | Phase 2 | Pending |
| GRAPH-04 | Phase 2 | Pending |
| GRAPH-05 | Phase 2 | Pending |
| GRAPH-06 | Phase 2 | Pending |
| RECORD-01 | Phase 2 | Pending |
| RECORD-02 | Phase 2 | Pending |
| RECORD-03 | Phase 2 | Pending |
| RECORD-04 | Phase 2 | Pending |
| RECORD-05 | Phase 2 | Pending |
| RECORD-06 | Phase 2 | Pending |
| RECORD-07 | Phase 2 | Pending |
| QUERY-01 | Phase 2 | Pending |
| QUERY-02 | Phase 2 | Pending |
| QUERY-03 | Phase 2 | Pending |
| QUERY-04 | Phase 2 | Pending |
| QUERY-05 | Phase 2 | Pending |
| KNOWLEDGE-01 | Phase 2 | Pending |
| KNOWLEDGE-02 | Phase 2 | Pending |
| KNOWLEDGE-03 | Phase 2 | Pending |
| KNOWLEDGE-04 | Phase 2 | Pending |
| MEMORY-01 | Phase 2 | Pending |
| MEMORY-02 | Phase 2 | Pending |
| MEMORY-03 | Phase 2 | Pending |
| MEMORY-04 | Phase 2 | Pending |
| EXPLORE-01 | Phase 3 | Pending |
| EXPLORE-02 | Phase 3 | Pending |
| EXPLORE-03 | Phase 3 | Pending |
| EXPLORE-04 | Phase 3 | Pending |
| PLAN-01 | Phase 4 | Pending |
| PLAN-02 | Phase 4 | Pending |
| PLAN-03 | Phase 4 | Pending |
| PLAN-04 | Phase 4 | Pending |
| PLAN-05 | Phase 4 | Pending |
| DCONST-01 | Phase 4 | Pending |
| DCONST-02 | Phase 4 | Pending |
| DCONST-03 | Phase 4 | Pending |
| DCONST-04 | Phase 4 | Pending |
| HIER-01 | Phase 5 | Pending |
| HIER-02 | Phase 5 | Pending |
| HIER-03 | Phase 5 | Pending |
| HIER-04 | Phase 5 | Pending |
| REPEAT-01 | Phase 3 | Pending |
| REPEAT-02 | Phase 3 | Pending |
| REPEAT-03 | Phase 3 | Pending |
| SAFETY-01 | Phase 6 | Pending |
| SAFETY-02 | Phase 6 | Pending |
| SAFETY-03 | Phase 6 | Pending |
| SAFETY-04 | Phase 6 | Pending |
| PERF-01 | Phase 6 | Pending |
| PERF-02 | Phase 6 | Pending |
| PERF-03 | Phase 6 | Pending |
| PERF-04 | Phase 6 | Pending |
| PROD-01 | Phase 7 | Pending |
| PROD-02 | Phase 7 | Pending |
| PROD-03 | Phase 7 | Pending |
| PROD-04 | Phase 7 | Pending |
| PROD-05 | Phase 7 | Pending |

**Coverage:**
- v1 requirements: 48 total
- v2 requirements: 14 total
- v3 requirements: 14 total
- **Total: 76 requirements**
- Mapped to phases: 76
- Unmapped: 0 ✓

---

*Requirements defined: 2026-02-16*
*Last updated: 2026-02-16 after comprehensive transcription analysis*
