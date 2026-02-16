# Codebase Structure

**Analysis Date:** 2026-02-16

## Directory Layout

```
tmrl_docker_trainer/
├── core/                          # Layer 1: Brain Capacity
│   ├── __init__.py
│   ├── brain_core.py              # Main orchestrator (1178 lines)
│   ├── brain_capacity.py           # Action discretization, disjoint validation
│   └── state_manager.py            # StateVector, state tracking
│
├── knowledge/                      # Layer 2: Knowledge Graphs
│   ├── __init__.py
│   ├── knowledge_manager.py        # Per-frame knowledge graph (1010 lines)
│   └── memory_handler.py           # Short-term memory
│
├── intelligence/                   # Layer 3: Intelligence Modules
│   ├── __init__.py
│   ├── brain_intelligence.py       # Base intelligence class
│   ├── intelligence_awareness.py   # Awareness intelligence
│   ├── intelligence_experimentation.py   # Experimentation (1544 lines)
│   ├── intelligence_explore.py     # Exploration intelligence
│   ├── intelligence_repeat.py      # Repeat intelligence
│   ├── intelligence_monitor.py     # Range monitoring
│   ├── intelligence_future_constraints.py  # Constraint prediction
│   └── order_discovery.py          # Bin acquisition (paired nudges)
│
├── control/                        # Layer 4: System Orchestration
│   ├── __init__.py
│   ├── system_coordinator_corrected.py  # Main decision loop (1043 lines)
│   ├── goal_orchestrator.py        # Goal management
│   ├── episode_controller.py       # Episode lifecycle
│   ├── frame_action_controller.py  # Control loop cadence
│   ├── environment_protocol.py     # Environment bridge
│   ├── environment_timing.py       # Timing management
│   ├── timestamp_manager_corrected.py  # Time tracking
│   └── system_initializer.py       # Startup sequence
│
├── adapters/                       # Environment-Specific Code
│   ├── __init__.py
│   ├── tmrl_adapter.py             # TrackMania/TMRL adapter
│   ├── tmrl_live_adapter.py        # Live TrackMania adapter
│   └── live_validation.py          # Validation for live mode
│
├── utils/                          # Utilities
│   ├── __init__.py
│   ├── exceptions.py               # Exception hierarchy
│   └── validators.py               # Configuration validators
│
├── config/                         # Configuration Files
│   ├── __init__.py
│   ├── system_config_corrected.json    # Main system configuration
│   ├── server_config.json          # Server configuration
│   └── trainer_config.json         # Trainer configuration
│
├── tests/                          # Tests & Checkpoints
│   ├── checkpoint_*.py             # Checkpoint validation tests
│   └── ...
│
├── docs/                           # Documentation
│   ├── SYSTEM_DOCUMENTATION.md
│   ├── AUDIT_REPORT.md
│   ├── system_architecture.md
│   ├── DEMO_HARNESS_RUNBOOK.md
│   └── ...
│
├── intelligence/                   # Analysis scripts
├── knowledge/                      # Knowledge/data output
├── logs/                           # Execution logs
├── checkpoints/                    # Saved checkpoints
├── weights/                        # Model weights
├── archive/                        # Previous versions
│
├── __init__.py                     # Package initialization
├── run_initialization.py           # Entry point: System initialization
├── tmrl_live_control.py            # Entry point: Live training
├── run_order_system.py             # Entry point: Bin discovery
├── run_order_system_standalone.py  # Standalone bin discovery
├── demo_test_harness.py            # Entry point: Test harness
├── demo_meeting_requirements.py    # Requirements verification
└── discover_v*.py                  # Discovery algorithm variants
```

## Directory Purposes

**core/:**
- Purpose: Brain Capacity - system capabilities (what the system CAN do)
- Contains: Action discretization, state representation, capacity queries
- Key files:
  - `brain_core.py`: Main orchestrator, aggregates capacity components
  - `brain_capacity.py`: Action bins, disjoint rules, combination validation
  - `state_manager.py`: StateVector (node positions across graphs)

**knowledge/:**
- Purpose: Knowledge Graphs - what the system KNOWS (per-frame observations)
- Contains: FalkorDB graph management, frame/transition storage
- Key concept: One node PER FRAME (not discretized), actual observed values
- Database: FalkorDB (Redis-based graph database)

