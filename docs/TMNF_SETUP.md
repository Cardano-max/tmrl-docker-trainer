# TMNF + TMInterface 2.x Setup Guide

## Why TMNF?

TrackMania Nations Forever (2006) + TMInterface gives us:
- **10ms deterministic physics ticks** (vs 50ms non-deterministic in TM2020)
- **Game PAUSES** waiting for Python (no real-time pressure)
- **Full state access**: velocity, forces, yaw/pitch/roll, wheel contact, RPM
- **Save/rewind state**: each probe from exact same state = Pong-like
- **No D0 subtraction needed**: deterministic = no contamination between probes

Sutton's algorithm works 100% pure — no adaptations.

### TMNF Input Facts

| Input    | Type   | Range                        | Notes                    |
|----------|--------|------------------------------|--------------------------|
| Gas      | Binary | on / off                     | No analog throttle in TMNF |
| Brake    | Binary | on / off                     | No analog brake in TMNF  |
| Steering | Analog | -65536 to +65536 (int)       | Full precision            |

This means:
- Gas and brake discovery will find 2 bins each (off vs on threshold)
- Steering discovery will run the full Sutton sweep (~21+ bins expected)

---

## Architecture

```
TMNF Game (physics engine)
        |
        v  10ms physics tick
TMInterface 2.x (ModLoader)
        |
        v  loads AngelScript plugin
SuttonBridge.as (TCP server on port 8476)
        |
        v  TCP socket (localhost)
tmnf_adapter.py (Python TCP client)
        |
        v
Sutton Algorithm (intelligence_experimentation.py)
```

The game **pauses on each 10ms tick** until Python responds. No timing pressure.
Python reads state, queues action, releases tick. Fully synchronous. Fully deterministic.

---

## Step 1: Install TMNF

TMNF is **free**.

