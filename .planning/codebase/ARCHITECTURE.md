# Architecture

**Analysis Date:** 2026-02-16

## Pattern Overview

**Overall:** 3-Layer Real Intelligence System with Goal-Driven Orchestration

**Key Characteristics:**
- **Layer 1 (Core)**: Brain Capacity - what the system CAN do (actions, state representation)
- **Layer 2 (Knowledge)**: Knowledge Graphs - what the system KNOWS (per-frame observations, transitions)
- **Layer 3 (Intelligence)**: Intelligence Modules - how the system USES capacity and knowledge to reason
- **Layer 4 (Control)**: System Orchestration - goal-driven coordination of intelligence modules and episodes
- **Environment Adapters**: Isolated environment-specific code (TrackMania/TMRL)

This is an **environment-agnostic** architecture following Dr. Richard Sutton's framework where the system owns learning and decision-making, not reward/policy-based agents.

## Layers

**Layer 1 - Brain Capacity (Core):**
- Purpose: Defines what actions the system CAN perform and what states it can represent
- Location: `core/`
- Contains:
  - `brain_core.py`: BrainArchitecture - orchestrates capacity components
  - `brain_capacity.py`: ActionDiscretizer (bins), DisjointActionValidator, action combinations
  - `state_manager.py`: StateVector (state representation as node positions from all graphs)
- Depends on: Validators, exceptions
- Used by: System Coordinator, Intelligence modules

**Layer 2 - Knowledge (Knowledge Graphs):**
- Purpose: Records per-frame observations and action-state transitions without discretization
- Location: `knowledge/`
- Contains:
  - `knowledge_manager.py`: KnowledgeManager - manages FalkorDB graphs, stores Frame nodes and ACTION edges
  - `memory_handler.py`: MemoryHandler - short-term memory of recent transitions
- Key concept: One node PER FRAME (not discretized intervals), stores ACTUAL observed values
- Depends on: FalkorDB, State Manager
- Used by: Intelligence modules (awareness, monitoring, exploration)

**Layer 3 - Intelligence (Decision-Making Modules):**
- Purpose: Multiple specialized intelligence modules that reason about actions using capacity and knowledge
- Location: `intelligence/`
- Contains:
  - `intelligence_awareness.py`: AwarenessIntelligence - compares predicted vs actual state
  - `intelligence_experimentation.py`: ExperimentationIntelligence - discovers action effects and bins
  - `intelligence_explore.py`: ExplorationIntelligence - systematic state-space exploration
  - `intelligence_repeat.py`: RepeatEpisodeIntelligence - replay successful episodes
  - `intelligence_monitor.py`: RangeMonitorIntelligence - monitors range constraints
  - `intelligence_future_constraints.py`: FutureConstraintsIntelligence - predicts constraint violations
  - `order_discovery.py`: OrderDiscovery - bin acquisition via paired nudges (Sutton-compliant)
- Depends on: Knowledge graphs, State Manager, Brain Capacity
- Used by: Goal Orchestrator and System Coordinator

**Layer 4 - Control (System Orchestration):**
- Purpose: Orchestrates intelligence modules, manages episodes, coordinates with environment
- Location: `control/`
- Contains:
  - `system_coordinator_corrected.py`: SystemCoordinator - main decision loop, integrates all layers
  - `goal_orchestrator.py`: GoalOrchestrator - manages open/closed-ended goals, priorities, constraints
  - `episode_controller.py`: EpisodeController - manages episode lifecycle (frames, failure detection, termination)
  - `frame_action_controller.py`: FrameActionController - control loop cadence (NOT game frame sync)
  - `environment_protocol.py`: EnvironmentBridge - communication protocol with environment
  - `environment_timing.py`: Timing management for environment interaction
  - `timestamp_manager_corrected.py`: TimestampManager - tracks time synchronization
  - `system_initializer.py`: SystemInitializer - startup sequence, bin discovery, validation
- Depends on: All three layers, adapters
- Used by: Entry points (run_initialization.py, tmrl_live_control.py)

