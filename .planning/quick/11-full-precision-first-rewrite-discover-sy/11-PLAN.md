---
phase: quick-11
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - adapters/tmnf_adapter.py
  - intelligence/intelligence_experimentation.py
  - test_phase_a_tmnf.py
  - test_precision_discovery.py
autonomous: true
must_haves:
  truths:
    - "TMNFAdapter exposes wire precision metadata for every action channel"
    - "Adapter converts float gas/brake/left/right to uint8 via faithful quantization, not hardcoded > 0.0"
    - "Nature detection derives probe values from wire precision, not hardcoded NATURE_PROBE_VALUES"
    - "Binary search MIN stops at wire_step boundary, not floating-point epsilon"
    - "Discovery can run from zero speed (gas/brake), not just MIN_PROBE_SPEED=200"
    - "All existing offline tests still pass"
  artifacts:
    - path: "adapters/tmnf_adapter.py"
      provides: "get_wire_precision() method + faithful uint8 quantization"
      contains: "get_wire_precision"
    - path: "intelligence/intelligence_experimentation.py"
      provides: "Wire-precision-aware nature detection + MIN search"
      contains: "wire_precision"
    - path: "test_phase_a_tmnf.py"
      provides: "Wire precision plumbing + --from-zero flag"
      contains: "from_zero"
    - path: "test_precision_discovery.py"
      provides: "Offline verification of wire precision, quantization, and probe derivation"
  key_links:
    - from: "adapters/tmnf_adapter.py"
      to: "intelligence/intelligence_experimentation.py"
      via: "get_wire_precision() dict passed to detect_action_nature()"
      pattern: "wire_precision"
    - from: "test_phase_a_tmnf.py"
      to: "adapters/tmnf_adapter.py"
      via: "adapter.get_wire_precision() call before run_discovery_tmnf()"
      pattern: "get_wire_precision"
---

<objective>
Eliminate 3 Sutton-violating hardcoding issues: (1) hardcoded NATURE_PROBE_VALUES in nature detection, (2) hardcoded `> 0.0` threshold in adapter's uint8 conversion, (3) hardcoded MIN_PROBE_SPEED=200 requirement. Replace all three with precision-first discovery: the adapter reports its wire precision, nature detection derives probes from it, MIN search stops at the wire boundary, and discovery can optionally run from zero speed.

Purpose: Sutton says "First, find the system's precision. Based on that, find what is small and what is large." Currently we hardcode the probes (1e-6, 0.001, 1.0, 1000.0) and the adapter silently quantizes any positive float to 1, masking the real system boundary. This fix makes the algorithm discover the true boundary at ~1/255 for uint8 channels.

Output: Modified adapter, modified intelligence module, modified test harness, new offline verification script.
</objective>

<execution_context>
@C:/Users/ateeb/.claude/get-shit-done/workflows/execute-plan.md
@C:/Users/ateeb/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@adapters/tmnf_adapter.py
@intelligence/intelligence_experimentation.py
@test_phase_a_tmnf.py
@TMinterface/AgenticBridge.as
</context>

<tasks>

