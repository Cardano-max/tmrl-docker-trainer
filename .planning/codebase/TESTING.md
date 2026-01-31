# Testing Patterns

**Analysis Date:** 2026-01-31

## Test Framework

**Runner:**
- No formal test framework detected (pytest, unittest not explicitly configured)
- Tests are standalone Python scripts with manual execution
- Two test categories: Live integration tests and demo harnesses

**Assertion Library:**
- No formal assertion library used
- Manual assertions: `if not condition: return` or logging errors
- Success determined by: data presence, connection success, operation completion

**Run Commands:**
```bash
python test_sutton_live.py           # Sutton-compliant bin discovery
python tests/test_knowledge_live.py  # Knowledge graph live test
python demo_test_harness.py          # Demo validation of all tickets
python tests/live_system_validator.py # Full system validation
```

## Test File Organization

**Location:**
- Dedicated test directory: `tests/` (contains `test_knowledge_live.py`, `live_system_validator.py`, `stress_test_falkordb.py`)
- Root-level test scripts: `test_sutton_live.py`, `demo_test_harness.py`, `demo_meeting_requirements.py`
- Live validation scripts integrated with source

**Naming:**
- Prefix with `test_` or `live_` for discovery: `test_knowledge_live.py`, `test_sutton_live.py`
- Demo/validation names are descriptive: `demo_test_harness.py`, `live_system_validator.py`
- Stress tests: `stress_test_falkordb.py`

**Structure:**
```
tests/
├── test_knowledge_live.py          # Knowledge graph with FalkorDB
├── live_system_validator.py        # System-wide validation
└── stress_test_falkordb.py         # Database stress test

Root:
├── test_sutton_live.py             # Order discovery algorithm
├── demo_test_harness.py            # Ticket validation demo
└── demo_meeting_requirements.py    # Requirements verification
```

## Test Structure

**Suite Organization:**
```python
# test_sutton_live.py pattern
def main():
    print("\n" + "=" * 60)
    print("SUTTON-COMPLIANT BIN DISCOVERY (BASELINE-SUBTRACTED)")
    print("=" * 60)

    # Phase 1: Connection
    print("\n" + "=" * 60)
    print("PHASE 1: CONNECTION")
    print("=" * 60)
    # ... execution code

    # Phase 2: Warm up car
    # ...

    # Phase 3: Discovery
    # ...

    # Phase 4: Results
    # ...

    return 0

if __name__ == '__main__':
    sys.exit(main())
```

**Patterns:**
- Phase-based structure with clear section markers
- Visual progress output (prints and separators)
- Early failure return (check conditions, return on failure)
- Final validation and summary
- Exit code return (0 for success, non-zero for failure)

**Example from `test_sutton_live.py`:**
```python
def main():
    print("\n" + "=" * 60)
    print("PHASE 1: CONNECTION")
    print("=" * 60)

    from adapters.tmrl_live_adapter import TMRLLiveAdapter

    adapter = TMRLLiveAdapter(host='127.0.0.1', port=9000)

    print(f"\n[1] Connecting to TrackMania...")
    if not adapter.connect(timeout=5.0):
        print("  [FAIL] Could not connect")
        return 1  # Early return on failure

    print("  [OK] Connected")

    # ... more phases

    return 0
```

## Test Registry Pattern

**From `demo_test_harness.py`:**
```python
class TestRegistry:
    """Registry of all available tests using registry pattern"""

    def __init__(self):
        self._tests: Dict[str, Callable] = {}
        self._descriptions: Dict[str, str] = {}

    def register(self, name: str, description: str):
        """Decorator to register a test function"""
        def decorator(func: Callable):
            self._tests[name] = func
            self._descriptions[name] = description
            return func
        return decorator

    def run_test(self, name: str, harness: 'DemoTestHarness') -> TestResult:
        """Run a test by name"""
        test_func = self._tests.get(name)
        if not test_func:
            return TestResult(
                test_name=name,
                passed=False,
                error=f"Test '{name}' not found"
            )

        start = time.time()
        try:
            result = test_func(harness)
            result.duration = time.time() - start
            return result
        except Exception as e:
            return TestResult(
                test_name=name,
                passed=False,
                error=str(e),
                duration=time.time() - start
            )
```

**Usage:**
```python
# Decorator-based registration
registry = TestRegistry()

@registry.register("knowledge_graph", "Test knowledge graph persistence")
def test_knowledge_graph(harness):
    # Test implementation
    return TestResult(test_name="knowledge_graph", passed=True)

# Running tests
result = registry.run_test("knowledge_graph", harness)
```

