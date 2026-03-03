---
phase: quick-8
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - test_multi_speed_binary_proof.py
autonomous: true

must_haves:
  truths:
    - "Binary nature of gas/brake is consistent across multiple car speeds (stopped, 50, 100, 150, 200+ km/h)"
    - "Binary nature of left/right steering is consistent across multiple speeds"
    - "Extended range probing below current MIN discovers real MIN (or confirms current MIN is correct)"
    - "InputType::Gas analog axis (via int32 protocol) is tested live to verify -19661 threshold claim"
    - "All claims are fact-checked with live probes, not assumptions"
    - "Comprehensive JSON results saved with per-speed breakdowns"
  artifacts:
    - path: "test_multi_speed_binary_proof.py"
      provides: "Multi-speed binary proof + extended range + analog gas axis test"
      min_lines: 300
  key_links:
    - from: "test_multi_speed_binary_proof.py"
      to: "adapters/tmnf_adapter.py"
      via: "TMNFAdapter TCP connection"
      pattern: "TMNFAdapter"
---

<objective>
Create a comprehensive multi-speed binary proof test that validates all 4 TMNF inputs (gas, brake, left, right) remain binary across different car speeds, probes below current MIN boundaries to find true MIN, and fact-checks the InputType::Gas analog axis claim from TMInterface docs.

Purpose: Prove that TMNF's binary input behavior is a fundamental game property (not speed-dependent), discover true MIN boundaries with extended range, and verify the analog gas axis threshold (-19661) claim with live testing -- all fact-checked, no assumptions.

Output: `test_multi_speed_binary_proof.py` script + JSON results file with per-speed breakdown
</objective>

<execution_context>
@C:/Users/ateeb/.claude/get-shit-done/workflows/execute-plan.md
@C:/Users/ateeb/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@test_phase_a_tmnf.py
@adapters/tmnf_adapter.py
@TMinterface/AgenticBridge.as
@verify_rubrics.py
@intelligence/intelligence_experimentation.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create multi-speed binary proof + extended range + analog gas axis test script</name>
  <files>test_multi_speed_binary_proof.py</files>
  <action>
Create `test_multi_speed_binary_proof.py` with these test groups:

**GROUP A: MULTI-SPEED BINARY PROOF (gas + brake)**
For each speed in [0 (rest), 50, 100, 150, 200, 250 km/h]:
  1. Accelerate to target speed (or restart race for rest)
  2. Save state at that speed
  3. Probe gas with values [0.001, 0.01, 0.1, 0.5, 1.0] -- all must give identical delta (proving binary)
  4. Probe brake with same values -- all must give identical delta
  5. Record D0 at each speed (expected: more negative drag at higher speeds)
  6. Compare: delta_gas and delta_brake must be speed-independent in KIND (binary), even if magnitude changes

**GROUP B: MULTI-SPEED STEERING PROOF (left + right)**
For each speed in [50, 100, 150, 200, 250 km/h] (skip rest -- steering at 0 km/h has no effect):
  1. Accelerate to target speed, save state
  2. Probe left=1.0 with gas=1.0 for 5 ticks, measure yaw delta
  3. Probe right=1.0 with gas=1.0 for 5 ticks, measure yaw delta
  4. Verify opposite signs at each speed
  5. Record: yaw magnitude increases with speed (physics property, not a bug)

**GROUP C: EXTENDED RANGE PROBING (find true MIN)**
From saved state at 200 km/h:
  1. Gas: probe values descending below current MIN (0.001): try 0.0009, 0.0005, 0.0001, 1e-5, 1e-6, 1e-8, 1e-10, 1e-15
     - For each, compare delta to D0. First value where delta == D0 is true MIN.
     - Binary search between last-working and first-D0 to narrow boundary.
  2. Brake: same extended range probing below current MIN (0.001)
  3. Left/Right: probe below current MIN (0.1): try 0.09, 0.05, 0.01, 0.001, 1e-4, 1e-6, 1e-10, 1e-15
     - These values pass through adapter as float -> uint8 (>0.0 = 1), so the real boundary
       is in the adapter's `> 0.0` comparison, not in the game. Document this fact.

