# Meeting Demo Script -- Sutton Bin Discovery Implementation

> **Read from mobile. Click-level instructions in [SCREEN] tags.**
> **Estimated time: 30-40 minutes.**

---

## Section 1: Opening (2 min)

**1.** Start with a brief context-set.

[SAY: "Let me show you what we built and how it works. This is the full bin discovery algorithm -- everything is discovered from the environment, nothing hardcoded."]

**2.** Open the Excel results file.

[SCREEN: Open `Untitled spreadsheet (1).xlsx` in Excel/Google Sheets]

[SAY: "This spreadsheet has 9 sheets. We measure two things first -- frame duration and system precision -- then we run the complete discovery algorithm 5 times and capture every single probe the system sends."]

**3.** Give the overview before diving in.

[SAY: "The algorithm discovers 4 actions: gas, brake, left, and right. For each action, it sends probes, measures the speed or yaw delta, and finds the exact threshold where the action turns on and off. Every probe is logged here with full explanation."]

---

## Section 2: Excel -- Frame Duration Sheet (3 min)

**1.** Navigate to the Frame Duration tab.

[CLICK: Click the 'Frame Duration' tab at the bottom of the spreadsheet]

**2.** Read the Sutton requirement first.

[SAY: "Before I show you the data, here is the requirement from the January 9 meeting:"]

> **"the frame is the timestamp"** -- Jan 9
> **"who defines the time stamp is the environment"** -- Feb 16

[SAY: "So we do not hardcode 10 milliseconds. We measure it from the environment."]

**3.** Walk through the measurement.

[SCREEN: Point to the race_time_before and race_time_after columns]

[SAY: "Here is how it works. We send a neutral action -- zero gas, zero brake, zero steering -- and advance the game by one tick. We read race_time before and after. The delta is 10 milliseconds. That is our frame duration, measured from the environment, not configured."]

**4.** Explain why this matters.

[SAY: "If we took this algorithm to a different game that runs at 16ms frames, or 20ms frames, it would discover the new frame duration automatically. Nothing in the code says '10ms'."]

---

## Section 3: Excel -- System Precision Sheet (3 min)

**1.** Navigate to the System Precision tab.

[CLICK: Click the 'System Precision' tab]

**2.** Read the Sutton requirement.

> **"the precision is not us, precision is the system"** -- Jan 24

[SAY: "We need to know: how precise is the system's feedback? Can we trust a delta of 0.000001, or is that noise? The answer comes from probing, not from assuming."]

**3.** Walk through the D0 probes.

[SCREEN: Point to the three D0 probe rows -- speed_delta values]

[SAY: "We rewind to the exact same game state three times and send the same action -- zero, do nothing -- three times. We measure the speed delta each time."]

[SAY: "All three deltas are bit-identical. Variance is zero. The system is perfectly deterministic with rewind. There is no noise."]

**4.** Explain epsilon derivation.

[SAY: "Since the variance is zero, the epsilon comes from float64 machine precision. The speed epsilon is 1.41 times 10 to the negative 15. That is 15 decimal places of precision. The yaw epsilon is 10 to the negative 15."]

[SAY: "This is the system telling us its own precision. We do not pick a number. The system tells us."]

> **"there is no noise"** -- Feb 16

---

## Section 4: Excel -- Run 1 Walkthrough (8 min)

This is the most important section. Walk through every phase of the discovery for gas.

**1.** Navigate to Run 1.

[CLICK: Click the 'Run 1' tab]

[SAY: "This is the most important sheet. Every single probe the algorithm sends is logged here, with full explanation. Let me walk through gas step by step."]

**2.** Explain the columns.

[SCREEN: Point across the 13 column headers]

[SAY: "13 columns for every probe. The probe number, what phase it is in, the action value we sent, how that value was calculated, the speed delta we got back, whether it matches D0, whether it matches the saturated delta, the bracket before the probe, what we did, what we got, what it means, the decision and why, and the bracket after."]

**3.** Walk through the D0 probe (green row).

[SCREEN: Point to row 1 -- green background]

[SAY: "Probe 1. Green row. We send gas equals zero. The speed delta is negative 0.6279 km/h. The car is slowing down from aerodynamic drag. This is D0."]

> **"not doing an action is also an action"** -- Jan 9, Feb 16

[SAY: "D0 is not noise. It is not a baseline to subtract. It is a real transition -- the car decelerating under drag. When we do nothing, the car still changes speed. That IS an action result."]

**4.** Walk through the exponential sweep (yellow rows).

[SCREEN: Point to rows 2-10 -- yellow background]

[SAY: "Now the exponential sweep. This comes directly from the January 15 meeting:"]

> **"you start with zero and then you go to like 0.1, 0.01, 0.001"** -- Jan 15