## Mocking

**Framework:** No mocking library (unittest.mock, pytest-mock not used)

**Patterns:**
- **NO MOCKS** - Codebase uses real services throughout
- Real TrackMania connection (TCP socket to port 9000)
- Real FalkorDB database (Docker container)
- Real vgamepad controller (ViGEmBus driver)

**Documented requirement from `demo_test_harness.py`:**
```python
"""
DEMO TEST HARNESS - Live Validation of All Tickets

Console-based test harness for validating:
- Ticket-1: Per-frame action execution
- Ticket-2: Experimentation module (min/max order discovery)
- Ticket-3: FalkorDB knowledge graph (one node per frame)

NO MOCKS. NO SIMULATED DATA. ALL REAL.

Requirements:
    - TrackMania 2020 running with OpenPlanet
    - TMRL_GrabData plugin active (TCP port 9000)
    - FalkorDB running (docker start falkordb)
    - ViGEmBus driver installed (for vgamepad)
    - Car on track ready to drive
"""
```

**Connection mocking pattern (fallback approach in `tests/test_knowledge_live.py`):**
```python
# Try multiple connection methods with fallback
def try_socket_connection():
    """Try TCP socket connection"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect(('127.0.0.1', 9000))
        # ... use real connection
        return connection_object
    except Exception as e:
        print(f"[SKIP] TCP socket (port 9000): {e}")
    return None

# Fallback to HTTP if socket fails
connection = try_socket_connection()
if connection is None:
    connection = try_http_connection(8080)
if connection is None:
    connection = try_http_connection(29201)
```

**What to Mock:** Nothing in this codebase - all tests are integration tests against real systems

**What NOT to Mock:** Everything (real connections preferred for validation of Sutton constraints)

## Fixtures and Factories

**Test Data:**
```python
# Pattern from test_sutton_live.py
discovery = SuttonCompliantDiscovery(adapter, feedback_name='speed')

# Configure for live testing
discovery.eps_effect = 2.0       # Effect must be > 2 speed/sec to be significant
discovery.snr_threshold = 1.2    # SNR > 1.2 required
discovery.alpha_max = 0.85       # MAX = 85% of full effect
discovery.measure_duration_ms = 200  # Longer measurements for stability
discovery.measure_reps = 4       # More reps for reliability
```

**Test Result Dataclass from `demo_test_harness.py`:**
```python
@dataclass
class TestResult:
    """Result of a single test"""
    test_name: str
    passed: bool
    evidence: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
```

**Location:**
- No dedicated fixtures directory
- Test data embedded in test scripts
- Configuration in-script via constructor or method calls

## Coverage

**Requirements:** None enforced (no pytest.ini, setup.cfg found)

**View Coverage:** Not applicable (no coverage tool configured)

**Observation:** Tests focus on end-to-end validation rather than unit test coverage metrics

## Test Types

**Unit Tests:**
- Scope: Individual components in isolation (rarely used)
- Approach: Manual instantiation and method calls
- Example: `demo_test_harness.py` has individual test functions for each ticket

**Integration Tests:**
- Scope: Component interactions with real services
- Approach: Live connection tests with actual TrackMania and FalkorDB
- Examples:
  - `test_sutton_live.py`: Tests discovery algorithm with live TrackMania
  - `test_knowledge_live.py`: Tests knowledge recording with FalkorDB
  - `live_system_validator.py`: Tests all modules together

**E2E Tests:**
- Framework: Manual scripts (not automated test framework)
- Examples:
  - `demo_test_harness.py`: Validates all tickets end-to-end
  - `demo_meeting_requirements.py`: Verifies meeting requirements
  - `live_system_validator.py`: Full system validation

**Performance/Stress Tests:**
- `stress_test_falkordb.py`: Database performance under load

## Common Patterns

**Connection Testing:**
```python
# From test_knowledge_live.py - Connection with fallback
METHODS = {
    'socket': {'port': 9000, 'type': 'tcp'},      # TMRL_GrabData
    'http_8080': {'port': 8080, 'type': 'http'},  # GrabData HTTP
    'http_29201': {'port': 29201, 'type': 'http'} # OpenPlanet API
}

connection = try_socket_connection()
if connection is None:
    connection = try_http_connection(8080)
if connection is None:
    connection = try_http_connection(29201)
if connection is None:
    print("[FAILED] Cannot connect to TrackMania")
    return
```

