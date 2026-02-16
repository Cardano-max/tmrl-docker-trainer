# Technology Stack

**Analysis Date:** 2026-02-16

## Languages

**Primary:**
- Python 3.x - Core system implementation, intelligence modules, adapters, knowledge management
- JavaScript (ES6+) - React UI for system code explorer (`ui/explorer/src`)

**Secondary:**
- JSON - Configuration files (`config/system_config_corrected.json`, `config/server_config.json`, `config/trainer_config.json`)

## Runtime

**Environment:**
- CPython 3.x (primary runtime for backend system)
- Node.js (for UI development and testing)

**Package Manager:**
- pip (Python dependencies)
- npm (JavaScript dependencies) - see `ui/explorer/package.json`

## Frameworks

**Core System:**
- TMRL (TrackMania Reinforcement Learning) 0.x - Environment interface for autonomous racing
  - Location: Integrated via `adapters/tmrl_adapter.py` and `adapters/tmrl_live_adapter.py`
  - Purpose: TrackMania environment communication, observation/action handling

**Knowledge Graphs:**
- FalkorDB - Graph database for knowledge representation
  - Redis-backed (running on localhost:6379 by default)
  - Used in: `core/brain_core.py`, `knowledge/knowledge_manager.py`
  - Storage: One node per frame with state transitions as edges

**Frontend:**
- React ^19.2.3 - UI framework
  - Located: `ui/explorer/src/`
  - Configuration: Create React App (CRA) via react-scripts 5.0.1

**Testing:**
- Jest - Test framework
  - Dependencies: `@testing-library/jest-dom`, `@testing-library/react`, `@testing-library/dom`
  - Configuration: Built into react-scripts

## Key Dependencies

**Critical (Backend System):**
- numpy - Numerical computations, array operations
  - Used in: `tmrl_live_control.py` for vector operations
- PyTorch (torch) - Neural network support (conditional import)
  - Used in: TMRL integration for actor modules
  - Optional: System gracefully handles ImportError if torch not available
- vgamepad - Virtual Xbox 360 controller simulation
  - Used in: `adapters/tmrl_live_adapter.py` for live control output
  - Dependency: ViGEmBus driver required on Windows
  - Purpose: Translates system actions to actual game input

**Infrastructure:**
- redis-py (via FalkorDB) - Redis protocol client
  - Purpose: Communication with FalkorDB instance
  - Connection: `localhost:6379` (configurable in `config/system_config_corrected.json`)

**Development/Testing:**
- react-scripts 5.0.1 - Build and dev server
- web-vitals ^2.1.4 - Performance metrics
- @testing-library/user-event ^13.5.0 - User interaction simulation in tests

## Configuration

**Environment:**
- Configuration: JSON files in `config/` directory
  - `system_config_corrected.json` - Main system configuration (actions, feedbacks, environment settings)
  - `server_config.json` - Server settings
  - `trainer_config.json` - Training configuration
  - Format: Flat JSON with sections for actions, feedbacks, environment, intelligence, knowledge

**Database Configuration:**
- FalkorDB: `localhost:6379` (from `config/system_config_corrected.json`)
- Graph names: `knowledge`, `system_config` (multiple named graphs supported)

**Build:**
- React Scripts configuration (implicit, via CRA)
- ESLint: `react-app` preset (in `ui/explorer/package.json`)

## Platform Requirements

**Development:**
- Python 3.x runtime
- Node.js runtime (for UI)
- FalkorDB instance (running as Redis-compatible service on port 6379)
- TrackMania 2020+ with OpenPlanet mod
- TMRL plugin for TrackMania (TMRL_GrabData plugin)
- ViGEmBus driver (Windows only, for vgamepad virtual controller)

**Production:**
- Python 3.x runtime
- FalkorDB service
- TrackMania environment with TMRL networking
- Virtual controller support (vgamepad + ViGEmBus on Windows)
- TCP/Socket connectivity to TrackMania TMRL server (default: 127.0.0.1:9000)

## Communication Protocols

**Inter-Process:**
- TCP Socket: `127.0.0.1:9000` (TMRL protocol, 11-float struct, 44 bytes per message)
- Redis Protocol: `localhost:6379` (FalkorDB communication)

---

*Stack analysis: 2026-02-16*