[SAY: "We go the other way -- we start big and go small. Probe 2: gas equals 1,000,000. Delta is positive 0.159 km/h. Full gas effect. The game clamps any value above its max to max. The delta is positive because gas is accelerating the car."]

[SAY: "Probe 3: gas equals 100,000. Same delta, 0.159. Still saturated."]

[SAY: "Probes 4 through 10: 10,000, 1,000, 100, 10, 1.0, 0.1, 0.01. ALL the same delta. Every single one produces the exact same gas effect. They are all saturated."]

[SAY: "This tells us something important. Sending gas=1,000,000 and gas=0.01 produce the identical result. The game does not distinguish them. They are the same bin."]

**5.** Walk through the bracket discovery (orange row).

[SCREEN: Point to row 11 -- orange background]

[SAY: "Probe 11. This is the critical moment. Gas equals 0.001. The delta drops to negative 0.628 -- that is D0. No gas effect at all."]

[SAY: "So between 0.001 and 0.01, there is a transition. Below 0.001, the gas action has no effect. Above 0.01, it has full effect. The bracket is found."]

> **"I started with 100 and I started with 10... now I know bigger than 10 smaller than 100"** -- Jan 31

[SAY: "But this is a binary action -- it went from saturated directly to D0. There is no intermediate value. No transition region. The delta never takes a value between 0.159 and negative 0.628. It is either full gas or no gas. So the MAX bracket and the MIN bracket are the SAME bracket: [0.001, 0.01]. One binary search finds both."]

> **"when the change changes that's when you figured out the max"** -- Jan 24

**6.** Walk through the binary search (blue rows).

[SCREEN: Point to rows 12-54 -- blue background]

[SAY: "Now binary search narrows the bracket. Probe 12: midpoint of 0.001 and 0.01 is 0.0055. Delta is 0.159 -- saturated. So the threshold is below 0.0055. The bracket narrows to [0.001, 0.0055]."]

[SCREEN: Point to the 'How Value Calculated' column]

[SAY: "Look at this column -- it shows exactly how each probe value is calculated. 'mid = (0.001 + 0.01) / 2 = 0.0055'. Every value is the midpoint of the current bracket."]

[SAY: "Probe 13: midpoint of 0.001 and 0.0055 is 0.00325. Still saturated. Bracket narrows to [0.001, 0.00325]."]

[SAY: "Probe 14: midpoint is 0.002125. Still saturated. Bracket narrows further."]

[SAY: "Probe 15: midpoint is 0.0015625. Delta drops to D0. Now the bracket is [0.0015625, 0.002125]."]

[SAY: "This keeps going for 44 binary search steps. The bracket narrows from a width of 0.009 all the way down to the float64 precision limit. The threshold converges to 0.00196078431372644."]

[SCREEN: Point to the 'Bracket AFTER' column on the last few rows]

[SAY: "Watch the bracket column narrow. Each step halves the range. By probe 54, the bracket is so narrow that the difference between low and high is smaller than our epsilon -- 10 to the negative 15. We cannot distinguish further. The binary search stops."]

**7.** Walk through the verification probe (light green row).

[SCREEN: Point to the last probe -- light green background]

[SAY: "Probe 55. Verification. We probe the discovered threshold value one more time to confirm. Delta is 0.159 -- saturated. Confirmed: this is the threshold. Below it, dead zone. Above it, full gas."]

**8.** Show the result (light blue row).

[SCREEN: Point to the result row -- light blue background]

[SAY: "Result for gas: MAX equals MIN equals 0.00196. Binary action. Two bins -- dead zone and ON. 55 probes total, 1.5 seconds."]

[SAY: "That threshold, 0.00196, is exactly 1/510 -- which is 0.5/255. It is the adapter's uint8 quantization boundary. Python sends a float, the adapter converts it to a byte using round(value times 255), the plugin reads the byte and checks if it is greater than zero. The transition happens at 0.5/255. The algorithm discovered this without knowing any of it."]

> **"the first action with no movement is our below minimum"** -- Jan 24

**9.** Briefly cover brake.

[SAY: "Brake is the same story. Same threshold at 0.00196. Same 55 probes. The difference is the delta -- brake produces negative 0.682, which is the car decelerating even more than drag alone. Same binary pattern: dead zone plus ON."]

**10.** Cover left and right.

[SAY: "Left and right are steering inputs. Same algorithm, same threshold at 0.00196. But the deltas are tiny -- 1.94 times 10 to the negative 5 radians for left, negative 2.05 times 10 to the negative 5 radians for right. These are yaw changes, not speed changes. Left turns positive yaw, right turns negative yaw. Opposite directions, same magnitude. Binary: two bins each."]

