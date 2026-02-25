"""
Offline tests for precision discovery and precision-based bin count.

Tests:
  1. measure_precision() binary search finds correct precision
  2. build_bins(precision=...) computes correct bin count
  3. Binary inputs skip precision (returns None)
  4. Bin count capped to [2, 100]
  5. Backward compat: build_bins() with no precision uses DEFAULT_NUM_BINS
  6. num_bins overrides precision when both provided
  7. Edge cases: precision=0, precision > range, very small precision

Run:
  python -m pytest tests/test_precision_discovery.py -v
  OR
  python tests/test_precision_discovery.py
"""

import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intelligence.intelligence_experimentation import (
    FrameBinDiscovery,
    ProbeResult,
)


# ═══════════════════════════════════════════════════════════════════
# MOCK PROBE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

def make_linear_probe_fn(slope: float = 1.0):
    """
    Mock probe where delta = slope * action_value.
    Linear relationship: different actions always produce different deltas.
    Precision will converge to search_precision (smallest step distinguishable).
    """
    def probe_fn(value: float) -> ProbeResult:
        delta = slope * value
        return ProbeResult(
            action_value=value,
            delta_state=delta,
            feedback_before={'speed': 100.0},
            feedback_after={'speed': 100.0 + delta},
            frame_duration_s=0.01,
            valid=True,
        )
    return probe_fn


def make_step_probe_fn(step_size: float = 0.05):
    """
    Mock probe where delta = floor(value / step_size) * step_size.
    Simulates a system with discrete resolution: values within the same
    step produce identical deltas.
    Precision should converge to approximately step_size.
    """
    def probe_fn(value: float) -> ProbeResult:
        delta = math.floor(value / step_size) * step_size
        return ProbeResult(
            action_value=value,
            delta_state=delta,
            feedback_before={'speed': 100.0},
            feedback_after={'speed': 100.0 + delta},
            frame_duration_s=0.01,
            valid=True,
        )
    return probe_fn


def make_binary_probe_fn(threshold: float = 0.001):
    """
    Mock probe for binary input: delta=0 below threshold, delta=1.0 above.
    """
    def probe_fn(value: float) -> ProbeResult:
        delta = 1.0 if value > threshold else 0.0
        return ProbeResult(
            action_value=value,
            delta_state=delta,
            feedback_before={'speed': 100.0},
            feedback_after={'speed': 100.0 + delta},
            frame_duration_s=0.01,
            valid=True,
        )
    return probe_fn


# ═══════════════════════════════════════════════════════════════════
# TEST: measure_precision()
# ═══════════════════════════════════════════════════════════════════

def test_measure_precision_linear():
    """Linear system: precision should converge to search_precision."""
    disc = FrameBinDiscovery('steering', (0.0, 1.0),
                              search_precision=0.001, noise_epsilon=1e-10)
    disc.a_min = 0.01
    disc.a_max = 0.5

    probe_fn = make_linear_probe_fn(slope=2.0)
    precision = disc.measure_precision(probe_fn)

    assert precision is not None, "Precision should not be None for analog input"
    # With linear probe (every delta different), precision converges to search_precision
    # The binary search narrows until a_high - a_low < search_precision
    # So precision = a_high - a_min ~= a_min + search_precision - a_min = search_precision
    assert precision < 0.01, f"Precision should be small, got {precision}"
    print(f"  PASS: Linear system precision = {precision:.6f}")


def test_measure_precision_step():
    """Step system: precision should approximate the step size."""
    step_size = 0.05
    disc = FrameBinDiscovery('steering', (0.0, 1.0),
                              search_precision=0.001, noise_epsilon=1e-10)
    disc.a_min = 0.01
    disc.a_max = 0.5

    probe_fn = make_step_probe_fn(step_size=step_size)
    precision = disc.measure_precision(probe_fn)

    assert precision is not None, "Precision should not be None for step system"
    # Precision should be close to step_size (within search_precision tolerance)
    assert abs(precision - step_size) < step_size * 0.5, \
        f"Precision {precision:.6f} should be close to step_size {step_size}"
    print(f"  PASS: Step system precision = {precision:.6f} (step_size={step_size})")


