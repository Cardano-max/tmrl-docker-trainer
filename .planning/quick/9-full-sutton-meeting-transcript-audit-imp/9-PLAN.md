---
phase: quick-9
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - intelligence/intelligence_experimentation.py
  - test_phase_a_tmnf.py
  - .planning/quick/9-full-sutton-meeting-transcript-audit-imp/TRANSCRIPT_AUDIT.md
autonomous: true

must_haves:
  truths:
    - "Every Sutton meeting transcript has been read and cross-referenced against the implementation"
    - "Binary actions are detected BEFORE the exponential sweep wastes probes (two-stage model)"
    - "Binary detection uses multi-magnitude probing: 3+ orders of magnitude with identical delta means BINARY"
    - "Binary actions report MAX=1.0, MIN=threshold (discovered, not hardcoded), bins=2"
    - "Analog actions still use full Sutton sweep + binary search (unchanged)"
    - "No hardcoded values, no normalization, no averaging remain in the codebase"
    - "Config file contains no hard-coded ranges that override discovery"
    - "Audit document maps each implementation detail to a specific transcript quote"
  artifacts:
    - path: "intelligence/intelligence_experimentation.py"
      provides: "Two-stage discovery: nature detection then appropriate algorithm"
      contains: "detect_action_nature"
    - path: "test_phase_a_tmnf.py"
      provides: "Updated test runner that uses two-stage discovery"
      contains: "detect_action_nature"
    - path: ".planning/quick/9-full-sutton-meeting-transcript-audit-imp/TRANSCRIPT_AUDIT.md"
      provides: "Micro-level transcript audit with quote-to-code mapping"
      min_lines: 100
  key_links:
    - from: "intelligence/intelligence_experimentation.py"
      to: "test_phase_a_tmnf.py"
      via: "FrameBinDiscovery.detect_action_nature() called before run_discovery()"
      pattern: "detect_action_nature"
    - from: "intelligence/intelligence_experimentation.py"
      to: "archive/meeting_transcripts/"
      via: "Every algorithm step traceable to a transcript quote"
      pattern: "Sutton"
---

<objective>
Audit ALL Sutton meeting transcripts against the implementation at micro-level, then implement the two-stage binary/analog discovery model in FrameBinDiscovery.

Purpose: The current algorithm runs Sutton's full exponential sweep [1e6 to 1e-6] for binary actions, finding no transition because all values produce the same delta. This wastes ~13 probes and reports meaningless MAX=1e6, MIN=1e-6 boundaries. Sutton himself asked "What mathematical model will we use for digital/binary discovery?" This task answers that question with a principled two-stage approach: detect nature first, then apply the appropriate algorithm.

Output: Updated intelligence_experimentation.py with two-stage model, updated test runner, transcript audit document
</objective>

<execution_context>
@C:/Users/ateeb/.claude/get-shit-done/workflows/execute-plan.md
@C:/Users/ateeb/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@intelligence/intelligence_experimentation.py
@test_phase_a_tmnf.py
@verify_rubrics.py
@config/tmnf_config.json
@archive/meeting_transcripts/algorithm_spec_for_disocvery_algo_from_meeting.md
@archive/meeting_transcripts/experimentation_algorithm.md
@archive/meeting_transcripts/Authoratative_law_from_Jan2026_meetings.md
@archive/meeting_transcripts/meeting_transcript_16feb2026.txt
@archive/meeting_transcripts/meeting_transcript_09_JAn2026.txt
@archive/meeting_transcripts/meeting_transcript_15_jan_2026
@archive/meeting_transcripts/meeting_transcript_24Jan2026.txt
@archive/meeting_transcripts/meeting_transcript_31Jan2026.txt
@archive/meeting_transcripts/meeing_transcription_31Jan2026.txt
@multi_speed_binary_proof_20260303_092924.json
</context>

<tasks>

<task type="auto">
  <name>Task 1: Full transcript audit + produce TRANSCRIPT_AUDIT.md</name>
  <files>.planning/quick/9-full-sutton-meeting-transcript-audit-imp/TRANSCRIPT_AUDIT.md</files>
  <action>
Read ALL 7 meeting transcripts (9 Jan, 15 Jan, 24 Jan, 31 Jan x2, 16 Feb, plus algorithm_spec_for_disocvery_algo_from_meeting.md) in full detail. For each, extract:

1. **Quote-to-code mapping**: For each Sutton requirement/statement, find the exact line(s) in intelligence_experimentation.py that implement it. Flag any MISSING implementations.

2. **Compliance audit table** with columns:
   - Transcript source (meeting date + approximate position)
   - Sutton quote (verbatim or close paraphrase)
   - Requirement ID (REQ-01 through REQ-25 from Authoratative_law)
   - Implementation location (file:line or "MISSING")
   - Status: COMPLIANT / DEVIATION / MISSING / NOT_APPLICABLE

