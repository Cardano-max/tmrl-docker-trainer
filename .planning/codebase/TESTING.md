# Testing Patterns

**Analysis Date:** 2026-02-16

## Test Framework

**Runner:**
- Python's built-in `unittest` and manual test runners (no pytest/nose detected)
- Tests typically run via direct module execution or import

**Assertion Library:**
- Python's built-in `assert` statements
- Manual validation with `print()` output
- No external assertion framework (pytest, nose)

**Run Commands:**
```bash
# Direct test execution
python tests/test_delta_discovery.py

# Demo test harness
python demo_test_harness.py

# Individual test discovery script
python discover_v1.py
python discover_v2.py
python discover_v3.py
```

## Test File Organization

**Location:**
- Tests co-located in `tests/` directory at project root
- Test files paired with functionality (e.g., `test_delta_discovery.py` for experimentation algorithm)
- Demo/integration tests in root: `demo_test_harness.py`, `test_sutton_live.py`
- Live validation tests: `tests/test_knowledge_live.py`, `tests/test_live_delta_discovery.py`

**Naming:**
- Test files: `test_*.py` or `*_test.py`
- Test functions: `test_*()` or `TEST-*` (in harness registry)
- Mock classes: `Mock*Environment` or similar
- Test data: `*_data.py` or inline mock objects

**Structure:**
```
tests/
├── micro_test_1.py          # Focused unit tests
├── micro_test_2_brake.py    # Specific scenario tests
├── stress_test_falkordb.py  # Database stress tests
├── test_delta_discovery.py  # Algorithm validation
├── test_knowledge_live.py   # Live knowledge graph tests
└── test_live_delta_discovery.py
```

## Test Structure

**Suite Organization:**
From `tests/test_delta_discovery.py`:
```python
# Mock environments at top
class MockPongEnvironment:
    def __init__(self, max_speed=1.0, min_effective=0.1, precision=6):
        self.position = 5.0
        # ...

# Individual test functions
def test_single_pass_pong():
    """REQ-C04: Single descending pass finds both max and min."""
    print("\n" + "="*60)
    print("TEST 1: Single Descending Pass (Pong)")
    print("="*60)
    # ...
    assert a_max is not None
    print("  [PASS]")
    return True

# Test registry pattern
def run_all_tests():
    tests = [
        ("Single Pass (Pong)", test_single_pass_pong),
        ("Bins = k*min", test_bins_k_times_min),
        # ...
    ]
    for name, test_fn in tests:
        try:
            if test_fn():
                passed += 1
```

**Patterns:**
- No setup/teardown methods; local state initialization in tests
- Print-based output with ASCII separators for readability
- Return boolean from test functions (True = pass, False = fail)
- Exception handling wraps entire test execution
- Track pass/fail count and report at end

## Mocking

**Framework:** Manual mock objects (no `unittest.mock` or `pytest.mock`)

**Patterns:**
```python
# Mock environment class (full implementation)
class MockTrackManiaEnvironment:
    """TrackMania-like: speed 0-500, gas/brake 0-1, max accel 2.5/frame"""
    def __init__(self):
        self.speed = 0.0
        self.position = 0.0
        self.precision = 7

    def get_feedbacks(self):
        return {
            'speed': round(self.speed, self.precision),
            'position': round(self.position, self.precision),
        }

    def send_action(self, action):
        gas = action.get('gas', 0.0)
        brake = action.get('brake', 0.0)
        # Simulate physics...

# Dependency injection in tests
env = MockTrackManiaEnvironment()
coordinator = ExperimentationCoordinator(
    actions_config=actions_config,
    send_action_fn=env.send_action,      # Mock injected
    get_feedbacks_fn=env.get_feedbacks,  # Mock injected
    wait_fn=lambda t: None,               # Mock lambda
    reset_fn=env.reset                    # Mock method
)
```

**What to Mock:**
- Environment interactions: `send_action_fn`, `get_feedbacks_fn`, `wait_fn`, `reset_fn`
- External database (FalkorDB) is NOT mocked - tests expect real database
- Physics/dynamics - mock environment classes replicate system behavior
- Time delays - replaced with lambda `lambda t: None`

**What NOT to Mock:**
- Real algorithm implementation (test the actual code)
- Database operations (tests validate against real FalkorDB instance)
- State managers and knowledge graphs (tested against real implementations)
- Discretization logic (core system being tested)

## Fixtures and Factories

