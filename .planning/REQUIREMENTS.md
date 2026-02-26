# Requirements: Milestone v1.0 Full Sutton Pipeline

**Created:** 2026-02-26
**Source:** 6 Dr. Sutton meeting transcripts + authoritative spec
**Scope:** Complete system from brain capacity through hierarchical intelligence
**Environment:** TMNF + TMInterface (primary), TM2020 (compat)

---

## Previously Validated (Phase A: Bin Discovery -- DONE)

REQ-01 through REQ-25 from `Authoratative_law_from_Jan2026_meetings.md`:
Frame atomicity, MIN/MAX discovery, precision discovery, bins in action space,
no noise, no interference, per-frame probing, bidirectional steering.

All validated: 9/9 live rubrics, 12/12 offline tests, stable 3/3 runs on TMNF.

---

## System Initialization (INIT)

- [x] **INIT-01**: System validates config on startup before any experimentation
  - _"we're gonna create us a validation first... the system validates the config"_ -- Jan 24
- [x] **INIT-02**: System checks for prior knowledge (existing graphs) at startup
  - _"when there is previous knowledge... no need to validate anything because the previous knowledge knows everything"_ -- Jan 24
- [x] **INIT-03**: If no prior knowledge, system runs bin discovery automatically before proceeding
  - _"the system won't start before it the experiments"_ -- Jan 24
- [x] **INIT-04**: If prior knowledge exists, system loads it and skips experimentation
  - _"when there is previous knowledge... no need to validate anything"_ -- Jan 24
- [x] **INIT-05**: System prints status during startup (validation started, bins acquired, graphs initialized, system ready)
  - _"you can print everything to screen like validation started, bins acquired, graphs initialized and so on"_ -- Jan 24
- [x] **INIT-06**: Frame duration comes from environment config, not hardcoded
  - _"this needs to be determined by the system so it's being configured not hard-coded"_ -- Jan 24

## Brain Capacity Micro-Processes (BRAIN)

- [ ] **BRAIN-01**: Send an action to the environment (per frame)
  - _"your function to send actions should send actions per frame"_ -- Jan 15
- [ ] **BRAIN-02**: Perform an action (environment executes it for exactly one frame)
  - _"by sending an action you send an action just for that frame"_ -- Jan 15
- [ ] **BRAIN-03**: Record the action (store what was sent)
  - _"six things here one is send an action... record the action"_ -- Jan 9
- [ ] **BRAIN-04**: Receive a feedback from the environment
  - _"receive a feedback... collect the feedback"_ -- Jan 9
- [ ] **BRAIN-05**: Collect that feedback (capture all state variables)
  - _"receive a feedback... collect the feedback"_ -- Jan 9
- [ ] **BRAIN-06**: Record the feedback (store in graph as node)
  - _"record the feedback"_ -- Jan 9
- [ ] **BRAIN-07**: Query the graph (search for node, edge, or relationship)
  - _"sometimes I'm going to query the graph on my current state. Sometimes... future state. Sometimes... the past"_ -- Jan 9
- [ ] **BRAIN-08**: Initialize graphs (one graph per environment feedback variable)
  - _"experimentation... is also capacity... it's going to determine things before we can start recording our graph"_ -- Jan 24
- [ ] **BRAIN-09**: Compare current state vs known state
  - _"awareness is just comparing where I think I am and what the environment tells that I am"_ -- Jan 9
- [ ] **BRAIN-10**: Micro-processes are small, modular, generic -- intelligence orchestrates them
  - _"instead of creating exploration, let's create small pieces. Then... we're just going to use the small pieces"_ -- Jan 9

## Knowledge Graph Infrastructure (GRAPH)

- [ ] **GRAPH-01**: Nodes represent discretized state values (feedback values like speed, position)
  - _"action are being stored as a relationship feedback being stored as notes"_ -- Jan 9
- [ ] **GRAPH-02**: Edges represent action bins that caused transitions
  - _"action are being stored as a relationship"_ -- Jan 9
- [ ] **GRAPH-03**: Node discretization by system precision (from bin discovery)
  - _"the minimum is 0.1... every 0.1 becomes one node because that's the bin"_ -- Jan 15
- [ ] **GRAPH-04**: No duplicate nodes -- returning to a state reuses existing node
  - _"is the duplication of nodes allowed or not? No not at all"_ -- Jan 24
- [ ] **GRAPH-05**: One graph per feedback variable (speed graph, position graph, etc.)
  - Jan 9 architecture: separate graphs per state variable
- [ ] **GRAPH-06**: All graphs updated simultaneously per frame
  - _"recording a graph is gonna be multiple graphs at the same time in the frame"_ -- Jan 24
- [ ] **GRAPH-07**: Same state reachable via different actions = same node with multiple edges
  - _"you go to the same node in two different ways"_ -- Authoritative Law F
- [ ] **GRAPH-08**: Knowledge graph stores bins, not raw continuous action values
  - REQ-18 from Authoritative Law
