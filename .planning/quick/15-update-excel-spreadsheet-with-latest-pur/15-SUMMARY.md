# Quick Task 15: Update Excel with Pure Sutton 5-Run Results

## What Was Done

Updated `Untitled spreadsheet (1).xlsx` with latest results from Pure Sutton single-algorithm discovery (quick-14).

## Sheets (9 total)

| Sheet | Content |
|-------|---------|
| Frame Duration | How frame duration is measured (10ms, from race_time delta) |
| System Precision | How epsilon is measured (speed/yaw variance, deterministic=True) |
| Run 1-5 | Full probe-level data per run (55-56 probes per action, color-coded) |
| Summary | Cross-run stability table + key findings |
| Algorithm | Step-by-step algorithm explanation with real numbers |

## Key Numbers

- **Gas:** MAX = MIN = 0.001960784314, nature=binary, 55 probes
- **Brake:** MAX = MIN = 0.001960784314, nature=binary, 55 probes
- **Left:** MAX = MIN = 0.001960784314, nature=binary, 56 probes
- **Right:** MAX = MIN = 0.001960784314, nature=binary, 56 probes
- **All 5 runs:** BIT-IDENTICAL (deterministic rewind)

## Color Coding in Run Sheets

- Green = D0 probe (action=0)
- Yellow = Exponential sweep (1e6 down to 0.001)
- Orange = Combined bracket found (saturated -> D0 directly)
- Blue = Binary search (narrowing to exact threshold)

## Data Source

`validation_pure_sutton_20260304_092849.json`

## Commits

- `54cc04c`: feat(quick-15): update Excel with Pure Sutton 5-run results
