# Deep Sutton Transcript Re-Read + Implementation Verification + Internet Research

**Date:** 2026-03-04
**Research method:** 3 parallel agents (transcript analysis, internet research, implementation audit)
**Scope:** All 7 meeting transcripts, full codebase, TMInterface docs, published papers, open-source repos

---

## Table of Contents

1. [Sutton's Algorithm (Verbatim)](#1-suttons-algorithm-verbatim)
2. [Implementation Comparison](#2-implementation-comparison)
3. [TMInterface Truth](#3-tminterface-truth)
4. [uint8 Verdict](#4-uint8-verdict)
5. [MAX/MIN Algorithm Assessment](#5-maxmin-algorithm-assessment)
6. [Gaps and Deviations](#6-gaps-and-deviations)
7. [Anti-Hallucination Findings](#7-anti-hallucination-findings)
8. [Future Perspective](#8-future-perspective)
9. [Recommendations](#9-recommendations)

---

## 1. Sutton's Algorithm (Verbatim)

The complete algorithm reconstructed from Sutton's exact words across all 7 meeting transcripts. Every quote below is a direct transcription.

### 1.1 The Core Loop

```
FOR each action (gas, brake, steering_left, steering_right, etc.):

  PHASE 1: EXPONENTIAL SWEEP (Powers of 10, going DOWN)
    Start at 1e6
    Send each value for ONE FRAME
    Record the delta (state change)
    Go: 1e6, 1e5, 1e4, 1e3, 100, 10, 1, 0.1, 0.01, 0.001...

  PHASE 2: FIND MAX BRACKET
    All values above MAX give the SAME delta (saturated)
    When delta FIRST drops below the saturated value:
      -> The bracket is [current_value, previous_value]

  PHASE 3: BINARY SEARCH FOR MAX
    "Line" algorithm (alternate from ends inward)
    Until boundary where saturated meets non-saturated
    -> That boundary is MAX

  PHASE 4: FIND MIN BRACKET
    Continue exponential sweep downward
    When delta FIRST becomes 0 (no change at all):
      -> The bracket is [current_value, previous_value]

  PHASE 5: BINARY SEARCH FOR MIN
    Same "line" algorithm
    Until boundary where "has effect" meets "no effect"
    -> That boundary is MIN

  PHASE 6: STORE RESULTS
    MIN, MAX for this action
    Bins = range from MIN to MAX
    Number of bins approximately = MAX / MIN
```

### 1.2 Key Quotes by Topic

#### MAX Discovery

| Source | Quote |
|--------|-------|
| Jan 24 | "the change when the change changes that's when you figured out the max" |
| Jan 31 (Pong) | "if you go beyond the max the delta won't change" |
| Feb 16 | "I send 10 to the power of 6. What is the change? 10. 10 to the power 5. 10... 100. 10. 10. Less than 10." |
| Feb 16 | "So I know that it's smaller than this and bigger than this... So I go to the end of my line, and I try 90..." |

#### MIN Discovery

| Source | Quote |
|--------|-------|
| Jan 24 | "no change is minimum... difference in Delta is the max" |
| Feb 16 | "the first action with no movement is our below minimum... so the second last would become our minimum" |
| Jan 31 (Pong) | "when delta becomes 0... i go below the minimum" |

#### Precision

| Source | Quote |
|--------|-------|
| Jan 24 | "the precision is not us precision is the system" |
| Jan 31 (Pong) | "the feedback that the system gives you is the precision of the system" |
| Feb 16 | "the maximum minimum cannot be guessed by you... has to be calculated" |

#### Frames as Atomic Unit

| Source | Quote |
|--------|-------|
| Jan 15 | "it should be per frame per frame yes it should be exactly" |
| Feb 16 | "you are sending actions for frame not actions for second" |
| Jan 31 (Graph) | "everything has to be done in multiples of frames" |

#### No Hardcoding

| Source | Quote |
|--------|-------|
| Feb 16 | "0.8, 0.5, 0.3 doesn't make sense... this is not an algorithm this is a guess" |
| Jan 24 | "the bins needs to be figured out by the system. Not by us." |

#### Action=0 is Real

| Source | Quote |
|--------|-------|
| Feb 16 | "the action of not giving an action is also an action" |
| Feb 16 | "there is no noise" |
| Jan 9 | "If you interfere with the environment, it's not experimentation, it's an exploration" |

#### State Independence

| Source | Quote |
|--------|-------|
| Jan 9 | "acceleration works in any kind of state, not only from zero" |
| Jan 9 | "we don't need to change the car state to test" |

### 1.3 What Sutton NEVER Said

These concepts appear nowhere in any of the 7 transcripts:

| Concept | Status |
|---------|--------|
| uint8 / uint16 / uint32 / uint64 | **Never mentioned.** Sutton talks about actions as continuous values. |
| D0 subtraction | **Never mentioned.** We invented this. Sutton says action=0 IS an action, not a baseline. |
| Epsilon tolerance | **Never mentioned.** Sutton uses exact comparison: "the delta won't change" = identity. |
| Averaging | **Never mentioned.** One probe = one measurement. "there is no noise." |
| Warmup | **Never mentioned.** No concept of warmup period anywhere. |
| Digital vs analog as separate algorithms | **Never mentioned.** Sutton describes ONE algorithm for all actions. |
| Starting from zero speed as requirement | **Never mentioned.** "acceleration works in any kind of state." |
| Powers of 2 vs powers of 10 | **Powers of 10 explicitly.** "10 to the power of 6... 10 to the power 5..." |
| Binary search "from ends" | **Explicitly described.** "So I go to the end of my line, and I try 90..." |

---

## 2. Implementation Comparison

Side-by-side comparison of what Sutton described vs what our code does.

**Primary source file:** `intelligence/intelligence_experimentation.py`

### 2.1 Algorithm Structure

| Sutton's Spec | Our Code | Match? | Notes |
|---------------|----------|--------|-------|
| Single algorithm for all actions | Two-stage: detect nature first, then branch | **PARTIAL** | Nature detection (line 376) is our optimization, not in Sutton's spec |
| Exponential sweep: 1e6 down | `get_exponential_sequence()` generates powers of 10 | **YES** | Faithful to "10 to the power of 6" |
| D0 measured as first step | `detect_action_nature()` measures D0 at line 430 | **YES** | D0 is measured but NOT subtracted |
| MAX bracket from exponential sweep | Lines 756-770: find where delta changes from saturated | **YES** | Exact Sutton pattern |
| Binary search for MAX | `_binary_search_max()` at line 874 | **YES** | Correct invariant: low=not saturated, high=saturated |
| MIN bracket from continued sweep | Lines 773-787: find where delta equals D0 | **YES** | Correct: "first value with no movement" |
| Binary search for MIN | `_binary_search_min()` at line 917 | **YES** | Correct invariant: low=same as D0, high=different |
| Store MIN, MAX, bins | `build_bins()` at line 1076 | **PARTIAL** | Defaults to 10 uniform divisions when Sutton says bins ~ MAX/MIN |

### 2.2 Stage 1: Nature Detection (NOT in Sutton's spec)

**File:** `intelligence/intelligence_experimentation.py`, lines 376-488
**Class method:** `FrameBinDiscovery.detect_action_nature()`

This is our addition. Sutton's algorithm does not pre-classify actions as binary or analog. He describes one algorithm that works for everything.

**What it does:**
1. Measures D0 (action=0)
2. Probes values across multiple orders of magnitude
3. If all non-D0 deltas are identical -> classify as BINARY
4. If deltas differ across magnitudes -> classify as ANALOG
5. If fewer than 2 non-D0 deltas -> classify as NONE

**Why we added it:** Binary actions (TMNF gas/brake/left/right) have no transition region. Sutton's full exponential sweep would probe 13+ values finding nothing between MAX and MIN. Nature detection identifies this in ~6 probes and takes a shortcut.

**Assessment:** Valid optimization. Does not violate Sutton's algorithm -- it just detects that the algorithm's Phases 2-3 would be trivial (all probes saturated = no bracket) and skips to Phase 4-5 directly.

### 2.3 Stage 2A: Binary Path

**File:** `intelligence/intelligence_experimentation.py`, lines 490-646
**Class method:** `FrameBinDiscovery._run_binary_discovery()`

This path only fires when nature detection classifies the action as BINARY.

| Step | What it does | Sutton Compliance |
|------|-------------|-------------------|
| MAX validation | Probes 1.0, confirms it produces delta_max | **VALID** -- for binary, any value above threshold = MAX |
| MIN search | Binary search between smallest active probe and 0.0 | **VALID** -- Sutton's Phase 5 applied directly |
| Wire step floor | Stops binary search at wire resolution (1/255 for uint8) | **VALID** -- "precision is the system" |
| Result | 2 bins: dead zone + active | **CORRECT** for binary actions |

### 2.4 Stage 2B: Analog Path (Sutton's Full Algorithm)

**File:** `intelligence/intelligence_experimentation.py`, lines 710-868
**Inside:** `FrameBinDiscovery.run_discovery()`

This is Sutton's algorithm implemented faithfully:

| Sutton Phase | Code Lines | Implementation |
|-------------|------------|----------------|
| D0 measurement | Already done in Stage 1, line 430 | Reused from nature detection |
| Exponential sweep | Lines 737-787 | Combined MAX and MIN bracketing in ONE pass |
| MAX binary search | Lines 826-834, calls `_binary_search_max()` | Standard binary search with correct invariant |
| MIN binary search | Lines 841-853, calls `_binary_search_min()` | Standard binary search with correct invariant |

**One deviation:** Sutton implies two separate exponential sweeps (one for MAX, then continue for MIN). Our code does both in a single pass through the sequence. The result is identical because the sequence is monotonically decreasing and MAX bracket is always found before MIN bracket.

### 2.5 Binary Search Implementation

**MAX search** (line 874):
```
Invariant: delta(low) is NOT saturated, delta(high) IS saturated
Binary until (high - low) <= search_precision
Return: high (smallest saturated value)
```

**MIN search** (line 917):
```
Invariant: delta(low) is SAME AS D0, delta(high) is DIFFERENT from D0
Binary until (high - low) <= search_precision
Return: high (smallest value with effect)
```

Both correctly implement Sutton's "line" algorithm. The Feb 16 transcript example:
> "So I know that it's smaller than this and bigger than this... So I go to the end of my line, and I try 90..."

### 2.6 Bin Building

**File:** `intelligence/intelligence_experimentation.py`, lines 1076-1136
**Method:** `FrameBinDiscovery.build_bins()`

**What Sutton said:** "bins = range from MIN to MAX" and "number of bins approximately = MAX / MIN"

**What our code does:** Defaults to 10 uniform divisions of [MIN, MAX] when `num_bins` is not provided (line 1089: `n = num_bins or self.DEFAULT_NUM_BINS`).

**Gap:** Sutton suggests the number of bins should be derived from the ratio MAX/MIN, not hardcoded. For binary actions this is irrelevant (2 bins regardless). For analog actions, this matters.

---

## 3. TMInterface Truth

What the game ACTUALLY supports, from official documentation and verified repos.

### 3.1 InputType Enum (from donadigo.com/tminterface)

| Enum | Value | Type | Range | Notes |
|------|-------|------|-------|-------|
| `InputType::Down` | 0 | bool | 0/1 | Brake |
| `InputType::Up` | 1 | bool | 0/1 | Gas (accelerate) |
| `InputType::Left` | 2 | bool | 0/1 | Digital steer left |
| `InputType::Right` | 3 | bool | 0/1 | Digital steer right |
| `InputType::Steer` | 4 | int | -65536 to +65536 | Analog steering |
| `InputType::Gas` | 5 | int | -65536 to +65536 | Analog gas/brake axis |

### 3.2 TMNF Gas is Binary (Nadeo Confirmed)

TMNF (and all classic TrackMania games) process gas as binary:
> "100% or 0% gas or brakes, no in between." -- Nadeo developer

Even though TMInterface exposes `InputType::Gas` (enum 5) as an analog axis with range [-65536, +65536] and defined thresholds:
- Acceleration threshold: -19661 (values below this = full gas)
- Braking threshold: 19661 (values above this = full brake)

...the TMNF physics engine internally treats this as binary. Any value exceeding the threshold gives 100% acceleration or braking. There is no proportional throttle.

**Our code uses:** `InputType::Up` (enum 1) for gas and `InputType::Down` (enum 0) for brake. This is correct for TMNF.

### 3.3 Steering is Genuinely Analog

**InputType::Steer** (enum 4):
- Range: -65536 to +65536 (131,073 distinct values)
- Convergence rate: 0.2 per tick = 13,107 units per tick
- The car's steering converges toward the target value at 0.2/tick

**InputType::Left / InputType::Right** (enums 2, 3):
- These are keyboard keys
- Digital Left sets the steering target to -65536 (full left lock)
- Digital Right sets the steering target to +65536 (full right lock)
- The car still converges at 0.2/tick toward these extremes

**Our code uses:** `InputType::Left` and `InputType::Right` for steering.

**Why:** Analog steer via `InputType::Steer` requires a joystick or vJoy binding. Without one, `SetInputState(InputType::Steer, value)` fails with "Failed to execute input: no binding for Steer (analog) found." (See MEMORY.md: "Analog Steering Does NOT Work")

**Implication:** Our binary left/right steering is correct for the current setup (no joystick). If analog steering were needed, the system would need a vJoy virtual joystick driver.

### 3.4 Wire Protocol (Our TCP Bridge)

**AgenticBridge.as** (lines 155-181) reads:
```
CSetInputState layout: [int32 type][uint8 left][uint8 right][uint8 accel][uint8 brake][int32 steer]
```

The plugin reads each field and converts to game API calls:
- `left`: `ReadUint8() > 0` -> `SetInputState(InputType::Left, 0 or 1)` (line 156)
- `right`: `ReadUint8() > 0` -> `SetInputState(InputType::Right, 0 or 1)` (line 157)
- `accel`: `ReadUint8() > 0` -> `SetInputState(InputType::Up, 0 or 1)` (line 158)
- `brake`: `ReadUint8() > 0` -> `SetInputState(InputType::Down, 0 or 1)` (line 159)
- `steer`: `ReadInt32()` -> `SetInputState(InputType::Steer, value)` only if non-zero (line 178-179)

### 3.5 Open Source Repos Analyzed

| Repo | Approach | Relevant Finding |
|------|----------|-----------------|
| **Linesight-RL** | DQN with discrete actions via keyboard (Left/Right/Up/Down) | Uses same `Python_Link.as` TCP bridge pattern. Our AgenticBridge.as is based on this. |
| **tmrl** | SAC/REDQ with continuous actions via vgamepad for TM2020 | Uses virtual gamepad for analog inputs. Not applicable to TMNF without joystick. |
| **TMIBruteforceGUI** | GUI for TMInterface's built-in bruteforce mode | Modifies inputs frame-by-frame. Does not do discovery. |
| **donadigo/TMInterfaceClientPython** | Official Python client for TMInterface 1.x | Uses mmap API (dead in 2.x). Not compatible with our TCP bridge. |

---

## 4. uint8 Verdict

### 4.1 The Question

Is uint8 the correct wire format for gas/brake in our TCP protocol?

### 4.2 The Answer: uint8 is TECHNICALLY CORRECT but FUNCTIONALLY MISLEADING

**The three-layer quantization chain:**

```
Layer 1: Python sends float [0.0, 1.0]
         -> round(val * 255) -> uint8 [0, 255]
         (tmnf_adapter.py, line 425)

Layer 2: Plugin reads uint8
         -> uint8 > 0 ? true : false
         (AgenticBridge.as, line 158)

Layer 3: Game receives boolean
         -> SetInputState(InputType::Up, 1 or 0)
         (AgenticBridge.as, line 164)
```

**The TCP wire format is uint8.** This is a fact. It is the type we chose for the Linesight-RL compatible protocol.

**But the game only ever sees 0 or 1.** The 254 intermediate uint8 values (1 through 254) are all collapsed to `true` by the plugin's `> 0` comparison.

**Therefore:**
- `get_wire_precision()` correctly reports 256 levels for the TCP wire (adapter -> plugin)
- But the GAME's precision is 2 levels (off or on)
- The discovery algorithm finds MIN at approximately 1/255 = 0.00392
- This is the **adapter's rounding boundary** (where `round(val * 255)` transitions from 0 to 1)
- This is NOT the **game's true boundary** (which is any non-zero value)

### 4.3 What This Means for Discovery

The discovery algorithm correctly finds the boundary of our system. The system includes our adapter. So the discovered MIN at ~0.004 is the real threshold of our complete pipeline: Python float -> uint8 -> boolean -> game.

**This is actually consistent with Sutton:** "the precision is not us, precision is the system." Our system's precision is determined by the uint8 rounding in our adapter code. The game's internal precision (binary) is irrelevant because we cannot send sub-uint8 values over TCP.

### 4.4 Could We Use bool (uint8 0/1) Instead?

Yes, and it would be simpler. But uint8 was chosen for Linesight-RL compatibility, and it allows future extension if a game with actual analog gas were connected through the same protocol. The wire format is an implementation choice, not a correctness issue.

### 4.5 Verdict

| Aspect | Assessment |
|--------|-----------|
| uint8 for TCP wire | **Correct** -- matches Linesight-RL protocol, backward compatible |
| get_wire_precision() reporting 256 levels | **Technically correct** about the wire, but misleading about the game |
| Discovery finding MIN at ~0.004 | **Correct** -- this IS the system boundary (adapter rounding threshold) |
| TMNF gas being binary | **Confirmed** by Nadeo developer, TMInterface docs, and all repos |

---

## 5. MAX/MIN Algorithm Assessment

### 5.1 Algorithm Classification

Our algorithm combines:
1. **Exponential search** (galloping/doubling search): Start large, decrease by powers of 10
2. **Binary search**: Narrow the bracket to precision

This combination was first described by Jon Bentley and Andrew Chi-Chih Yao in 1976 for searching in unbounded sorted arrays. It is formally known as "galloping search" or "exponential search."

### 5.2 Complexity Analysis

For an action with MAX at position `i` in the exponential sequence:

| Phase | Probes | Reason |
|-------|--------|--------|
| Exponential sweep to MAX bracket | O(log10(range)) | Powers of 10 descent |
| Binary search for MAX | O(log2(bracket_width / precision)) | Halving |
| Exponential sweep to MIN bracket | O(log10(MAX/MIN)) | Continued descent |
| Binary search for MIN | O(log2(bracket_width / precision)) | Halving |
| **Total** | **O(log(range))** | Logarithmic in the search range |

This is **provably optimal** for finding a monotone boundary in an unknown-range system. No algorithm can do better than O(log i) for locating position i in an unbounded sorted sequence (Bentley-Yao 1976).

### 5.3 Powers of 10 vs Powers of 2

Sutton explicitly uses powers of 10: "10 to the power of 6... 10 to the power 5..."

**Powers of 2** would give tighter initial brackets (factor of 2 instead of 10), meaning fewer binary search steps. But powers of 10 require fewer exponential steps to cover the same range:
- Powers of 10: 13 probes to cover [1e-6, 1e6]
- Powers of 2: 40 probes to cover [2^-20, 2^20]

**Total probe count is similar.** Powers of 10 trade wider brackets for fewer exponential steps. Both are O(log) overall.

Sutton's choice of powers of 10 is also more **interpretable** -- probe values are 1, 10, 100, 1000 rather than 1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024.

### 5.4 Comparison to Published Work

| Work | What it does | How it differs |
|------|-------------|----------------|
| **Pazis & Lagoudakis 2009** (ICML) | "Binary Action Search for Learning Continuous-Action Control Policies" | Searches for optimal action VALUE during POLICY EXECUTION, not for discovering action BOUNDARIES during experimentation |
| **BE-CBO** (ICML 2024) | Boundary exploration in black-box optimization | Optimizes objective functions by exploring boundaries in high-dimensional spaces. Different problem. |
| **Bentley & Yao 1976** | Exponential search + binary search for sorted unbounded sequences | The theoretical foundation. Our algorithm is an instance of this. |
| **Linesight-RL** | Discrete DQN with keyboard actions | No discovery algorithm. Actions are pre-defined. |
| **tmrl** | SAC/REDQ with continuous actions | No discovery. Continuous action space is assumed known. |

**Assessment:** No published algorithm does exactly what Sutton's algorithm does (per-frame action boundary discovery in deterministic environments via exponential sweep + binary search). The algorithm is a novel application of Bentley-Yao to reinforcement learning action space discovery.

### 5.5 Optimality Verdict

| Question | Answer |
|----------|--------|
| Is exponential sweep + binary search optimal for this problem? | **YES** -- O(log i) is provably optimal for unbounded monotone boundary search |
| Could we do it faster? | **NO** -- for unknown-range boundary detection, no algorithm beats O(log i) |
| Is Sutton's specific implementation (powers of 10) optimal within the class? | **Within a constant factor** -- powers of 2 give tighter brackets but more exponential steps |
| Is the two-stage nature detection an improvement? | **YES for efficiency** -- saves ~7 probes on binary actions, does not affect correctness |

---

## 6. Gaps and Deviations

Every difference between Sutton's specification (from transcripts) and our current implementation.

### 6.1 Nature Detection (Not in Spec)

**Source:** `intelligence/intelligence_experimentation.py`, lines 376-488
**Severity:** LOW (optimization, not violation)

Sutton describes one algorithm for all actions. We pre-classify actions as binary/analog/none and take different paths. This saves probes on binary actions but is not part of the original specification.

**Impact:** None for correctness. Binary actions discovered via nature detection + binary path produce identical results to what Sutton's full algorithm would produce (MAX=1.0, MIN at threshold boundary, 2 bins).

### 6.2 Plugin Boolean Collapse

**Source:** `TMinterface/AgenticBridge.as`, lines 156-159
**Severity:** HIGH (misleading precision)

The plugin converts all uint8 values to boolean:
```angelscript
const bool accelerate = clientSock.ReadUint8() > 0;  // line 158
```

This means `get_wire_precision()` reports 256 levels for gas/brake, but the game only ever sees 2 levels. The discovery algorithm correctly finds the boundary at ~1/255 (the adapter's rounding threshold), but this boundary is an artifact of OUR quantization, not the game's physics.

**Impact:** Discovery produces correct results for our system (the adapter IS part of the system), but the reported "wire precision" is misleading about the game's actual capability.

### 6.3 Steering Probes Include gas=1.0

**Severity:** MEDIUM (physical necessity)

When probing steering (left/right), the car must be moving to observe yaw changes. Our probing function sends gas=1.0 alongside the steering action. This is a physical necessity (a stationary car cannot turn) but is not explicitly part of Sutton's spec.

Sutton says "acceleration works in any kind of state" but does not address the case where one action's effect depends on another action being active.

### 6.4 Dead Code in ExperimentationIntelligence

**Source:** `intelligence/intelligence_experimentation.py`, line 1262
**Severity:** LOW

The `load_from_documentation()` method references `is_bidir` (line 1262) which is not defined in scope. This method is dead code (never called in current system) but would crash if used.

### 6.5 Combined MAX+MIN in One Exponential Pass

**Source:** `intelligence/intelligence_experimentation.py`, lines 737-787
**Severity:** NEGLIGIBLE

Sutton implies two separate phases: (1) exponential sweep for MAX, then (2) continue for MIN. Our code does both in a single pass. The result is mathematically identical because the sequence is monotonically decreasing and MAX is always encountered before MIN.

### 6.6 Binary Search Precision Floor

**Source:** `intelligence/intelligence_experimentation.py`, lines 896, 937
**Severity:** LOW

Binary search stops when `(high - low) <= search_precision`. The precision is either provided by the user or derived from wire precision. Sutton says "precision is the system" but does not specify a stopping criterion for binary search. Our approach is reasonable.

### 6.7 Wire Precision vs Game Precision

**Source:** `adapters/tmnf_adapter.py`, lines 758-802
**Severity:** HIGH (conceptual confusion)

`get_wire_precision()` reports the TCP wire format's precision (uint8 = 256 levels). But the game's actual precision for gas/brake is 2 levels (binary). The wire precision metadata is correct about the wire but does not reflect the end-to-end system precision.

This matters because the nature detection uses wire precision to derive probes (line 407-417). If wire precision says 256 levels, it generates probes spanning those levels. But the game collapses all non-zero uint8 values to ON.

**What happens in practice:** Discovery correctly identifies the action as BINARY (because all non-D0 deltas are identical regardless of uint8 value). So the misleading precision does not cause incorrect results -- it just wastes a few probes in the dead zone near 1/255.

### 6.8 build_bins() Default of 10 Uniform Divisions

**Source:** `intelligence/intelligence_experimentation.py`, line 1074
**Severity:** LOW

Sutton says "bins approximately = MAX / MIN." Our code defaults to 10 uniform divisions when `num_bins` is not specified. For binary actions this is irrelevant (build_bins detects binary and returns 2 bins). For analog actions, 10 bins may be too many or too few.

### 6.9 D0 Measurement as Explicit First Step

**Severity:** INFORMATIONAL

Our code measures D0 as an explicit first step (`detect_action_nature()` line 430). Sutton's algorithm has D0 measurement as part of the exponential sweep (the first probe at the largest value IS the saturated delta, and D0 is implicitly "what happens when you send nothing").

However, Sutton also says "the action of not giving an action is also an action" -- which implies D0 should be explicitly measured. This is our inference, documented honestly in the quick-9 TRANSCRIPT_AUDIT.md.

---

## 7. Anti-Hallucination Findings

What we were wrong about, what has been proven, and what remains unproven.

### 7.1 Confirmed Hallucinations

| Claim | Reality | How Proven |
|-------|---------|-----------|
| "201 bins for steering" | **HALLUCINATED.** Analog steer fails without joystick binding. All "analog steer" probes measured natural physics drift (~0.001), not real steering. | Live testing: `SetInputState(InputType::Steer, value)` -> "no binding for Steer (analog) found" |
| "Convert Inputs to Analog Steering fixes it" | **FALSE.** This TMInterface setting is a REPLAY OUTPUT FORMATTER. It reformats replay files during validation playback. It does NOT create input bindings. | TMInterface documentation + live testing |
| "vgamepad needs warmup" | **FALSE.** vgamepad is a virtual gamepad driver. It works immediately. The "warmup" was our misdiagnosis of a different issue. | Live testing |
| "tminterface Python package works with TMInterface 2.x" | **FALSE.** The tminterface Python package uses mmap IPC, which was the TMInterface 1.x API. TMInterface 2.x uses a TCP socket protocol via AngelScript plugins. | TMInterface changelog + code analysis |
| "TMNF has analog gas" | **FALSE.** TMNF gas is binary. Confirmed by Nadeo developer, TMInterface API docs, and all tested repos. | TMInterface InputType docs + Nadeo statement |

### 7.2 Confirmed Truths

| Claim | Evidence |
|-------|---------|
| Gas is binary (2 bins) | Nadeo developer statement, TMInterface API (InputType::Up = bool), multi-speed binary proof (5 runs, all identical deltas) |
| Brake is binary (2 bins) | Same evidence as gas, InputType::Down = bool |
| Digital left/right works without joystick | `InputType::Left` and `InputType::Right` are keyboard keys, always available. Confirmed by Linesight-RL and our live tests. |
| Rewind is deterministic | TMInterface `RewindToState()` restores exact simulation state. Confirmed by rubric R1 (rewind determinism) across 5+ runs. |
| D0 is consistent at zero speed | Rubric R11 verified: D0 at rest = 0 for speed. No initialization pollution. |
| Steering accumulates over ticks | Rubric R12 verified: 5 ticks of digital left produces more yaw change than 1 tick. |
| Exponential sweep + binary search is optimal | Bentley-Yao 1976: O(log i) is provably optimal for unbounded monotone boundary search. |

### 7.3 Things We Added (Not Hallucinations, But Not Sutton)

| Addition | Status |
|----------|--------|
| D0 subtraction | We used to subtract D0 from probe deltas. Removed after transcript audit (quick-9). Sutton never said to subtract D0. |
| Two-stage nature detection | Our optimization. Works correctly. Not in Sutton's spec. |
| Epsilon tolerance for delta comparison | We use `measurement_epsilon` to compare deltas. Sutton says "the delta won't change" implying exact comparison. In practice, floating-point comparison needs a tolerance. |
| Wire precision API | Our addition for adapter-level precision metadata. Sutton says "precision is the system" but does not specify how to obtain it. |
| Faithful uint8 quantization | Our improvement over the original `> 0.0` threshold. Correctly maps floats to uint8 via `round(val * 255)`. |

---

## 8. Future Perspective

### 8.1 Sutton's Vision (From Transcripts)

The discovery algorithm is not an end in itself. It is the first step in a larger system:

```
Discovery -> Knowledge Graph -> Exploration -> Planning (MPC) -> Intelligence
```

Key quotes about the future:

| Source | Quote |
|--------|-------|
| Feb 16 | "now I'm gonna say I need to be at 112 in two frames... this is called planning" |
| Jan 9 | "we are creating a bunch of little pieces... small intelligence that when combined they become a bigger intelligence" |
| Jan 31 (Graph) | "each node is one frame's delta... the graph enables pathfinding" |

### 8.2 How Discovery Feeds the Graph

1. **Discovery** produces: MIN, MAX, and the number of bins for each action
2. **Bins** are the **vocabulary** -- the discrete set of meaningfully different actions
3. **Each node** in the knowledge graph is a state (speed, yaw, etc.)
4. **Each edge** is labeled with: which bin was used and what delta resulted
5. **Planning** = graph pathfinding: "I need to be at 112 in two frames" = find a 2-edge path from current node to target node

### 8.3 What This Means for Our Code

- The discovery module is DONE (for binary actions in TMNF)
- The knowledge graph (Phases 2-3) is DONE (variable graphs, multi-graph manager, frame recording)
- Next: exploration (systematically try all bins at various states to fill the graph)
- Then: planning (MPC using the filled graph)

### 8.4 Analog Steering Discovery (Future)

If/when we add joystick support:
- `InputType::Steer` becomes available (131,073 values)
- The exponential sweep + binary search will find the real analog MAX and MIN
- The convergence rate (0.2/tick = 13,107 units/tick) means the per-frame MAX is bounded by the car's physics, not the input range
- This is exactly the scenario Sutton's algorithm was designed for: unknown range, unknown precision, system tells you

---

## 9. Recommendations

### 9.1 Critical Fixes

| # | Fix | Severity | Effort |
|---|-----|----------|--------|
| 1 | **Document the boolean collapse explicitly** -- Add a comment in `get_wire_precision()` that explains the plugin collapses uint8 to boolean for gas/brake/left/right. The wire precision is about the TCP format, not the game's effective precision. | HIGH | 5 min |
| 2 | **Add `game_precision` to wire precision metadata** -- Alongside `wire_type: 'uint8'`, add `game_type: 'bool'` and `game_levels: 2` for gas/brake/left/right. This makes the dual nature explicit. | HIGH | 15 min |
| 3 | **Fix dead code in `load_from_documentation()`** -- The `is_bidir` variable on line 1262 is undefined. Either remove the method or fix it. | LOW | 2 min |

### 9.2 Algorithmic Improvements

| # | Improvement | Rationale | Effort |
|---|------------|-----------|--------|
| 4 | **Derive num_bins from MAX/MIN ratio** -- Sutton says "bins approximately = MAX/MIN." Change `build_bins()` default from 10 to `int(round(a_max / a_min))` when `num_bins` is not provided. | Sutton compliance | 10 min |
| 5 | **Add analog steering discovery path** -- When adapter reports `InputType::Steer` is available (joystick bound), use int32 wire precision (65,536 levels) for probe derivation. | Future readiness | 2 hours |

### 9.3 Documentation

| # | Action | Rationale |
|---|--------|-----------|
| 6 | **Keep this analysis document updated** when future changes are made to the discovery algorithm | This document is the authoritative cross-reference between Sutton's words and our code |
| 7 | **Add transcript quote references to code comments** -- Key functions should cite which transcript and timestamp supports them | Traceability |

### 9.4 Things to NOT Change

| # | What | Why |
|---|------|-----|
| 1 | Two-stage nature detection | Valid optimization, saves probes, does not violate Sutton |
| 2 | uint8 wire format | Linesight-RL compatible, future-extensible, correct for TCP |
| 3 | Powers of 10 in exponential sweep | Sutton explicitly uses powers of 10 |
| 4 | Binary search implementation | Correct invariants, correct stop conditions |
| 5 | Wire step floor for MIN search | Prevents searching below wire resolution -- "precision is the system" |

---

## Appendix A: Code Reference Map

Key functions and their line numbers in `intelligence/intelligence_experimentation.py`:

| Line | Function/Class | Purpose |
|------|---------------|---------|
| 59 | `ExperimentationPhase` | Enum for discovery phases |
| 79 | `ActionBin` | Dataclass for a single bin |
| 104 | `ProbeResult` | Dataclass for a single probe result |
| 116 | `ActionDiscoveryResult` | Complete discovery result for one action |
| 167 | `FrameBinDiscovery` | Main class: Sutton's algorithm for one action |
| 376 | `detect_action_nature()` | Stage 1: binary/analog/none classification |
| 490 | `_run_binary_discovery()` | Stage 2A: binary action fast path |
| 652 | `run_discovery()` | Main entry: two-stage discovery |
| 874 | `_binary_search_max()` | Binary search for MAX boundary |
| 917 | `_binary_search_min()` | Binary search for MIN boundary |
| 954 | `_binary_search_min_consecutive()` | Alternative MIN search (consecutive probe comparison) |
| 994 | `search_bin_boundaries()` | Find transition boundaries between bins |
| 1076 | `build_bins()` | Build bins from discovered MIN/MAX |
| 1142 | `make_bidirectional_bins()` | Mirror bins for steering |
| 1206 | `ExperimentationIntelligence` | Orchestrator for all actions |

Key functions in `adapters/tmnf_adapter.py`:

| Line | Function/Class | Purpose |
|------|---------------|---------|
| 76 | `float_to_steer()` | Convert float to int32 steering |
| 405 | `_send_set_input_state()` | Send action over TCP (uint8 quantization) |
| 425 | (gas quantization) | `np.uint8(min(255, max(0, round(gas_val * 255))))` |
| 758 | `get_wire_precision()` | Wire precision metadata (256 levels for uint8) |

Key lines in `TMinterface/AgenticBridge.as`:

| Line | Code | Significance |
|------|------|-------------|
| 156 | `const bool left = clientSock.ReadUint8() > 0;` | Boolean collapse: uint8 -> bool |
| 157 | `const bool right = clientSock.ReadUint8() > 0;` | Same collapse |
| 158 | `const bool accelerate = clientSock.ReadUint8() > 0;` | Same collapse |
| 159 | `const bool brake = clientSock.ReadUint8() > 0;` | Same collapse |
| 164 | `simManager.SetInputState(InputType::Up, accelerate ? 1 : 0);` | Game API call |
| 178-179 | `if (steer != 0) { simManager.SetInputState(InputType::Steer, steer); }` | Analog steer only if non-zero |

## Appendix B: Algorithm Complexity Proof Sketch

**Claim:** Exponential sweep + binary search achieves O(log i) probes to find boundary at position i.

**Proof:**
1. Exponential sweep with factor k (we use k=10) takes ceil(log_k(i)) probes to overshoot i
2. This creates a bracket of width at most k * i
3. Binary search within this bracket takes ceil(log_2(k * i / precision)) probes
4. Total: O(log_k(i) + log_2(k * i / precision)) = O(log(i))

**Lower bound:** Any comparison-based search in an unbounded ordered set requires Omega(log i) comparisons (information-theoretic lower bound).

**Conclusion:** Our algorithm is asymptotically optimal.

## Appendix C: Comparison to Linesight-RL

Linesight-RL (the repo our plugin is based on) uses:
- DQN with discrete actions: {nothing, up, down, left, right, up+left, up+right, down+left, down+right}
- Pre-defined action space (9 combinations)
- No discovery algorithm
- Same TCP bridge pattern (`Python_Link.as`)

**Key difference:** Linesight-RL ASSUMES the action space. We DISCOVER it. This is the core innovation.

## Appendix D: TMInterface API URLs

| Resource | URL |
|----------|-----|
| TMInterface main page | https://donadigo.com/tminterface |
| TMInterface 2.x documentation | https://donadigo.com/tminterface/docs |
| InputType enum | https://donadigo.com/tminterface/docs/api/enums/InputType |
| Linesight-RL repo | https://github.com/pb4git/Linesight-RL |
| tmrl repo | https://github.com/trackmania-rl/tmrl |
| TMIBruteforceGUI | https://github.com/theboyknowsclass/TMIBruteforceGUI |
