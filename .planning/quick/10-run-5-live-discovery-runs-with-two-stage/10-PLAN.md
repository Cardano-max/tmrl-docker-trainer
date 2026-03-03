---
phase: quick-10
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - run_5_two_stage_validation.py
  - .planning/quick/10-run-5-live-discovery-runs-with-two-stage/10-PLAN.md
autonomous: true

must_haves:
  truths:
    - "Script connects to live TMNF, runs 5 full discovery cycles using two-stage model"
    - "All 4 actions (gas, brake, left, right) detected as BINARY via detect_action_nature()"
    - "MAX = 1.0 for all actions (validated by probing, not hardcoded)"
    - "MIN found via binary search (near adapter boundary, extremely small)"
    - "D0 measured and differs from active delta for all actions"
    - "bins = 2 for all 4 actions across all 5 runs"
    - "Cross-run stability: identical values across all 5 runs (deterministic rewind)"
    - "Sutton compliance validated: no hardcoded values, nature discovered, frame duration measured"
    - "Results cross-referenced against multi_speed_binary_proof data"
  artifacts:
    - path: "run_5_two_stage_validation.py"
      provides: "5-run two-stage validation script"
      min_lines: 300
  key_links:
    - from: "run_5_two_stage_validation.py"
      to: "test_phase_a_tmnf.py"
      via: "imports measure_frame_duration, measure_system_precision, run_discovery_tmnf, TMNF_ACTIONS_CONFIG, make_probe_fn"
      pattern: "from test_phase_a_tmnf import"
    - from: "run_5_two_stage_validation.py"
      to: "intelligence/intelligence_experimentation.py"
      via: "two-stage discovery called through run_discovery_tmnf"
      pattern: "run_discovery_tmnf"
    - from: "run_5_two_stage_validation.py"
      to: "adapters/tmnf_adapter.py"
      via: "TMNFAdapter for live TMNF connection"
      pattern: "TMNFAdapter"
---

<objective>
Create a new 5-run two-stage validation script that exercises the detect_action_nature() + binary path discovery model from quick-9 against live TMNF, validates Sutton compliance, checks cross-run determinism, cross-references against prior multi-speed binary proof data, and produces a comprehensive JSON + terminal report.

Purpose: Prove the two-stage model (quick-9) works correctly under repeated live conditions -- all TMNF actions detected as BINARY, correct boundaries found, deterministic across runs, no hardcoded values.

Output: `run_5_two_stage_validation.py` (new script), JSON results file, terminal validation report.
</objective>

<execution_context>
@C:/Users/ateeb/.claude/get-shit-done/workflows/execute-plan.md
@C:/Users/ateeb/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@C:/Users/ateeb/Desktop/tmrl_docker_trainer/test_phase_a_tmnf.py
@C:/Users/ateeb/Desktop/tmrl_docker_trainer/intelligence/intelligence_experimentation.py
@C:/Users/ateeb/Desktop/tmrl_docker_trainer/adapters/tmnf_adapter.py
@C:/Users/ateeb/Desktop/tmrl_docker_trainer/run_5_discovery_validation.py
@C:/Users/ateeb/Desktop/tmrl_docker_trainer/multi_speed_binary_proof_20260303_092924.json
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create run_5_two_stage_validation.py -- 5-run two-stage discovery with full validation</name>
  <files>run_5_two_stage_validation.py</files>
  <action>
Create a NEW script `run_5_two_stage_validation.py` (do NOT modify the old `run_5_discovery_validation.py`).

The script MUST import and reuse functions from `test_phase_a_tmnf.py`:
```python
from test_phase_a_tmnf import (
    measure_frame_duration,
    measure_system_precision,
    run_discovery_tmnf,
    TMNF_ACTIONS_CONFIG,
    make_probe_fn,
    save_results,
)
from adapters.tmnf_adapter import TMNFAdapter
```

This ensures it uses the SAME two-stage discovery code (detect_action_nature + binary path) that quick-9 shipped.

**Structure:**

1. **Connection + Setup** (same as test_phase_a_tmnf.py main):
   - `TMNFAdapter().connect(port=args.port)`
   - `wait_for_race(timeout=60)`
   - Accelerate to 200 km/h (needed for steering yaw detection)
   - `measure_frame_duration(adapter)`
   - `measure_system_precision(adapter, use_rewind=True, num_probes=3)`

2. **5-Run Loop** (`run_5_cycles` function):
   - For each run (1-5):
     - `adapter.save_state()` at start of each run (fresh rewind point)
     - Call `run_discovery_tmnf(adapter, use_rewind=True, frame_duration_s=fd, precision=prec)`
     - Store results dict in `all_runs[]`
     - Print per-run summary table immediately after each run
   - Between runs: release all inputs, wait a tick, save new state