**Async/Real-time Testing:**
```python
# From test_sutton_live.py - Sequential action/observation
print("\n[2] Warm up car...")
for _ in range(150):
    adapter.send_action_dict({'gas': 1.0, 'brake': 0.0, 'steering': 0.0})
    time.sleep(0.02)  # TrackMania runs at ~60fps

fb = adapter.get_feedbacks()
speed = fb.get('speed', 0)
print(f"Speed after warmup: {speed:.1f}")
```

**State Validation:**
```python
# From live_system_validator.py - Persistent connection validation
class LiveConnectionManager:
    def __init__(self):
        self.tm_socket = None
        self.tm_connected = False
        self._recv_thread = None
        self._running = False
        self._observation_queue = Queue(maxsize=100)
        self._last_feedbacks = None
        self._observations_received = 0
        self._errors = 0
```

**Failure Detection Pattern:**
```python
# From test_sutton_live.py
print("[OK] Connected")

# Next test
print(f"\n[3] Verifying telemetry...")
fb = adapter.get_feedbacks()
if 'pos_x' not in fb or 'pos_z' not in fb:
    print("  [WARN] Position data not available - steering discovery may fail")
```

**Evidence Collection:**
```python
# From demo_test_harness.py - Test result structure
@dataclass
class TestResult:
    test_name: str
    passed: bool
    evidence: List[str] = field(default_factory=list)  # Collect evidence
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration: float = 0.0

# Usage in test
result.evidence.append(f"Speed change: {speed_change:+.2f}")
result.data['speed_before'] = speed_before
result.data['speed_after'] = speed_after
```

## Test Execution Model

**Sequential Phases:**
1. **Initialization** - Connect to services, load configuration
2. **Pre-test validation** - Verify preconditions (car on track, data available)
3. **Warmup** - Prime the environment (accelerate car, etc.)
4. **Test execution** - Run the actual test
5. **Results collection** - Gather metrics and observations
6. **Cleanup** - Release controls, close connections
7. **Summary** - Print results and status

**Early exit on failure:**
```python
if not adapter.connect(timeout=5.0):
    print("  [FAIL] Could not connect")
    return 1  # Exit immediately on critical failure
```

**Progress reporting:**
```python
for _ in range(150):
    adapter.send_action_dict({'gas': 1.0, ...})
    time.sleep(0.02)

print(f"  Speed after warmup: {speed:.1f}")  # Verify progress
```

## Test Configuration

**Configuration approach:**
- Test-specific settings passed directly to components
- Example from `test_sutton_live.py`:
```python
discovery = SuttonCompliantDiscovery(adapter, feedback_name='speed')
discovery.eps_effect = 2.0       # Tunable thresholds
discovery.snr_threshold = 1.2
discovery.alpha_max = 0.85
discovery.measure_duration_ms = 200
discovery.measure_reps = 4
```

**Requirements documentation:**
Every test file documents its requirements in the module docstring:
```python
"""
LIVE TEST: Sutton-Compliant Bin Discovery

REQUIREMENTS:
- TrackMania running with TMRL_GrabData plugin
- Car on track (can be moving - NO STATE RESET)
- vgamepad/ViGEmBus installed
"""
```

**No test configuration files:**
- No pytest.ini, setup.cfg, tox.ini found
- Tests are self-contained executable scripts
- Configuration is code-driven, not file-driven

## Observation Patterns

**Real-time observation from `test_knowledge_live.py`:**
```python
# Continuous sampling loop
while time.time() - start_time < duration:
    # Get current state
    feedbacks = get_feedbacks()
    if feedbacks is None:
        continue

    # Send action
    send_action(1.0, 0.0, 0.0)

    # Record
    recorder.record(feedbacks, action)

    # Progress
    frame = recorder.get_frame_count()
    if frame % 10 == 0:
        print(f"  Frame {frame}: speed={feedbacks['speed']:.2f}")

    time.sleep(0.05)  # Sample at ~20Hz
```

**Structured result validation from `demo_test_harness.py`:**
```python
if frames_count > 0 and transitions_count > 0:
    print(f"[OK] {frames_count} frame nodes stored")
    print(f"[OK] {transitions_count} transitions with gas/brake/steering")
    print("[OK] Actual values stored (not discretized)")
    print("\nSUCCESS: Knowledge Graph V2 working correctly!")
else:
    print("[FAILED] No data stored")
```

---

*Testing analysis: 2026-01-31*
