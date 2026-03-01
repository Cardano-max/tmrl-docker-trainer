---
phase: quick-5
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docs/SUTTON_COMPLIANCE_AUDIT.md
  - intelligence/intelligence_experimentation.py
  - test_phase_a_tmnf.py
  - adapters/tmnf_adapter.py
autonomous: true
must_haves:
  truths:
    - "Every user question (i through viii plus follow-ups) is answered with exact file paths, line numbers, and code excerpts"
    - "Audit document explains frame duration, tick measurement, rewind, exponential sequence, precision, steering ticks, D0, and adapter thresholds with Sutton compliance verdicts"
    - "Code fixes are applied: TODO comments for state-dependence documentation, frame_duration_ms added to config timing section, precision measurement step documented"
  artifacts:
    - path: "docs/SUTTON_COMPLIANCE_AUDIT.md"
      provides: "Complete Q&A audit answering all user questions with code evidence"
      min_lines: 200
  key_links:
    - from: "docs/SUTTON_COMPLIANCE_AUDIT.md"
      to: "intelligence/intelligence_experimentation.py"
      via: "Line-number references to exponential sequence, binary search, precision"
      pattern: "intelligence_experimentation.py"
    - from: "docs/SUTTON_COMPLIANCE_AUDIT.md"
      to: "adapters/tmnf_adapter.py"
      via: "Line-number references to TICK_MS, binary threshold, rewind"
      pattern: "tmnf_adapter.py"
---

<objective>
Create a comprehensive Sutton compliance audit document that answers all of the user's specific questions about the codebase with exact code references, line numbers, and Sutton compliance verdicts. Apply targeted code fixes for identified issues (state dependence documentation, missing config fields, hardcoded values).

Purpose: The user needs to understand exactly how frame duration, ticks, rewind, exponential sequences, precision, steering ticks, D0, and adapter thresholds work in the codebase -- and whether each aspect is Sutton-compliant or needs fixing.
Output: docs/SUTTON_COMPLIANCE_AUDIT.md with all answers, plus minor code fixes.
</objective>

<execution_context>
@C:/Users/ateeb/.claude/get-shit-done/workflows/execute-plan.md
@C:/Users/ateeb/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@intelligence/intelligence_experimentation.py
@adapters/tmnf_adapter.py
@test_phase_a_tmnf.py
@control/system_initializer.py
@config/tmnf_config.json
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create comprehensive Sutton Compliance Audit document</name>
  <files>docs/SUTTON_COMPLIANCE_AUDIT.md</files>
  <action>
Create docs/SUTTON_COMPLIANCE_AUDIT.md answering ALL user questions with exact code evidence. Structure as Q&A sections:

**Q-i: Frame Duration**
- TICK_MS = 10 hardcoded at adapters/tmnf_adapter.py:47 -- used only as protocol constant (game physics tick IS 10ms)
- system_initializer.py:344-407 `_discover_frame_duration()` measures it from race_time delta -- Sutton compliant ("who defines the time stamp is the environment")
- test_phase_a_tmnf.py:208 has `frame_duration_s=0.01` hardcoded in ProbeResult -- this is the test file, not the algorithm. Verdict: TICK_MS is a protocol constant (TMNF physics engine IS 10ms), but system_initializer correctly discovers it from environment. Config should have environment.timing.frame_duration_ms for validator.
- FINDING: tmnf_config.json is MISSING `environment.timing.frame_duration_ms` field even though ConfigValidator requires it. This is a bug.

**Q-ii: How One Tick Gets Measured**
- tmnf_adapter.py `wait_one_tick()` at line 631-649: clears tick_ready, sets tick_ack (releases background thread), waits for next tick_ready
- Background thread `_handle_run_step()` at line 355-386: receives SCRunStepSync from game, fetches sim state, signals tick_ready, waits for tick_ack, applies action, acks game
- This happens NOT at start of main file -- it happens per-tick during the probe loop. The adapter.connect() starts background thread, then each wait_one_tick() cycles one physics frame.

**Q-iii: Game Pauses During Rewind**
- Game pauses because TMInterface's SCRunStepSync protocol is SYNCHRONOUS: game sends tick, waits for Python to respond before advancing
- rewind() at tmnf_adapter.py:674-701 sends CRewindToState during tick window (between tick_ready and tick_ack)
- This is GOOD per Sutton: deterministic, game is frozen while we restore state. "Pong-like" -- same state = same outcome.
- NOT hardcoding -- the game engine itself provides this synchronous stepping.

**Q-iv: Is One Frame = One Tick = One Probe?**
- One frame = one tick = one 10ms physics step: YES
- One probe = one tick: NO. Due to TMInterface's one-tick input delay, each probe is MINIMUM 2 ticks:
  - Tick 1: send action (loads for NEXT tick), read fb_before
  - Tick 2: action takes effect, read fb_after