<task type="auto">
  <name>Task 1: Adapter wire precision API + faithful uint8 quantization</name>
  <files>adapters/tmnf_adapter.py</files>
  <action>
  1. Add `get_wire_precision()` method to `TMNFAdapter` class (after `get_statistics()`):
     Returns a dict with one key per action channel ('gas', 'brake', 'left', 'right', 'steering').
     Each value is a dict: {'wire_type': str, 'wire_bits': int, 'wire_min': int, 'wire_max': int, 'float_min': float, 'float_max': float, 'float_step': float}.

     For gas/brake/left/right: wire_type='uint8', wire_bits=8, wire_min=0, wire_max=255, float_min=0.0, float_max=1.0, float_step=1.0/255.
     For steering: wire_type='int32', wire_bits=32, wire_min=-65536, wire_max=65536, float_min=-1.0, float_max=1.0, float_step=1.0/65536.

     This is a PURE DATA method (no TCP needed). It reports the known wire format from AgenticBridge.as protocol.

  2. In `_TMNFSocketClient._send_set_input_state()`, change the gas/brake conversion from:
     ```python
     accel = np.uint8(1 if gas_val > 0.0 else 0)
     brake = np.uint8(1 if brake_val > 0.0 else 0)
     ```
     to faithful uint8 quantization:
     ```python
     accel = np.uint8(min(255, max(0, round(gas_val * 255))))
     brake = np.uint8(min(255, max(0, round(brake_val * 255))))
     ```

     Similarly change left/right from `1 if ... > 0.0 else 0` to:
     ```python
     left  = np.uint8(min(255, max(0, round(action.get('left', 0) * 255))))
     right = np.uint8(min(255, max(0, round(action.get('right', 0) * 255))))
     ```

     This means gas=0.004 -> uint8(1) -> plugin sees `1 > 0 = true` -> game ON.
     gas=0.001 -> uint8(0) -> plugin sees `0 > 0 = false` -> game OFF.
     The algorithm discovers MIN at ~1/255 = 0.00392 — the REAL system boundary.

     Update the docstring/comments on `_send_set_input_state` to explain faithful quantization.
     Also update the TMNFAdapter class docstring (lines 511-515) to remove ">0.0 = full gas" and explain the faithful quantization.

     Do NOT change the steering conversion (float_to_steer) — it already does faithful int32 mapping.
  </action>
  <verify>
  Run: `python -c "from adapters.tmnf_adapter import TMNFAdapter; a = TMNFAdapter(); p = a.get_wire_precision(); assert p['gas']['wire_type'] == 'uint8'; assert p['gas']['float_step'] == 1.0/255; assert p['steering']['wire_type'] == 'int32'; print('PASS:', p)"`

  Verify quantization math manually:
  `python -c "import numpy as np; assert np.uint8(min(255, max(0, round(0.004 * 255)))) == 1; assert np.uint8(min(255, max(0, round(0.001 * 255)))) == 0; assert np.uint8(min(255, max(0, round(1.0 * 255)))) == 255; assert np.uint8(min(255, max(0, round(0.5 * 255)))) == 128; print('PASS')"`
  </verify>
  <done>
  TMNFAdapter.get_wire_precision() returns correct metadata for all 5 channels.
  _send_set_input_state uses faithful uint8 quantization (round(val * 255)) instead of hardcoded > 0.0 threshold.
  gas=0.004 maps to uint8(1) (ON), gas=0.001 maps to uint8(0) (OFF).
  </done>
</task>

