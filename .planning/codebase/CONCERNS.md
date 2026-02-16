# Codebase Concerns

**Analysis Date:** 2026-02-16

## Tech Debt

**Deprecated Discovery Algorithm Still Present:**
- Issue: `OrderDiscovery` class (lines 575-1244 in `intelligence/order_discovery.py`) marked DEPRECATED - violates Sutton's "no state reset" constraint
- Files: `intelligence/order_discovery.py:575-1244`, `intelligence/order_discovery.py:1237-1243`
- Impact: Dead code consuming ~600 lines; confusion about which discovery method to use; `discover_bins_single_pass()` redirects to correct method but creates indirection
- Fix approach: Remove deprecated `OrderDiscovery` class entirely; keep only `SuttonCompliantDiscovery` (lines 87-570)

**Vestigial Reward Variable:**
- Issue: `memory_handler.py` line 39 contains `rewards: List[float]` field - violates meeting requirement "Our goal there's no reward, there's no policy"
- Files: `memory_handler.py:39`
- Impact: Misleading terminology; violates semantic purity of gap_report.md requirement N2
- Fix approach: Rename to `outcomes` or remove entirely; update any code that references this field

**Multiple Test/Discovery Variants:**
- Issue: `discover_v1.py`, `discover_v2.py`, `discover_v3.py` exist alongside main codebase - unclear which is current vs experimental
- Files: `discover_v1.py`, `discover_v2.py`, `discover_v3.py`
- Impact: Maintainability confusion; duplicated logic; unclear which version implements correct algorithm
- Fix approach: Consolidate into single discovery entry point or move experimental variants to `archive/`

## Known Bugs

**Action Sending Not Wired to Real Environment (L6 Limitation):**
- Issue: System records actions but doesn't send them to TMRL in control mode
- Files: `core/brain_core.py` (send_action methods exist but may not reach OpenPlanet), `adapters/tmrl_live_adapter.py:180-195`
- Trigger: Running live validation script without manual environment setup
- Symptoms: System initializes, discovers bins, records transitions, but car doesn't actually receive input
- Workaround: `TMRLLiveAdapter.send_action()` implemented but requires actual TMRL/OpenPlanet connection to validate
- Impact: System cannot close the control loop - operates in observation/learning mode only

**Simulated TMRL Interface in Validation:**
- Issue: `stepD_live_validation.py` uses mock `TMRLInterface` class (lines 91-111) that returns random feedback values
- Files: `stepD_live_validation.py:91-111` (get_observation returns random values)
- Trigger: Running validation without real TrackMania + OpenPlanet running
- Symptoms: Validation passes with synthetic data; transitions appear valid but don't reflect real environment dynamics
- Impact: Validation script cannot verify against real environment; false positives on system correctness
- Fix approach: Integrate with actual `TMRLLiveAdapter` connection; skip validation if TrackMania unavailable

## Performance Bottlenecks

**Single-Threaded Knowledge Graph Recording (L7 Limitation):**
- Problem: Transitions recorded to FalkorDB synchronously - each graph write blocks until complete
- Files: `core/brain_core.py:534-567` (edge creation), `knowledge/knowledge_manager.py` (record_transition calls)
- Current implementation: Each call to `record_transition()` executes blocking `graph.query()` (brain_core.py line 538, 554, 592, 635, 666, 681, 702)
- Cause: FalkorDB Python client uses synchronous I/O; query executes immediately
- Bottleneck: At high telemetry rates (500Hz+), recording one transition per frame can exceed frame duration
- Impact: Decision cycle may miss frame boundaries; experimentation timing affected
- Improvement path:
  1. Implement batch recording (evidence exists in `coordinator.record_batch()` - brain_core.py suggest this but not implemented)
  2. Move graph writes to async queue
  3. Or: Reduce recording frequency (record every Nth transition)

