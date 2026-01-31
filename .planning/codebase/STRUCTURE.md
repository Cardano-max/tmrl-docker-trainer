# Codebase Structure

**Analysis Date:** 2026-01-31

## Directory Layout

```
project-root/
├── config/                    # Configuration files
│   ├── system_config_corrected.json    # Primary system config (actions, feedbacks, timing, bins)
│   └── __init__.py
├── core/                      # Layer 1: BRAIN CAPACITY - What system CAN do
│   ├── brain_core.py          # BrainArchitecture, DisjointActionValidator, ActionDiscretizer
│   ├── brain_capacity.py      # Atomic capacity functions (sensory, motor, knowledge)
│   ├── state_manager.py       # StateVector, StateManager (current position in all graphs)
│   └── __init__.py
├── control/                   # CONTROL LAYER - Orchestration and coordination
│   ├── system_coordinator_corrected.py    # Main coordinator (reads feedback → decision → action)
│   ├── system_initializer.py  # Initialization sequence (validation → experimentation → ready)
│   ├── goal_orchestrator.py   # Goal definitions (OPEN_ENDED, CLOSED_ENDED)
│   ├── episode_controller.py  # Episode lifecycle (frames, failure detection, stuck detection)
│   ├── frame_action_controller.py         # Control loop (send action, read feedback per iteration)
│   ├── environment_protocol.py            # EnvironmentBridge (abstraction for env communication)
│   ├── environment_timing.py  # Frame timing and synchronization
│   ├── timestamp_manager_corrected.py     # Frame clock vs wall clock management
│   └── __init__.py
├── intelligence/              # Layer 3: INTELLIGENCE - How system USES capacity + knowledge
│   ├── brain_intelligence.py  # Supervisor intelligence (meta-reasoning)
│   ├── intelligence_awareness.py          # Awareness: knowledge vs reality comparison
│   ├── intelligence_experimentation.py    # Bin discovery via order-of-magnitude search
│   ├── intelligence_explore.py            # Exploration: try untried actions
│   ├── intelligence_repeat.py             # Episode replay: recreate exact transitions
│   ├── intelligence_monitor.py            # Range monitoring: constraint checking
│   ├── intelligence_future_constraints.py # Prediction: will action violate constraints?
│   ├── order_discovery.py     # Core algorithm for min/max discovery (Sutton-compliant)
│   └── __init__.py
├── knowledge/                 # Layer 2: KNOWLEDGE - What system KNOWS (passive storage)
│   ├── knowledge_manager.py   # Per-frame knowledge graphs (FalkorDB-backed)
│   ├── memory_handler.py      # Short-term memory (recent episodes) + long-term (FalkorDB)
│   └── __init__.py
├── adapters/                  # Layer 4: ENVIRONMENT - Environment-specific code (isolated)
│   ├── tmrl_adapter.py        # TrackMania/TMRL data extraction (EnvironmentAdapter interface)
│   ├── tmrl_live_adapter.py   # Live TCP/socket communication with TrackMania
│   ├── live_validation.py     # Validation for live mode
│   └── __init__.py
├── utils/                     # Utilities and exceptions
│   ├── exceptions.py          # SystemException, ConfigurationError, etc.
│   ├── validators.py          # ConfigValidator, InputValidator
│   └── [other utilities]
├── tests/                     # Test suite
│   ├── [test files]
├── docs/                      # Documentation
│   ├── SYSTEM_DOCUMENTATION.md
│   ├── meeting_requirements.md
│   └── [design documents]
├── archive/                   # Historical and reference materials
│   ├── meeting_transcripts/   # Dr. Richard Sutton's meeting transcripts (ground truth)
│   ├── new_meeing_transcripts/# Latest transcripts (31-Jan-2026)
│   └── [docker files, old code]
├── checkpoints/               # Model checkpoints and saved states
├── logs/                      # Runtime logs and traces
├── knowledge/                 # Knowledge graph backups (complementary to FalkorDB)
├── ui/                        # Optional: UI explorer
├── weights/                   # Neural network weights (if applicable)
└── [entry point scripts]      # See "Entry Points" below
```

## Directory Purposes