<task type="auto">
  <name>Task 2: Wire-precision-aware nature detection + MIN search + zero-speed option</name>
  <files>intelligence/intelligence_experimentation.py, test_phase_a_tmnf.py</files>
  <action>
  **A. intelligence/intelligence_experimentation.py changes:**

  1. Modify `detect_action_nature()` signature to accept optional `wire_precision: dict = None` parameter.
     When wire_precision is provided, DERIVE probe values from it instead of using hardcoded `NATURE_PROBE_VALUES`:
     ```python
     if wire_precision:
         float_max = wire_precision['float_max']
         float_step = wire_precision['float_step']
         # Derive probes: max, then descending powers of 10, down to wire step
         probes = []
         val = float_max
         while val >= float_step:
             probes.append(val)
             val /= 10.0
         probes.append(float_step)  # smallest wire can represent
         # Deduplicate and sort descending
         probes = sorted(set(probes), reverse=True)
     else:
         probes = list(self.NATURE_PROBE_VALUES)  # fallback
     ```
     Keep `NATURE_PROBE_VALUES` as a class constant for backward compatibility but add a comment: "# Legacy fallback — prefer wire_precision-derived probes".
     In the probe loop, use `probes` instead of `self.NATURE_PROBE_VALUES`.
     Update the docstring to explain the precision-first approach: "Probes are DERIVED from wire precision when available (Sutton: 'first find the system's precision')."

  2. Modify `_run_binary_discovery()` signature to accept optional `wire_precision: dict = None`.
     When searching for MIN, add a stop condition: if the binary search interval `(high - low)` drops below `wire_precision['float_step']`, stop — we've reached the wire's resolution limit.
     Specifically, in the existing `_binary_search_min()` call within `_run_binary_discovery()`, the `self.search_precision` is already used as stop condition. So the key change is: when `_run_binary_discovery` is called with wire_precision, set a `wire_step` floor:
     ```python
     wire_step = wire_precision['float_step'] if wire_precision else None
     ```
     Before calling `_binary_search_min()`, if `wire_step` and `self.search_precision`:
       use `max(self.search_precision, wire_step)` as the effective precision.
     Or: temporarily set `self.search_precision = max(self.search_precision or 0, wire_step)` before the binary search, restore after.

     This prevents the 50-step binary search from grinding down to 9.77e-16 when the wire only resolves 1/255.

     Also change the reference to `self.NATURE_PROBE_VALUES` on line 518 (in the smallest_active search loop) to use the same derived probes. Store the derived probes as `self._nature_probes` in `detect_action_nature()` and reference that in `_run_binary_discovery()`.

  3. Modify `run_discovery()` signature to accept optional `wire_precision: dict = None`.
     Pass it through to `detect_action_nature(probe_fn, wire_precision=wire_precision)` and `_run_binary_discovery(probe_fn, wire_precision=wire_precision)`.

  **B. test_phase_a_tmnf.py changes:**

  4. In `run_discovery_tmnf()`, add `wire_precision: dict = None` parameter.
     Before the discovery loop, if wire_precision is provided, pass `wire_precision.get(action_name)` for each action to `disc.run_discovery(probe_fn, wire_precision=wire_precision.get(action_name))`.

  5. In `make_probe_fn()`, no changes needed (probe values come from the discovery algorithm, not the probe function).

  6. In `main()`, after connecting and before running discovery:
     ```python
     # Get wire precision from adapter (Sutton: "first find the system's precision")
     wire_prec = adapter.get_wire_precision()
     logger.info(f"  Wire precision: {wire_prec}")
     ```
     Pass `wire_precision=wire_prec` to `run_discovery_tmnf()`.

  7. Add `--from-zero` flag to argparse. When set, skip the "accelerate to MIN_PROBE_SPEED" loop entirely.
     Change the speed check block to:
     ```python
     if args.from_zero:
         logger.info("  --from-zero: testing from current speed (Sutton: 'try from zero speed')")
     else:
         MIN_PROBE_SPEED = 200.0
         fb = adapter.get_feedbacks()
         speed = fb.get('speed', 0)
         if speed < MIN_PROBE_SPEED:
             logger.info(f"  Accelerating to {MIN_PROBE_SPEED} km/h...")
             # ... existing acceleration loop ...
     ```

  8. In `save_results()`, add wire_precision to the output JSON (new 'wire_precision' key at top level).
     Update signature to accept `wire_precision: dict = None`.
  </action>
  <verify>
  Verify the code parses without errors:
  `python -c "from intelligence.intelligence_experimentation import FrameBinDiscovery, ExperimentationIntelligence; print('import OK')"`
  `python -c "from test_phase_a_tmnf import run_discovery_tmnf, make_probe_fn; print('import OK')"`

  Verify wire_precision-derived probes for uint8 channel:
  ```
  python -c "
  from intelligence.intelligence_experimentation import FrameBinDiscovery
  d = FrameBinDiscovery('gas')
  wp = {'wire_type': 'uint8', 'wire_bits': 8, 'wire_min': 0, 'wire_max': 255, 'float_min': 0.0, 'float_max': 1.0, 'float_step': 1.0/255}
  # Simulate what detect_action_nature would derive
  probes = []
  val = wp['float_max']
  while val >= wp['float_step']:
      probes.append(val)
      val /= 10.0
  probes.append(wp['float_step'])
  probes = sorted(set(probes), reverse=True)
  print('Derived probes:', [f'{p:.6g}' for p in probes])
  assert probes[0] == 1.0, f'Max probe should be 1.0, got {probes[0]}'
  assert any(abs(p - wp['float_step']) < 1e-10 for p in probes), 'Wire step must be in probes'
  print('PASS')
  "
  ```

  Verify --from-zero flag parses:
  `python test_phase_a_tmnf.py --help | grep from-zero`
  </verify>
  <done>
  detect_action_nature() derives probes from wire_precision when available (not hardcoded).
  _run_binary_discovery() respects wire_step as floor for MIN search.
  run_discovery() passes wire_precision through the chain.
  test_phase_a_tmnf.py plumbs wire_precision from adapter to discovery.
  --from-zero flag allows testing from zero speed.
  All imports succeed without errors.
  </done>
</task>