**GROUP D: ANALOG GAS AXIS FACT-CHECK**
This tests the TMInterface docs claim that InputType::Gas(5) is an analog axis with threshold at -19661.
Our current adapter sends gas as uint8 (binary) via InputType::Up. To test analog gas, we need to:
  1. NOTE: Testing analog gas requires modifying the protocol to send InputType::Gas instead of InputType::Up.
     Since modifying the plugin mid-test is not safe, instead:
     - Document the CLAIM from TMInterface docs: "InputType::Gas(5), range [-65536, 65536], accel threshold -19661"
     - Document the FACT: Our adapter uses InputType::Up (digital), not InputType::Gas (analog)
     - Document WHY: TMNF docs say "TMNF/TMUF do not support analog acceleration"
     - Flag this as FUTURE_TEST: requires AgenticBridge.as modification to add InputType::Gas channel
  2. Instead, prove current binary behavior is correct by showing InputType::Up with any positive value
     produces the same delta (already done in Group A, cross-reference results)

**OUTPUT:**
- Print clear table per speed showing: speed, D0, gas_delta, brake_delta, left_delta, right_delta, all_binary
- Save comprehensive JSON with all probe data per speed
- Print verdict: "BINARY NATURE CONFIRMED ACROSS ALL SPEEDS" or list exceptions
- Extended range results: "TRUE MIN for gas = X, brake = X, left = X, right = X"

**IMPLEMENTATION NOTES:**
- Reuse the existing probe pattern from verify_rubrics.py: rewind -> tick1 (replayed) -> read before -> tickN (ours) -> read after -> delta
- Use existing TMNFAdapter with its connect/wait_for_race/save_state/rewind API
- For steering probes at each speed: use 5 ticks with gas=1.0 (same as R5/R6 rubric)
- For gas/brake probes: use 1 tick (same as R3/R4/R7/R8 rubric)
- Add --port and --speed CLI args matching existing scripts
- Use argparse with --skip-analog flag (default: analog test skipped since it needs plugin change)
- Save results to `multi_speed_binary_proof_{timestamp}.json`
  </action>
  <verify>
    python test_multi_speed_binary_proof.py --help
    # Should show usage with --port, --speed, --skip-analog flags
    # Verify file has all 4 groups implemented
    # Verify JSON output format includes per-speed breakdown
  </verify>
  <done>
    Script exists with all 4 test groups (A: multi-speed gas/brake, B: multi-speed steering, C: extended range MIN, D: analog gas documentation).
    Running `python test_multi_speed_binary_proof.py --port 8476` with TMNF active produces:
    1. Per-speed binary proof table for gas/brake across 6 speeds
    2. Per-speed steering proof across 5 speeds
    3. Extended range MIN boundaries for all 4 inputs
    4. Analog gas axis fact-check documentation
    5. JSON results file with complete probe data
  </done>
</task>

</tasks>

<verification>
- Script imports and parses correctly: `python -c "import test_multi_speed_binary_proof"`
- All test groups A-D are implemented as separate functions
- JSON output structure includes: speeds tested, per-speed results, extended range MIN, verdicts
- No hardcoded epsilons or thresholds -- uses same discovery patterns as existing code
- Cross-references verify_rubrics.py patterns (probe_action, accelerate_to, null_action helpers)
</verification>

<success_criteria>
- test_multi_speed_binary_proof.py exists and runs without import errors
- Groups A-D all implemented with clear per-speed output tables
- Extended range probing goes below 1e-10 to find true MIN
- Analog gas axis properly documented as FUTURE_TEST (not fake-tested)
- JSON results saved with timestamp, per-speed breakdown, and verdicts
- When run against live TMNF: proves binary nature across all tested speeds
</success_criteria>

<output>
After completion, create `.planning/quick/8-multi-speed-binary-proof-fact-check-vali/8-SUMMARY.md`
</output>