def test_measure_precision_binary_returns_none():
    """Binary input (MIN ~= MAX): measure_precision should return None."""
    disc = FrameBinDiscovery('gas', (0.0, 1.0),
                              search_precision=0.001, noise_epsilon=0.01)
    disc.a_min = 0.001
    disc.a_max = 0.005  # Very close to a_min -> binary

    probe_fn = make_binary_probe_fn()
    precision = disc.measure_precision(probe_fn)

    assert precision is None, f"Binary input should return None, got {precision}"
    print(f"  PASS: Binary input returns None")


def test_measure_precision_no_min_max():
    """No MIN/MAX discovered: returns None."""
    disc = FrameBinDiscovery('gas', (0.0, 1.0))
    disc.a_min = None
    disc.a_max = None

    probe_fn = make_linear_probe_fn()
    precision = disc.measure_precision(probe_fn)

    assert precision is None, f"No MIN/MAX should return None, got {precision}"
    print(f"  PASS: No MIN/MAX returns None")


# ═══════════════════════════════════════════════════════════════════
# TEST: build_bins(precision=...)
# ═══════════════════════════════════════════════════════════════════

def test_build_bins_with_precision():
    """Precision-based bin count: n = ceil(range / precision)."""
    disc = FrameBinDiscovery('steering', (0.0, 1.0), search_precision=0.001)
    disc.a_min = 0.01
    disc.a_max = 0.50
    disc.delta_0 = 0.0
    disc.delta_max = 5.0

    # range = 0.50 - 0.01 = 0.49, precision = 0.05
    # n = ceil(0.49 / 0.05) = ceil(9.8) = 10
    bins = disc.build_bins(precision=0.05)

    # bins[0] = DEAD_ZONE, bins[1..n] = active bins
    active_bins = [b for b in bins if b.label != 'DEAD_ZONE']
    assert len(active_bins) == 10, f"Expected 10 active bins, got {len(active_bins)}"
    print(f"  PASS: precision=0.05 -> {len(active_bins)} active bins (range=0.49)")


def test_build_bins_precision_cap_low():
    """Very large precision -> capped to minimum 2 bins."""
    disc = FrameBinDiscovery('steering', (0.0, 1.0), search_precision=0.001)
    disc.a_min = 0.01
    disc.a_max = 0.50
    disc.delta_0 = 0.0
    disc.delta_max = 5.0

    # range = 0.49, precision = 0.49 -> n = ceil(1.0) = 1 -> capped to 2
    bins = disc.build_bins(precision=0.49)
    active_bins = [b for b in bins if b.label != 'DEAD_ZONE']
    assert len(active_bins) == 2, f"Expected 2 active bins (min cap), got {len(active_bins)}"
    print(f"  PASS: precision=0.49 -> 2 bins (capped to minimum)")


def test_build_bins_precision_cap_high():
    """Very small precision -> capped to maximum 100 bins."""
    disc = FrameBinDiscovery('steering', (0.0, 1.0), search_precision=0.001)
    disc.a_min = 0.01
    disc.a_max = 0.50
    disc.delta_0 = 0.0
    disc.delta_max = 5.0

    # range = 0.49, precision = 0.001 -> n = ceil(490) = 490 -> capped to 100
    bins = disc.build_bins(precision=0.001)
    active_bins = [b for b in bins if b.label != 'DEAD_ZONE']
    assert len(active_bins) == 100, f"Expected 100 active bins (max cap), got {len(active_bins)}"
    print(f"  PASS: precision=0.001 -> 100 bins (capped to maximum)")


def test_build_bins_backward_compat():
    """No precision arg: falls back to DEFAULT_NUM_BINS = 10."""
    disc = FrameBinDiscovery('steering', (0.0, 1.0), search_precision=0.001)
    disc.a_min = 0.01
    disc.a_max = 0.50
    disc.delta_0 = 0.0
    disc.delta_max = 5.0

    bins = disc.build_bins()
    active_bins = [b for b in bins if b.label != 'DEAD_ZONE']
    assert len(active_bins) == disc.DEFAULT_NUM_BINS, \
        f"Expected {disc.DEFAULT_NUM_BINS} active bins, got {len(active_bins)}"
    print(f"  PASS: No precision -> {disc.DEFAULT_NUM_BINS} bins (default)")


