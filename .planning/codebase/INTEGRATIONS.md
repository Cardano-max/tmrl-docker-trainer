# External Integrations

**Analysis Date:** 2026-02-16

## APIs & External Services

**TrackMania (TMRL):**
- TMRL Framework - Reinforcement learning environment
  - SDK/Client: `tmrl` package
  - Integration: `adapters/tmrl_adapter.py`, `adapters/tmrl_live_adapter.py`
  - Protocol: Actor module interface (`TorchActorModule`, `RolloutWorker`)
  - Purpose: Environment observation/action interface for autonomous racing

**OpenPlanet (TrackMania Plugin):**
- TMRL_GrabData Plugin - Live telemetry streaming
  - Protocol: TCP binary struct over socket
  - Connection: `127.0.0.1:9000` (from config)
  - Data Format: 11 floats (44 bytes per frame) containing:
    - speed, distance, position (x, y, z)
    - inputs (steer, gas, brake)
    - race state (finished flag)
    - engine state (gear, rpm)
  - Files: `adapters/tmrl_live_adapter.py` (OpenPlanetClient class)

## Data Storage

**Databases:**
- FalkorDB (Graph Database)
  - Type: Redis-backed graph database
  - Connection: `localhost:6379` (configurable: `database_host`, `database_port` in config)
  - Client: `falkordb` Python package
  - Graphs: Multiple named graphs
    - `knowledge`: Per-frame knowledge graph (nodes: Frame objects, edges: ACTION transitions)
    - `system_config`: System metadata and discovered bins
  - Schema: Cypher query language
  - Used in: `core/brain_core.py`, `knowledge/knowledge_manager.py`, `run_initialization.py`
  - Operations: Graph creation, node recording, transition recording, querying

**File Storage:**
- Local filesystem only
  - Configuration: JSON files in `config/` directory
  - Checkpoints: `/root/TmrlData/checkpoints` (from config, path configurable)
  - No cloud storage integration detected

**Caching:**
- In-memory caching
  - Enabled: `enable_caching: true` in config
  - Cache size: `10000` entries
  - Purpose: State history and action memory

## Authentication & Identity

**Auth Provider:**
- None - System assumes local/trusted environment
- No external authentication mechanisms
- FalkorDB: No authentication configured (localhost connection)
- TrackMania/TMRL: No API keys or credentials required

## Monitoring & Observability

**Error Tracking:**
- None - No external error tracking service
- All errors logged locally

**Logs:**
- Python logging module (standard library)
  - Format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
  - Level: Configurable via config (`log_level: "INFO"`)
  - Output: Console (basicConfig used across modules)
  - Modules: Every major module initializes logging (e.g., `adapters/`, `control/`, `core/`, `knowledge/`, `intelligence/`)

**Performance Metrics:**
- Custom metrics: Frames recorded, transitions recorded, queries executed, error count
  - Location: `knowledge/knowledge_manager.py` (KnowledgeManager.stats dict)
  - Real-time tracking: 97.4 transitions/second documented

## CI/CD & Deployment

**Hosting:**
- Local development environment
- No remote deployment pipeline detected
- Docker support mentioned in historical files (deleted: Dockerfile.server, Dockerfile.trainer, docker-compose.yml)

**CI Pipeline:**
- None detected
- Manual testing via scripts: `demo_test_harness.py`, `run_initialization.py`

## Environment Configuration

**Required env vars:**
- None explicitly required; all configuration via JSON files
- System expects environment variables for:
  - Database connection (`database_host`, `database_port`)
  - Checkpoint path (`checkpoint_path`)
  - Logging level (`log_level`)

**Secrets location:**
- No secrets mechanism
- Configuration is plain JSON in `config/` directory
- No `.env` file pattern used

## Webhooks & Callbacks

**Incoming:**
- TMRL Rollout Worker callbacks (via RolloutWorker networking)
  - Purpose: Receive environment observations
  - Location: `tmrl_live_control.py` (RealIntelligenceActor class)

**Outgoing:**
- vgamepad virtual controller output
  - Purpose: Send actions to TrackMania via virtual Xbox controller
  - Location: `adapters/tmrl_live_adapter.py` (VGamepadController class)
- TCP socket to TrackMania TMRL plugin
  - Purpose: Send action structs to game
  - Protocol: Binary struct format

## Graph Database Schema

**Knowledge Graph (FalkorDB):**

Nodes:
```
(:Frame {
  frame_id: int,
  speed: float,
  gear: float,
  rpm: float,
  distance: float,
  position_x: float,
  position_y: float,
  position_z: float,
  timestamp: float
})
```

Edges:
```
-[:ACTION {
  gas: float,
  brake: float,
  steering: float
}]->
```

Transaction Example:
```
(Frame:0 {speed:0.01}) --[:ACTION {gas:0.5}]--> (Frame:1 {speed:5.23})
```

Query Pattern: Cypher (via `graph.query()` method)
- Example: `MATCH (f:Frame) RETURN count(f) as cnt`
- Example: `MATCH ()-[a:ACTION]->() RETURN count(a) as cnt`

## System Coordinator Integration Points

**Integration Sources (from `control/system_coordinator_corrected.py`):**
- FalkorDB: Knowledge graph operations
- TMRL Adapter: Environment interactions
- Goal Orchestrator: Goal-based exploration
- Episode Controller: Episode lifecycle management
- Frame/Action Controller: Per-frame action generation
- Intelligence Modules: Awareness, experimentation, exploration, future constraints

---

*Integration audit: 2026-02-16*