**Test Data:**
```python
# Mock environment as fixture/factory
class MockPongEnvironment:
    @staticmethod
    def create_with_defaults():
        return MockPongEnvironment(max_speed=1.0, min_effective=0.1)

# Inline data structures
actions_config = {
    'gas': {'type': 'continuous', 'range': [0.0, 1.0]},
    'brake': {'type': 'continuous', 'range': [0.0, 1.0]},
}

# Test probe data
probes = [
    ProbeResult(
        action_value=val,
        delta_state=delta,
        feedback_before=fb_before,
        feedback_after=fb_after,
        frame_duration_s=0.05
    )
    for val in test_values
]
```

**Location:**
- Mock environment classes defined at top of test file
- Configuration dictionaries defined per test or in setup
- Dataclass instances created inline with real values
- No separate fixtures directory

## Coverage

**Requirements:** Not explicitly enforced (no .coveragerc found)

**View Coverage:** Not automated in codebase

**Strategy:**
- Experimentation algorithm tested exhaustively: `test_delta_discovery.py` covers 11 test cases
- System integration tested with `demo_test_harness.py` (live TrackMania environment)
- Live validation via `test_sutton_live.py` (requires real environment connection)
- Mock environments validate algorithm across different system dynamics

## Test Types

**Unit Tests:**
- Scope: Individual components (ActionDiscretizer, FeedbackDiscretizer, FrameBinDiscovery)
- Approach: Create mock environments, execute single operations, assert outcomes
- Example: `test_single_pass_pong()` tests algorithm on Pong mock
- Fast execution, no external dependencies needed

**Integration Tests:**
- Scope: Full experimentation flow (coordinator + intelligence + mock environment)
- Approach: Run complete bin discovery algorithm, validate all phases
- Example: `test_full_coordinator_pong()` and `test_full_coordinator_trackmania()`
- Tests interaction between ExperimentationCoordinator, ExperimentationIntelligence, mocks

**Live Tests:**
- Scope: Real environment interaction (requires TrackMania + TMRL + FalkorDB)
- Approach: `demo_test_harness.py` connects to actual game, records transitions
- Folder: `tests/test_*_live.py` files
- Documentation: `docs/DEMO_RUNBOOK.md` describes setup
- NO mocks - validates against real physics and real database

**E2E Tests:**
- Not explicitly structured but enabled by test harness registry pattern
- `TestRegistry` class allows running named tests from console
- Could plug into CI/CD pipeline

## Common Patterns

**Async Testing:**
Not used (no async code in codebase)

**Error Testing:**
```python
# Test exception raising
def test_emergency_fallback():
    intel = ExperimentationIntelligence(actions_config)
    try:
        intel.skip_experimentation_with_defaults()
        print("  [FAIL] Should have raised error")
        return False
    except RuntimeError:
        print("  Correctly rejected without flag")
    return True
```

**Parametrized Testing (Custom):**
```python
# Manual loop over test cases instead of pytest.mark.parametrize
def run_all_tests():
    tests = [
        ("Single Pass (Pong)", test_single_pass_pong),
        ("Bins = k*min", test_bins_k_times_min),
        ("Proportionality", test_proportionality_verification),
    ]

    passed = 0
    failed = 0
    for name, test_fn in tests:
        try:
            if test_fn():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            traceback.print_exc()

    print(f"RESULTS: {passed}/{passed + failed} passed")
```

**Test Output Format:**
- ASCII headers with `"="*60` for sections
- Test names printed at start: `print("TEST 1: Single Descending Pass (Pong)")`
- Progress output during execution: `print(f"  a={val:8.4f} -> delta={delta:.6f}")`
- Results at end: `print("  [PASS]")` or `print("  [FAIL]")`
- Summary line: `print(f"RESULTS: {passed}/{passed + failed} passed, {failed} failed")`

**Demo Harness Pattern:**
From `demo_test_harness.py` - test registry with decorator:
```python
class TestRegistry:
    def register(self, name: str, description: str):
        """Decorator to register a test function"""
        def decorator(func: Callable):
            self._tests[name] = func
            self._descriptions[name] = description
            return func
        return decorator

registry = TestRegistry()

@registry.register("per_frame_execution", "Verify per-frame action execution")
def test_per_frame_execution(harness: DemoTestHarness) -> TestResult:
    # Test implementation
    return TestResult(test_name="per_frame_execution", passed=True, ...)
```

**Assertion Style:**
- Direct `assert` statements with optional message:
  ```python
  assert a_max is not None, "Max should be discovered"
  assert abs(a_min - 0.1) < 0.01, f"Min should be ~0.1, got {a_min}"
  ```
- Comparison assertions for ranges:
  ```python
  assert bins[0].label == 'DEAD_ZONE', "First bin should be dead-zone"
  assert len(bins) == 11, f"Should be 11 bins, got {len(bins)}"
  ```

---

*Testing analysis: 2026-02-16*