- For steering: 1 + 5 = 6 ticks per probe (MEASURE_TICKS=5 at test_phase_a_tmnf.py:157)
- Delta is measured per-MEASURE_TICKS, not per-tick. Gas/brake: delta = speed change over 1 tick. Steering: delta = yaw change over 5 ticks.

**Q-v: Exponential Sequence -- Why Not 10^6?**
- get_exponential_sequence() at intelligence_experimentation.py line ~331-348
- Starts from action_range max (1.0 for TMNF), descends: [1.0, 0.1, 0.01, 0.001, 0.0001, 0.00001, 0.000001]
- Does NOT send 10^6, 10^5, etc. because TMNF action range is [0, 1]. Values > 1 get clamped to 1 -- wasteful probes with identical results.
- Sutton's algorithm from meetings assumed Pong with action ranges like [0, 1000]. For TMNF [0, 1], starting at 1.0 IS the "large value" in Sutton's "large value -> saturated?"
- This IS correct: the sequence exhaustively covers every power of 10 within the valid action range.

**Q-vi: Rewind in Layman Terms (With Numbers)**
- Walk through a concrete gas discovery example:
  1. Car at speed=15.2 km/h, pos=(100, 10, 50), race_time=2340ms
  2. save_state() captures ALL physics bytes (8368 bytes raw SimStateData)
  3. Probe action=1.0 (gas ON): speed -> 15.8 (delta = +0.6)
  4. rewind() sends those exact 8368 bytes back to game
  5. Car is back at speed=15.2, pos=(100, 10, 50), race_time=2340ms -- EXACTLY
  6. Probe action=0.1 (gas ON, same because binary): speed -> 15.8 (delta = +0.6)
  7. rewind() again -- back to exact same state
  8. Probe action=0.0 (no gas): speed -> 15.13 (delta = -0.068, coasting drag = D0)
  9. Every probe starts from IDENTICAL state. No D0 subtraction needed. Pure Sutton.

**Q-vii/viii: Are We Using Two Ticks Instead of One?**
- YES, minimum 2 ticks per probe. This is TMInterface's inherent input delay, not our choice.
- test_phase_a_tmnf.py:149-173 documents this: "SetInputState during OnRunStep takes effect NEXT tick, not current"
- Tick 1 uses replayed inputs (with rewind: always the same, consistent fb_before)
- Tick 2+ uses our action (the actual measurement)
- Impact on graph/planning: Delta is still per-frame for gas/brake (1 tick of action effect). For steering it's per-5-frames. The graph records the delta as-is, so the planner knows "left for 5 ticks produces yaw delta X."
- This does NOT destroy planning because the planner will chain actions using these exact deltas.

**Q: Precision -- Hardcoded or Measured?**
- search_precision=0.001 at intelligence_experimentation.py FrameBinDiscovery.__init__ line ~192 -- HARDCODED
- measurement_epsilon set externally by test_phase_a_tmnf.py (0.01 for gas/brake, 1e-5 for steer) -- HARDCODED per-action
- system_precision=6 default in ActionDiscoveryResult line ~126 -- HARDCODED
- Verdict: PARTIAL COMPLIANCE. Sutton says "determined by the system, not hard-coded." We should ADD a precision measurement step that empirically determines epsilon by comparing repeated D0 probes. Currently precision is assumed, not discovered.
- FINDING: Add TODO to implement precision discovery (probe D0 multiple times, measure variance, set epsilon = 2 * max_deviation).

**Q: Why 5 Ticks for Steering?**
- MEASURE_TICKS=5 at test_phase_a_tmnf.py:157 for is_steer actions
- Because yaw change per single tick is ~0.0002 rad, below the epsilon threshold
- 5 ticks accumulates ~0.001 rad, above epsilon
- Impact on planning: Creates inconsistency. Gas/brake deltas are per-tick, steering deltas are per-5-ticks. The planner must know this and scale accordingly.
- NOT ideal per Sutton ("frame is atomic unit"), but pragmatically necessary. Document that steering bins represent 5-tick effect, not 1-tick.

**Q: Why Is D0 Not Zero?**
- Gas D0 = -0.068 to -0.100 (speed dropping due to friction/drag while coasting)
- Steering D0 = ~1e-8 (near zero, tiny float rounding)
- D0 varies across cycles even WITH rewind because save_state() is called at slightly different race_time values between action discoveries
- Sutton: "Not doing an action is also an action." D0 represents the real physics of the car coasting. It's NOT noise. It's NOT zero because the car is decelerating.
- Sutton compliant: we store D0 as a real transition, never subtract it.