### Option A: Official Site (standalone)
1. Go to https://trackmaniaforever.com/
2. Download TrackMania Nations Forever
3. Install (default: `C:\Program Files (x86)\TmNationsForever\`)

### Option B: Steam (free)
1. Open Steam → Search "TrackMania Nations Forever"
2. Click "Play Game" (free) → Install

---

## Step 2: Install TMInterface 2.x via ModLoader

TMInterface 2.x uses a ModLoader approach — different from TMInterface 1.x.

1. Go to https://donadigo.com/tminterface/
2. Download the **TMInterface 2.x** release (look for ModLoader in the name)
3. Run the installer or follow the README for manual install
4. Launch TMNF once via TMInterface to confirm it hooks correctly

> **Note:** TMInterface 1.x used shared memory (`tminterface.client`).
> TMInterface 2.x uses AngelScript plugins over TCP. Our adapter uses 2.x.

---

## Step 3: Install the SuttonBridge Plugin

The plugin is an AngelScript file that opens a TCP socket and bridges Python to the game.

### Install location

Copy `TMinterface/SuttonBridge.as` from this repository to:

```
%APPDATA%\TMInterface\Plugins\SuttonBridge.as
```

Typically this resolves to:
```
C:\Users\<YourName>\AppData\Roaming\TMInterface\Plugins\SuttonBridge.as
```

### Verify plugin loaded

1. Launch TMNF via TMInterface.exe
2. Open the TMInterface console (usually F5 or overlay)
3. You should see: `[SuttonBridge] Listening on port 8476`

### Change port (optional)

In the TMInterface console, run:
```
set custom_port 9000
```
Then pass `--port 9000` when running the Python script.

---

## Step 4: Install Python Dependencies

The `tminterface` Python package provides the `SimStateData` struct parser
(binary format for state bytes received over TCP):

```bash
pip install tminterface
```

Verify:
```bash
python -c "from tminterface.structs import SimStateData; print('OK')"
```

> **Note:** We no longer use `tminterface.client` or `tminterface.interface`.
> Only `tminterface.structs` is used for parsing binary state data.

---

## Step 5: Launch TMNF via TMInterface

1. Open `TMInterface.exe` (in your TMNF folder or from ModLoader)
2. TMNF should launch with the TMInterface overlay
3. Check TMInterface console for: `[SuttonBridge] Listening on port 8476`

If the plugin does not load, check that `SuttonBridge.as` is in the Plugins folder.

---

## Step 6: Start a Race

1. In TMNF: Solo → Start a Race
2. Pick any track (a simple flat track is best for discovery)
3. Start the race and let the countdown finish (or start probing from countdown — it works either way)

---

## Step 7: Run the Test

With TMNF running and SuttonBridge connected:

```bash
python test_phase_a_tmnf.py
```

### Options

```bash
# Default: rewind between probes (each probe from identical state)
python test_phase_a_tmnf.py

# Without rewind (sequential probing — car state accumulates)
python test_phase_a_tmnf.py --no-rewind

# Speed up the game (useful for faster discovery)
python test_phase_a_tmnf.py --speed 5.0

# Custom port (if you changed it in TMInterface)
python test_phase_a_tmnf.py --port 9000

# Only discover steering (skip gas/brake — they're binary so trivial)
python test_phase_a_tmnf.py --steering-only

# Specific actions
python test_phase_a_tmnf.py --actions steering,gas
```

---

## What to Expect

### Gas and Brake

Gas and brake are **binary** in TMNF. The discovery algorithm will find:
- `delta_0` near 0 (no input = no acceleration)
- `delta_max` at gas=1.0 (full gas)
- Binary threshold: discovery finds the switch point (~0.001 or similar)
- **2 bins** for gas, **2 bins** for brake

This is expected and correct. Binary inputs have 2 bins: off and on.

### Steering

Steering is **analog**. The full Sutton downward sweep runs:
- Powers of 10 sweep (1.0, 0.1, 0.01, ...) to bracket MAX
- Binary search for exact MAX
- Powers of 10 sweep downward for MIN
- Binary search for exact MIN
- Bidirectional bins (symmetric: negative steer = left turn)

Expected: ~21+ bins, similar to TM2020 steering discovery.

### With Rewind (default)

Each probe starts from the EXACT same state. Deltas are perfectly comparable.
```
steering=1.0  → delta_yaw = +X (max right turn from this exact state)
steering=0.5  → delta_yaw = +Y (same starting state, half steering)
steering=0.01 → delta_yaw = +Z (same starting state, minimal steering)
```

No noise, no D0 subtraction, no contamination. Pure Sutton.

### Without Rewind

Sequential probing. Car state accumulates between probes.
Deltas include speed/drag changes. Still deterministic.

---

## Troubleshooting

### "Could not connect to SuttonBridge.as plugin"

1. Is TMNF launched via TMInterface.exe? (not directly)
2. Is `SuttonBridge.as` in `%APPDATA%\TMInterface\Plugins\`?
3. Does the TMInterface console show `Listening on port 8476`?
4. Is another process using port 8476? Try `--port 8477`

### "No race detected"

- Start a solo race in TMNF first
- Wait for the countdown to begin (or finish — either works)
- Then run the script

### "Timeout waiting for state"

- The game might be paused or at the main menu
- Make sure a race is actively running
- Check TMInterface overlay is active

### Plugin shows "Failed to bind port"

- Another process is using that port
- Change port: `set custom_port 8477` in TMInterface console
- Run Python with `--port 8477`

### Old tminterface imports fail

If you see errors like:
```
ImportError: cannot import name 'Client' from 'tminterface.client'
```
This is expected — the old mmap API no longer works with TMInterface 2.x.
The new `tmnf_adapter.py` uses TCP sockets and does NOT import `tminterface.client`.
Only `tminterface.structs` (for binary state parsing) is needed.

### Connection drops mid-run

- The plugin has no hard timeout on Python response — Python can take as long as needed
- Check for exceptions in the Python console
- Restart TMNF + plugin and re-run

---

## File Reference

| File | Purpose |
|------|---------|
| `TMinterface/SuttonBridge.as` | AngelScript TCP bridge plugin (install to Plugins folder) |
| `adapters/tmnf_adapter.py` | Python TCP client (uses TCP, not old mmap API) |
| `test_phase_a_tmnf.py` | Phase A discovery script for TMNF |
| `docs/TMNF_SETUP.md` | This file |