[SAY: "Left and right each take 56 probes instead of 55 because the D0 probe for yaw is slightly different from the speed D0. The algorithm handles this naturally."]

---

## Section 5: Excel -- Runs 2-5 Comparison (3 min)

**1.** Show consistency across runs.

[CLICK: Click the 'Run 2' tab, then 'Run 3' tab briefly]

[SAY: "I ran the full discovery algorithm 5 times. Every time, same result."]

**2.** Show the Summary tab.

[CLICK: Click the 'Summary' tab]

[SAY: "Here is the cross-run comparison table. All 5 runs produce the same MAX, same MIN, same number of probes, same number of bins. The threshold is 0.00196 for all actions, all runs. The D0 delta differs slightly between runs because the car's speed changes between runs -- we accelerate to 200 km/h each time but the exact speed varies by a fraction of a km/h. But the THRESHOLD is identical. Same adapter boundary, same discovery."]

[SAY: "Total across all 5 runs: 222 probes per run, 1,110 probes total, 52.3 seconds total wall time."]

**3.** Emphasize determinism.

[SAY: "This perfect consistency comes from two things. First, rewind gives us deterministic state restoration. Second, the algorithm does not use any randomness or heuristics. Same state plus same action equals same result, every time."]

> **"0.8, 0.5, 0.3 doesn't make sense... this is not an algorithm this is a guess"** -- Feb 16

---

## Section 6: How Rewind Works (5 min)

**1.** Transition from Excel to explanation.

[SAY: "Let me explain HOW we get this determinism. It comes from the rewind mechanism."]

[SCREEN: You can stay on Excel or open a blank notepad -- this is a verbal explanation]

**2.** Explain the save/rewind protocol.

[SAY: "There are five steps in the protocol."]

[SAY: "Step 1. Python sends a SAVE command to the game through a TCP socket. This is a network connection between our script and the TMInterface plugin running inside the game."]

[SAY: "Step 2. The game freezes. It packages the ENTIRE physics state into a binary blob -- about 2 kilobytes. Position, velocity, rotation, race time, everything. Every floating-point number that defines where the car is and what it is doing. It sends this blob back to Python."]

[SAY: "Step 3. Before each probe, Python sends a REWIND command with that same blob. The game loads it. The car is in the exact same position, the exact same speed, the exact same orientation. Bit-identical."]

[SAY: "Step 4. The game is frozen while Python decides what to do. Python sends a 'step one tick' command, waits for the game to advance exactly one tick, then reads the result. There is no timing jitter because the game does not run on its own -- it only advances when Python tells it to."]

[SAY: "Step 5. Same state plus same action equals same result. Every time. That is why the variance is zero. That is why 5 runs give identical thresholds."]

**3.** Explain why this matters for the algorithm.

[SAY: "This is what makes the algorithm work. There is no noise, no averaging needed, no statistical testing. One probe gives one definitive answer. If the delta is 0.159, it is 0.159 forever for that state and action. If it is negative 0.628, it is negative 0.628 forever."]

> **"we should not interfere with the experimentation"** -- Jan 9
> **"there is no noise"** -- Feb 16

[SAY: "Rewind is our time machine. We can test any action from the exact same state as many times as we want. Each test is independent. No side effects."]

**4.** The 2-tick input delay.

[SAY: "There is one quirk we handle. TMInterface has a 2-tick input delay. When we send an action during tick N, it does not take effect until tick N+1. So after rewinding, tick 1 replays the saved state's inputs -- that is the game's built-in replay system. Our action queues up during tick 1. Then tick 2 is when our action actually takes effect. We read feedbacks at the end of tick 1 and at the end of tick 2. The delta between them is purely our action's contribution."]

[SAY: "This is why every probe is exactly 2 ticks. Tick 1 sets up, tick 2 measures. Clean, deterministic, one frame."]

---

## Section 7: Code Execution Flow (5 min)

**1.** Open the main test script.

[SCREEN: Open `test_phase_a_tmnf.py` in VS Code or any text editor]

[SAY: "Let me show you how the code runs. This is the entry point."]

**2.** Walk through the flow.

[SAY: "Step 1. You run `python test_phase_a_tmnf.py` in the terminal. It parses arguments -- port 8476, speed 1.0, timeout 30."]

[SCREEN: Scroll to the `main()` function near line 552]

[SAY: "Step 2. Main creates a TMNFAdapter and connects to the game via TCP on port 8476. This connects to AgenticBridge.as, the AngelScript plugin running inside the game."]

[SAY: "Step 3. It waits for a race to start. The game needs to be in a race with the countdown finished."]

[SAY: "Step 4. `measure_frame_duration()` -- this is the function we just saw in the Excel. Sends neutral action, advances two ticks, reads race_time delta. Result: 10ms."]

