---
phase: quick-1
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - intelligence/intelligence_experimentation.py
  - test_phase_a_live.py
autonomous: true

must_haves:
  truths:
    - "Algorithm runs a single downward pass (powers of 10) finding MAX bracket then MIN bracket in one sweep — not separate phases"
    - "D0 is measured as action=0 but is NOT described as a separate 'Step 1' — it is context for understanding 'no change', acknowledged as needed for physics environments"
    - "Epsilon comparison is minimal and simple — not a per-action dict of hand-tuned values"
    - "Test script warmup is minimal — just enough for vgamepad hardware registration, no full-gas preflight, no coast period"
    - "No MEASURING_DELTA0 phase enum — D0 measurement is part of the sweep, not a separate orchestration phase"
  artifacts:
    - path: "intelligence/intelligence_experimentation.py"
      provides: "Refactored algorithm matching meeting spec"
    - path: "test_phase_a_live.py"
      provides: "Minimal warmup test script"
  key_links:
    - from: "intelligence/intelligence_experimentation.py"
      to: "archive/meeting_transcripts/algorithm_spec_from_meetings.md"
      via: "Algorithm structure matches spec section 14"
---

<objective>
Refactor the bin discovery algorithm to match the meeting spec exactly as documented in algorithm_spec_from_meetings.md.

Purpose: The current code works and passes tests, but its structure has drifted from the meetings. The spec describes ONE downward pass from 1e6 finding MAX bracket then MIN bracket. The code has a separate "Step 1: Measure D0" phase, per-action epsilon dictionaries, and the test script has an excessive 10-second warmup + 2-second preflight that violates "do not interfere with the environment."

Output: Cleaner code that matches the meeting language, simpler epsilon handling, minimal test warmup.
</objective>

<execution_context>
@C:/Users/ateeb/.claude/get-shit-done/workflows/execute-plan.md
@C:/Users/ateeb/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@archive/meeting_transcripts/algorithm_spec_from_meetings.md  (THE authoritative spec)
@intelligence/intelligence_experimentation.py  (current implementation)
@test_phase_a_live.py  (current test script)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Refactor FrameBinDiscovery.run_discovery to single-pass downward sweep</name>
  <files>intelligence/intelligence_experimentation.py</files>
  <action>
Refactor FrameBinDiscovery.run_discovery() to match the meeting spec (algorithm_spec_from_meetings.md section 14):

**Algorithm restructure — single downward pass:**
The spec describes ONE pass going DOWN from the largest value. Currently the code has a separate "STEP 1: Measure D0" then "STEP 2: Exponential bracketing" etc. Restructure to:

1. Probe action=0 first to know what "no change" means in a physics environment. This is acknowledged in the spec as necessary for car environments (section 5C: "The car case requires comparing against what action=0 produces"). But do NOT label it "Step 1" or make it a separate phase — it is setup/context, not part of the sweep.

2. Then do the single downward sweep (powers of 10 from the top of the action range):
   - Record delta for each probe
   - First probe = saturated delta
   - When delta first drops below saturated: MAX bracket found, binary search it
   - Keep going down
   - When delta becomes same as action=0: MIN bracket found, binary search it
   - Done

3. Remove the `MEASURING_DELTA0` enum value from `ExperimentationPhase`. The D0 measurement is just a probe, not an orchestration phase.

**Simplify epsilon handling:**
- Remove the `ACTION_EPSILON` dict and `DEFAULT_EPSILON` class variables from `ExperimentationIntelligence`
- Instead, use a single simple approach: `FrameBinDiscovery` takes an optional `epsilon` parameter (default 0.05). For steering, the caller passes a smaller epsilon since heading deltas are in radians (much smaller scale than speed deltas).
- The `_deltas_are_same` method stays but uses this single epsilon value
- Remove the `measurement_epsilon` attribute — just use `self.epsilon` set at construction time

**Update docstrings and comments:**
- Remove references to "6-step algorithm" — the spec describes it as a sweep, not numbered steps
- Replace "experimentation_algorithm.md" references with "algorithm_spec_from_meetings.md"
- Keep the algorithm description accurate but aligned with meeting language
- Remove "Exact" branding throughout (artifact of earlier naming)

**What to preserve (these work correctly):**
- `FrameBinDiscovery` class structure
- `compute_delta()` method (speed for gas/brake, heading for steering)
- `_binary_search_max()` and `_binary_search_min()` methods
- `build_bins()` and `make_bidirectional_bins()`
- `ExperimentationIntelligence` and `ExperimentationCoordinator` classes
- `ProbeResult`, `ActionBin`, `ActionDiscoveryResult` dataclasses
- The probe retry logic for invalid steering probes
- `get_exponential_sequence()` — correct as-is

**What NOT to do:**
- Do NOT remove D0 measurement entirely — physics environments need it (spec section 5C acknowledges this)
- Do NOT change the binary search logic — it works correctly
- Do NOT change compute_delta — the heading computation for steering is correct
- Do NOT change the coordinator/intelligence class structure
  </action>
  <verify>
