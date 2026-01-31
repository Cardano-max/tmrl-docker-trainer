# Architecture

**Analysis Date:** 2026-01-31

## Pattern Overview

**Overall:** Four-Layer Capacity-Knowledge-Intelligence (CKI) Framework

**Key Characteristics:**
- Layer 1 (CAPACITY): What system CAN do - atomic capabilities without decision-making
- Layer 2 (KNOWLEDGE): What system KNOWS - passive storage (knowledge graphs, memory, state)
- Layer 3 (INTELLIGENCE): How system USES capacity + knowledge - decision modules that answer questions
- Layer 4 (ENVIRONMENT): Separate concern - isolated in adapters, never integrated into system logic

**Supervisor's Core Principle (from meeting transcripts):**
"Capacity is the allowance of the system to do something. Brain capacity is not to answer. Who answers is intelligence."

## Layers

**Layer 1: BRAIN CAPACITY**
- Purpose: Provides atomic capabilities the system can execute. Each capacity = ONE thing system can DO (not answer).
- Location: `core/brain_capacity.py`, `core/brain_core.py`
- Contains:
  - Sensory capacities: `sense_speed()`, `sense_gear()`, `sense_rpm()`, `sense_all()`
  - Motor capacities: `act_gas()`, `act_brake()`, `act_steer()`, `act_release()`, `act_combined()`
  - Discretization capacities: `discretize_action()`, `discretize_feedback()`, `discretize_state()`
  - Knowledge capacities: `store_transition()`, `query_transition()`, `query_tried_count()`, `query_untried()`
  - Action space capacities: `get_valid_actions()`, `get_action_count()`, `get_no_action()`
  - Connection capacities: `connect()`, `disconnect()`, `is_connected()`
- Depends on: FalkorDB (for knowledge queries), environment adapters
- Used by: Intelligence modules, system coordinator

**Layer 2: KNOWLEDGE (Passive Storage)**
- Purpose: Store both prior and acquired knowledge without making decisions
- Locations:
  - `core/state_manager.py`: State tracking (StateVector = combination of all graph node positions)
  - `knowledge/knowledge_manager.py`: Per-frame knowledge graphs (FalkorDB-backed)
  - `knowledge/memory_handler.py`: Short-term memory (recent episodes, actions) + long-term memory (FalkorDB)
- Knowledge Types:
  - **Prior Knowledge**: From config (actions, feedbacks, disjoint rules) - human-provided, fixed
  - **Acquired Knowledge**: From experience (bins, transitions, state mappings) - system-discovered through experimentation
- Key Data Structures:
  - Knowledge graphs: One node per frame, edges with action values: `Frame:0 --[ACTION {gas:0.5}]--> Frame:1`
  - State vector: Dict of graph positions representing "where am I in all graphs"
  - Bins: Min/max ranges for each action (ACQUIRED through experimentation, not from config)
- Depends on: FalkorDB, configuration
- Used by: Intelligence modules for queries and awareness checks

**Layer 3: INTELLIGENCE (Decision Making)**
- Purpose: Interpret capacity + knowledge to answer "what should I do?" - always returns a decision
- Locations: `intelligence/` directory
- Modules (each is ONE type of intelligence):
  - `intelligence_awareness.py`: Compares internal model (knowledge) vs external reality (sensors). Detects when car is on ice (motor turned but position unchanged).
  - `intelligence_explore.py`: Finds untried actions from current state. Returns valid action respecting disjoint rules.
  - `intelligence_repeat.py`: Recreates previous episodes by querying knowledge graph for exact frame sequences.
  - `intelligence_monitor.py`: Range monitoring - detects when state drifts outside constraints.
  - `intelligence_future_constraints.py`: Predicts if action will violate hard/soft constraints. Answers "is this safe?"
  - `intelligence_experimentation.py`: Automatic bin discovery using order-of-magnitude search. Runs on startup as capacity validation.
- Entry point pattern: `decide_action(feedbacks: Dict) -> Optional[Dict]`
- Depends on: Brain capacity, knowledge manager, state manager
- Used by: System coordinator and goal orchestrator

**Layer 4: ENVIRONMENT (Isolated)**
- Purpose: Handle all environment-specific code without affecting system logic
- Location: `adapters/` directory
- Contains:
  - `adapters/tmrl_adapter.py`: TrackMania/TMRL data extraction
  - `adapters/tmrl_live_adapter.py`: Live TCP/socket communication
  - `adapters/live_validation.py`: Validation for live mode