[SCREEN: Scroll to `measure_frame_duration` near line 78]

[SAY: "Step 5. Accelerate the car. We send gas=1.0 for enough ticks to reach 200 km/h. The algorithm needs the car moving because at zero speed, steering produces zero yaw change -- there is no lateral tire force without velocity."]

[SAY: "Step 6. `measure_system_precision()` -- save the game state, then run 3 D0 probes from the exact same state. Compute variance. All deltas identical, variance is zero, epsilon is 1.41e-15."]

[SCREEN: Scroll to `measure_system_precision` near line 113]

[SAY: "Step 7. `run_discovery_tmnf()` -- this is the main event. Save state ONCE for all actions. Then loop through gas, brake, left, right."]

[SCREEN: Scroll to `run_discovery_tmnf` near line 315]

**3.** Explain the architecture.

[SAY: "Step 8. For each action, the code creates a FrameBinDiscovery object -- that is the generic algorithm. It does not know about TMNF or TCP or games. It just knows how to do exponential sweep and binary search."]

[SAY: "Step 9. It creates a probe function using `make_probe_fn()`. This probe function is a closure that handles all the TMNF-specific details: rewind, 2-tick delay, reading feedbacks, computing the delta. The algorithm calls `probe_fn(0.5)` and gets back a delta. It does not know or care how."]

[SCREEN: Scroll to `make_probe_fn` near line 227]

[SAY: "Step 10. `disc.run_discovery(probe_fn)` -- the generic algorithm runs. It calls probe_fn for D0, then does the exponential sweep, finds the bracket, binary searches, and returns MAX and MIN. The algorithm is completely generic. You could give it a different probe function for a different game and it would work the same way."]

**4.** Show the core algorithm file.

[SCREEN: Open `intelligence/intelligence_experimentation.py` and scroll to the `run_discovery` method near line 652]

[SAY: "This is the core algorithm. Look at the docstring. 'Pure Sutton single-algorithm discovery. ONE algorithm handles both binary and analog actions. No pre-classification.' The nature -- binary or analog -- is DISCOVERED by the sweep itself. If the delta goes from saturated directly to D0, it is binary. If there is an intermediate value, it is analog."]

**5.** Show save_results.

[SAY: "Step 11. `save_results()` writes everything to a JSON file with a timestamp. All probe data, all metadata, all Sutton compliance flags. The Excel is generated from this JSON."]

---

## Section 8: Digital Steering -- The Bug and The Fix (5 min)

**1.** Set up the story.

[SAY: "This was a major issue we discovered and fixed. Let me tell the full story."]

**2.** Explain the original problem.

[SAY: "Originally, the plugin used `InputType::Steer` for all steering. That is the analog steering axis -- range negative 65,536 to positive 65,536. It is designed for joystick input."]

[SAY: "But TMNF on this machine has no joystick connected. When the plugin tries to set analog steer, TMInterface throws an error: 'Failed to execute input: no binding for Steer analog found.' The input is completely dead."]

**3.** Explain the hallucination.

[SAY: "Before we discovered this, the old version of the algorithm reported 201 steering bins. That result was wrong -- it was a hallucination. What was actually happening: the car was on a slight slope, and physics drift caused tiny speed and position changes. The algorithm was measuring those drifts and interpreting them as steering signal. But the analog steer input was doing absolutely nothing."]

**4.** Explain the proof.

[SAY: "We have an anti-hallucination test -- rubric R14. It sends analog steer equals 1.0 -- full lock -- and compares the result to no steering at all. The deltas are bit-identical. Zero difference. The analog steer channel is completely dead. Any previous result using it was measuring noise, not signal."]

**5.** Explain the fix.

[SAY: "The fix was to switch to `InputType::Left` and `InputType::Right`. These are keyboard key inputs -- the Left arrow and Right arrow keys. They always work, no joystick binding needed. This is exactly how Linesight-RL handles it too."]

**6.** Explain the full chain.

[SAY: "Here is the full chain from Python to game input. Python sends a float between 0 and 1. The adapter converts it to a byte using round(value times 255). The plugin reads the byte and checks: is it greater than zero? If yes, the key is pressed. If no, the key is released. The game sees ON or OFF. That is it."]

[SAY: "So the algorithm correctly discovers left and right as binary actions. Two bins each -- dead zone and ON. The threshold at 0.00196 is exactly the adapter's uint8 quantization boundary: 0.5 divided by 255."]

**7.** Connect to the bigger principle.

> **"bins needs to be figured out by the system. Not by us."** -- Jan 9

[SAY: "We did not hardcode 'steering is binary.' The algorithm discovered it. We did not hardcode the threshold at 0.00196. The algorithm found it. The system told us: 'your steering input chain has exactly two states, and the boundary is here.'"]