**Q: Gas MIN is Adapter Defined?**
- tmnf_adapter.py:416: `accel = np.uint8(1 if gas_val > 0.001 else 0)`
- This 0.001 is the adapter's binary threshold -- it's code in our Python adapter, not a game physics constant
- The algorithm discovers MIN=0.001 because that's where the adapter flips from OFF to ON
- So yes: the algorithm correctly discovers the adapter's threshold. But the threshold itself is OUR choice (0.001), not the game's.
- This is fine because Sutton says "discover the environment." The adapter IS part of the environment from the algorithm's perspective. The algorithm has no knowledge of what 0.001 means -- it discovers it empirically.

Each section should include:
- Exact file path and line number
- Code excerpt (3-5 lines)
- Sutton compliance verdict: COMPLIANT / PARTIAL / NON-COMPLIANT
- Fix recommendation if not fully compliant
</action>
  <verify>Test that the file exists and has all sections: `wc -l docs/SUTTON_COMPLIANCE_AUDIT.md` should be >= 200 lines. Grep for all question headers (Q-i through Q-viii).</verify>
  <done>All user questions answered with exact code references and Sutton compliance verdicts. Audit document is self-contained and referenceable.</done>
</task>

<task type="auto">
  <name>Task 2: Apply code fixes for identified compliance gaps</name>
  <files>config/tmnf_config.json, test_phase_a_tmnf.py, intelligence/intelligence_experimentation.py</files>
  <action>
Apply these targeted fixes:

1. **config/tmnf_config.json**: Add `timing` section under `environment`:
```json
"environment": {
    "type": "tmnf",
    "adapter": "adapters.tmnf_adapter.TMNFAdapter",
    "protocol": "tcp",
    "host": "127.0.0.1",
    "port": 8476,
    "timing": {
        "frame_duration_ms": 10,
        "note": "Discovered from environment by SystemInitializer (INIT-06). This value is a fallback only."
    }
}
```
This fixes the ConfigValidator requirement for environment.timing.frame_duration_ms.

2. **test_phase_a_tmnf.py**: Add inline comment at line 208 documenting that frame_duration_s=0.01 is a known hardcoded value that should match the discovered frame duration:
```python
frame_duration_s=0.01,   # 10ms -- matches TMNF physics tick. TODO: use discovered value from adapter
```

3. **intelligence/intelligence_experimentation.py**: Add docstring/comment to FrameBinDiscovery.__init__ at search_precision and measurement_epsilon explaining:
- search_precision=0.001 is the binary search convergence threshold (not measurement precision)
- measurement_epsilon should be discovered empirically (TODO: add precision discovery step)
- Document that D0 varies with game state (state-dependent, not random noise)

4. **test_phase_a_tmnf.py**: Add comment block near MEASURE_TICKS=5 (line 157) explaining the planning impact:
```python
# MEASURE_TICKS for steering: accumulates signal over N ticks because per-tick
# yaw delta (~0.0002 rad) is below measurement_epsilon.
# PLANNING IMPACT: steering bin deltas represent 5-tick effect, not 1-tick.
# Planner must divide by MEASURE_TICKS to get per-tick delta if needed.
MEASURE_TICKS = 5 if is_steer else 1
```

Do NOT change any algorithm logic. Only add comments, docstrings, and the config timing field.
</action>
  <verify>
    - `python -c "import json; json.load(open('config/tmnf_config.json'))"` succeeds (valid JSON)
    - `python -c "from utils.validators import ConfigValidator; ConfigValidator.validate_config(json.load(open('config/tmnf_config.json')))"` with appropriate imports
    - `grep -n "MEASURE_TICKS" test_phase_a_tmnf.py` shows the new comment
    - `grep -n "search_precision" intelligence/intelligence_experimentation.py` shows the new docstring
  </verify>
  <done>Config has environment.timing.frame_duration_ms. All hardcoded values have explanatory comments. State-dependence of D0 is documented. Planning impact of MEASURE_TICKS is documented. No algorithm logic changed.</done>
</task>

</tasks>

<verification>
1. docs/SUTTON_COMPLIANCE_AUDIT.md exists with >= 200 lines
2. All 12+ user questions are answered (grep for section headers)
3. Each answer includes file path, line number, code excerpt, and verdict
4. config/tmnf_config.json is valid JSON with environment.timing.frame_duration_ms
5. No algorithm logic was changed (only comments/docs/config)
</verification>

<success_criteria>
- User can read SUTTON_COMPLIANCE_AUDIT.md and find the answer to every question they asked
- Each answer includes exact file:line references they can verify
- Each answer has a clear Sutton compliance verdict
- Config timing field is added so ConfigValidator passes
- All hardcoded values have explanatory comments documenting why they exist and what should be measured instead
</success_criteria>

<output>
After completion, create `.planning/quick/5-sutton-compliance-audit-documentation-co/5-SUMMARY.md`
</output>
