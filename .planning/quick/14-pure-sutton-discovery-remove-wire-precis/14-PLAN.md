# Quick Task 14: Pure Sutton Discovery — Single Algorithm, No Shortcuts

## Context

After deep transcript analysis (quick-12), we identified that:
1. Our binary path hardcodes MAX=1.0, but Sutton's algorithm finds MAX where delta changes from saturated
2. For binary actions, MAX = MIN ≈ 0.002 (the threshold where uint8 rounds from 0 to 1)
3. The two-stage nature detection is our optimization — Sutton has ONE algorithm for all actions
4. Wire precision is a shortcut that Sutton doesn't need — the exponential sweep discovers everything

## What Changes

**Replace the two-stage model with Sutton's single algorithm:**
1. Remove `detect_action_nature()` as a prerequisite — nature is DISCOVERED by the sweep
2. Remove `_run_binary_discovery()` — no separate binary path needed
3. The exponential sweep naturally handles both cases:
   - ANALOG: delta goes saturated → intermediate → D0 (two brackets found)
   - BINARY: delta goes saturated → D0 directly (one bracket found, MAX=MIN)
4. Remove wire_precision parameter from `run_discovery()` — algorithm doesn't need it
5. Keep wire_precision in adapter (it's adapter metadata, not algorithm input)

## The Pure Sutton Algorithm

```
1. Measure D0 = probe_fn(0.0)
2. Exponential sweep: 1e6, 1e5, 1e4, ..., 1e-6
   - First non-D0 delta = saturated delta (delta_max)
   - When delta CHANGES from saturated (drops to different value or D0):
     → MAX bracket = [current_val, prev_val]
   - After MAX bracket found, continue sweep
   - When delta becomes D0:
     → MIN bracket = [current_val, prev_val]
   - Special: if delta goes directly from saturated to D0 (binary):
     → MAX bracket and MIN bracket are the SAME bracket
     → Binary search will find MAX = MIN = threshold
3. Binary search MAX bracket → MAX
4. Binary search MIN bracket → MIN
5. If MAX bracket == MIN bracket → MAX = MIN (binary action, 1 effective bin)
6. Return MIN, MAX
```

## Tasks

### Task 1: Rewrite `run_discovery()` as Pure Sutton Single Algorithm

**File:** `intelligence/intelligence_experimentation.py`

**Changes:**
- Rewrite `run_discovery()` to be ONE algorithm path (no nature detection gate)
- Algorithm steps:
  1. Measure D0 = probe_fn(0.0)
  2. Exponential sweep from 1e6 downward
  3. Track `delta_max` (first non-D0 delta = saturated reference)
  4. Find MAX bracket (where delta changes from saturated)
  5. If delta goes directly to D0 → combined bracket (binary detected)
  6. If delta goes to intermediate value → separate MAX and MIN brackets (analog)
  7. Binary search each bracket
  8. Store a_max, a_min, nature (binary if MAX≈MIN, analog otherwise)
- Remove `wire_precision` parameter from `run_discovery()`
- Keep `detect_action_nature()` and `_run_binary_discovery()` as deprecated/unused (don't delete — other code may reference them)
- `_binary_search_max()` and `_binary_search_min()` stay unchanged
- `build_bins()` stays unchanged (it already handles binary: detects when delta_at_min == delta_max)

**Key logic for the combined bracket (binary detection in pure Sutton):**
```python
# During exponential sweep:
if not found_max_bracket:
    if not self._is_saturated(delta):
        # Delta changed from saturated — but is it D0 or intermediate?
        if self._is_same_as_delta0(delta):
            # Saturated → D0 directly = BINARY action
            # MAX and MIN share the same bracket
            max_bracket = min_bracket = (val, prev_val)
            found_max_bracket = found_min_bracket = True
        else:
            # Saturated → intermediate = ANALOG action
            max_bracket = (val, prev_val)
            found_max_bracket = True
```

**After binary search:**
```python
if max_bracket == min_bracket:
    # Binary: MAX and MIN converge to same threshold
    self.nature = 'binary'
    # Both binary searches return the same value
else:
    self.nature = 'analog'
```

### Task 2: Update `test_phase_a_tmnf.py` to Remove Wire Precision from Discovery Call

**File:** `test_phase_a_tmnf.py`

**Changes:**
- In `run_discovery_tmnf()`: remove `wire_precision=action_wire_prec` from `disc.run_discovery()` call
- Keep wire_precision in the function signature and logging (it's still useful metadata for the JSON output)
- The algorithm now discovers everything from probing alone
- Verify all actions still work: gas, brake, left, right

### Task 3: Run 5 Live Validation Runs and Report Results

**Script:** `run_5_tmnf_and_excel.py` (already exists, reuse or create `run_5_pure_sutton.py`)

**Steps:**
1. Connect to TMNF via TMInterface
2. Accelerate to ~200 km/h (save state at speed)
3. Run discovery 5 times, saving state between runs
4. For each run, capture: MIN, MAX, D0, delta_max, probes, nature for all 4 actions
5. Save JSON results
6. Print summary table showing:
   - Per-action: MIN, MAX, nature, probes across 5 runs
   - Cross-run stability: are MIN/MAX identical?
   - Key finding: MAX should now be ≈ MIN ≈ 0.002 for binary actions (not 1.0)

**Expected results for TMNF binary actions:**
- Gas: MAX ≈ MIN ≈ 0.002 (uint8 rounding boundary), nature=binary
- Brake: MAX ≈ MIN ≈ 0.002, nature=binary
- Left: MAX ≈ MIN ≈ 0.002, nature=binary
- Right: MAX ≈ MIN ≈ 0.002, nature=binary
- All 5 runs identical (deterministic rewind)

## Files Modified

| File | Action |
|------|--------|
| intelligence/intelligence_experimentation.py | EDIT — rewrite run_discovery() |
| test_phase_a_tmnf.py | EDIT — remove wire_precision from discovery call |
| run_5_pure_sutton.py | CREATE — 5-run validation script |

## Verification

1. Offline: existing tests in test_precision_discovery.py may need updating (they test wire_precision path)
2. Live: 5 runs against TMNF produce consistent results
3. MAX = MIN for all binary actions (not MAX=1.0 anymore)
4. Nature correctly detected as 'binary' through the sweep (not pre-classified)