**No Query Result Caching (L8 Limitation):**
- Problem: Each state query hits FalkorDB directly; repeated queries for same state reexecute same computation
- Files: `core/brain_core.py:652-674` (query_transition method)
- Current: `query_transition()` executes Cypher query every call; no cache
- Impact: Slight overhead for knowledge-intensive operations (awareness checking, exploration planning)
- Improvement path: Add LRU cache on query results; invalidate on new transitions

**No Per-Frame Computation Budget Enforcement:**
- Problem: Experimentation and intelligence modules may exceed frame duration without detection
- Files: `intelligence/intelligence_experimentation.py:probe_one_frame()` has logging warning (line 826) but no exception
- Current: Only logs warning if cycle exceeds frame_duration_s
- Impact: Silent timing violations; frame synchronization constraint (Sutton requirement) may be violated unnoticed
- Fix approach: Implement strict frame-budget enforcement; raise exception if exceeded

## Fragile Areas

**Bin Discovery Relies on Environmental Stability:**
- Files: `intelligence/order_discovery.py:87-570` (SuttonCompliantDiscovery class), `intelligence/intelligence_experimentation.py:273-635`
- Why fragile: Algorithm assumes environment response is deterministic and repeatable; requires multiple probes per action value
- Safe modification:
  1. Add environment stability check before experimentation
  2. Detect if same action produces different feedback delta (would indicate non-deterministic environment)
  3. Increase probe repetitions automatically if variance detected
- Test coverage gaps: No tests validate discovery against stochastic environments; all test cases assume deterministic response

**State Discretization Precision Depends on Feedback Format:**
- Files: `core/brain_core.py:246-260` (update_precision method), `brain_core.py:504-520` (create indices)
- Fragility: Resolution = precision detected from feedback decimals; if feedback values are imprecise or noisy, resolution becomes too coarse
- Safe modification:
  1. Validate that detected precision matches expected precision from config
  2. Add manual precision override in config
  3. Add noise filtering before precision detection
- Test coverage: No tests validate precision detection against noisy feedback

**Knowledge Graph Query Performance Unknown at Scale:**
- Files: `core/brain_core.py:420-718` (KnowledgeGraph class), `intelligence/intelligence_repeat.py:98-170` (decision making queries)
- Unknown: How many transitions can FalkorDB handle before queries degrade
- Fragility: No explicit limits; no scaling tests; unknown query O(N) behavior
- Safe modification: Add monitoring/metrics on query execution time; flag if queries exceed threshold
- Impact: System may silently degrade as experience grows

**Adaptation to New Environment Requires Code Changes:**
- Files: `adapters/tmrl_adapter.py:242-334` (TMRLAdapter hardcodes TrackMania field parsing), `adapters/tmrl_live_adapter.py:330-395` (feedback naming)
- Fragility: New environment requires custom adapter implementation; framework exists but integration untested
- Test coverage: Only TMRL adapter tested; generic adapter pattern validated in code but not with real environment

## Scaling Limits

**FalkorDB Graph Growth (Unknown Capacity):**
- Current state: No transitions recorded yet (test system only)
- Theoretical limit: FalkorDB has no known published limits in codebase
- Concern: How many nodes/edges before queries degrade?
- Scaling path:
  1. Run stress tests (`tests/stress_test_falkordb.py` exists - 370 lines)
  2. Monitor query times as graph grows
  3. Implement graph partitioning if single-graph scaling fails
  4. Consider sharding by feedback type (already one graph per feedback)

**Memory Usage with Large Experience:**
- Concern: `StateManager` caches state history; `MemoryHandler` caches transitions
- Unknown: How much memory for 1M transitions? 10M? 100M?
- Scaling path: Add memory monitoring; implement LRU eviction for state cache