**Environment Adapters:**
- Purpose: Isolates environment-specific code (TrackMania/TMRL) from core system
- Location: `adapters/`
- Contains:
  - `tmrl_adapter.py`: TMRLAdapter - extracts feedbacks/actions from TMRL observations
  - `tmrl_live_adapter.py`: Live validation adapter for TrackMania
  - `live_validation.py`: Validation logic for live environment interaction
- Pattern: Abstract EnvironmentAdapter interface, TrackMania-specific implementations
- Used by: System Coordinator, Frame Action Controller

**Supporting Modules:**
- `utils/`: Exceptions, validators, configuration helpers
- `config/`: System configuration (actions, feedbacks, bins, constraints)
- `tests/`: Verification and checkpoint tests

## Data Flow

**System Initialization Flow:**

```
run_initialization.py
  ↓
SystemInitializer.initialize()
  ├→ Connect to FalkorDB
  ├→ Check existing knowledge (prior knowledge)
  ├→ If fresh: Run OrderDiscovery (paired nudges)
  │    └→ Discover bins (min, max, ratio)
  ├→ Store bins in brain capacity
  ├→ Initialize graphs (one per feedback)
  └→ Return: System ready for operation
```

**Per-Frame Decision Cycle:**

```
FrameActionController (control loop)
  ├→ Receive feedback from environment
  ├→ StateManager.update_current_state()
  │    └→ Convert feedback to StateVector (graph positions)
  │
  ├→ SystemCoordinator.make_decision()
  │    ├→ GoalOrchestrator.get_active_goal()
  │    ├→ Intelligence modules reason:
  │    │    ├→ AwarenessIntelligence: Compare prediction vs reality
  │    │    ├→ FutureConstraintsIntelligence: Check constraint violations
  │    │    ├→ RangeMonitorIntelligence: Monitor ranges
  │    │    ├→ Selected intelligence (Explore/Repeat/Experiment based on goal)
  │    │    └→ Return action recommendation
  │    ├→ BrainCapacity.filter_valid_combinations()
  │    │    └→ Check disjoint rules
  │    ├→ Validate action against constraints
  │    └→ Return DecisionPackage (action + reasoning)
  │
  ├→ Send action to environment (via adapter)
  ├→ Record transition to knowledge graph
  │    └→ Frame → ACTION → Next_Frame
  │
  ├→ EpisodeController.check_episode_status()
  │    ├→ Check frame/time limits
  │    ├→ Detect stuck (no progress N actions)
  │    ├→ Check goal achievement
  │    └→ Return: continue or end episode
  │
  └→ Repeat until episode ends
```

**Knowledge Recording:**

```
FrameObservation (feedback from environment)
  ↓
StateManager converts to StateVector
  ↓
KnowledgeManager.record_transition()
  ├→ Create/retrieve Frame nodes in FalkorDB
  │    (One node per frame with ACTUAL observed values)
  ├→ Create ACTION edges (gas, brake, steering values)
  └→ Update statistics
```

**State Management:**

```
Current architecture maintains THREE states:
- previous_state: Last known state (from memory)
- current_state: Current awareness (where we are now)
- future_state: Predicted state (planning - not yet used)

StateVector = Dict[graph_name → node_position]
Example: {'speed': 45.2, 'lidar_0': 2.1, 'lidar_1': 3.4}
```

## Key Abstractions

**StateVector:**
- Purpose: Represents system state as vector of node positions from ALL knowledge graphs
- Examples: `core/state_manager.py` StateVector class (lines 23-60)
- Pattern: Dictionary mapping graph_name → observed_value, with timestamp and frame number

**DecisionPackage:**
- Purpose: Structured decision output with explainability
- Example: `control/system_coordinator_corrected.py` DecisionPackage (lines 80-100)
- Pattern: Contains action (continuous + discrete), current/predicted states, constraint violations, reasoning dict

**Goal:**
- Purpose: Orchestrator for system behavior - what to achieve
- Example: `control/goal_orchestrator.py` Goal class
- Pattern: Open-ended (time/episode-based) or closed-ended (state-based) with constraints

