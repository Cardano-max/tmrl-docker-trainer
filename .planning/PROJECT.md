# Intelligent Agent Architecture: MPC-RL Hybrid System

## What This Is

A modular, environment-agnostic intelligent agent system that combines Model Predictive Control and Reinforcement Learning to enable autonomous agents (robots, autonomous vehicles, etc.) to learn from experience while respecting hard safety constraints. Unlike traditional RL that relies on reward signals, this system uses goal-based planning with dynamic constraint intervals, learning what actions affect which state variables, and building multi-layered hierarchical intelligence through knowledge graphs.

**Current Milestone**: v1.0 Full Sutton Pipeline
**Target Environments**: TMNF + TMInterface (primary), TM2020 (compat)
**Nature**: Research implementation -- Dr. Sutton provides theory in meeting transcripts, we implement the engineering exactly as specified

## Core Value

**Enable safe, goal-based autonomous learning that scales hierarchically** — The system must be able to learn optimal action sequences within constrained intervals rather than through trial-and-error reward seeking, making it applicable to life-critical domains where failure is not an option.

## Architecture Vision (from Dr. Sutton meetings)

### Three Fundamental Layers

1. **Brain Capacity** — The foundational processing architecture
   - Configuration-driven initialization (JSON/YAML, environment-agnostic)
   - State tracking: current state, previous state, full history
   - Action discretization: continuous → discrete bins with constraints
   - Knowledge graph generation: one graph per state variable
   - State-action relationship recording: explicit edges with discrete action labels
   - Query system: retrieve state nodes, find attempted/untried actions

2. **Knowledge** — Data acquired through brain capacity
   - Populated knowledge graphs with state nodes as intervals
   - Action relationships (edges) labeled with specific action names and bins
   - State transitions recorded with timestamps (system and environment)
   - Memory of all previous episodes and trajectories
   - Independent variable graphs linked through multi-variable goals

