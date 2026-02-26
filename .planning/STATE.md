# Project State: Intelligent Agent Architecture

**Last Updated:** 2026-02-26 -- Milestone v1.0 started
**Current Status:** Defining requirements for Full Sutton Pipeline

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-02-26)

**Core Value:** Enable safe, goal-based autonomous learning that scales hierarchically

---

## Current Position

Phase: Not started (defining requirements)
Plan: --
Status: Defining requirements
Last activity: 2026-02-26 -- Milestone v1.0 Full Sutton Pipeline started

---

## Accumulated Context

### Phase A: Bin Discovery (COMPLETE)

**What shipped:**
- Sutton's 4-step bin discovery algorithm (FrameBinDiscovery)
- Precision discovery via binary search (measure_precision)
- TMNF + TMInterface TCP bridge (SuttonBridge.as + tmnf_adapter.py)
- Gas: 2 bins (binary), Brake: 2 bins (binary), Steering: 201 bins (precision-discovered)
- 9/9 live rubrics, 12/12 offline tests, stable 3/3 runs
- REQ-01 through REQ-25 validated

**Key Files:**
- `intelligence/intelligence_experimentation.py` -- Core algorithm
- `adapters/tmnf_adapter.py` -- TMNF TCP bridge
- `TMinterface/SuttonBridge.as` -- AngelScript plugin for TMInterface 2.x
- `test_phase_a_tmnf.py` -- Live test
- `tests/test_precision_discovery.py` -- Offline tests
- `verify_rubrics.py` -- 9 live rubric tests

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 1 | Refactor algorithm code to match meeting spec exactly | 2026-02-22 | 3e19bba | quick/1-refactor-algorithm-code-to-match-meeting/ |
| 2 | Wire ACTION_PROBE_FRAMES into probe + multi-frame probe system | 2026-02-22 | 6afaf24 | quick/2-wire-action-probe-frames-into-probe-one-/ |
| 3 | Rewrite TMNF adapter for TMInterface 2.x TCP bridge | 2026-02-25 | b073c2d | quick/3-rewrite-tmnf-adapter-for-tminterface-2-x/ |

### Decision Log

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| FrameBinDiscovery as single implementation | Most complete; includes all 4 steps + bidirectional steering | LOCKED |
| Config-driven, env-agnostic | Multiple environments, same architecture | LOCKED |
| Separate graph per state variable | Reveals action dependencies, enables knowledge derivation | LOCKED |
| Goal/constraint-based planning, not reward | Safety-critical systems cannot learn through failure | LOCKED |
| Three-layer architecture (Brain -> Knowledge -> Intelligence) | Dr. Sutton's explicit specification | LOCKED |
| D0 is context, not separate phase | algorithm_spec section 13 | LOCKED |
| TMNF + TMInterface for deterministic rewind | Pure Sutton compliance: 1 tick/probe, no D0 subtraction, no noise | LOCKED |
| Research-driven from transcripts | Sutton provides theory, we implement engineering exactly as specified | LOCKED |

---

## Meeting Transcription Files

- `archive/meeting_transcripts/meeting_transcript_09_JAn2026.txt` -- Architecture (3 layers, micro-processes)
- `archive/meeting_transcripts/meeting_transcript_15_jan_2026` -- Core algorithm (sweeps, bins)
- `archive/meeting_transcripts/meeting_transcript_24Jan2026.txt` -- Config/env (startup, prior knowledge)
- `archive/meeting_transcripts/meeing_transcription_31Jan2026.txt` -- Pong deep-dive (multiples, precision)
- `archive/meeting_transcripts/meeting_transcript_31Jan2026.txt` -- Graph formation (planning, pathfinding)
- `archive/meeting_transcripts/meeting_transcript_16feb2026.txt` -- Noise/steering (no noise, per-frame)

---

*State updated: 2026-02-26*
*Milestone v1.0: Full Sutton Pipeline -- requirements in progress*