**`config/`**
- Purpose: System configuration (prior knowledge from human)
- Contains: `system_config_corrected.json` with action ranges, feedback definitions, disjoint rules, experimentation config, environment timing
- CRITICAL: Frame timing must match environment FPS (e.g., 50ms for TMRL's 20Hz)
- Mutability: Read-only at runtime (except for acquired bins stored separately)

**`core/`**
- Purpose: Brain capacity layer (what system CAN do)
- `brain_core.py`: Facade providing all capacities (sense, act, discretize, query, connect)
- `brain_capacity.py`: Individual capacity implementations (sensory, motor, knowledge, connection)
- `state_manager.py`: Tracks "where am I?" across all knowledge graphs
- Key exports: `BrainArchitecture`, `StateVector`, `StateManager`, `DisjointActionValidator`, `ActionDiscretizer`

**`control/`**
- Purpose: System orchestration and episode management
- Main flow:
  1. `system_initializer.py`: One-time startup (validation + experimentation)
  2. `system_coordinator_corrected.py`: Episode loop (feedback → decision → action)
  3. `goal_orchestrator.py`: What are we trying to achieve?
  4. `episode_controller.py`: When does episode end?
  5. `frame_action_controller.py`: Per-frame action dispatch
  6. `environment_protocol.py`: How to talk to environment?
  7. `environment_timing.py`: Frame synchronization
- Key exports: `SystemCoordinator`, `SystemInitializer`, `EpisodeController`, `FrameActionController`, `GoalOrchestrator`

**`intelligence/`**
- Purpose: Decision-making modules (how to USE capacity + knowledge)
- Pattern: Each module answers ONE question
  - `intelligence_awareness.py`: "Does knowledge match reality?"
  - `intelligence_explore.py`: "What actions haven't I tried?"
  - `intelligence_experimentation.py`: "What are the min/max values for each action?"
  - `intelligence_repeat.py`: "Can I recreate this episode exactly?"
  - `intelligence_monitor.py`: "Are we within safe ranges?"
  - `intelligence_future_constraints.py`: "Will this action violate constraints?"
  - `brain_intelligence.py`: Meta-reasoning (supervisor level)
- Key exports: All Intelligence classes ending in `Intelligence`

**`knowledge/`**
- Purpose: Storage layer (what system KNOWS)
- `knowledge_manager.py`: Per-frame graphs in FalkorDB (structure: one node per frame, edges with actions)
- `memory_handler.py`: Short-term memory (dictionaries, deques) + long-term memory (FalkorDB)
- Data: Transitions, state vectors, discovered bins, episode recordings
- Key exports: `KnowledgeManager`, `MemoryHandler`, `EpisodeMemory`

**`adapters/`**
- Purpose: Environment-specific code (ISOLATED from system logic)
- `tmrl_adapter.py`: TrackMania data extraction (implements `EnvironmentAdapter` interface)
- `tmrl_live_adapter.py`: Live TCP socket communication
- `live_validation.py`: Validation helpers
- Key pattern: Abstract `EnvironmentAdapter` interface allows ANY environment to plug in
- Key exports: `EnvironmentAdapter`, `TMRLAdapter`, `GenericEnvironmentAdapter`

**`utils/`**
- Purpose: Cross-cutting utilities
- `exceptions.py`: Exception hierarchy (SystemException, ConfigurationError, etc.)
- `validators.py`: Schema validation (ConfigValidator) and input validation (InputValidator)
- Used by: All layers for validation and error handling

**`tests/`**
- Purpose: Automated testing
- Patterns: Unit tests, integration tests, system tests
- Key files: Test harnesses for bin discovery, state management, intelligence modules

**`docs/`**
- Purpose: Design documentation
- Key files:
  - `SYSTEM_DOCUMENTATION.md`: Overall system design
  - `meeting_requirements.md`: Requirements from supervisor transcripts
  - `system_architecture.md`: Detailed architecture diagrams

**`archive/`**
- Purpose: Historical reference and ground truth
- `meeting_transcripts/`: Dr. Sutton's meeting transcripts (AUTHORITATIVE SOURCE)
  - `latest_meeting_transcript.txt`
  - `meeting_transcript_24Jan2026.txt`
  - `all_meeting_transcripts.txt`
- `new_meeing_transcripts/`: Latest meetings (31-Jan-2026)
  - `meeting_transcript_31Jan2026.txt`
- Used by: When understanding system design decisions, trace back to transcript

## Key File Locations

**Entry Points:**
- `run_initialization.py`: Initialize system (validation + experimentation)
- `run_order_system.py`: Run episode execution system
- `tmrl_live_control.py`: Live control demo
- `demo_test_harness.py`: Test harness for demonstrations
- `demo_meeting_requirements.py`: Verification that requirements are met

**Configuration:**
- `config/system_config_corrected.json`: All system parameters (actions, feedbacks, timing, bins, experimentation)

**Core Logic:**
- `core/brain_core.py`: BrainArchitecture (all capacities)
- `core/state_manager.py`: State tracking
- `control/system_coordinator_corrected.py`: Main episode loop
- `knowledge/knowledge_manager.py`: Knowledge graphs (FalkorDB)

**Testing & Validation:**
- `tests/`: Test suite
- `intelligence/order_discovery.py`: Core bin discovery algorithm
- `control/system_initializer.py`: Initialization with validation

**Intelligence Decisions:**
- `intelligence/intelligence_awareness.py`: Knowledge vs reality
- `intelligence/intelligence_explore.py`: Untried actions
- `intelligence/intelligence_experimentation.py`: Bin discovery
- `intelligence/intelligence_repeat.py`: Episode replay
- `intelligence/intelligence_future_constraints.py`: Constraint prediction

## Naming Conventions

**Files:**
- `system_coordinator_corrected.py`: "corrected" indicates supervisor-approved version
- `timestamp_manager_corrected.py`: "corrected" indicates version addressing timing issues
- `brain_*.py`: Core brain functions (capacity, intelligence)
- `intelligence_*.py`: Intelligence modules (each handles one type of reasoning)
- `*_adapter.py`: Environment-specific adapters

**Directories:**
- `core/`: Brain-level functionality (capacity)
- `control/`: Orchestration and coordination
- `intelligence/`: Decision-making (uses capacity + knowledge)
- `knowledge/`: Storage and memory
- `adapters/`: Environment-specific (isolated)
- `utils/`: Cross-cutting utilities
- `archive/`: Historical reference

**Classes:**
- `*Intelligence`: Intelligence modules (e.g., `AwarenessIntelligence`)
- `*Manager`: Management classes (e.g., `KnowledgeManager`, `StateManager`)
- `*Controller`: Control flow classes (e.g., `EpisodeController`, `FrameActionController`)
- `*Validator`: Validation classes (e.g., `DisjointActionValidator`)
- `*Adapter`: Environment adapters (e.g., `TMRLAdapter`)

**Functions:**
- `decide_*`: Intelligence decision functions (e.g., `decide_action()`)
- `query_*`: Knowledge queries (e.g., `query_untried()`)
- `sense_*`: Sensory capacities (e.g., `sense_speed()`)
- `act_*`: Motor capacities (e.g., `act_gas()`)
- `execute_*`: Control execution (e.g., `execute_action_for_iterations()`)

## Where to Add New Code

**New Intelligence Module (e.g., curiosity-driven exploration):**
- Primary code: `intelligence/intelligence_<name>.py`
  - Create class `<Name>Intelligence` inheriting from base pattern
  - Implement `decide_action(feedbacks: Dict) -> Optional[Dict]`
  - Use brain capacity queries: `brain.query_untried(state)`, `brain.query_transition(state, action)`
- Integration: Import and register in `control/system_coordinator_corrected.py`
- Tests: Add test file `tests/test_intelligence_<name>.py`
- Config: Add config section in `config/system_config_corrected.json` if parameters needed

**New Capacity Function (e.g., analyze energy efficiency):**
- Primary code: `core/brain_capacity.py` → add method in `BrainCapacity` class
- Registration: Add entry in `_register_all_capacities()` method
- Export: Ensure callable from `BrainArchitecture` facade
- Tests: Add test in `tests/test_brain_capacity.py`

**New Environment Support (e.g., racing simulator beyond TrackMania):**
- Adapter code: `adapters/<env>_adapter.py`
  - Implement `EnvironmentAdapter` abstract interface
  - Methods: `extract_feedbacks()`, `extract_actions()`, `get_frame()`, `format_action_for_env()`
- Live variant: `adapters/<env>_live_adapter.py` for real-time control
- Config: Add `environment` section in system config
- No changes needed to core system logic (environment-agnostic design)

**New Constraint Type (e.g., energy budget):**
- Implementation: `intelligence/intelligence_future_constraints.py` → add `ConstraintType` enum
- Factory: Add case in `ConstraintFactory.create()`
- Usage: Goals can include these constraints: `StateConstraint(feedback_name='energy', min_value=0.0, max_value=100.0)`

**New Test:**
- Location: `tests/test_<component>.py`
- Pattern: Use fixtures from test harness (`demo_test_harness.py`)
- Example: Test frame action controller with mock environment

## Special Directories

**`checkpoints/`**
- Purpose: Save/restore system state (agent weights, knowledge graph snapshots)
- Generated: Yes (during training runs)
- Committed: No (too large, regenerated)
- Usage: Resume training from previous checkpoint

**`logs/`**
- Purpose: Runtime logs and traces
- Generated: Yes (at runtime)
- Committed: No (too large, regenerated)
- Structure: `logs/<demo_name>/<YYYY-MM-DD>/` with session logs

**`knowledge/`**
- Purpose: Backup knowledge graphs (complementary to FalkorDB)
- Generated: Yes (during episode execution)
- Committed: No (live data)
- Format: JSON snapshots of graph structure

**`weights/`**
- Purpose: Neural network weights (if policy learning added)
- Generated: Maybe (not currently used)
- Committed: No (large, regenerated)
- Format: PyTorch .pt or TensorFlow .pb

**`archive/meeting_transcripts/`**
- Purpose: **AUTHORITATIVE SOURCE** for system requirements
- Generated: No (human-created from supervisor meetings)
- Committed: Yes (critical reference)
- Format: `.txt` files of meeting transcripts with timestamps
- Usage: When understanding WHY system works a certain way, read the relevant transcript

---

*Structure analysis: 2026-01-31*
*Design pattern: Four-layer CKI (Capacity-Knowledge-Intelligence) per Dr. Richard Sutton*
*Ground truth source: archive/meeting_transcripts/ and archive/new_meeing_transcripts/*
