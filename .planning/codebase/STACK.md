# Technology Stack

**Analysis Date:** 2026-01-31

## Languages

**Primary:**
- Python 3.x - Entire system: core logic, intelligence modules, adapters, knowledge management
  - Files: `core/`, `intelligence/`, `adapters/`, `knowledge/`, `control/`, `utils/`

**Configuration:**
- JSON - System and environment configuration
  - Files: `config/system_config_corrected.json`, `config/server_config.json`, `config/trainer_config.json`

## Runtime

**Environment:**
- Python 3.x interpreter (version not explicitly pinned, assumed 3.8+)

**Package Manager:**
- pip (Python package installer)
- Lockfile: Not detected (no requirements.txt, pipfile, or poetry.lock found)

## Frameworks & Key Libraries

**Core Dependencies:**

- **falkordb** - Graph database client
  - Purpose: Persistent knowledge graph storage
  - Used in: `core/brain_core.py`, `knowledge/knowledge_manager.py`, `run_initialization.py`
  - Critical for storing discovered bins, frames, transitions
  - Version: Not pinned

- **vgamepad** - Virtual Xbox 360 controller
  - Purpose: Real-time control input to TrackMania
  - Used in: `adapters/tmrl_live_adapter.py`
  - Requires: ViGEmBus driver installed on Windows
  - Version: Not pinned

**Standard Library Modules Used:**
- `socket` - TCP communication with TrackMania (port 9000)
  - Files: `adapters/tmrl_live_adapter.py`, `control/environment_protocol.py`
- `struct` - Binary protocol parsing (11 floats from TMRL_GrabData)
  - Files: `adapters/tmrl_live_adapter.py`
- `threading` - Concurrent I/O handling
  - Files: `adapters/tmrl_live_adapter.py` (receive thread, action send)
- `json` - Configuration and state serialization
  - Used throughout for config parsing
- `logging` - Structured logging
  - Used in all modules for debug/info output
- `time` - Timing measurements, frame synchronization
  - Critical for respecting FPS constraints (50ms per frame = 20Hz)
- `dataclasses` - Data structure definitions
  - Used for: LiveObservation, LiveAction, FrameObservation, FrameAction, StateVector
- `typing` - Type hints
  - Used throughout for IDE support and documentation
- `pathlib` - Path operations
- `itertools` - product() for action combination generation
- `functools` - lru_cache for optimized queries
- `statistics` - Data analysis (mean, median for discovery)
- `collections.deque` - Episode history buffer
- `enum` - Episode end reasons, goal types

## Configuration

**Environment Configuration:**
- Primary: `config/system_config_corrected.json` (current production config)
- Legacy: `config/server_config.json`, `config/trainer_config.json`

**Configuration Structure:**
- Actions: gas, brake, steering (continuous, normalized ranges)
- Feedbacks: speed (critical), gear, rpm
- Experimentation: min_action_step (0.01), change_threshold (0.001)
- Environment: type="tmrl", mode="offline|live", protocol="direct"
- Timing: frame_duration_ms=50 (20 FPS match requirement)
- Database: host="localhost", port=6379 (FalkorDB/Redis)
- Intelligence modules: awareness, repeat, exploration, future constraints, monitoring

**Hard-Coded Configuration Concerns:**
Per meeting transcript (24 Jan 2026), supervisor (Dr. Sutton) requires:
- Frame duration and FPS must be READ FROM CONFIG, not hard-coded
- Currently: `frame_duration_ms=50` defined in config
- Must NOT create arbitrary timestamps - use system/environment FPS

## Database & Storage

**Graph Database:**
- FalkorDB (Redis-based graph database)
  - Connection: TCP localhost:6379
  - Graphs used:
    - `knowledge`: Frame nodes with ACTION edges (per-frame recording)
    - `system_config`: DiscoveredBins (min/max for gas/brake/steering)
    - `discovery_log`: DiscoveryResult details
  - Client: `falkordb` Python package

**Data Structures:**
- Frame nodes: `frame_id`, `speed`, `gear`, `rpm`, `timestamp`
- Transition edges: `gas`, `brake`, `steering` values
- Bin discovery results: min, max, ratio, order_of_magnitude
- No in-memory persistence between runs (volatile)