<task type="auto">
  <name>Task 3: Offline verification script — prove precision-first works without TMNF</name>
  <files>test_precision_discovery.py</files>
  <action>
  Create `test_precision_discovery.py` — a standalone offline test that validates the precision-first rewrite WITHOUT needing a running TMNF instance. Uses mock probe functions to simulate system responses.

  Structure:
  ```python
  """
  OFFLINE VERIFICATION: Precision-First Discovery Rewrite

  Tests the 3 fixes without TMNF running:
  1. Wire precision API returns correct metadata
  2. Faithful uint8 quantization maps correctly
  3. Nature detection derives probes from wire precision
  4. MIN search stops at wire step boundary
  5. Zero-speed flag exists

  Run: python test_precision_discovery.py
  """
  ```

  Test functions (each prints PASS/FAIL):

  1. `test_wire_precision_metadata()`:
     - Create TMNFAdapter(), call get_wire_precision()
     - Assert gas/brake/left/right are uint8, steering is int32
     - Assert float_step for uint8 = 1/255, float_step for steering = 1/65536
     - Assert wire_min/wire_max correct

  2. `test_faithful_quantization()`:
     - Test the quantization formula: `np.uint8(min(255, max(0, round(val * 255))))`
     - Cases: 0.0->0, 0.001->0, 0.002->1, 0.004->1, 0.5->128, 1.0->255, 1.5->255 (clamped), -0.1->0 (clamped)
     - The critical boundary: 1/510 = 0.00196 -> 0 (rounds down), 1/255 = 0.00392 -> 1 (rounds to 1)

  3. `test_nature_probes_derived_from_wire()`:
     - Create FrameBinDiscovery('gas')
     - Simulate what detect_action_nature would produce with wire_precision for uint8:
       float_max=1.0, float_step=1/255
     - Verify probes span from 1.0 down to 1/255 in powers of 10
     - Verify hardcoded [1e-6, 0.001, 1.0, 1000.0] are NOT used when wire_precision provided

  4. `test_binary_discovery_with_wire_floor()`:
     - Create FrameBinDiscovery with search_precision and measurement_epsilon
     - Create a mock probe_fn that simulates a binary action:
       action=0 -> delta=-2.5 (D0, deceleration from gravity)
       action>=(1/255) -> delta=+5.0 (active, acceleration)
       action<(1/255) -> delta=-2.5 (D0, below wire resolution)
     - Call run_discovery(probe_fn, wire_precision=uint8_precision)
     - Assert nature='binary', a_min is close to 1/255 (not 9.77e-16)
     - Assert bins=2

  5. `test_analog_discovery_with_wire_floor()`:
     - Mock probe_fn for analog action (steering-like):
       action=0 -> delta=0 (D0)
       action >= 0.5 -> delta=0.001 (saturated)
       action in [0.01, 0.5) -> delta proportional (analog)
       action < 0.01 -> delta=0 (D0)
     - Call run_discovery(probe_fn, wire_precision=int32_steer_precision)
     - Assert nature='analog', a_max close to 0.5, a_min close to 0.01

  6. `test_from_zero_flag_exists()`:
     - Import argparse setup from test_phase_a_tmnf and verify --from-zero is recognized
     - (Just parse `['--from-zero']` and assert args.from_zero is True)

  Main: run all tests, count PASS/FAIL, print summary, exit(1) if any failures.
  Save results to `precision_discovery_offline_verification.json`.
  </action>
  <verify>
  `python test_precision_discovery.py` — all 6 tests PASS, exit code 0.
  </verify>
  <done>
  All 6 offline tests pass:
  - Wire precision metadata correct for all channels
  - Faithful quantization boundary at ~1/255 (0.00392)
  - Nature probes derived from wire precision
  - Binary MIN search stops at wire step (not floating-point epsilon)
  - Analog discovery still works with wire precision
  - --from-zero flag recognized
  </done>
</task>

</tasks>

<verification>
1. `python test_precision_discovery.py` — all 6 offline tests PASS (exit 0)
2. `python -c "from adapters.tmnf_adapter import TMNFAdapter; print(TMNFAdapter().get_wire_precision())"` — returns valid dict
3. `python -c "from intelligence.intelligence_experimentation import FrameBinDiscovery; print('OK')"` — imports clean
4. `python test_phase_a_tmnf.py --help` — shows --from-zero flag
5. No existing functionality broken (all imports work, no syntax errors)
</verification>

<success_criteria>
- TMNFAdapter.get_wire_precision() returns wire format metadata for all 5 action channels
- Adapter uses faithful uint8 quantization: gas=0.004 -> uint8(1), gas=0.001 -> uint8(0)
- Nature detection probes derived from wire precision (not hardcoded 1e-6/0.001/1.0/1000.0)
- Binary MIN search bounded by wire step (1/255 for uint8, not 9.77e-16)
- Discovery can run from zero speed with --from-zero flag
- All 6 offline verification tests pass
</success_criteria>

<output>
After completion, create `.planning/quick/11-full-precision-first-rewrite-discover-sy/11-SUMMARY.md`
</output>