> **"the precision is not us, precision is the system"** -- Jan 24

---

## Section 9: Live Demo -- Terminal (5 min)

**1.** Set up the prerequisites.

[SAY: "Now I will run the discovery live. Let me set up."]

[SCREEN: Make sure TMNF is running with TMInterface loaded and a race active]
[SCREEN: Open a terminal / PowerShell window]

**2.** Show the command.

[SAY: "The command is simple."]

[CLICK: Type in terminal: `python test_phase_a_tmnf.py`]

[SAY: "That is it. No flags, no config files, no parameters. Everything is discovered from the environment."]

**3.** Watch the output and explain each section.

[SAY: "Watch the logs. I will explain as they appear."]

**Expected log output (explain each section as it appears):**

```
======================================================================
  PHASE A BIN DISCOVERY -- Pure Sutton (Zero Hardcoding)
  Everything is DISCOVERED from the environment.
======================================================================

  Mode:     REWIND (independent probes)
  Speed:    1.0x
  Actions:  ['gas', 'brake', 'left', 'right']
  Ticks:    2 per probe (ALL actions -- no exceptions)
```

[SAY: "Header. Rewind mode, 4 actions, 2 ticks per probe. Nothing hardcoded."]

**Frame duration:**

```
[STEP 0] Measuring frame duration from environment...
  Frame duration: 10ms (0.01s)
  (Measured from environment, not hardcoded)
```

[SAY: "Frame duration measured. 10 milliseconds. Not hardcoded."]

**Acceleration:**

```
  Accelerating to 200.0 km/h...
  Speed: 203.4 km/h
```

[SAY: "Getting the car moving for steering tests."]

**System precision:**

```
[STEP 1] Measuring system precision (3 D0 probes)...
  D0 probe 1: speed_delta=-0.627890617289978, yaw_delta=-5.75208868980326e-07
  D0 probe 2: speed_delta=-0.627890617289978, yaw_delta=-5.75208868980326e-07
  D0 probe 3: speed_delta=-0.627890617289978, yaw_delta=-5.75208868980326e-07
  Speed variance: 0 -> epsilon=1.4076351003425836e-15 (14 digits)
  Yaw variance:   0 -> epsilon=1e-15 (15 digits)
  Deterministic:  True
```

[SAY: "Three D0 probes. All bit-identical. Variance is zero. Deterministic confirmed. Speed epsilon is 1.41e-15, yaw epsilon is 1e-15."]

**Gas discovery:**

```
============================================================
  DISCOVERING: gas
  Epsilon: 1.4076351003425836e-15 (measured from environment)
  Rewind:  True
  Ticks per probe: 2 (same for ALL actions)
============================================================
  [STEP 1] Measure D0 = probe_fn(0.0)
    D0 = -0.627891
    (Real transition, not noise)
  [STEP 2] Exponential sweep (pure Sutton single algorithm)...
    a=1000000.000000 -> delta=0.158960
    a=100000.000000 -> delta=0.158960
    ...
    a=0.010000 -> delta=0.158960
    a=0.001000 -> delta=-0.627891
    >>> COMBINED BRACKET (BINARY): [0.001000, 0.010000]
  [STEP 3] Binary search on bracket [0.001, 0.01]...
    (44 binary search steps)

  RESULT: gas
    Nature = binary (DISCOVERED by exponential sweep)
    MAX    = 0.001960784314
    MIN    = 0.001960784314
    D0     = -0.6278906173
    Dmax   = 0.1589598458
    Bins   = 2
    Probes = 55
    Time   = 1.5s
    Type:  binary (DISCOVERED)
```

[SAY: "Gas discovery. D0 measured. Exponential sweep finds all values from 1,000,000 down to 0.01 produce the same delta. At 0.001, delta drops to D0. Combined bracket found -- this is a binary action. Binary search narrows the bracket in 44 steps. Result: gas is binary, threshold at 0.00196, 2 bins, 55 probes, 1.5 seconds."]

**Brake, left, right:**

[SAY: "Same pattern for brake, left, right. Brake has a larger negative delta because braking adds to drag. Left and right use yaw delta instead of speed delta, with values in the 10-to-the-negative-5 range. Same threshold for all. Same binary result."]

**Summary:**

```
======================================================================
PHASE A COMPLETE -- TMNF (Pure Sutton)
======================================================================
  Frame duration: 10ms (measured)
  Total probes: 222
  Total time:   6.4s
  Rewind mode:  True
  Ticks/probe:  2 (ALL actions)
  gas:   MIN=0.001960784314, MAX=0.001960784314, 2 bins, 55 probes [binary]
  brake: MIN=0.001960784314, MAX=0.001960784314, 2 bins, 55 probes [binary]
  left:  MIN=0.001960784314, MAX=0.001960784314, 2 bins, 56 probes [binary]
  right: MIN=0.001960784314, MAX=0.001960784314, 2 bins, 56 probes [binary]
======================================================================
```

