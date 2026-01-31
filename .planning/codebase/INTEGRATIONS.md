# External Integrations

**Analysis Date:** 2026-01-31

## APIs & External Services

**TrackMania Real-Time Control (TMRL):**
- Service: TrackMania 2020 game engine via OpenPlanet plugin
- What it's used for: Real-time racing environment, telemetry input, virtual controller output
  - SDK/Client: TMRL_GrabData OpenPlanet plugin (custom binary protocol)
  - Protocol: TCP socket to 127.0.0.1:9000
  - Data format: Binary struct with 11 floats (44 bytes)
  - Implementation: `adapters/tmrl_live_adapter.py`, `adapters/tmrl_adapter.py`
  - Dependencies:
    - TrackMania 2020 installed and running
    - OpenPlanet scripting environment loaded
    - TMRL_GrabData plugin active (provides TCP server on port 9000)

**Telemetry Data Provided:**
| Index | Field | Source | Range | Usage |
|-------|-------|--------|-------|-------|
| 0 | speed | api.Speed | 0-1000+ km/h | PRIMARY feedback (critical) |
| 1 | distance | api.Distance | 0-track length | Episode tracking |
| 2 | pos_x | api.Position.x | World coords | State tracking |
| 3 | pos_y | api.Position.y | World coords | Position history |
| 4 | pos_z | api.Position.z | World coords | Elevation tracking |
| 5 | input_steer | api.InputSteer | -1.0 to +1.0 | Action validation |
| 6 | input_gas | api.InputGasPedal | 0.0 to 1.0 | Action validation |
| 7 | input_brake | api.InputIsBraking | 0.0 or 1.0 | Action validation |
| 8 | finished | race_state == Finish | 0.0 or 1.0 | Episode end detection |
| 9 | gear | api.EngineCurGear | -1, 0, 1..6 | State tracking |
| 10 | rpm | api.EngineRpm | 0-10000+ | State tracking |

**No Yaw/Pitch/Roll Available** - System computes heading from position deltas: `atan2(dz, dx)`

## Data Storage

**Databases:**
- FalkorDB (Graph Database, Redis-backed)
  - Connection: TCP localhost:6379 (hardcoded in most code, configurable via system_config)
  - Client: `falkordb` Python package
  - Purpose: Persistent knowledge graph storage

**Graph Schema:**

1. **knowledge graph** - Per-frame knowledge recording
   ```
   Node: (:Frame {frame_id, speed, gear, rpm, timestamp})
   Edge: -[:ACTION {gas, brake, steering}]->
   Example: (Frame:0) --[:ACTION {gas:0.5}]--> (Frame:1)
   ```
   - Purpose: Track state transitions with action values
   - Created by: `knowledge/knowledge_manager.py` - `EpisodeRecorder.record_frame()`
   - Size: One node per frame + one edge per transition
   - Meeting requirement (Dr. Sutton): "system should be able to record one node per frame"

2. **system_config graph** - Discovered bins (acquired knowledge)
   ```
   Node: (:DiscoveredBins {
       gas_min, gas_max, gas_ratio,
       brake_min, brake_max, brake_ratio,
       steering_min, steering_max, steering_ratio,
       discovered_at: timestamp
   })
   ```
   - Purpose: Store min/max effective action values discovered during experimentation
   - Created by: `run_initialization.py` - `save_discovered_bins()`
   - Requirement: Must be discovered before system can record knowledge graphs

3. **discovery_log graph** - Detailed discovery results
   ```
   Node: (:DiscoveryResult {
       action, min, max, min_order, max_order, ratio, timestamp
   })
   ```
   - Purpose: Audit trail of bin discovery process
   - Created by: `run_initialization.py` - `save_discovery_log()`
   - Used for: Verification and debugging discovery algorithm

**File Storage:**
- Local filesystem only
- Checkpoint path (configurable): `/root/TmrlData/checkpoints` (Docker) or local path
- No external cloud storage

**Caching:**
- In-Memory: Episode buffer (short-term memory)
  - Capacity: configurable, default 10 episodes
  - Type: deque for FIFO eviction
- lru_cache: Python functools for query optimization in `brain_core.py`
- No distributed cache (Redis cache disabled)

## Authentication & Identity

**Auth Provider:**
- None - System runs locally with no remote authentication
- Access control: TCP socket listening on localhost only (127.0.0.1)
- No user authentication or session management

**Internal Service Authentication:**
- FalkorDB: No authentication configured (local development setup)
- TrackMania: No authentication (local game instance)

## Monitoring & Observability

**Error Tracking:**
- None (no Sentry, Datadog, or external service)
- Local logging only

**Logs:**
- Approach: Python logging module (basicConfig in multiple files)
- Format: `%(asctime)s [%(levelname)s] %(message)s`
- Levels: DEBUG, INFO, WARNING, ERROR
- Output: Console stderr
- Location: `logging.basicConfig()` in:
  - `run_initialization.py`
  - `adapters/tmrl_live_adapter.py`
  - `core/brain_core.py`
  - Intelligence modules

**No Log Aggregation:**
- Logs not persisted to file
- No central log storage (development only)