3. **Deviation analysis**: For each deviation or missing item, explain:
   - What Sutton said
   - What we implemented instead
   - Whether the deviation is justified (e.g., D0 measurement is an inference we added, not from Sutton -- document this honestly per section 13 of algorithm_spec)
   - Whether it should be changed

4. **Hardcoding audit**: Scan ALL files (intelligence_experimentation.py, test_phase_a_tmnf.py, config/tmnf_config.json, verify_rubrics.py) for:
   - Hardcoded epsilon/precision values (grep for literal floats like 0.001, 1e-6, etc.)
   - Hardcoded ranges
   - Hardcoded bin counts (DEFAULT_NUM_BINS = 10 in FrameBinDiscovery)
   - Magic numbers that should be discovered
   - Document each: is it justified or a violation?

5. **Binary/digital gap analysis**: Specifically audit:
   - Feb 16 transcript where Sutton asks about binary/digital model
   - Current handling of binary actions in run_discovery() (lines ~500-516: "All probes saturated -> BINARY action")
   - What the multi_speed_binary_proof confirmed (gas MIN = 1e-15, brake MIN = 1e-15)
   - Why current approach is inadequate (reports MAX=1e6, MIN=1e-6 instead of real boundaries)

Format as a detailed markdown document with clear sections. Be HONEST about what Sutton said vs what we inferred (section 13 of algorithm_spec is the gold standard for this honesty).
  </action>
  <verify>
    The audit document exists, contains quotes from all 7 transcripts, has the compliance table, and flags the binary detection gap.
    grep for "MISSING" and "DEVIATION" in the audit to see what needs fixing.
  </verify>
  <done>
    TRANSCRIPT_AUDIT.md contains:
    - Quotes from all 7 meeting sources
    - Compliance table with REQ-01 through REQ-25 status
    - Hardcoding audit with file:line references
    - Binary/digital gap analysis with specific code references
    - Honest separation of "Sutton said" vs "we inferred"
  </done>
</task>

<task type="auto">
  <name>Task 2: Implement two-stage binary/analog discovery in FrameBinDiscovery</name>
  <files>intelligence/intelligence_experimentation.py, test_phase_a_tmnf.py</files>
  <action>
**In intelligence/intelligence_experimentation.py**, add a `detect_action_nature()` method to `FrameBinDiscovery` and modify `run_discovery()`:

**Stage 1: Nature Detection** -- new method `detect_action_nature(probe_fn) -> str`

The principle (from multi-speed binary proof results): If probing 3+ orders of magnitude all produce identical delta, the action is BINARY. If deltas differ across magnitudes, the action is ANALOG.

```python
def detect_action_nature(self, probe_fn) -> str:
    """Detect whether action is BINARY or ANALOG before full sweep.

    Sutton's algorithm assumes analog actions with a transition region.
    For binary actions (like TMNF gas/brake/steering), there IS no
    transition -- all values produce the same delta. This wastes the
    full exponential sweep finding no brackets.

    Detection method (from multi-speed binary proof):
      Probe 3+ orders of magnitude: [1e-6, 0.001, 1.0, 1000.0]
      If ALL deltas identical (within measurement_epsilon) -> BINARY
      If ANY delta differs -> ANALOG (proceed with Sutton's full sweep)

    Returns: 'binary' or 'analog'
    """
```

Implementation:
1. First measure D0 = probe_fn(0.0) and store self.delta_0
2. Probe 4 values spanning orders of magnitude: [1e-6, 0.001, 1.0, 1000.0]
3. Collect deltas, excluding any that equal D0 (dead zone probes)
4. If ALL non-D0 deltas are identical (within measurement_epsilon) -> BINARY
5. If fewer than 2 non-D0 deltas found -> action has no detectable effect, return 'none'
6. If deltas differ -> ANALOG

**Stage 2A: Binary path** -- if nature == 'binary':
- self.delta_max = the common non-D0 delta from stage 1
- Find true MIN: binary search between the lowest active probe and D0 boundary
  Use the probes from stage 1 to set the bracket: lowest value that still differs from D0 (high) and lowest value that equals D0 (low). If all tested values differ from D0, MIN is below 1e-6 -- set MIN = smallest tested value.
- MAX = 1.0 (the nominal full-scale value, since any value above threshold produces the same effect)
  BUT validate: probe 1.0 and confirm delta matches delta_max. If not, something is wrong.
- self.a_max = 1.0 (or last confirmed saturated value)
- self.a_min = discovered MIN from binary search
- Return (self.a_max, self.a_min)

