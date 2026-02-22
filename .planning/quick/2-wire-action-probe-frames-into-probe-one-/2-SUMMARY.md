---
phase: quick-2
plan: 01
subsystem: intelligence
tags: [bin-discovery, probe-frames, brake, multi-frame]

# Dependency graph
requires:
  - phase: quick-1
    provides: "Refactored algorithm with single downward sweep"
provides:
  - "Multi-frame probe system with action-specific frame counts"
  - "Stabilization coast for clean D0 measurement"
  - "Speed recovery between probes for consistent deltas"
  - "Action-specific probe speeds (brake=50 km/h)"
affects: [phase-a-bin-discovery]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ACTION_PROBE_FRAMES dict lookup with PROBE_FRAMES as default"
    - "probe_frames local variable captured in closure scope"
    - "ACTION_PROBE_SPEEDS dict for action-specific regime speeds"

key-files:
  created: []
  modified:
    - intelligence/intelligence_experimentation.py

key-decisions:
  - "Brake uses 3 probe frames (immediate response, no drivetrain startup)"
  - "Gas/steering use 10 probe frames (drivetrain needs ~6 frames to engage)"
  - "Brake probed at 50 km/h (at low speed, brake indistinguishable from drag)"
  - "Speed recovery brings car back to D0 speed ±2 km/h between probes"
  - "Stabilization coast: 5 consecutive negative-delta frames = pure drag"

patterns-established:
  - "Multi-frame probes: apply action N frames, measure last-frame delta"
  - "Speed recovery between probes for consistent operating point"

# Metrics
duration: 3min
completed: 2026-02-22
---

# Quick Task 2: Wire ACTION_PROBE_FRAMES into probe_one_frame Summary

**Action-specific probe frame counts + full multi-frame probe system commit**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-22
- **Completed:** 2026-02-22
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Wired `ACTION_PROBE_FRAMES` dict into `probe_one_frame()` closure via `probe_frames` local variable
- Brake now uses 3 probe frames (was always 10) — car stays near D0 speed for comparable deltas
- Gas/steering keep 10 frames (drivetrain startup ~6 frames)
- Committed all multi-frame probe system changes from previous session:
  - Multi-frame probes (apply action N frames, measure steady-state delta)
  - Stabilization coast (5 negative-delta frames = pure drag before D0)
  - Speed recovery between probes (consistent operating point)
  - Action-specific probe speeds (brake=50 km/h, others=25 km/h)
  - Removed unused methods (_binary_search_min_consecutive, search_bin_boundaries)

## Task Commits

1. **Task 1: Wire ACTION_PROBE_FRAMES + commit multi-frame probe system** - `6afaf24` (refactor)

## Files Modified
- `intelligence/intelligence_experimentation.py` - probe_one_frame uses action-specific frame count, full multi-frame probe system

## Key Change

Before (always 10 frames for all actions):
```python
for i in range(self.PROBE_FRAMES):  # Always 10
```

After (action-specific):
```python
probe_frames = self.ACTION_PROBE_FRAMES.get(action_name, self.PROBE_FRAMES)
for i in range(probe_frames):  # brake=3, others=10
```

Frame indices also updated to use `probe_frames` instead of `self.PROBE_FRAMES`.

## Deviations from Plan

None - plan executed exactly as written.

## Next Steps

- Run live test to verify brake detection works with 3 probe frames at 50 km/h
- Compare stability across runs

---
*Phase: quick-2*
*Completed: 2026-02-22*