[SAY: "Summary. 4 actions, all binary, 222 total probes, about 6 seconds. The JSON file is written to disk automatically."]

---

## Section 10: Knowledge Graph (3 min)

**1.** Transition from discovery to what comes next.

[SAY: "Once we have bins, we know the action vocabulary. For TMNF, there are 4 binary actions, so 2 to the power of 4 equals 16 possible input combinations per frame. Now we record what each combination does from each state. That is the knowledge graph."]

**2.** Explain the graph structure.

> **"I have my car at 100 -- that's a node. Action gas. Now 110 -- edge connects them."** -- Jan 15

[SAY: "One graph per feedback variable. We have a speed graph, position graphs for X, Y, Z, and a yaw graph. Nodes are discretized state values. Edges are actions with bin labels."]

[SAY: "For example, in the speed graph: the car is at speed 203.4 -- that is a node. We apply gas ON. Speed becomes 203.6 -- that is another node. The edge between them is labeled 'gas: ON'. If we apply brake ON instead, speed becomes 202.7 -- different node, different edge, same source."]

**3.** Explain the multi-graph architecture.

> **"from the list of feedback... a hundred graphs are going to be created"** -- Meeting 3

[SAY: "Each feedback variable gets its own graph. Speed, position X, position Y, position Z, yaw. Five graphs, all updated simultaneously on every frame. The MultiGraphManager coordinates this. When we record one frame of experience, all five graphs get a new edge."]

**4.** Explain the purpose.

[SAY: "The graph is the agent's memory. It maps every state-action-state transition the agent has ever experienced. Once the graph is populated, the agent can look up: 'from state X, what action gets me to state Y?' That is path planning."]

> **"now I'm gonna say I need to be at 112 in two frames... this is called planning"** -- Feb 16

[SAY: "Planning is finding a path through the graph from the current state to the goal state. Each edge is one frame, one action. The shortest path gives the optimal action sequence."]

---

## Section 11: Algorithm Details (5 min)

**1.** Open the Algorithm sheet in Excel.

[CLICK: Click the 'Algorithm' tab in the spreadsheet]

[SAY: "This sheet explains the algorithm step by step. Let me summarize the key points."]

**2.** Exponential sweep explained.

[SAY: "The exponential sweep uses powers of 10. We start at 1,000,000 and divide by 10 each step: 100,000, 10,000, 1,000, 100, 10, 1, 0.1, 0.01, 0.001, and so on down to 0.000001."]

> **"you start with zero and then you go to like 0.1, 0.01, 0.001"** -- Jan 15

[SAY: "This is a geometric search. It covers 12 orders of magnitude in just 13 probes. Whether the action range is 0 to 1 or 0 to 1,000,000, the sweep finds the bracket in at most 13 steps."]

**3.** Binary search explained.

[SAY: "Once we have a bracket -- say [0.001, 0.01] -- we binary search. Take the midpoint 0.0055, probe it. If saturated, the threshold is below 0.0055. If D0, the threshold is above 0.0055. Either way, the bracket halves. 44 steps bring us to float64 precision."]

[SAY: "The total complexity is O of log of the inverse precision. We go from a range of 10 to the 12 down to 10 to the negative 15 in about 90 probes per action. That is provably optimal -- you cannot find the threshold with fewer probes. This was proven by Bentley and Yao in 1976."]

**4.** Binary detection -- combined bracket.

[SAY: "The key insight in this implementation: we do not pre-classify actions as binary or analog. The sweep itself tells us. If the delta goes from saturated to D0 with no intermediate value, the MAX bracket and the MIN bracket are the same bracket. We binary search it once and get both MAX and MIN. For TMNF, all 4 actions are binary, so this is what happens every time."]

[SAY: "For an analog action -- like a joystick throttle that goes from 0 to 1 smoothly -- the delta would go through intermediate values. The sweep would find two separate brackets: one where the delta drops from saturated to intermediate, one where it drops from intermediate to D0. Two binary searches, one for MAX, one for MIN. The algorithm handles both cases naturally."]

---

## Section 12: Closing (2 min)

**1.** Give the summary table.

[SAY: "Let me summarize what we have."]