**Stage 2B: Analog path** -- if nature == 'analog':
- Proceed with existing run_discovery() logic (Sutton's full exponential sweep + binary search)
- The 4 probes from stage 1 are NOT wasted -- they already measured D0 and some of the exponential sequence. Reuse them by pre-populating self.probes and adjusting the exponential sweep to skip already-tested values.

**Modify `run_discovery()`:**
1. Call `detect_action_nature()` first
2. If binary: run binary path (fast, ~10 probes total)
3. If analog: run existing exponential + binary search (unchanged)
4. If none: return (None, None) as before
5. Log which path was taken with clear reasoning

**Modify `build_bins()`:**
No changes needed -- it already detects binary via `delta_at_min == delta_max`. But add a comment noting the two-stage model makes this detection more reliable since MIN/MAX are now meaningful for binary actions.

**In test_phase_a_tmnf.py**, update `run_discovery_tmnf()`:
- Add logging that shows the nature detection result before full discovery
- The existing `make_probe_fn` and overall flow stay the same -- FrameBinDiscovery.run_discovery() handles the two-stage logic internally
- Update the result dict to include `'nature_detection': 'binary'` or `'analog'` so results files show which path was taken

**CRITICAL CONSTRAINTS (from Sutton compliance):**
- Do NOT hardcode which actions are binary. The system DISCOVERS this. (Sutton: "bins needs to be figured out by the system. Not by us.")
- Do NOT hardcode MIN=0.0 or MAX=1.0 for binary. Discover MIN via binary search. MAX is validated, not assumed.
- Do NOT remove D0 measurement. It is still needed for comparison (Sutton: "not doing an action is also an action").
- Do NOT change the analog path at all. Sutton's sweep + binary search for analog actions must remain exactly as-is.
- Do NOT add averaging. Each probe is one measurement. (Sutton: "No averaging")
- The nature detection probes count toward total_experiments.
- Keep all existing logging patterns. Add new logging for nature detection with clear labels.

**What this fixes:**
- Binary actions now get meaningful boundaries: gas MAX=1.0, MIN=~1e-15 (discovered, not hardcoded)
- Instead of 13+ wasted exponential sweep probes finding no transition, binary detection takes ~6-8 probes
- Analog actions (if we ever encounter one) get the full Sutton treatment unchanged
- Results files now show the detection reasoning
  </action>
  <verify>
    python -c "from intelligence.intelligence_experimentation import FrameBinDiscovery; d = FrameBinDiscovery('test'); print('detect_action_nature' in dir(d))"
    # Should print True

    # Verify no hardcoded binary classification:
    grep -n "input_type.*binary\|is_binary.*True\|nature.*=.*binary" intelligence/intelligence_experimentation.py
    # Should NOT show any hardcoded assignments -- only discovered results

    # Verify analog path preserved:
    grep -n "get_exponential_sequence\|_binary_search_max\|_binary_search_min" intelligence/intelligence_experimentation.py
    # All three should still exist (analog path unchanged)

    # Verify test runner updated:
    grep -n "nature_detection\|detect_action_nature" test_phase_a_tmnf.py
    # Should show the nature detection result being logged/stored
  </verify>
  <done>
    1. FrameBinDiscovery has detect_action_nature() method that probes 4 orders of magnitude
    2. run_discovery() calls detect_action_nature() first, branches to binary or analog path
    3. Binary path: discovers MIN via binary search, validates MAX=1.0, reports bins=2
    4. Analog path: unchanged Sutton exponential sweep + binary search
    5. test_phase_a_tmnf.py includes nature_detection in results
    6. No hardcoded binary/analog classifications -- everything discovered
    7. Running test_phase_a_tmnf.py against TMNF should detect all 4 actions as binary and report meaningful MIN/MAX boundaries (not 1e6/1e-6)
  </done>
</task>

</tasks>

<verification>
- Transcript audit covers all 7 meeting sources with specific quotes
- intelligence_experimentation.py has two-stage model (detect_action_nature + run_discovery)
- Binary detection is DISCOVERED, not hardcoded (grep confirms no hardcoded input_type assignments)
- Analog path is UNCHANGED (all existing methods still present)
- test_phase_a_tmnf.py logs which detection path was taken
- No new hardcoded values introduced (no magic floats that should be discovered)
- D0 measurement preserved as step 1 (Sutton compliance)
- All existing tests/rubrics should still work (verify_rubrics.py unchanged)
</verification>

<success_criteria>
- TRANSCRIPT_AUDIT.md exists with compliance table for all 25 REQs
- detect_action_nature() exists in FrameBinDiscovery
- run_discovery() branches based on nature detection
- Binary actions get meaningful boundaries (not 1e6/1e-6)
- Analog actions get full Sutton sweep (unchanged)
- Zero hardcoded binary/analog classifications
- Results include nature_detection field
</success_criteria>

<output>
After completion, create `.planning/quick/9-full-sutton-meeting-transcript-audit-imp/9-SUMMARY.md`
</output>
