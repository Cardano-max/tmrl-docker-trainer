# TMRL Intelligent System (Dr. Sutton Collaboration)

## What This Is

A **frame-based intelligent learning system** for the TrackMania Racing League (TMRL) that learns action-feedback relationships through structured experimentation. The system discovers the minimum/maximum bounds (bins) of controllable actions, records learned transitions in knowledge graphs (FalkorDB), and orchestrates goal-driven behavior using internal state awareness and constraint satisfaction.

**Key distinction:** This separates **Brain Capacity** (what the system CAN do—sensors, actions, timing) from **Intelligence** (how the system USES capacity to make decisions based on knowledge graphs).

## Core Value

**The system must reliably discover and exploit the minimum/maximum action bounds (bins) for each controllable action, then use this knowledge to build a queryable knowledge graph of state transitions that enables goal-driven planning.**

If bins aren't discovered correctly, the entire intelligence layer collapses. This is table stakes.

## Architecture Principles (Invariants)

### 1. Three-Layer Separation
- **Brain Capacity**: Actions, feedbacks, time management, frame rate, discretization
- **Knowledge**: Knowledge graphs (FalkorDB), state-transition history, bins
- **Intelligence**: Awareness, goal orchestration, planning, constraint satisfaction

### 2. Three States
- **Internal State**: What the system thinks (from knowledge graphs)
- **Environment State**: Ground truth (from environment feedback)
- **Sensorial State**: Raw sensor values (motor positions, temperatures)

### 3. Frame-Based Timing
- All intelligence operates on **frame** granularity, not wall-clock time
- One action per frame during training
- Internal timestamp manager (not environment clock)
- Frame rate discovered/validated from environment, not hardcoded

### 4. Knowledge vs Capacity
- **Prior Knowledge**: Actions/feedbacks from config file
- **Acquired Knowledge**: Bins and knowledge graphs from experimentation
- Bins MUST be discovered; user CANNOT hardcode them

## Requirements

### Validated (Existing in Codebase)
- ✓ Basic TrackMania environment connection
- ✓ Config file structure (actions, feedbacks)
- ✓ Frame-based control loop
- ✓ Some knowledge graph infrastructure

### Active (Must Implement / Fix)

#### 1. **Capacity Layer**
- [ ] **Frame Rate Discovery**: Determine FPS from environment, not hardcoded
- [ ] **Action Binding**: Send actions to environment via generic protocol
- [ ] **Feedback Reception**: Receive feedback values with frame alignment
- [ ] **Disjoint Action Filtering**: Eliminate impossible action combinations
- [ ] **Bin Discovery Algorithm**: Binary search for min/max per action
- [ ] **Discretization**: Convert continuous feedback into state bins

#### 2. **Knowledge Layer**
- [ ] **FalkorDB Integration**: Stable graph database for long-term memory
- [ ] **Knowledge Graph Recording**: Record state transitions at frame rate
- [ ] **Node Deduplication**: No duplicate nodes; reuse state nodes
- [ ] **Query Interface**: "From state X with action Y, where do I end up?"
- [ ] **Replay Capability**: "Show episode 4337 again"
- [ ] **Memory Persistence**: Load/save knowledge graphs across sessions

#### 3. **Intelligence Layer**
- [ ] **Awareness Intelligence**: Compare internal state (from graph) vs environment state
- [ ] **Goal Orchestration**: Execute multi-frame plans to reach constrained states
- [ ] **Constraint Validation**: Hard constraints (cannot violate), soft constraints (report)
- [ ] **Failure Detection**: Recognize when system is stuck (no progress)
- [ ] **Episode Control**: System owns episode length (not environment)

#### 4. **Validation System**
- [ ] **Config Validation**: Verify config matches environment
- [ ] **Awareness Validation**: Internal state matches environment feedback
- [ ] **Constraint Validation**: Feedbacks within expected ranges

#### 5. **Communication Protocol**
- [ ] **Generic Message Format**: Send/receive independent of TrackMania specifics
- [ ] **Port-Based Routing**: Environment listens on defined port
- [ ] **Bidirectional Handshake**: Verify both directions before proceeding

### Out of Scope (Explicitly Excluded)

- **MPC (Model Predictive Control)**: Deferred to future phase; focus on 3-state architecture first
- **Reward/Policy Learning**: System uses goals and constraints, not rewards
- **Blind Exploration**: Exploration MUST be goal-based, never random
- **User-Defined Bins**: Users cannot guess; system must discover
- **Environment-Specific Code in Core**: All TrackMania specifics isolated
- **State Coverage Completion**: "All reachable states" is infinite; not a termination criterion

## Context

### From Meetings with Dr. Richard Sutton
- **Motivation**: Building an intelligent system that can learn action-feedback relationships in a continuous control environment
- **Problem Solved**: Current implementations mix capacity and intelligence, making it impossible to debug or scale
- **Key Insight**: "Whatever God gave you is brain capacity. What you do with it is intelligence."
- **Research Phase**: This is fundamentally a **research project**, not production engineering—bugs reveal missing concepts

### Technical Debts / Known Issues
- Frame rate hardcoded (not discovered from environment)
- Bin discovery algorithm buggy or missing
- Knowledge graph node duplication occurring
- Timestamp management confuses internal vs external time
- Communication protocol TrackMania-specific instead of generic
- Disjoint action filtering not implemented

## Constraints

- **Tech Stack**: Python, FalkorDB (Redis-compatible), TrackMania environment
- **Frame Rate**: Environment-driven (not hardcoded); currently ~70 FPS
- **Development Approach**: Capacity-first (validate basics before intelligence layers)
- **Research Constraint**: All decisions must be explainable to Dr. Sutton; guessing not acceptable

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| FalkorDB for knowledge graphs | Redis-compatible, queryable, persistent | — Pending validation |
| Binary search for bin discovery | O(log N) convergence, mathematically sound | ✓ Conceptually correct, implementation buggy |
| Frame-based not time-based | Aligns with environment granularity, simplifies synchronization | — Needs validation against real environment |
| Generic protocol for communication | Enable different environments (not TrackMania-only) | — Partially implemented |
| Internal timestamp manager | Decouples system timing from environment timing | — Needs stress testing |

---

*Last updated: 2025-02-16 after codebase analysis*
