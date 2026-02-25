---
phase: quick
plan: "3"
subsystem: tmnf-adapter
tags: [tmnf, tminterface, tcp, angelscript, adapter]
dependency_graph:
  requires: [adapters/tmnf_adapter.py, tminterface.structs]
  provides: [TMinterface/SuttonBridge.as, adapters/tmnf_adapter.py]
  affects: [test_phase_a_tmnf.py, docs/TMNF_SETUP.md]
tech_stack:
  added: [TCP sockets, AngelScript plugin, struct packing]
  patterns: [background-thread receive loop, event-based tick synchronization]
key_files:
  created:
    - TMinterface/SuttonBridge.as
  modified:
    - adapters/tmnf_adapter.py
    - test_phase_a_tmnf.py
    - docs/TMNF_SETUP.md
decisions:
  - "Port 8476 hardcoded as default in both plugin and adapter; configurable via RegisterVariable custom_port"
  - "CSetInputState extended: original 4-byte binary payload + int32 analog steer appended"
  - "Gas and brake documented as binary-only in TMNF; discovery will find 2 bins each"
  - "Background thread owns socket reads; main thread owns action writes via _lock"
  - "SavedState wraps raw bytes (not SimStateData object) to avoid re-serialization"
metrics:
  duration: "~6 minutes"
  completed: "2026-02-25"
  tasks: 4
  files_changed: 4
---

# Quick Task 3: Rewrite TMNF Adapter for TMInterface 2.x

Replaced old mmap-based `tminterface.client` adapter with TCP socket bridge using AngelScript plugin pattern from Linesight-RL, extended with analog steer support.

## What Was Done

### Task 1 — TMinterface/SuttonBridge.as (CREATE)

AngelScript TCP server plugin for TMInterface 2.x (ModLoader).

- Listens on port 8476 (configurable via `custom_port` variable)
- `Render()`: accepts new TCP connections, sends `SCOnConnectSync` handshake
- `OnRunStep()`: sends `SCRunStepSync` + race time, calls `WaitForResponse()` (game pauses here)
- `WaitForResponse()`: dispatches messages until matching type received
- `CSetInputState (10)`: reads `[uint8 left][uint8 right][uint8 accel][uint8 brake][int32 steer]`
  - Applies binary `InputType::Up/Down`, analog `InputType::Steer`
- `CGetSimulationState (9)`: `simManager.SaveState()` → streams bytes back to Python
- `CRewindToState (7)`: reads bytes from Python, reconstructs `SimulationState`, rewinds
- Also handles: `CSetSpeed`, `CGiveUp`, `CExecuteCommand`, `CPreventSimulationFinish`, `CShutdown`
- Commit: `611c23a`

### Task 2 — adapters/tmnf_adapter.py (REWRITE)

Complete rewrite replacing `from tminterface.interface import TMInterface` (mmap API) with TCP socket client.

**`_TMNFSocketClient` (internal):**
- Connects to `SuttonBridge.as` plugin over TCP localhost
- Background `run_receive_loop()` reads `SCRunStepSync`, fetches `CGetSimulationState`, signals `tick_ready`, waits for `tick_ack`, sends `CSetInputState`, acks game
- Thread-safe `_send_raw()` with `_lock`
- `_read_int32()`: 4-byte blocking recv
- `SavedState` class wraps raw bytes for rewind

**`TMNFAdapter` (public API):**
- `connect(port=8476, timeout=60)`: TCP connect + starts background thread
- `wait_for_race(timeout=120)`: waits for first tick from game
- `get_feedbacks()`: waits on `tick_ready`, returns telemetry dict
- `send_action_dict({'gas', 'brake', 'steering'})`: queues action (binary gas/brake, analog steer)
- `wait_one_tick()`: clears `tick_ready`, sets `tick_ack`, waits for next `tick_ready`
- `save_state()`: stores `_state_bytes` as `SavedState`
- `rewind()`: sends `CRewindToState` with saved bytes
- `set_speed(float)`, `give_up()`, `execute_command(str)`: direct protocol commands
- Same public API as old mmap adapter — no changes needed in ExperimentationCoordinator

Commit: `b4bec14`

### Task 3 — test_phase_a_tmnf.py (UPDATE)

- Action config corrected: `gas`/`brake` = binary type, `steering` = analog
- Epsilon values: `1e-6` gas/brake, `1e-5` steering (deterministic — no noise floor)
- Probe fn: yaw delta for steering (direct from TMInterface, no position approximation)
- New CLI flags: `--port 8476`, `--steering-only`, `--actions gas,steering`
- Setup instructions updated for plugin-based workflow
- Expected bins documented: 2 gas, 2 brake, ~21+ steering
- Commit: `e6e6955`

### Task 4 — docs/TMNF_SETUP.md (UPDATE)

- Architecture diagram updated: shows TCP path through `SuttonBridge.as`
- Step 3 added: copy `SuttonBridge.as` to `%APPDATA%\TMInterface\Plugins\`
- Step 4 updated: `pip install tminterface` for structs only (no client import)
- TMNF input facts table (binary gas/brake, analog steer)
- New CLI flags documented (`--port`, `--steering-only`, `--actions`)
- Troubleshooting: old tminterface import errors, port conflicts
- Commit: `b073c2d`

## Protocol Extension

```
Original Linesight CSetInputState:
  [int32 type=10][uint8 left][uint8 right][uint8 accel][uint8 brake]
  Total: 8 bytes

Our SuttonBridge extension:
  [int32 type=10][uint8 left][uint8 right][uint8 accel][uint8 brake][int32 steer]
  Total: 12 bytes
```

AngelScript applies both binary (Up/Down) and analog (Steer):
```angelscript
simManager.SetInputState(InputType::Up,    accelerate > 0 ? 1 : 0);
simManager.SetInputState(InputType::Down,  brake > 0 ? 1 : 0);
simManager.SetInputState(InputType::Steer, steer);  // -65536 to +65536
```

## Commits

| Commit  | Message |
|---------|---------|
| 611c23a | feat(quick-3): create AngelScript TCP bridge plugin SuttonBridge.as |
| b4bec14 | feat(quick-3): rewrite tmnf_adapter.py as TMInterface 2.x TCP socket client |
| e6e6955 | feat(quick-3): update test_phase_a_tmnf.py for TMNF binary gas/brake + TCP bridge |
| b073c2d | docs(quick-3): update TMNF_SETUP.md for TMInterface 2.x TCP bridge |

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

Files created/modified:
- FOUND: TMinterface/SuttonBridge.as
- FOUND: adapters/tmnf_adapter.py
- FOUND: test_phase_a_tmnf.py
- FOUND: docs/TMNF_SETUP.md

Commits verified:
- FOUND: 611c23a
- FOUND: b4bec14
- FOUND: e6e6955
- FOUND: b073c2d

Protocol verification:
- CSetInputState payload: 12 bytes, type=10, steer=32768 for 0.5 input: PASSED
- float_to_steer(-1.0)=-65536, (0.0)=0, (1.0)=65536: PASSED
- MessageType enum matches Linesight protocol exactly: PASSED
- tminterface.structs.SimStateData importable: PASSED