**Action Space Explosion with Disjoint Filtering:**
- Files: `core/brain_core.py:52-129` (DisjointActionValidator class)
- Current: All combinations generated then filtered for disjoint violations
- Issue: For N actions with M bins each, generates N^M combinations then filters
- Example: 3 actions × 10 bins each = 1000 combinations generated (exponential growth)
- Scaling limit: ~5 actions × ~5 bins = manageable; ~10 actions × ~10 bins = 10^10 combinations (memory explosion)
- Scaling path: Generate only valid combinations (skip disjoint violators during generation, not after)

## Dependencies at Risk

**FalkorDB Python Client Dependency:**
- Risk: FalkorDB is relatively young graph database; Python client may have stability issues
- Evidence: No version pinning in codebase (setup/requirements not shown)
- Impact: Graph write failures could halt system; no fallback storage
- Migration plan: Already using abstract `KnowledgeGraph` interface - could swap backend to Neo4j or PostgreSQL if needed

**No Async/Threading for Background Operations:**
- Files: `adapters/tmrl_live_adapter.py:15-20` (imports threading), `adapters/tmrl_live_adapter.py:166-207` (_recv_thread)
- Risk: Live adapter uses threading for receive loop but main system is single-threaded
- Fragility: Thread safety of state variables not guaranteed; potential race conditions on `self._latest_obs`
- Impact: System may crash or deadlock under concurrent access
- Mitigation: Add thread locks around shared state or use queue.Queue (thread-safe by design)

## Security Considerations

**No Input Validation on Environment Feedback:**
- Issue: Feedbacks accepted from environment without range/type validation
- Files: `adapters/tmrl_live_adapter.py:273-305` (get_observation returns dict directly), no validation before use
- Risk: Malformed feedback could cause state manager overflow or incorrect decisions
- Current mitigation: None visible
- Recommendations: Validate feedback values against expected ranges before recording

**No Authentication for TMRL Connection:**
- Issue: TMRL/OpenPlanet connection uses TCP socket with no authentication
- Files: `adapters/tmrl_live_adapter.py:172-178` (socket connection)
- Risk: Attacker could inject fake feedback or actions on shared network
- Recommendations:
  1. Add authentication token to TMRL protocol
  2. Use encrypted connection (TLS)
  3. Document network security requirements

**Knowledge Graphs Not Backed Up:**
- Issue: FalkorDB graphs stored locally; no backup mechanism visible
- Files: No backup code found in `knowledge_manager.py` or `brain_core.py`
- Risk: Loss of all acquired knowledge if database corrupted or deleted
- Recommendations: Implement periodic graph export to disk; implement rollback capability

## Test Coverage Gaps

**Bin Discovery Against Non-Deterministic Environments:**
- Untested: What happens if same action produces different feedback delta on repeated probes?
- Files: `intelligence/order_discovery.py:87-570`, `tests/test_delta_discovery.py`
- Risk: Discovery algorithm could fail silently or produce incorrect bins
- Priority: **HIGH** - affects core capability
- Current tests: All use deterministic pong environment

**Large-Scale Knowledge Graph Operations:**
- Untested: Performance with >1M transitions
- Files: `tests/stress_test_falkordb.py` exists but unclear if comprehensive
- Risk: System scales to production but queries degrade unexpectedly
- Priority: **MEDIUM** - affects production readiness

**Thread Safety of Live Adapter:**
- Untested: Concurrent access to `_latest_obs`, `_recv_thread`
- Files: `adapters/tmrl_live_adapter.py:166-207`, `adapters/tmrl_live_adapter.py:279-290`
- Risk: Race conditions under simultaneous reads/writes
- Priority: **HIGH** - affects system stability

**Disjoint Action Validation Edge Cases:**
- Untested: What if all actions are mutually disjoint? What if no actions are disjoint?
- Files: `core/brain_core.py:81-104` (is_valid_combination)
- Risk: Empty action space or overconstrained system
- Priority: **MEDIUM**