## Networking

**TMRL (TrackMania) Integration:**
- Protocol: TCP socket
- Host: 127.0.0.1 (localhost only)
- Port: 9000 (configurable in config)
- Data Format: Binary struct with 11 floats (44 bytes per packet)
  - From TMRL_GrabData OpenPlanet plugin
  - Fields: speed, distance, pos_x/y/z, input_steer, input_gas, input_brake, finished, gear, rpm

**Socket Details:**
- Receive: Streaming data at 20 Hz (50ms per frame)
- Send: Virtual gamepad controller input (gas, brake, steering)
- Threading: Dedicated receive thread prevents blocking reads

## Virtual Controller

**vgamepad Implementation:**
- Provides VX360Gamepad class (virtual Xbox 360 controller)
- Methods:
  - `left_joystick_float(x, y)` - Steering control
  - `right_trigger_float()` - Gas pedal
  - `left_trigger_float()` - Brake pedal
- Requires: ViGEmBus driver installation (Windows only)
- Fallback: System works offline without vgamepad, but cannot control live

## Time Synchronization

**Frame-Based Timing:**
- Environment-driven: FPS defined by TrackMania (60 fps) but system runs at 20 Hz (50ms)
- Frame ID: Sequential counter from environment
- Timestamp: System clock (absolute time)
- Critical constraint (from supervisor): ALL calculations must complete in 50ms window
- Timing verification: `TimestampManager` validates frame boundaries

## Memory Management

**Short-Term Memory:**
- RAM-based episode storage
- Capacity: configurable (default 10)
- Used for: quick replay, recent transition lookup

**Long-Term Memory:**
- FalkorDB persistent storage
- Used for: knowledge graphs, discovered bins, historical analysis

**No Explicit Caching Layer:**
- lru_cache used for query optimization (brain_core.py)
- Batch processing: configurable batch_size (default 100)

## Testing & Development

**Test Files Present:**
- `test_sutton_live.py` - Sutton-compliant algorithm validation
- `demo_test_harness.py` - System integration tests
- `diagnose_telemetry.py` - Connection diagnostics
- `run_order_system_standalone.py` - Standalone order discovery testing
- `verify_falkordb.py` - Graph database verification
- `verify_falkordb_graphs.py` - Graph content inspection

**No Detected Testing Framework:**
- No pytest, unittest, or tox configuration
- Tests appear to be manual validation scripts
- No CI/CD pipeline detected

## Deployment & Distribution

**Deployment Environment:**
- Target: Windows (vgamepad/ViGEmBus support)
- Docker support partially present: references to `/root/TmrlData/checkpoints` but no active Dockerfile
- Local development: Direct Python execution

**Requirements Not Explicitly Documented:**
- vgamepad installation: `pip install vgamepad`
- ViGEmBus driver: Manual Windows installation required
- FalkorDB: Docker container or local installation required
- TrackMania 2020 with OpenPlanet plugin + TMRL_GrabData

## Meeting Requirements Cross-Reference

**From meeting transcript (24 Jan 2026, Dr. Sutton):**

✅ **IMPLEMENTED:**
1. FalkorDB for knowledge graphs - ACTIVE
2. Per-frame action recording (not continuous) - ACTIVE in `control/frame_action_controller.py`
3. Frame-based timing (50ms = 20Hz) - CONFIGURED in system_config_corrected.json
4. Timestamp from environment FPS - TimestampManager reads frame_duration_ms from config
5. Order-of-magnitude discovery algorithm - `intelligence/order_discovery.py` implements Sutton-compliant paired nudge
6. Bin discovery as capacity (mandatory before recording) - `run_initialization.py` requires successful discovery
7. No state reset during bin discovery - Uses paired nudges without forcing baseline

⚠️ **REQUIRES VALIDATION:**
1. Hardcoded timestamp values - Verify all frame timing uses config, not magic numbers
2. FalkorDB capacity (memory limits) - Needs stress testing for millions of nodes/sec
3. Action synchronization - Must ensure no frame is missed during action transmission

---

*Stack analysis: 2026-01-31*
