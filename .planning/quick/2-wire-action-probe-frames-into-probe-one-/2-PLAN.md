---
phase: quick-2
plan: 01
subsystem: intelligence
tags: [bin-discovery, probe-frames, brake]

# Dependency graph
requires:
  - phase: quick-1
    provides: "Refactored algorithm with ACTION_PROBE_FRAMES dict"
provides:
  - "probe_one_frame uses action-specific frame count from ACTION_PROBE_FRAMES"
affects: [phase-a-bin-discovery]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Action-specific probe frame counts via ACTION_PROBE_FRAMES dict lookup"

key-files:
  created: []
  modified:
    - intelligence/intelligence_experimentation.py

key-decisions:
  - "Brake uses 3 probe frames (immediate response, no drivetrain startup)"
  - "Gas/steering keep 10 frames (drivetrain needs ~6 frames to engage)"
  - "probe_frames local variable captures action-specific count at probe creation"

patterns-established:
  - "ACTION_PROBE_FRAMES dict lookup with PROBE_FRAMES as default"
---

# Quick Task 2: Wire ACTION_PROBE_FRAMES into probe_one_frame

## Goal
The `ACTION_PROBE_FRAMES = {'brake': 3}` dict exists on `ExperimentationIntelligence` (line 809) but `probe_one_frame()` always uses `self.PROBE_FRAMES` (10). Fix the probe closure to use action-specific frame counts.

## Tasks

### Task 1: Update probe_one_frame to use ACTION_PROBE_FRAMES

**File:** `intelligence/intelligence_experimentation.py`

**Changes:**
1. At probe closure creation (~line 857), capture action-specific frame count:
   ```python
   probe_frames = self.ACTION_PROBE_FRAMES.get(action_name, self.PROBE_FRAMES)
   ```

2. Replace `self.PROBE_FRAMES` references inside the closure with `probe_frames`:
   - Line 884: `for i in range(self.PROBE_FRAMES):` → `for i in range(probe_frames):`
   - Line 888: `if i == self.PROBE_FRAMES - 3:` → `if i == probe_frames - 3:`
   - Line 890: `elif i == self.PROBE_FRAMES - 2:` → `elif i == probe_frames - 2:`

3. Update the log line (~line 1000) to show the actual probe_frames being used:
   ```python
   logger.info(f"  Probe: {probe_frames} game frames per probe, ...")
   ```

**Verification:** The loop will use 3 frames for brake (from ACTION_PROBE_FRAMES) and 10 for gas/steering (default PROBE_FRAMES).