**FrameAction:**
- Purpose: Action taken at a frame - atomic decision unit
- Example: `knowledge/knowledge_manager.py` FrameAction (lines 44-48)
- Pattern: gas, brake, steering values (continuous)

**Transition:**
- Purpose: Complete knowledge edge - state change via action
- Example: `knowledge/knowledge_manager.py` Transition (lines 52-56)
- Pattern: from_frame --[ACTION]--> to_frame

**EnvironmentAdapter:**
- Purpose: Abstract interface for environment interaction
- Pattern: Abstract base class with extract_feedbacks(), extract_actions(), format_action_for_env()
- Concrete: TMRLAdapter for TrackMania/TMRL

## Entry Points

**run_initialization.py:**
- Location: `/c/Users/ateeb/Desktop/tmrl_docker_trainer/run_initialization.py`
- Triggers: Manual startup (python run_initialization.py)
- Responsibilities:
  1. Check existing FalkorDB knowledge
  2. Ask user about prior knowledge usage
  3. Run bin discovery if fresh start
  4. Initialize graphs
  5. Report status

**tmrl_live_control.py:**
- Location: `/c/Users/ateeb/Desktop/tmrl_docker_trainer/tmrl_live_control.py`
- Triggers: Manual startup for live training
- Responsibilities:
  1. Initialize system (with prior knowledge)
  2. Connect to TrackMania
  3. Run control loop (FrameActionController)
  4. Record episodes to knowledge graphs

**demo_test_harness.py:**
- Location: `/c/Users/ateeb/Desktop/tmrl_docker_trainer/demo_test_harness.py`
- Triggers: Demonstration/testing mode
- Responsibilities:
  1. Verify system setup
  2. Run test sequences
  3. Validate components

**run_order_system.py:**
- Location: `/c/Users/ateeb/Desktop/tmrl_docker_trainer/run_order_system.py`
- Triggers: Standalone bin discovery
- Responsibilities:
  1. Run OrderDiscovery algorithm
  2. Output discovered bins to console

## Error Handling

**Strategy:** Layered exception hierarchy with specific error types per layer

**Patterns:**

1. **Capacity Layer Errors:** `core/`
   - ConfigurationError, BrainCapacityError, DiscretizationError, GraphOperationError
   - Example: Invalid action bins, missing config, graph connection failure

2. **Knowledge Layer Errors:** `knowledge/`
   - DatabaseConnectionError, GraphOperationError
   - Example: FalkorDB unreachable, query failure

3. **Intelligence Layer Errors:** `intelligence/`
   - IntelligenceError (general), with specific types in experimentation
   - Example: Awareneness check failure, exploration bounds error

4. **Control Layer Errors:** `control/`
   - SystemException (general), EpisodeError (specific)
   - Example: Goal validation failure, episode termination issue

5. **Generic/Utils:** `utils/`
   - SystemException (base), ValidationError, StateNotFoundError

**Pattern:** Try-catch at layer boundaries, log with layer prefix (e.g., `[BRAIN]`, `[KNOWLEDGE]`), propagate upward with context

## Cross-Cutting Concerns

**Logging:**
- Approach: Python logging module with layer-specific logger names
- Pattern: Each module creates `logger = logging.getLogger(__name__)`
- Format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- Layer prefixes in messages: `[BRAIN]`, `[KNOWLEDGE]`, `[INTELLIGENCE]`, `[CONTROL]`, `[ADAPTER]`

**Validation:**
- Approach: Validators in `utils/validators.py` - ConfigValidator, InputValidator
- Pattern: Validate configuration at startup, validate inputs at layer boundaries
- Example: Check action values in range, check state vector completeness

**Authentication/Environment Access:**
- Approach: Direct call protocol via EnvironmentBridge
- Pattern: System communicates with environment through well-defined protocol (actions out, feedbacks in)
- No security/auth layer - assumes trusted environment

**State Consistency:**
- Approach: StateManager maintains single source of truth for current state
- Pattern: All layers query StateManager for current state, no independent state tracking
- Synchronization: Per-frame updates from environment feedback

---

*Architecture analysis: 2026-02-16*