**Adaptation to New Environments:**
- Untested: Generic adapter pattern with non-TMRL environment
- Files: `adapters/tmrl_adapter.py:58-91` (GenericEnvironmentAdapter), but no tests
- Risk: Pattern documented but never validated; new environments may fail silently
- Priority: **MEDIUM** - blocks environment portability claims

## Missing Critical Features

**No Real-Time Action Sending (L6):**
- Problem: EnvironmentProtocol defined but action transmission to environment not verified
- Blocks: System cannot close control loop; only observation/learning possible
- Implementation exists: `TMRLLiveAdapter.send_action()` in `adapters/tmrl_live_adapter.py:180-195`
- Blocker: No validation that actions actually reach TrackMania; no feedback loop confirmation
- Fix: Implement action echo from environment (send action X, verify TrackMania received X)

**No Pathfinding to Goal State (Future Constraints):**
- Problem: `goal_orchestrator.py:256` has TODO comment "Query knowledge graphs for path to target"
- Blocks: Closed-ended goals cannot plan path to target
- Current: Returns optimistic default (True, 0.5)
- Impact: Goal validation incomplete; system cannot verify feasibility of goals
- Requirements: Implement graph traversal to find action sequence from current state to goal state

**No Probabilistic Pathfinding (Architecture Constraint):**
- Problem: Mentioned in Sutton transcripts as future work; not implemented
- Blocks: Multi-step planning in stochastic environments
- Current: Deterministic system only
- Status: INTENTIONALLY NOT IMPLEMENTED per supervisor ("learn MPC first")
- Impact: None currently (deterministic system constraint is intentional)

**No MPC Integration (Intentional Future Work):**
- Problem: Supervisor explicitly said "not implement MPC and control car... just learn and understand MPC"
- Status: NOT A BUG - intentional design decision
- Evidence: latest_meeting_transcript.txt lines ~200-250
- When to implement: After MPC study complete (supervisor referenced do-mpc.com)

## Architectural Constraints / Known Limitations

**L1-L12 From known_limitations.md (ALL NOTED - Most Resolved, Some Remain):**

**RESOLVED Issues:**
- ✅ L1: Experimentation interference - FIXED (2026-01-12)
- ✅ L2: Knowledge clearing - FIXED
- ✅ L6: Real-time action sending - IMPLEMENTED (awaits validation)

**REMAINING Limitations:**
- L3: Failure conditions assume TrackMania feedback names (`speed`, `lidar_0`, etc.) - workaround documented
- L5: TMRL memory format only - workaround: implement custom `MemoryExtractor`
- L7: Single-threaded knowledge recording - workaround: use batch recording
- L8: No query caching - low impact, documented
- L9: OpenPlanet required - environmental requirement
- L10: Docker Windows networking - documented workaround with IP addresses
- L11: One action per frame - architectural constraint, intentional
- L12: Episode length not goal-based - architectural constraint, intentional

**Impact:** Most limitations are documented and have workarounds. None are critical blockers.

## Summary by Severity

| Severity | Category | Count | Status |
|----------|----------|-------|--------|
| **CRITICAL** | Live environment validation accuracy | 1 | Simulated interface needs real connection |
| **HIGH** | Deprecated dead code | 2 | `OrderDiscovery` class, multiple discovery versions |
| **HIGH** | Thread safety of live adapter | 1 | Race conditions possible |
| **HIGH** | Non-deterministic environment testing | 1 | No validation of bin discovery robustness |
| **MEDIUM** | Performance scalability unknown | 3 | Graph scaling, memory scaling, action space |
| **MEDIUM** | Vestigial reward variable | 1 | Semantic pollution |
| **MEDIUM** | Test coverage gaps (new environments) | 1 | Adapter pattern untested |
| **LOW** | Query caching (performance optimization) | 1 | Documented, low impact |
| **INTENTIONAL** | MPC not implemented | 1 | By design - supervisor mandate |
| **INTENTIONAL** | Pathfinding not implemented | 1 | By design - future work |

---

*Concerns audit: 2026-02-16*