Run: `python -c "from intelligence.intelligence_experimentation import ExperimentationCoordinator, FrameBinDiscovery, ExperimentationPhase; print('Import OK'); assert not hasattr(ExperimentationPhase, 'MEASURING_DELTA0'), 'MEASURING_DELTA0 should be removed'; print('Phase enum OK'); d = FrameBinDiscovery('test', (0.0, 1.0)); assert hasattr(d, 'epsilon'), 'Should have epsilon attr'; print('Epsilon OK'); print('ALL CHECKS PASS')"`

Also verify no syntax errors: `python -m py_compile intelligence/intelligence_experimentation.py`
  </verify>
  <done>
- run_discovery() is a single downward sweep with D0 as setup context, not a separate phase
- MEASURING_DELTA0 removed from ExperimentationPhase enum
- No ACTION_EPSILON dict — single epsilon parameter on FrameBinDiscovery
- Docstrings reference algorithm_spec_from_meetings.md, not "6-step" language
- All existing classes, methods, and dataclasses still importable
  </done>
</task>

<task type="auto">
  <name>Task 2: Strip excessive warmup from test_phase_a_live.py</name>
  <files>test_phase_a_live.py</files>
  <action>
The meeting spec says "do not interfere with the environment" (section 3). The current test script violates this with:

1. **10-second full-gas warmup** (lines 78-85): Sends gas=1.0 for 200 iterations at 50ms. This is partly needed for vgamepad hardware registration (TrackMania needs to detect the virtual controller), but 10 seconds of full gas is excessive interference.

2. **2-second preflight check** (lines 126-177): Sends gas=1.0 for 40 frames, measures speed change, then coasts for 1 second. This is pure interference — "we don't need to change the car state to test."

**Changes:**

A. **Replace 10-sec warmup with minimal vgamepad registration:**
   - Keep SOME warmup because vgamepad hardware registration is a real requirement (not algorithmic, just driver-level)
   - Reduce to 2-3 seconds: Send neutral inputs (all zeros) rapidly for ~2 seconds. The vgamepad just needs the OS to register the device, it does NOT need full-gas. If zero-input registration doesn't work, send tiny gas pulses (0.01) instead.
   - Add a comment: "vgamepad hardware registration only — not algorithmic warmup. Spec: do not interfere with environment."

B. **Remove the entire STEP 2.5 preflight check** (lines 126-177):
   - Delete the whole block that sends gas=1.0 for 2 seconds and checks speed change
   - The algorithm itself will detect if the environment responds. If it doesn't, the discovery results will show no detectable range — that IS the answer.
   - Spec: "when the car is stopped and we do the guess, that is already being tested on that stage"

C. **Update step numbering:**
   - With preflight removed, renumber remaining steps (STEP 3 becomes STEP 2, etc.)

D. **Update the algorithm description in STEP 4 comments:**
   - Remove "6-step" language
   - Replace with: "Downward sweep: probe action=0 for context, then descend powers of 10, find MAX bracket, binary search, find MIN bracket, binary search"
   - Replace "experimentation_algorithm.md" references with "algorithm_spec_from_meetings.md"

E. **Update compliance checks (STEP 6):**
   - Remove checks that look for "Measure D0" string in source (since we renamed it)
   - Remove `checks["Step 1: D0 measured"]` — replace with a check that D0 was recorded (result.delta_0 exists)
   - Keep algorithmic checks (exponential bracketing, binary search, bidirectional steering)
   - Update string matching to match new docstring/comment text

**What to preserve:**
- Connection logic (STEP 1)
- Config loading (STEP 2)
- ExperimentationCoordinator initialization
- Results analysis and saving
- The overall structure of the test script
  </action>
  <verify>
Run: `python -m py_compile test_phase_a_live.py` (syntax check)

Also verify: `python -c "import ast; ast.parse(open('test_phase_a_live.py').read()); print('Parse OK')"` (AST parse check)

Manually verify: no "gas=1.0 warmup" or "preflight" blocks remain in the file. The only warmup should be 2-3 seconds of neutral/minimal input for vgamepad registration.
  </verify>
  <done>
- 10-second full-gas warmup replaced with 2-3 second minimal vgamepad registration
- Entire preflight check (STEP 2.5) removed
- Step numbering updated
- Algorithm description comments updated to match spec language
- Compliance checks updated to match refactored code
- No "interference" with environment before discovery begins
  </done>
</task>

</tasks>

<verification>
After both tasks:
1. `python -m py_compile intelligence/intelligence_experimentation.py` — no syntax errors
2. `python -m py_compile test_phase_a_live.py` — no syntax errors
3. `python -c "from intelligence.intelligence_experimentation import ExperimentationCoordinator, FrameBinDiscovery"` — imports work
4. Grep for removed patterns: no "MEASURING_DELTA0", no "ACTION_EPSILON", no "preflight" in the codebase
5. Grep for updated references: "algorithm_spec_from_meetings.md" appears in both files
</verification>

<success_criteria>
- Algorithm code structure matches the meeting spec: single downward sweep, D0 as context not a phase, simple epsilon
- Test script respects "do not interfere with environment": minimal hardware registration only, no preflight
- Both files compile and import without errors
- Existing functionality preserved: all classes, methods, dataclasses still exist and work
</success_criteria>

<output>
After completion, create `.planning/quick/1-refactor-algorithm-code-to-match-meeting/1-SUMMARY.md`
</output>