**intelligence/:**
- Purpose: Intelligence Modules - reasoning about actions
- Contains: Specialized decision-making modules (awareness, exploration, experimentation, etc.)
- Pattern: Each module implements specific reasoning capability
- Modules can be combined via Goal Orchestrator

**control/:**
- Purpose: System Orchestration - coordinates all layers
- Contains: Main decision loop, goal management, episode management, environment bridge
- Key file: `system_coordinator_corrected.py` - the MAIN LOOP

**adapters/:**
- Purpose: Environment-specific code isolation
- Contains: TrackMania/TMRL data extraction, action formatting
- Design: Abstract EnvironmentAdapter interface with concrete implementations
- Principle: Core system is environment-agnostic, adapters handle specifics

**utils/:**
- Purpose: Shared utilities and infrastructure
- Contains: Custom exceptions, input validators, configuration helpers

**config/:**
- Purpose: System configuration (not code)
- Files:
  - `system_config_corrected.json`: Actions, feedbacks, bins, constraints, rules
  - `server_config.json`: Server/networking configuration
  - `trainer_config.json`: Training-specific settings

**tests/:**
- Purpose: Verification and validation
- Pattern: Checkpoint tests verify system behavior
- Files: `checkpoint_*.py` - test scenarios and validation

**docs/:**
- Purpose: Documentation and specifications
- Contains: Architecture docs, implementation guides, runbooks, audit reports

## Key File Locations

**Entry Points:**

- `run_initialization.py`: Main startup - checks prior knowledge, runs bin discovery, initializes system
- `tmrl_live_control.py`: Live training with TrackMania environment
- `run_order_system.py`: Standalone bin discovery (OrderDiscovery algorithm)
- `run_order_system_standalone.py`: Alternative standalone bin discovery
- `demo_test_harness.py`: Test and verification harness
- `demo_meeting_requirements.py`: Verify meeting requirements compliance

**Configuration:**

- `config/system_config_corrected.json`: Main configuration (actions, feedbacks, bins, constraints)
  - Actions: gas, brake, steering (with bins and disjoint rules)
  - Feedbacks: speed, lidar_0...lidar_18, etc.
  - Constraints: Min/max ranges for each feedback
  - Disjoint rules: gas disjoint brake (cannot both be active)

**Core Logic:**

- `control/system_coordinator_corrected.py`: Main decision loop (1043 lines)
  - `make_decision()`: Per-frame decision cycle
  - Integrates all four layers
  - Returns DecisionPackage with action and reasoning

- `control/goal_orchestrator.py`: Goal management
  - Open-ended goals (time/episode-based)
  - Closed-ended goals (state-based)
  - Goal priority and scheduling

- `core/brain_core.py`: Capacity orchestrator (1178 lines)
  - `BrainArchitecture` class
  - Aggregates all capacity components
  - Manages action discretization and validation

- `knowledge/knowledge_manager.py`: Knowledge graph (1010 lines)
  - Per-frame node creation
  - Transition edge recording
  - FalkorDB interface

**Intelligence Modules:**

- `intelligence/intelligence_awareness.py`: Compares predicted vs actual state
- `intelligence/intelligence_experimentation.py`: Discovers action effects (1544 lines)
- `intelligence/intelligence_explore.py`: Systematic exploration
- `intelligence/intelligence_repeat.py`: Replay successful episodes
- `intelligence/order_discovery.py`: Bin acquisition (paired nudges)

**Testing & Verification:**

- `tests/checkpoint_*.py`: Checkpoint validation tests
- `demo_test_harness.py`: Comprehensive test harness
- `diagnose_telemetry.py`: Telemetry diagnostics

## Naming Conventions

**Files:**

- Module files: `snake_case.py` (e.g., `system_coordinator_corrected.py`)
- Test files: `checkpoint_*.py` or `test_*.py` (e.g., `checkpoint_brake.py`)
- Configuration: `*_config.json` or `*_config_corrected.json`
- Documentation: `UPPERCASE.md` (e.g., `SYSTEM_DOCUMENTATION.md`)

**Directories:**

- Core modules: Lowercase (e.g., `core/`, `knowledge/`, `control/`)
- Shared: `utils/`, `adapters/`, `config/`
- Output: `logs/`, `checkpoints/`, `weights/`
- Development: `archive/`, `tickets/`, `tools/`, `ui/`

**Classes:**