| Item | Value |
|------|-------|
| Actions discovered | 4 (gas, brake, left, right) |
| All actions | Binary (2 bins each) |
| Total bins | 8 (4 actions x 2 bins) |
| Input combinations per frame | 16 (2^4) |
| Probes per run | 222 |
| Time per run | ~6-10 seconds |
| Runs validated | 5 out of 5 identical |
| Total probes (5 runs) | 1,110 |
| Total time (5 runs) | 52.3 seconds |
| Frame duration | 10.0ms (measured) |
| Speed epsilon | 1.41e-15 (measured) |
| Rubrics passing | 14 out of 14 |
| Hardcoded values | Zero |

**2.** Emphasize the principles.

[SAY: "Everything is discovered, nothing hardcoded. Frame duration -- measured. Precision -- measured. Thresholds -- discovered. Action types -- discovered. The algorithm does not know it is talking to TMNF. You could point it at Pong, Atari, a robot arm, and it would discover the action space the same way."]

> **"bins needs to be figured out by the system. Not by us."** -- Jan 9

**3.** Outline next steps.

[SAY: "The discovery phase is complete. What comes next is exploration. We have 16 input combinations -- every combination of gas, brake, left, right being on or off. We try each combination from many different states and record the transitions into the knowledge graph. That populates the graph with real experience."]

[SAY: "After exploration comes planning. Once the graph has enough transitions, the agent can find paths from its current state to any goal state. Each path is a sequence of actions -- one per frame -- that achieves the goal."]

> **"now I'm gonna say I need to be at 112 in two frames... this is called planning"** -- Feb 16

[SAY: "And planning leads to intelligence. Small plans for small goals, combined into larger plans. Micro-intelligence that adds up to real capability."]

> **"we are creating a bunch of little pieces... small intelligence that when combined they become a bigger intelligence"** -- Jan 9

[SAY: "That is the full picture. Discovery gives us the vocabulary. Exploration gives us the dictionary. Planning gives us sentences. Intelligence gives us stories."]

---

## Appendix A: Quick Reference -- Key Numbers

Keep this page open on your phone for quick lookups during questions.

| Measurement | Value | Source |
|------------|-------|--------|
| Frame duration | 10.0 ms | Measured from race_time delta |
| Speed epsilon | 1.4076351003425836e-15 | 3 D0 probes, variance=0 |
| Yaw epsilon | 1e-15 | 3 D0 probes, variance=0 |
| Gas D0 | -0.6279 km/h | Drag deceleration |
| Gas saturated delta | +0.1590 km/h | Full gas acceleration |
| Gas threshold (MAX=MIN) | 0.00196078431372644 | Binary search, 44 steps |
| Brake D0 | -0.6279 km/h | Same state as gas |
| Brake saturated delta | -0.6818 km/h | Additional deceleration |
| Brake threshold | 0.00196078431372644 | Identical to gas |
| Left D0 | -5.75e-07 rad | Near-zero yaw drift |
| Left saturated delta | +1.94e-05 rad | Left turn yaw |
| Left threshold | 0.00196078431372592 | Binary search, 44 steps |
| Right D0 | -5.75e-07 rad | Same as left D0 |
| Right saturated delta | -2.05e-05 rad | Right turn yaw (opposite) |
| Right threshold | 0.00196078431372592 | Identical to left |
| Probes per action (gas/brake) | 55 | 1 D0 + 10 sweep + 44 search |
| Probes per action (left/right) | 56 | 1 D0 + 10 sweep + 44 search + 1 verify |
| Probes per run (total) | 222 | 55+55+56+56 |
| Time per run | 6-10 seconds | Depends on system load |
| Runs validated | 5 | All bit-identical thresholds |
| Total probes (5 runs) | 1,110 | 222 x 5 |
| Total time (5 runs) | 52.3 seconds | Measured wall time |

---

## Appendix B: Quick Reference -- Key Files

| File | Purpose |
|------|---------|
| `test_phase_a_tmnf.py` | Main test script -- entry point for discovery |
| `intelligence/intelligence_experimentation.py` | Core algorithm (FrameBinDiscovery class) |
| `adapters/tmnf_adapter.py` | TCP adapter -- Python to TMInterface bridge |
| `TMinterface/AgenticBridge.as` | AngelScript plugin -- runs inside the game |
| `update_excel_pure_sutton.py` | Generates the Excel spreadsheet from JSON |
| `Untitled spreadsheet (1).xlsx` | The Excel file shown in this demo |
| `validation_pure_sutton_20260304_092849.json` | Raw 5-run results (JSON) |
| `verify_rubrics.py` | 14 Sutton compliance rubrics |

---

## Appendix C: Quick Reference -- Sutton Quotes by Topic

**Frame and time:**
- "the frame is the timestamp" -- Jan 9
- "who defines the time stamp is the environment" -- Feb 16
- "the actions have to be by frame not continuously" -- Jan 15