- Key abstraction: `EnvironmentAdapter` - abstract interface ensuring ANY environment can plug in
- Depends on: Nothing from core system
- Used by: System coordinator only (via EnvironmentBridge)

## Data Flow

**INITIALIZATION FLOW:**
```
1. System reads config (prior knowledge: actions, feedbacks, disjoint rules)
2. Connect to FalkorDB and environment
3. Check if previous knowledge exists (knowledge graphs in DB)
   - YES → Load and skip experimentation
   - NO → Continue to step 4
4. Validate config (test that actions/feedbacks are valid)
5. Run experimentation (ExperimentationIntelligence discovers bins)
   - For each action: find minimum and maximum that cause change
   - System defines bins from min/max ratio
6. Initialize all knowledge graphs (one per feedback)
7. System ready for episodes
```

**EPISODE EXECUTION FLOW:**
```
1. Initialize episode (episode controller)
2. Loop until episode end condition:
   a. Read feedbacks from environment (sensory capacity)
   b. Update state manager (current state = all graph node positions)
   c. Awareness check: Does knowledge match reality?
   d. Choose goal (goal orchestrator - what are we trying to achieve?)
   e. Intelligence decision: What action achieves goal?
      - ExplorationIntelligence: "Try untried actions"
      - RepeatEpisodeIntelligence: "Repeat previous episode"
      - Other intelligences: domain-specific reasoning
   f. Validate action against constraints (FutureConstraintsIntelligence)
   g. Send action to environment (motor capacity)
   h. Record transition to knowledge graph (capacity)
3. End episode when:
   - Frame limit reached
   - Time limit reached
   - Environment signals failure (collision, off-track)
   - System detects no progress (stuck)
```

**FRAME-LEVEL SYNCHRONIZATION:**
- Frame duration comes from config (e.g., 50ms for TMRL)
- Environment FPS determines what frame timing is valid
- CRITICAL: If control cadence doesn't match environment FPS, actions may span multiple game frames
- Each iteration sends ONE action, reads ONE feedback, stores ONE transition

## State Management

**StateVector = Current Position in All Graphs:**
```python
StateVector {
  graph_positions: {
    'speed': 45.3,        # Current position in speed graph
    'gear': 3.0,          # Current position in gear graph
    'rpm': 5200.0         # Current position in rpm graph
  },
  timestamp: 1706745600.123,
  frame: 1542
}
```

**State Transitions:**
```
Previous State → [ACTION applied] → Current State
State(frame=100, speed=0.0) → [gas=0.5] → State(frame=101, speed=15.3)
Recorded as: Frame:100 --[ACTION {gas:0.5, brake:0.0, steer:0.0}]--> Frame:101
```

## Key Abstractions

**BrainArchitecture (core/brain_core.py):**
- Purpose: Facade for all brain capacities
- Provides: Query interface for intelligence modules
- Example: `brain.query_untried(current_state)` → returns actions never tried from this state
- Pattern: Each capacity is registered in a registry for dynamic lookup

**DisjointActionValidator (core/brain_core.py):**
- Purpose: Enforces action constraints from ontology
- Rule: Actions marked "disjoint" cannot both be active (non-NONE)
- Example: `gas disjoint brake` → cannot accelerate AND brake simultaneously
- Used by: Action discretizer to filter valid combinations

**ActionDiscretizer (core/brain_core.py):**
- Purpose: Convert continuous actions to discrete bins
- Bins are ACQUIRED knowledge (discovered via experimentation)
- Maps: `gas=0.567 → bin="MED"` based on discovered min/max ranges
- Handles: Disjoint filtering, caching of valid combinations

**EnvironmentBridge (control/environment_protocol.py):**
- Purpose: Decouple system from environment implementation
- Abstracts: How to send actions, read feedbacks, detect episodes
- Allows: Swapping environments without touching system logic
- Protocol: Direct call (in-process) or TCP socket (live mode)

**Goal (control/goal_orchestrator.py):**
- Purpose: Define what system is trying to achieve
- Types:
  - OPEN_ENDED: Run for N frames or until time limit (exploration)
  - CLOSED_ENDED: Run until state constraint is satisfied (e.g., reach 60 km/h)
- Contains: Constraints, priority, success conditions
- SUPERVISOR: "There's no reward, there's no policy. There's goals. There's constraints."