3. **Validation Engine** (`validate_all_runs` function):
   Returns a dict of verdicts. Check these conditions:

   **Per-run checks (for each of the 5 runs):**
   - `nature_binary`: All 4 actions have `nature_detection == 'binary'`
   - `max_is_1`: All 4 actions have `max == 1.0`
   - `bins_is_2`: All 4 actions have `bins == 2`
   - `d0_differs`: For each action, `delta_0 != delta_max` (D0 is real transition, not same as active)
   - `min_found`: All 4 actions have `min` that is a valid float > 0
   - `probes_efficient`: Each action uses <= 15 probes (binary path should use ~6-10, NOT 13+ from analog sweep)

   **Cross-run stability checks:**
   - `max_identical`: MAX is identical across all 5 runs for each action
   - `min_identical`: MIN is identical across all 5 runs for each action
   - `delta_max_identical`: delta_max identical across all 5 runs for each action
   - `d0_identical`: D0 identical across all 5 runs for each action
   - `bins_identical`: bins count identical across all 5 runs for each action
   - `probes_identical`: probe count identical across all 5 runs for each action

   **Sutton compliance checks:**
   - `nature_discovered`: nature_detection field exists and is not 'unknown'
   - `frame_duration_measured`: frame_duration > 0 and came from environment
   - `precision_measured`: precision dict has speed_epsilon and yaw_epsilon > 0
   - `no_hardcoded_max`: MAX was validated by probing (nature detection probes confirm binary)
   - `d0_is_real_action`: D0 was measured, not assumed to be 0
   - `binary_path_used`: nature == 'binary' triggered _run_binary_discovery (not analog sweep)

   **Cross-reference with multi_speed_binary_proof:**
   - Load `multi_speed_binary_proof_20260303_092924.json`
   - Check: gas/brake binary verdict matches (group_a_gas_binary_all_speeds, group_a_brake_binary_all_speeds)
   - Check: gas/brake MIN near adapter boundary (group_c_gas_true_min, group_c_brake_true_min)
   - Print cross-reference table

4. **Terminal Report** (`print_report` function):
   Print a clear, readable report with these sections:

   ```
   ======================================================================
     5-RUN TWO-STAGE VALIDATION REPORT
   ======================================================================

   ENVIRONMENT
     Frame duration: 10ms (measured)
     Precision: speed_epsilon=X, yaw_epsilon=Y (measured)
     Deterministic: True
     Probe speed: 200+ km/h

   PER-RUN RESULTS
   +------+--------+-------+-------+--------+--------+--------+--------+
   | Run  | Action | Nature| MAX   | MIN    | D0     | Dmax   | Probes |
   +------+--------+-------+-------+--------+--------+--------+--------+
   |  1   | gas    | BIN   | 1.0   | 1e-15  | -0.13  | 0.63   |   8    |
   |  1   | brake  | BIN   | 1.0   | 1e-15  | -0.13  | -1.06  |   8    |
   ...

   CROSS-RUN STABILITY
   +--------+-----------+-----------+-----------+-----------+-----------+
   | Action | MAX same? | MIN same? | Dmax same?| D0 same?  | Probes?   |
   +--------+-----------+-----------+-----------+-----------+-----------+
   | gas    | PASS      | PASS      | PASS      | PASS      | PASS      |
   ...

   SUTTON COMPLIANCE
   +---------------------------------------+--------+
   | Check                                 | Verdict|
   +---------------------------------------+--------+
   | Nature discovered (not assumed)        | PASS   |
   | Frame duration measured                | PASS   |
   | Precision measured from environment    | PASS   |
   | D0 is real action (not noise)          | PASS   |
   | Binary path used (efficient probing)   | PASS   |
   | MAX validated by probing               | PASS   |
   ...

   CROSS-REFERENCE: Multi-Speed Binary Proof
   +-----------------------------------+--------+---------+
   | Check                             | Proof  | This    |
   +-----------------------------------+--------+---------+
   | Gas binary                        | True   | True    |
   | Brake binary                      | True   | True    |
   | Gas true MIN                      | 1e-15  | 1e-15   |
   ...

   OVERALL: 18/18 PASS (or N/M with failures listed)
   ```

5. **Save Results** (`save_validation_json` function):
   Save to `validation_5run_twostage_{timestamp}.json` containing:
   - `timestamp`, `environment`, `two_stage_model: true`
   - `frame_duration_ms`, `precision` dict
   - `runs`: array of 5 run results (each with per-action data including nature_detection, probe_data)
   - `validation_verdicts`: all verdicts from validate_all_runs
   - `cross_reference`: comparison with multi_speed_binary_proof
   - `overall_pass`: bool