3. **Intelligence** — How the system uses knowledge
   - **Exploration Intelligence**: Try untested action combinations at each state node
   - **Planning Intelligence**: Find optimal path through graph to reach goal states
   - **Repetition Intelligence**: Replay successful trajectories from previous episodes
   - **Hierarchical Intelligence**: Compose smaller goals into larger goals (per Dr. Sutton's vacuum robot analogy)
   - **Constraint Validation**: Verify sequences stay within hard/soft constraint intervals

### Key Conceptual Breakthroughs

**From Meeting 2 & 3: Goal-Based Constraints vs Reward Functions**
- Traditional RL: Model learns to maximize rewards (can cheat/exploit)
- Our System: Model operates within constrained intervals (cannot violate rules)
- Human analogy: Don't learn from falling off a cliff; learn the cliff boundary first

**From Meeting 4: Data Input vs Data Knowledge**
- **Data Input**: Raw sensor values (LIDAR distances, position coordinates)
- **Data Knowledge**: Derived information (speed = Δposition/Δtime, acceleration = Δspeed/Δtime)
- System learns which inputs are independent, derives knowledge from them
- Reduces graph explosion while maintaining full expressiveness

**From Meeting 3-4: Modular Intelligence = Search Algorithm**
- Brain capacity creates state space graph
- Exploration = depth-first search for untested actions per node
- No reward function needed for exploration phase
- Reward/goals come later as constraint intervals

**From Meetings 4-5: Hierarchical Multi-Variable Control**
- Each state variable gets separate graph (position, velocity, acceleration, distance-to-obstacle, traffic-light-state)
- Actions affect different subsets of graphs
- High-level goals = combinations of intervals on multiple graphs
- System can plan complex sequences respecting all constraints simultaneously

## Requirements

## Current Milestone: v1.0 Full Sutton Pipeline

**Goal:** Implement the complete system specified across all 6 Sutton meeting transcripts -- from brain capacity micro-processes through knowledge graphs, exploration, planning, and hierarchical intelligence -- running on TMNF with deterministic rewind.

**What shipped (Phase A):**
- Bin discovery algorithm (downward sweep, MAX/MIN binary search)
- Precision discovery (system-measured, not assumed)
- Deterministic probing via TMNF + TMInterface TCP bridge
- Gas: 2 bins, Brake: 2 bins, Steering: 201 bins (stable 3/3 runs)
- 9/9 live rubrics, 12/12 offline tests passing

**Target features (this milestone):**
- Auto-startup integration (system won't start before bins acquired)
- Brain capacity micro-processes (send/perform/record action, receive/collect/record feedback, query graph)
- Per-variable knowledge graphs with no-duplicate-node semantics
- Per-frame state-action recording across all graphs simultaneously
- Exploration intelligence (untried action discovery, depth-first search)
- Awareness (environment state vs internal state comparison)
- Planning/MPC (pathfinding through graph, goal intervals, dynamic timestep)
- Hierarchical intelligence (goal composition, multi-level planning)
- Multiplicity testing (intermediates between MIN and MAX)

**Authoritative sources:**
- `archive/meeting_transcripts/algorithm_spec_from_meetings.md`
- `archive/meeting_transcripts/Authoratative_law_from_Jan2026_meetings.md`
- 6 individual meeting transcripts (Jan 9, 15, 24, 31x2, Feb 16)

### Validated

- [x] **REQ-01 to REQ-25** from Authoritative Law document (Phase A bin discovery)
- [x] Precision discovery (REQ-15, REQ-16)
- [x] Bidirectional steering (REQ-25)
- [x] Per-frame probing (REQ-01, REQ-03, REQ-21)
- [x] No noise/no interference (REQ-23, Section 3-4 of spec)

### Active (Core Implementations Needed)

**PHASE 1: Brain Capacity Foundation**
- [ ] Configuration System (JSON-based, env-agnostic)
- [ ] State Variable Manager (tracks current/previous/history)
- [ ] Action Discretizer (continuous→discrete with bins & constraints)
- [ ] Knowledge Graph Infrastructure (per-variable graph storage & querying)
- [ ] State-Action Recording (populate graphs with transitions)

**PHASE 2: Knowledge Base Layer**
- [ ] Multi-Graph Coordination (handle independent variables)
- [ ] State Node Creation (interval-based discretization)
- [ ] Edge Labeling (explicit action names from config)
- [ ] Transition Memory (episode-based trajectory storage)
- [ ] Query Optimization (fast state lookup in intervals)

**PHASE 3: Exploration Intelligence**
- [ ] Untried Action Discovery (find actions not yet performed at node)
- [ ] Combination Generation (handle n-ary action combinations)
- [ ] Exploration Heuristics (decide which untried action to try)
- [ ] Episode Loop Integration (episode start/end handling)

**PHASE 4: Planning Intelligence**
- [ ] Pathfinding in Multi-Graph (traverse graphs respecting constraints)
- [ ] Goal Definition Interface (specify desired intervals)
- [ ] Goal-to-Path Translation (convert goals to action sequences)
- [ ] Constraint Validation (verify paths satisfy hard/soft constraints)

**PHASE 5: Hierarchical Intelligence**
- [ ] Goal Composition (combine simple goals into complex goals)
- [ ] Dynamic Timestamping (adjust frequency based on distance-to-goal)
- [ ] Multi-Level Planning (decompose goal hierarchically)
- [ ] Inter-Level Communication (how level N influences level N+1)

**PHASE 6: Safety & Production Hardening**
- [ ] Hard/Soft Constraint Differentiation (stop vs update bounds)
- [ ] Simulation vs Real-World Modes (learning constraints differ)
- [ ] Graceful Degradation (behavior when no path found)
- [ ] Performance Optimization (scale to 100+ variables)

**PHASE 7: Integration & Deployment**
- [ ] End-to-End System Testing
- [ ] Multi-Environment Validation (TrackMania → Drone → Robot)
- [ ] Production Monitoring & Logging
- [ ] Documentation & Formalization (ready for publication)

### Out of Scope

- GPU acceleration (CPU-first implementation)
- Real-time neural network training during execution (graphs are data structures, not learned models)
- Reward shaping or traditional RL loss functions
- Communication between independent agents (single-agent focus for now)
- Mobile/edge deployment (research first, deployment later)

## Context

**Research Lineage**: Dr. Richard Sutton (RL pioneer) has identified a fundamental limitation in traditional RL — agents learn through failure, which is unacceptable in safety-critical domains. This research implements Sutton's vision of goal-based, constraint-respecting learning using knowledge graphs to isolate state variables.

**Prior Art Reviewed**: Model Predictive Control (for planning), Markov Decision Processes (for state representation), reinforcement learning (for adaptability), knowledge graphs (for structure).

**Current Codebase State** (from mapping):
- Basic reinforcement learning framework exists (trainer, worker, server architecture)
- Docker infrastructure established
- Some state tracking implemented
- Action handling partially complete
- FalkorDB graph database options explored

**Key Challenges Identified**:
- Isolating independent state variables (not all variables should be separate graphs)
- Handling continuous values without infinite node explosion (discretization strategy)
- Maintaining expressiveness while keeping graphs queryable
- Scaling to 100+ state variables and 1000+ action combinations
- Real-world deployment where "episode zero" is not reset

## Constraints

- **Architecture**: Modular, environment-agnostic (config-driven, not hardcoded)
- **Type Safety**: Must support any sensor type and action space
- **Performance**: Query response <100ms for graph operations
- **Scalability**: Handle 100+ independent state variables, 1000+ action combinations
- **Safety**: Hard constraints must never be violated; graceful failure on path-not-found
- **Generality**: Same codebase runs on TrackMania, drones, robots, healthcare systems with only config changes

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Knowledge graphs over neural networks | Interpretable, queryable, no training instability | Decision locked: Use FalkorDB or graph library |
| Separate graphs per state variable | Reveals action dependencies, reduces coupling | Decision locked: Must derive knowledge where possible |
| Config-driven over hardcoded | Must be production-ready for multiple domains | Decision locked: All actions/feedbacks from JSON |
| Discrete bins over continuous values | Prevents infinite node explosion, enables interval-based planning | Decision locked: User defines bin sizes in config |
| Goal constraints over reward signals | Enables safety-first learning | Decision locked: Planning based on state intervals, not reward functions |
| Hierarchical composition planned early | Will solve scaling problem for real-world systems | Pending: Needs Phase 5 implementation to validate |

---

**Last updated: 2026-02-26 -- Milestone v1.0 started (Full Sutton Pipeline)**