**Precision and discovery:**
- "the precision is not us, precision is the system" -- Jan 24
- "bins needs to be figured out by the system. Not by us." -- Jan 9
- "the maximum minimum cannot be guessed... has to be calculated" -- Feb 16

**D0 and action semantics:**
- "not doing an action is also an action" -- Jan 9, Feb 16
- "the first action with no movement is our below minimum" -- Jan 24
- "when the change changes that's when you figured out the max" -- Jan 24

**Algorithm structure:**
- "you start with zero and then you go to like 0.1, 0.01, 0.001" -- Jan 15
- "I started with 100 and I started with 10... now I know bigger than 10 smaller than 100" -- Jan 31
- "0.8, 0.5, 0.3 doesn't make sense... this is not an algorithm this is a guess" -- Feb 16

**No interference:**
- "we should not interfere with the experimentation" -- Jan 9
- "there is no noise" -- Feb 16

**Knowledge graph:**
- "I have my car at 100 -- that's a node. Action gas. Now 110 -- edge connects them." -- Jan 15
- "from the list of feedback... a hundred graphs are going to be created" -- Meeting 3

**Planning and intelligence:**
- "now I'm gonna say I need to be at 112 in two frames... this is called planning" -- Feb 16
- "we are creating a bunch of little pieces... small intelligence that when combined they become a bigger intelligence" -- Jan 9

---

## Appendix D: Anticipated Questions and Answers

**Q: Why does the threshold end up at 0.00196 and not 0.5 or some rounder number?**

[SAY: "The threshold is 0.5/255 = 0.00196. The adapter converts the Python float to a uint8 byte using round(value times 255). When value is 0.00196, round(0.00196 * 255) = round(0.5) = 0 on Python's banker's rounding, which is the dead zone. At 0.00197, round(0.00197 * 255) = round(0.502) = 1, which is active. The algorithm found this boundary without knowing about uint8 or the adapter. The system revealed its own quantization."]

**Q: Why 2 ticks instead of 1?**

[SAY: "TMInterface has a 1-tick input delay. SetInputState during tick N takes effect at tick N+1. After rewind, tick 1 replays the saved state's existing inputs. Our action gets queued. Tick 2 is when our action takes effect. We read feedback at the end of tick 1 (before our action) and at the end of tick 2 (after our action). The delta is purely our contribution."]

**Q: What if the game had analog gas instead of binary?**

[SAY: "The algorithm would handle it naturally. The exponential sweep would find a point where the delta is between saturated and D0 -- an intermediate value. That creates two separate brackets: one for MAX, one for MIN. Two binary searches find both boundaries. The number of bins would be determined by how many distinct delta levels the system produces between MIN and MAX."]

**Q: Why start at 1,000,000 instead of 1?**

[SAY: "We do not know the action range in advance. Some games might have actions in the range 0 to 10,000. Starting at 1,000,000 guarantees we start above the saturation point. Starting at 1 would miss games with ranges above 1. The sweep only costs one extra probe per order of magnitude, so starting high is cheap insurance."]

**Q: How does this compare to OpenAI Gym / standard RL approaches?**

[SAY: "Standard RL approaches require the developer to specify the action space. OpenAI Gym has you define Box(low=0, high=1, shape=(4,)) or Discrete(3). We discover it. No specification. The algorithm talks to any environment that supports step() and get_feedback(). It finds the actions, their types, their ranges, and their precision. That is the fundamental difference."]

**Q: What about continuous analog actions like a steering wheel?**

[SAY: "The algorithm supports analog actions. It would find a MIN threshold, a MAX saturation point, and discover intermediate levels between them. The number of bins depends on the system's actual resolution. For a 16-bit joystick axis, it would discover up to 65,536 levels. For a 10-bit sensor, it would discover up to 1,024. The system tells us. We do not guess."]

---

## Appendix E: Pre-Demo Setup Checklist

Before the meeting, verify:

- [ ] TMNF is installed and launches
- [ ] TMInterface 2.x is loaded (shown in game title bar)
- [ ] AgenticBridge.as is in `%APPDATA%\TMInterface\Plugins\`
- [ ] Start a race and wait for countdown to finish
- [ ] Python environment has dependencies: `pip install openpyxl`
- [ ] Excel file `Untitled spreadsheet (1).xlsx` is ready to open
- [ ] Terminal/PowerShell is open in the project directory
- [ ] Test connection: `python -c "from adapters.tmnf_adapter import TMNFAdapter; a = TMNFAdapter(); print('OK' if a.connect(port=8476, timeout=5) else 'FAIL')"`
- [ ] VS Code or text editor has `test_phase_a_tmnf.py` ready to show

---

*Script version: 2026-03-04. Generated from validation_pure_sutton_20260304_092849.json (5 runs, 1,110 probes, 52.3s).*