**EpisodeController (control/episode_controller.py):**
- Purpose: System-owned episode management (NOT environment-owned)
- Responsibilities:
  - Track frames and time
  - Detect end conditions (limit, failure, stuck)
  - Manage episode lifecycle
- END REASONS: frame_limit, time_limit, env_failure, system_stuck, goal_achieved, user_requested, error

## Entry Points

**System Initialization: `control/system_initializer.py`**
- Called by: User or orchestrator
- Triggers: `SystemInitializer.initialize()`
- Responsibilities:
  1. Load config
  2. Connect to FalkorDB and environment
  3. Check prior knowledge
  4. Run validation and experimentation (if no prior knowledge)
  5. Initialize all systems
- Output: `InitializationResult` with success status and bins acquired

**Episode Execution: `control/system_coordinator_corrected.py`**
- Called by: User or orchestrator after initialization
- Main class: `SystemCoordinator`
- Triggers: `SystemCoordinator.run_episode(goal: Goal)`
- Responsibilities:
  1. Create episode
  2. Loop: read feedback → awareness → intelligence → action → record
  3. Track end condition
  4. Return episode summary
- Output: `EpisodeSummary` with transitions, states visited, actions tried

**Frame-Level Action Dispatch: `control/frame_action_controller.py`**
- Called by: System coordinator on each frame
- Main class: `FrameActionController`
- Triggers: `FrameActionController.execute_action_for_iterations(action, num_iterations)`
- Responsibilities:
  1. Send action to environment
  2. Read feedback before and after
  3. Record iteration result
- Output: `ActionSequenceResult` with list of iterations

## Error Handling

**Strategy:** Layered error handling with supervisor supervision

**Error Types (utils/exceptions.py):**
- `SystemException`: Core system errors (initialization, coordination)
- `ConfigurationError`: Invalid config (wrong action ranges, missing feedbacks)
- `BrainCapacityError`: Capacity execution failed (query failed, action invalid)
- `IntelligenceError`: Intelligence module error (decision making failed)
- `GraphOperationError`: FalkorDB query error
- `StateNotFoundError`: State vector not found in memory
- `ValidationError`: Input validation failed

**Patterns:**
- Exceptions bubble up from capacity → intelligence → coordinator
- Coordinator catches and decides: retry, skip, abort episode
- All exceptions logged with context (frame, state, action attempted)
- Supervisor principle: "If something is wrong, fail fast and loudly"

## Cross-Cutting Concerns

**Logging:**
- Framework: Python `logging` module
- Pattern: Module-specific loggers with [LAYER] prefixes
  - `[BRAIN]` for capacity operations
  - `[INTELLIGENCE:*]` for intelligence modules
  - `[CONTROL]` for orchestration
- Levels: DEBUG (detailed), INFO (flow), WARNING (anomalies), ERROR (failures)

**Validation:**
- Capacity layer: Input validation before execution (InputValidator)
- Intelligence layer: Output validation (is decision valid?)
- Config layer: Schema validation on startup (ConfigValidator)
- Disjoint validation: Every action combination checked before returning

**Authentication/Authorization:**
- Not applicable - system is autonomous once initialized
- Environment connection requires credentials (stored in config/env vars)
- FalkorDB connection authenticated via password (config)

**Timing/Synchronization:**
- Frame timing from config: `environment.timing.frame_duration_ms`
- Environment FPS drives all timing (SUPERVISOR: "Environment determines timing")
- Control loop cadence must be integer multiple of frame duration or no synchronization
- Timestamp manager tracks frame clock separate from wall clock

**State Transitions:**
- Every frame produces ONE transition: `(previous_state, action, current_state)`
- Stored immediately to knowledge graph
- Used by awareness intelligence to detect anomalies
- Used by exploration to find untried transitions

**Bin Discovery (Experimentation):**
- Runs during initialization (capacity validation phase)
- Uses order-of-magnitude search: 10^0, 10^-1, 10^-2, etc.
- Finds minimum action that causes measurable change
- Finds maximum action below saturation point
- Ratio min/max determines number of bins
- ACQUIRED KNOWLEDGE - not from config, discovered by system

---

*Architecture analysis: 2026-01-31*
*Framework: Capacity-Knowledge-Intelligence (CKI) per Dr. Richard Sutton*
*Source: Meeting transcripts in archive/meeting_transcripts/ and archive/new_meeing_transcripts/*