def test_build_bins_num_bins_overrides_precision():
    """Explicit num_bins should override precision."""
    disc = FrameBinDiscovery('steering', (0.0, 1.0), search_precision=0.001)
    disc.a_min = 0.01
    disc.a_max = 0.50
    disc.delta_0 = 0.0
    disc.delta_max = 5.0

    bins = disc.build_bins(num_bins=5, precision=0.05)
    active_bins = [b for b in bins if b.label != 'DEAD_ZONE']
    assert len(active_bins) == 5, f"Expected 5 active bins (num_bins override), got {len(active_bins)}"
    print(f"  PASS: num_bins=5 overrides precision=0.05")


def test_build_bins_binary_input():
    """Binary input (MIN ~= MAX) should produce 2 bins regardless of precision."""
    disc = FrameBinDiscovery('gas', (0.0, 1.0), search_precision=0.001)
    disc.a_min = 0.001
    disc.a_max = 0.005  # Range < search_precision * 10 -> binary
    disc.delta_0 = 0.0
    disc.delta_max = 1.0

    bins = disc.build_bins(precision=0.001)
    assert len(bins) == 2, f"Expected 2 bins for binary input, got {len(bins)}"
    assert bins[0].label == 'DEAD_ZONE'
    assert bins[1].label == 'ON'
    print(f"  PASS: Binary input -> 2 bins (DEAD_ZONE + ON)")


def test_build_bins_precision_none_passthrough():
    """precision=None should behave same as no arg (default bins)."""
    disc = FrameBinDiscovery('steering', (0.0, 1.0), search_precision=0.001)
    disc.a_min = 0.01
    disc.a_max = 0.50
    disc.delta_0 = 0.0
    disc.delta_max = 5.0

    bins = disc.build_bins(precision=None)
    active_bins = [b for b in bins if b.label != 'DEAD_ZONE']
    assert len(active_bins) == disc.DEFAULT_NUM_BINS, \
        f"Expected {disc.DEFAULT_NUM_BINS}, got {len(active_bins)}"
    print(f"  PASS: precision=None -> default bins")


# ═══════════════════════════════════════════════════════════════════
# TEST: End-to-end precision -> bins
# ═══════════════════════════════════════════════════════════════════

def test_end_to_end_precision_to_bins():
    """Full flow: measure_precision -> build_bins(precision=...)."""
    step_size = 0.05
    disc = FrameBinDiscovery('steering', (0.0, 1.0),
                              search_precision=0.001, noise_epsilon=1e-10)
    disc.a_min = 0.01
    disc.a_max = 0.50

    probe_fn = make_step_probe_fn(step_size=step_size)
    precision = disc.measure_precision(probe_fn)
    assert precision is not None

    disc.delta_0 = 0.0
    disc.delta_max = 5.0
    bins = disc.build_bins(precision=precision)

    active_bins = [b for b in bins if b.label != 'DEAD_ZONE']
    expected_n = math.ceil((0.50 - 0.01) / precision)
    expected_n = max(2, min(expected_n, 100))

    assert len(active_bins) == expected_n, \
        f"Expected {expected_n} bins from precision={precision:.6f}, got {len(active_bins)}"
    print(f"  PASS: E2E: precision={precision:.6f} -> {len(active_bins)} active bins")


# ═══════════════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════════════

ALL_TESTS = [
    test_measure_precision_linear,
    test_measure_precision_step,
    test_measure_precision_binary_returns_none,
    test_measure_precision_no_min_max,
    test_build_bins_with_precision,
    test_build_bins_precision_cap_low,
    test_build_bins_precision_cap_high,
    test_build_bins_backward_compat,
    test_build_bins_num_bins_overrides_precision,
    test_build_bins_binary_input,
    test_build_bins_precision_none_passthrough,
    test_end_to_end_precision_to_bins,
]


if __name__ == '__main__':
    print("=" * 70)
    print("  PRECISION DISCOVERY -- Offline Unit Tests")
    print("=" * 70)
    print()

    passed = 0
    failed = 0

    for test_fn in ALL_TESTS:
        name = test_fn.__name__
        try:
            test_fn()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR: {name}: {e}")
            failed += 1

    print()
    print("=" * 70)
    print(f"  RESULTS: {passed}/{passed + failed} passed, {failed} failed")
    print("=" * 70)

    sys.exit(0 if failed == 0 else 1)