**Metrics Collected:**
- Frame processing speed (97.4 transitions/sec per README)
- Knowledge graph size (node/edge counts)
- Episode duration and frame count
- State transition statistics

## CI/CD & Deployment

**Hosting:**
- None - Local development only
- Designed for Windows (vgamepad/ViGEmBus)
- Docker references in config but no active Docker setup

**CI Pipeline:**
- None detected
- No GitHub Actions, GitLab CI, or Jenkins
- Manual testing scripts only

**Deployment Process:**
1. Ensure Python 3.x installed
2. Install dependencies: `pip install falkordb vgamepad`
3. Install ViGEmBus driver (Windows)
4. Start FalkorDB: `docker run --rm -d -p 6379:3000 falkordb/falkordb`
5. Start TrackMania with OpenPlanet + TMRL_GrabData plugin
6. Run: `python run_initialization.py` or `python run_order_system.py`

**No Build Pipeline:**
- No compilation, no artifact generation
- Direct Python execution

## Environment Configuration

**Required Environment Variables:**
- None explicitly set
- All configuration via `config/system_config_corrected.json`

**Key Configuration Entries (from system_config_corrected.json):**
```json
{
  "environment": {
    "type": "tmrl",
    "mode": "offline|live",
    "adapter_module": "adapters.tmrl_adapter",
    "live_adapter_module": "adapters.tmrl_live_adapter",
    "protocol": "direct",
    "protocol_host": "127.0.0.1",
    "protocol_port": 9000,
    "timing": {
      "frame_duration_ms": 50,
      "frames_per_second": 20
    }
  },
  "system_config": {
    "database_host": "localhost",
    "database_port": 6379
  }
}
```

**Secrets Location:**
- None - No API keys, credentials, or secrets stored
- System assumes local trusted environment

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

**Event System (Internal):**
- Episode callbacks:
  - `on_episode_start()` - Validation, initialization
  - `on_episode_step()` - Frame processing, intelligence evaluation
  - `on_episode_end()` - Knowledge persistence, metrics recording
- Implementation: `control/episode_controller.py` - `EpisodeController`

## Meeting Requirements Integration Cross-Reference

**From meeting transcripts (authoritative):**

**Knowledge Graph Storage (Req-001) - Dr. Sutton 15-Jan-2026:**
- ✅ IMPLEMENTED: One node per frame (not discretized intervals)
- ✅ IMPLEMENTED: Actual observed values stored (not quantized)
- ✅ IMPLEMENTED: Named edges with action values
- ✅ IMPLEMENTED: Frame ID as unique identifier
- Location: `knowledge/knowledge_manager.py` - `record_transition()`

**Bin Discovery Requirement (Req-002) - Dr. Sutton 24-Jan-2026:**
- ✅ IMPLEMENTED: Order-of-magnitude discovery algorithm
- ✅ IMPLEMENTED: Paired nudge measurements (no state reset)
- ✅ IMPLEMENTED: MIN = smallest v where effect > threshold
- ✅ IMPLEMENTED: MAX = smallest v achieving 85% of full effect
- ✅ IMPLEMENTED: Ratio = max/min (determines number of discrete levels)
- Location: `intelligence/order_discovery.py` - `SuttonCompliantDiscovery`
- Initialization: `run_initialization.py` - `run_bin_discovery()`

**Frame-Based Action Requirement (Req-003) - Dr. Sutton 24-Jan-2026:**
- ✅ IMPLEMENTED: Actions sent per frame, not continuously
- ✅ IMPLEMENTED: Frame timing from FPS (50ms = 20Hz for TMRL)
- ✅ IMPLEMENTED: Timestamp calculated from environment FPS
- ✅ IMPLEMENTED: All calculations must complete within frame duration
- Location: `control/frame_action_controller.py` - `FrameActionController`
- Timing: `control/timestamp_manager_corrected.py` - `TimestampManager`

**Disjoint Actions (Req-004) - Dr. Sutton 24-Jan-2026:**
- ✅ IMPLEMENTED: Gas and brake marked disjoint in config
- ✅ IMPLEMENTED: Action validation prevents simultaneous gas+brake
- Location: `config/system_config_corrected.json` - `disjoint_rules`
- Validation: `core/brain_core.py` - disjoint action filtering

**Prior vs Acquired Knowledge (Req-005) - Dr. Sutton 24-Jan-2026:**
- ✅ IMPLEMENTED: Prior knowledge from config (actions, feedbacks, constraints)
- ✅ IMPLEMENTED: Acquired knowledge from FalkorDB (bins, transitions, states)
- ✅ IMPLEMENTED: Startup check asks user to use prior knowledge
- Location: `run_initialization.py` - `ask_user_choice()`

**FalkorDB Constraints (Concern) - Dr. Sutton 24-Jan-2026:**
- ⚠️ FLAGGED: "Let me search and validate... FalkorDB memory limitations"
- ⚠️ FLAGGED: "If we have 1000 graphs, 60 FPS = 60,000 nodes/sec"
- Impact: System may hit memory limits with many graphs
- Mitigation discussed: Partition into multiple graphs if needed
- Status: Needs stress testing before high-volume production use

---

*Integration audit: 2026-01-31*