6. **CLI args:**
   - `--speed` (default: 1.0)
   - `--port` (default: 8476)
   - `--runs` (default: 5)
   - `--no-cross-ref` (skip multi_speed_binary_proof cross-reference if file missing)

**Key differences from old run_5_discovery_validation.py (do NOT copy these patterns):**
- OLD used hardcoded `EPSILON_GAS_BRAKE = 0.01` and `EPSILON_STEER = 1e-5` -- NEW uses `measure_system_precision()`
- OLD used `MEASURE_TICKS = 5` for steering -- NEW uses 2 ticks for ALL actions (from test_phase_a_tmnf.py's make_probe_fn)
- OLD used `FrameBinDiscovery(action_name, action_range)` with hardcoded ranges -- NEW passes no ranges, just search_precision and measurement_epsilon
- OLD had no nature_detection field -- NEW validates it exists and is 'binary'
- OLD used `run_single_cycle()` with its own probe function -- NEW calls `run_discovery_tmnf()` directly
- OLD generated Excel with openpyxl -- NEW writes JSON + terminal report only (no Excel dependency)
- OLD accelerated to only 10 km/h -- NEW accelerates to 200 km/h (needed for steering yaw)
  </action>
  <verify>
  1. `python -c "import run_5_two_stage_validation"` succeeds (imports without errors)
  2. Script has no openpyxl import (no Excel dependency)
  3. Script imports from test_phase_a_tmnf (not duplicating code)
  4. `grep -c "nature_detection\|nature_binary\|detect_action_nature\|two.stage" run_5_two_stage_validation.py` shows multiple hits for two-stage awareness
  5. `grep "MEASURE_TICKS\|action_range\|EPSILON_GAS_BRAKE\|EPSILON_STEER" run_5_two_stage_validation.py` shows ZERO hits (no old patterns)
  6. `grep "measure_frame_duration\|measure_system_precision\|run_discovery_tmnf" run_5_two_stage_validation.py` shows hits (reuses test_phase_a_tmnf functions)
  </verify>
  <done>
  Script exists, imports cleanly, uses two-stage model via test_phase_a_tmnf.py imports, has validation engine with per-run + cross-run + Sutton compliance + cross-reference checks, prints formatted terminal report, saves JSON results. Ready for live testing against TMNF.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>
  5-run two-stage validation script that connects to live TMNF, runs 5 discovery cycles using the two-stage model (detect_action_nature + binary path), validates Sutton compliance, checks cross-run determinism, and cross-references against prior multi-speed binary proof data.
  </what-built>
  <how-to-verify>
  1. Ensure TMNF is running with TMInterface 2.x and AgenticBridge.as loaded
  2. Start a race (countdown finished, car on track)
  3. Run: `python run_5_two_stage_validation.py --speed 5.0`
  4. Watch output -- should see:
     - Frame duration measured (10ms)
     - System precision measured
     - Acceleration to 200 km/h
     - 5 discovery cycles, each showing nature detection -> BINARY for all 4 actions
     - Per-run: MAX=1.0, bins=2, probes ~6-10 per action
     - Final validation report with all checks PASS
     - JSON file saved
  5. Verify the JSON file contains all runs + validation verdicts
  6. Check the overall verdict: all checks should PASS
  </how-to-verify>
  <resume-signal>Type "approved" if all 5 runs produce consistent BINARY results with all validation checks passing, or describe any issues.</resume-signal>
</task>

</tasks>

<verification>
- Script imports cleanly without TMNF connection (`python -c "import run_5_two_stage_validation"`)
- No hardcoded epsilons, ranges, or MEASURE_TICKS in the new script
- Reuses test_phase_a_tmnf.py functions (no code duplication)
- Two-stage model awareness throughout (nature_detection validation)
- Live test: 5 runs produce identical results, all binary, all PASS
</verification>

<success_criteria>
1. `run_5_two_stage_validation.py` exists and imports cleanly
2. Script reuses `measure_frame_duration`, `measure_system_precision`, `run_discovery_tmnf` from test_phase_a_tmnf.py
3. Live run produces 5 identical discovery cycles with nature=binary, MAX=1.0, bins=2 for all 4 actions
4. Cross-run stability: all values identical across 5 runs
5. Sutton compliance: all checks PASS
6. Cross-reference with multi_speed_binary_proof: consistent
7. JSON saved with all results + validation verdicts
8. Terminal report is clear, readable, and shows all verdicts
</success_criteria>

<output>
After completion, create `.planning/quick/10-run-5-live-discovery-runs-with-two-stage/10-SUMMARY.md`
</output>
