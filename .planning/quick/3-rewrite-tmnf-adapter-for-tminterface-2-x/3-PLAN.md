# Quick Task 3: Rewrite TMNF adapter for TMInterface 2.x socket bridge

## Context

Our `adapters/tmnf_adapter.py` uses the old `tminterface` Python mmap API which only works with TMInterface < 2.0.0.
User has TMInterface 2.12.0 (via ModLoader) which uses AngelScript plugins.

**Solution:** AngelScript plugin (TCP socket bridge) + Python TCP client. Based on Linesight-RL's pattern but extended with analog steer support.

**Reference:** Linesight-RL/linesight (Python_Link.as + tminterface2.py) — fetched and analyzed.

## TMNF Input Facts

- Gas: BINARY only (InputType::Up = on, off = no gas). No analog throttle.
- Brake: BINARY only (InputType::Down = on, off = no brake).
- Steering: ANALOG (InputType::Steer, -65536 to +65536).
- This means gas/brake discovery → trivial (2 bins each). Steering → full Sutton sweep.

## Tasks

### Task 1: Create AngelScript plugin `TMinterface/SuttonBridge.as`

Based on Linesight's Python_Link.as but:
- Extended `CSetInputState` to include analog steer (int32 after 4 binary bytes)
- Hardcoded port 8476 (simpler than Linesight's variable-based approach)
- Stripped: no frame capture, no camera reset, no toggle interface (keep it minimal)
- Keep: OnRunStep sync, GetSimulationState, SetInputState, RewindToState, GiveUp, SetSpeed, ExecuteCommand

Message protocol (same as Linesight with one extension):
```
CSetInputState: [int32 type][uint8 left][uint8 right][uint8 accelerate][uint8 brake][int32 steer_analog]
```
AngelScript side applies:
```
simManager.SetInputState(InputType::Up, accelerate?1:0)
simManager.SetInputState(InputType::Down, brake?1:0)
simManager.SetInputState(InputType::Steer, steer_analog)
```

Port configurable via `RegisterVariable("custom_port", 8476)`.

### Task 2: Rewrite `adapters/tmnf_adapter.py` — TCP socket client

Replace old mmap-based code with TCP socket client. Same public API:
- `connect(port=8476)` → TCP connect to localhost:port
- `get_feedbacks()` → Dict[str, float] (speed, position, velocity, yaw, etc.)
- `send_action_dict({'gas': 0-1, 'brake': 0-1, 'steering': -1 to +1})` → sends CSetInputState
- `wait_one_tick()` → waits for next SCRunStepSync from game
- `save_state()` → CGetSimulationState, store bytes
- `rewind()` → CRewindToState with saved bytes
- `set_speed(float)` → CSetSpeed
- `give_up()` → CGiveUp

State parsing uses `SimStateData` from `tminterface.structs` (same binary format over TCP).

Threading model:
- Main thread calls adapter methods (sequential algorithm)
- Background thread reads SCRunStepSync messages from game
- Same Event-based synchronization as before

### Task 3: Update `test_phase_a_tmnf.py`

- Update action configs for TMNF reality: gas=binary, brake=binary, steering=analog
- Add setup instructions in script header (copy .as plugin, set port, start race)
- Verify adapter connects and runs discovery

## Files

| File | Action |
|------|--------|
| `TMinterface/SuttonBridge.as` | CREATE — AngelScript plugin |
| `adapters/tmnf_adapter.py` | REWRITE — TCP socket client |
| `test_phase_a_tmnf.py` | UPDATE — TMNF-specific configs |
| `docs/TMNF_SETUP.md` | UPDATE — new setup instructions |

## Verification

1. Plugin deploys to TMInterface Plugins folder
2. Python connects to plugin via TCP
3. `get_feedbacks()` returns valid state data
4. `send_action_dict()` makes car move
5. `save_state()` + `rewind()` works
6. Full discovery run completes