- [ ] **GRAPH-09**: Precision limits state resolution (unreachable states don't get nodes)
  - _"If the system doesn't report it, it doesn't exist"_ -- Authoritative Law H
- [ ] **GRAPH-10**: Per-frame recording: one node per graph with the action edge that caused the transition
  - _"on this frame the system knows an action and a feedback... then on the next frame a feedback and an action"_ -- Jan 15
- [ ] **GRAPH-11**: Time is implicit in graph traversal (not stored explicitly)
  - _"time stamp in this graph is the difference between nodes"_ -- Jan 9
- [ ] **GRAPH-12**: Multiplicity testing -- intermediate actions between MIN and MAX validated experimentally
  - _"you must test multiples... you cannot assume linearity"_ -- Jan 31 Pong

## Exploration Intelligence (EXPLORE)

- [ ] **EXPLORE-01**: At current state node, query all graphs for tried actions
  - _"I check what nodes are the amine. I receive the information back of all the possible relationships"_ -- Jan 9
- [ ] **EXPLORE-02**: Compare tried actions against global combination list to find untried actions
  - _"I search from my list of combinations of relationships. And I see which one I haven't performed yet"_ -- Jan 9
- [ ] **EXPLORE-03**: Perform the untried action and record result in all graphs
  - _"And then I perform that one"_ -- Jan 9
- [ ] **EXPLORE-04**: Depth-first search through graph for systematic exploration
  - Jan 9: exploration = search algorithm through graph
- [ ] **EXPLORE-05**: Episode-based exploration (start, explore, end, save trajectory)
  - Jan 24: after experimentation, exploration is the first intelligence
- [ ] **EXPLORE-06**: Repetition -- replay successful trajectories from previous episodes
  - Jan 9: repetition intelligence uses prior episode data

## Awareness Intelligence (AWARE)

- [ ] **AWARE-01**: Collect current state from environment ("where the environment says I am")
  - _"where I am that you're saying comes from the environment"_ -- Jan 9
- [ ] **AWARE-02**: Search current state in knowledge graph ("where I think I am")
  - _"where I am internally on the system is important"_ -- Jan 9
- [ ] **AWARE-03**: Compare environment state vs graph state, flag discrepancies
  - _"awareness is just comparing where I think I am and what the environment tells that I am, that's it"_ -- Jan 9

## Planning / MPC Intelligence (PLAN)

- [ ] **PLAN-01**: Goal defined as interval on state variable (e.g., position 50-60)
  - _"the first goal is to be from 51 to 100... the second goal is speed from 45 to 55"_ -- pre-2026
- [ ] **PLAN-02**: Planning = pathfinding through the knowledge graph
  - _"Planning is just finding path from here to here"_ -- Jan 31 Graph
- [ ] **PLAN-03**: Multi-frame chaining when target unreachable in one frame
  - _"can I go in one frame from 100 to 112? No... in two frames? Yes"_ -- Jan 31 Graph
- [ ] **PLAN-04**: System knows what's achievable per frame (from MIN/MAX/bins)
  - _"If our system calculates it needs to move from 100 to 112 in one frame, the system knows that is wrong"_ -- Jan 31 Graph
- [ ] **PLAN-05**: Dynamic timestep -- increase planning frequency when off-target
  - _"the frequency of the calculation is going to be higher"_ -- pre-2026
- [ ] **PLAN-06**: Constraint intervals -- cannot leave safe bounds during planning
  - _"for us, falling is not an option"_ -- pre-2026
- [ ] **PLAN-07**: Graceful failure when no path found
  - _"path not found for such safety"_ -- pre-2026

## Hierarchical Intelligence (HIER)

- [ ] **HIER-01**: Goal composition -- combine multiple intervals across variables (AND logic)
  - _"the first goal is to be from 51 to 100. The second goal is speed from 45 to 55. And then distance from other car..."_ -- pre-2026
- [ ] **HIER-02**: Goal decomposition into achievable subgoals
  - Vacuum robot analogy: decompose complex goals into Level 1 actions
- [ ] **HIER-03**: Multi-level planning (Level N operates on aggregates of Level N-1)
  - Vacuum robot: Level 1 = individual, Level 2 = coordinate 2, Level 3 = coordinate floors
- [ ] **HIER-04**: Inter-level communication (Level N sends commands down, Level N-1 sends state up)
  - Architecture meetings: information flows bidirectionally between levels
- [ ] **HIER-05**: System stops if no safe path found through all constraint layers
  - Goal-based, not reward-based: system must respect all constraints

---

## Future Requirements (Deferred from this milestone)

- Knowledge derivation (speed = delta-position / delta-time) -- optimization after core works
- Stress testing (60,000 nodes/second performance) -- after graph infrastructure proven
- Graph persistence to FalkorDB -- after in-memory graphs working
- Documentation mode (skip experimentation if system has docs) -- after experimentation proven
- Multi-environment validation (drones, robots) -- needs simulated environments
- Production hardening (logging, monitoring, rollback) -- after core pipeline works
- Safety modes (simulation vs real-world) -- after planning works

## Out of Scope

| Feature | Reason |
|---------|--------|
| GPU acceleration | CPU-first implementation |
| Neural network training | Graphs are data structures, not learned models |
| Reward functions (traditional RL) | Goal/constraint-based, not reward-based |
| Multi-agent communication | Single-agent focus |
| Real-world hardware deployment | Simulation-first |

---

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| INIT-01 | Phase 1: System Initialization | ✓ Done |
| INIT-02 | Phase 1: System Initialization | ✓ Done |
| INIT-03 | Phase 1: System Initialization | ✓ Done |
| INIT-04 | Phase 1: System Initialization | ✓ Done |
| INIT-05 | Phase 1: System Initialization | ✓ Done |
| INIT-06 | Phase 1: System Initialization | ✓ Done |
| BRAIN-01 | Phase 2: Brain Capacity Micro-Processes | Pending |
| BRAIN-02 | Phase 2: Brain Capacity Micro-Processes | Pending |
| BRAIN-03 | Phase 2: Brain Capacity Micro-Processes | Pending |
| BRAIN-04 | Phase 2: Brain Capacity Micro-Processes | Pending |
| BRAIN-05 | Phase 2: Brain Capacity Micro-Processes | Pending |
| BRAIN-06 | Phase 2: Brain Capacity Micro-Processes | Pending |
| BRAIN-07 | Phase 2: Brain Capacity Micro-Processes | Pending |
| BRAIN-08 | Phase 2: Brain Capacity Micro-Processes | Pending |
| BRAIN-09 | Phase 2: Brain Capacity Micro-Processes | Pending |
| BRAIN-10 | Phase 2: Brain Capacity Micro-Processes | Pending |
| GRAPH-01 | Phase 3: Knowledge Graph Infrastructure | Pending |
| GRAPH-02 | Phase 3: Knowledge Graph Infrastructure | Pending |
| GRAPH-03 | Phase 3: Knowledge Graph Infrastructure | Pending |
| GRAPH-04 | Phase 3: Knowledge Graph Infrastructure | Pending |
| GRAPH-05 | Phase 3: Knowledge Graph Infrastructure | Pending |
| GRAPH-06 | Phase 3: Knowledge Graph Infrastructure | Pending |
| GRAPH-07 | Phase 3: Knowledge Graph Infrastructure | Pending |
| GRAPH-08 | Phase 3: Knowledge Graph Infrastructure | Pending |
| GRAPH-09 | Phase 3: Knowledge Graph Infrastructure | Pending |
| GRAPH-10 | Phase 3: Knowledge Graph Infrastructure | Pending |
| GRAPH-11 | Phase 3: Knowledge Graph Infrastructure | Pending |
| GRAPH-12 | Phase 3: Knowledge Graph Infrastructure | Pending |
| EXPLORE-01 | Phase 4: Exploration and Awareness | Pending |
| EXPLORE-02 | Phase 4: Exploration and Awareness | Pending |
| EXPLORE-03 | Phase 4: Exploration and Awareness | Pending |
| EXPLORE-04 | Phase 4: Exploration and Awareness | Pending |
| EXPLORE-05 | Phase 4: Exploration and Awareness | Pending |
| EXPLORE-06 | Phase 4: Exploration and Awareness | Pending |
| AWARE-01 | Phase 4: Exploration and Awareness | Pending |
| AWARE-02 | Phase 4: Exploration and Awareness | Pending |
| AWARE-03 | Phase 4: Exploration and Awareness | Pending |
| PLAN-01 | Phase 5: Planning / MPC | Pending |
| PLAN-02 | Phase 5: Planning / MPC | Pending |
| PLAN-03 | Phase 5: Planning / MPC | Pending |
| PLAN-04 | Phase 5: Planning / MPC | Pending |
| PLAN-05 | Phase 5: Planning / MPC | Pending |
| PLAN-06 | Phase 5: Planning / MPC | Pending |
| PLAN-07 | Phase 5: Planning / MPC | Pending |
| HIER-01 | Phase 6: Hierarchical Intelligence | Pending |
| HIER-02 | Phase 6: Hierarchical Intelligence | Pending |
| HIER-03 | Phase 6: Hierarchical Intelligence | Pending |
| HIER-04 | Phase 6: Hierarchical Intelligence | Pending |
| HIER-05 | Phase 6: Hierarchical Intelligence | Pending |

**Coverage:** 49/49 requirements mapped to phases (100%)
**All derived from Sutton meeting transcripts -- no invented requirements**

---

*Requirements defined: 2026-02-26*
*Traceability updated: 2026-02-26*
*Source: 6 meeting transcripts + authoritative spec + authoritative law*