- Pattern: PascalCase (e.g., `BrainArchitecture`, `StateManager`, `KnowledgeManager`)
- Specialized: Descriptive names with layer context (e.g., `AwarenessIntelligence`, `ExperimentationIntelligence`)
- Data classes: Descriptive ending in Result/Data (e.g., `AwarenessResult`, `StateVector`, `DecisionPackage`)

**Functions/Methods:**

- Pattern: snake_case (e.g., `make_decision()`, `record_transition()`, `is_valid_combination()`)
- Query methods: `get_*()`, `query_*()` (e.g., `get_current_state()`)
- Action methods: `execute_*()`, `perform_*()` (e.g., `execute_action()`)
- Status checks: `is_*()`, `has_*()` (e.g., `is_episode_ended()`)

**Variables/Constants:**

- Local variables: snake_case (e.g., `current_state`, `action_values`)
- Constants: UPPER_SNAKE_CASE (e.g., `DEFAULT_CONFIG_PATH`, `MAX_FRAMES`)
- Private: Leading underscore (e.g., `_bin_lookup`, `_cache`)

## Where to Add New Code

**New Intelligence Module:**
1. Create file in `intelligence/intelligence_*.py`
2. Inherit from base intelligence interface
3. Implement reasoning logic
4. Register with GoalOrchestrator in `control/goal_orchestrator.py`
5. Example:
   - `intelligence/intelligence_awareness.py` - 60 lines for awareness reasoning
   - Method: `perform_awareness_check()` returns AwarenessResult
   - Used by: SystemCoordinator when active goal requires awareness

**New Capability (Brain Capacity Extension):**
1. Add to `core/brain_capacity.py` or `core/brain_core.py`
2. Expose through BrainArchitecture interface
3. Add validation rules in validators
4. Example:
   - Add new action type: Update ActionDiscretizer in brain_capacity.py
   - Add new constraint: Update constraint checking in goal_orchestrator.py

**New Control/Orchestration Feature:**
1. Add to `control/system_coordinator_corrected.py` or relevant control file
2. Follow decision cycle pattern (query → process → decide)
3. Example:
   - New goal type: Add GoalType enum, Goal factory function in goal_orchestrator.py
   - New episode termination condition: Add to EpisodeController.check_episode_status()

**New Environment Adapter:**
1. Create file in `adapters/*.py`
2. Inherit from EnvironmentAdapter abstract base
3. Implement extract_feedbacks(), extract_actions(), format_action_for_env()
4. Register in SystemCoordinator adapter selection
5. Example: See `adapters/tmrl_adapter.py` for TrackMania implementation

**Configuration/Rules:**
1. Add to `config/system_config_corrected.json`
2. Update validators in `utils/validators.py`
3. Reload config via SystemInitializer
4. Example:
   - New action: Add to "actions" section with bins and disjoint rules
   - New feedback: Add to "feedbacks" section with description

**Tests & Checkpoints:**
1. Create in `tests/checkpoint_*.py` or `tests/test_*.py`
2. Follow checkpoint pattern from existing tests
3. Use demo_test_harness.py as integration runner
4. Example: See `tests/checkpoint_brake.py` for pattern

## Special Directories

**logs/:**
- Purpose: Runtime execution logs
- Generated: Yes (at runtime)
- Committed: No (.gitignore)
- Structure: Subdirectories by date/demo

**checkpoints/:**
- Purpose: Saved system state snapshots
- Generated: Yes (during training)
- Committed: No (large files)
- Format: Depends on persistence implementation

**weights/:**
- Purpose: Model weights (if any)
- Generated: Yes (during training)
- Committed: No
- Note: Currently not used in this architecture

**config/**
- Purpose: Configuration files (code & data)
- Generated: Some (discovered bins)
- Committed: Yes (core configs)
- Example: `system_config_corrected.json` is committed

**archive/**
- Purpose: Previous versions, deprecated code
- Generated: No (manual archival)
- Committed: Yes
- Note: Not part of active system

**tickets/**
- Purpose: Task tracking and specifications
- Generated: Manual documentation
- Committed: Yes
- Subdirectories: backlog, in_progress, completed, spikes

**docs/**
- Purpose: System documentation
- Generated: Manual + auto-generated specs
- Committed: Yes
- Key files: SYSTEM_DOCUMENTATION.md, AUDIT_REPORT.md, system_architecture.md

**ui/**
- Purpose: Visualization and UI tools
- Generated: Manual creation
- Committed: Yes (if checked in)
- Example: `explorer/` subdirectory for exploration visualization

---

*Structure analysis: 2026-02-16*
