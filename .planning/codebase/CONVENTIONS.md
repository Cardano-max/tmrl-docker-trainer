# Coding Conventions

**Analysis Date:** 2026-01-31

## Naming Patterns

**Files:**
- Snake case: `state_manager.py`, `brain_capacity.py`, `tmrl_live_adapter.py`
- Corrected variants: `system_coordinator_corrected.py`, `timestamp_manager_corrected.py`
- Test files: `test_knowledge_live.py`, `live_system_validator.py` (descriptive names, prefixed with test/live)
- Entry points: `tmrl_live_control.py`, `run_order_system.py`, `demo_test_harness.py`

**Functions:**
- Snake case: `sense_speed()`, `act_combined()`, `discretize_state()`
- Internal/private methods: Prefixed with underscore: `_extract_parameters()`, `_states_equal()`, `_receive_loop()`
- Handler functions: Named descriptively: `_handle_sense_state()`, `_handle_do_action()`, `_handle_who_am_i()`
- Query functions: Prefixed with verb: `query_exists()`, `query_tried_count()`, `get_state()`, `count_nodes()`
- Boolean checks: Prefixed with `is_` or `can_`: `is_connected()`, `can_sense()`, `can_act()`

**Variables:**
- Snake case throughout: `state_history`, `max_frames`, `episode_frames`, `graph_positions`
- Constants (rare): UPPER_SNAKE_CASE used minimally (seen in enum values, struct format)
- Meaningful names over abbreviations: `no_change_threshold` instead of `nct`, `state_transitions` instead of `st`

**Types:**
- Classes: PascalCase: `BrainIntelligence`, `StateManager`, `EpisodeController`, `LiveObservation`
- Enums: PascalCase class names: `OrderIntent`, `EpisodePhase`, `EpisodeEndReason`
- Enum members: UPPER_SNAKE_CASE: `SENSE_STATE`, `RUNNING`, `FRAME_LIMIT`

**Dataclasses:**
- PascalCase class names: `StateVector`, `Order`, `Response`, `DiscoveryResult`, `LocalGainResult`
- Field names follow variable conventions (snake_case)
- Used extensively for structured data and return types

## Code Style

**Formatting:**
- No explicit formatter configured (.prettierrc, .flake8, .pylintrc not found)
- Implicit standards observed from codebase:
  - 4-space indentation (standard Python)
  - Max line length appears to be ~100 characters (some lines reach 80-100)
  - Consistent spacing around operators and after commas

**Linting:**
- No pre-commit hooks detected
- No explicit linter configured
- Code follows PEP 8 conventions implicitly

**Example formatting from `intelligence/brain_intelligence.py`:**
```python
def interpret(self, user_input: str) -> Order:
    """
    Interpret user input into an Order.

    Args:
        user_input: Natural language input from user

    Returns:
        Order with intent and parameters
    """
    input_lower = user_input.lower().strip()

    # Pattern matching
    for intent, patterns in self.PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, input_lower):
                # Single responsibility per loop level
```

## Import Organization

**Order:**
1. Standard library (`sys`, `time`, `logging`, `json`, `socket`, etc.)
2. Third-party imports (`requests`, `vgamepad`, etc.)
3. Local/relative imports (`.` notation not used; absolute imports from project root)

**Path Aliases:**
- None detected. Uses absolute imports: `from core.state_manager import StateVector`
- Project structure allows direct absolute imports without aliases

**Example from `control/episode_controller.py`:**
```python
import logging
import time
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

from core.state_manager import StateVector
from utils.exceptions import SystemException
```

## Error Handling

**Patterns:**
- Custom exception hierarchy in `utils/exceptions.py`
- Base exception: `SystemException` (all system errors inherit from this)
- Specific exceptions for domains:
  - `BrainCapacityError`: Brain architecture failures
  - `KnowledgeError`: Knowledge operations
  - `IntelligenceError`: Intelligence decisions
  - `GraphOperationError`: Database operations
  - `ValidationError`: Input validation
  - `StateNotFoundError`: Queried state doesn't exist
  - `DatabaseConnectionError`: Connection failures

**Usage pattern from `control/episode_controller.py`:**
```python
def check(self, state: StateVector, feedbacks: Dict[str, float]) -> bool:
    """Check if condition is triggered"""
    try:
        triggered = self.check_fn(state, feedbacks)
        if triggered:
            self.trigger_count += 1
        return triggered
    except Exception as e:
        logger.error(f"[FAILURE] Condition '{self.name}' check failed: {e}")
        return False
```

**Pattern: Graceful degradation** - Functions return None or False on error rather than raising:
```python
def sense_speed(self) -> Optional[float]:
    if not self.adapter:
        return None
    feedbacks = self.adapter.get_feedbacks()
    return feedbacks.get('speed')
```

## Logging

**Framework:** `logging` module (standard library)

**Initialization pattern:**
```python
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
```

**Patterns:**
- Use `__name__` for logger identification
- Log level: Mostly INFO and WARNING
- Tagged messages with component markers in brackets: `[INTELLIGENCE]`, `[STATE]`, `[CAPACITY]`, `[EPISODE]`, `[STUCK]`
- Format: `f"[COMPONENT] Message: {details}"`

**Examples from codebase:**
```python
logger.info("[INTELLIGENCE] BrainIntelligence initialized")
logger.debug(f"[STATE] Updated: {new_state}")
logger.warning(f"[STUCK] System stuck! {self.actions_since_change} actions with no state change")
logger.error(f"[VGAMEPAD] Failed to initialize: {e}")
```

**When to log:**
- Initialization: Component initialization and configuration
- State changes: Important transitions, episode starts/ends
- Warnings: Failure detection, stuck conditions, missing connections
- Errors: Exception handling, invalid states
- Debug: Detailed operation traces (for development)

## Comments

**When to Comment:**
- Block comments for major sections: `# =========================================================================`
- Explain "why", not "what" (code should be self-documenting for "what")
- Non-obvious business logic or Dr. Sutton's constraints
- Component marker comments like `# SENSORY CAPACITIES`, `# ACTION HANDLERS`

**Example from `core/brain_capacity.py`:**
```python
# =========================================================================
# SENSORY CAPACITIES (Read from environment)
# =========================================================================

def sense_speed(self) -> Optional[float]:
    """
    Read current vehicle speed from environment.

    Returns:
        float: Current speed, or None if not connected
    """
    if not self.adapter:
        return None
    feedbacks = self.adapter.get_feedbacks()
    return feedbacks.get('speed')
```

**Module-level docstrings:**
Every file starts with a detailed module docstring explaining:
- Purpose of the module
- Key concepts and ontology (especially for core modules)
- Critical constraints (e.g., Dr. Sutton's "NO STATE RESET")
- Design decisions and rationale

**Example from `intelligence/brain_intelligence.py`:**
```python
"""
BRAIN INTELLIGENCE

Intelligence interprets orders, uses capacity and knowledge, and ALWAYS answers.

CRITICAL: Intelligence ALWAYS answers.
Capacity enables/blocks, Knowledge stores, Intelligence ANSWERS.

Ontology (Dr. Sutton):
- CAPACITY = allowance to DO something (can/cannot DO, never answers)
- KNOWLEDGE = passive storage (no decisions)
- INTELLIGENCE = interprets, accesses, manipulates (ALWAYS answers)

"access, manipulation, acquire, everything that you do with knowledge is intelligence"
"brain capacity is not to answer. Who answers is in the intelligence"
"""
```

## JSDoc/TSDoc

**Pattern:** Not used (Python project). Uses standard docstrings instead.

**Docstring style:**
- Google-style docstrings (consistent across codebase)
- Triple quotes: `"""`
- Structure:
  - Brief one-line summary
  - Blank line
  - Longer description (if needed)
  - Blank line
  - Args section with type and description
  - Returns section with type and description

**Example from `control/episode_controller.py`:**
```python
def should_end_episode(
    self,
    current_frame: int,
    current_state: Optional[StateVector] = None,
    feedbacks: Optional[Dict[str, float]] = None
) -> Tuple[bool, Optional[EpisodeEndReason]]:
    """
    Check if episode should end

    SUPERVISOR'S CRITERIA:
    "Episode length can be defined by: frames, failure conditions, time limits"

    Args:
        current_frame: Current frame number
        current_state: Current state (for failure checking)
        feedbacks: Current feedbacks (for failure checking)

    Returns:
        (should_end, reason)
    """
```

## Function Design

**Size:**
- Generally 5-50 lines, focused on single responsibility
- Longer functions (100+ lines) used for complex workflows with clear section comments
- Example: `IntelligenceExecutor.execute()` at ~400 lines has clear handler sections marked with comments

**Parameters:**
- Prefer explicit parameters over *args, **kwargs
- Use type hints on all function signatures
- Default parameters used for optional configuration
- Order: required parameters first, optional parameters last

**Return Values:**
- Single return value preferred for clarity
- Use dataclasses for complex return structures: `Order`, `Response`, `DiscoveryResult`
- Use tuples for paired returns: `Tuple[bool, Optional[EpisodeEndReason]]`
- Return None explicitly for "no value" cases (not implicit)
- Return False/empty list for failed operations (graceful degradation)

**Example from `control/episode_controller.py`:**
```python
def record_state(self, state: StateVector, action_count: int) -> bool:
    """Record new state and check for stuck condition"""
    # Clear responsibility
    # Single boolean return
    # Type hints on parameters
```

## Module Design

**Exports:**
- Classes and functions intended for external use are at module top-level
- Private/internal functions prefixed with underscore
- No explicit `__all__` lists observed (relies on underscore convention)

**Barrel Files:**
- `__init__.py` files present in packages but mostly empty or minimal
- Example: `core/__init__.py`, `adapters/__init__.py` are empty
- Direct imports from specific modules used: `from core.state_manager import StateVector`

**Example module structure from `adapters/tmrl_live_adapter.py`:**
```python
# Public dataclasses at top
@dataclass
class LiveObservation:
    """Real-time observation from TrackMania"""
    # ...

@dataclass
class LiveAction:
    """Action to send to TrackMania"""
    # ...

# Public classes
class VGamepadController:
    """Virtual Xbox 360 controller"""
    # ...

class OpenPlanetClient:
    """TCP client for OpenPlanet plugin"""
    # ...

# Main public interface
class TMRLLiveAdapter:
    """Main adapter for TMRL live control"""
    # ...
```

## Type Hints

**Coverage:** Comprehensive type hints throughout codebase
- All function parameters typed
- All return types specified
- Class attributes typed using dataclasses

**Optional types:** `Optional[Type]` used extensively for nullable values
**Complex types:** `Dict[str, Any]`, `List[str]`, `Tuple[bool, str]`, `Callable[[int], bool]`
**Example from `control/episode_controller.py`:**
```python
def __init__(
    self,
    max_frames: int = 10000,
    max_time_seconds: Optional[float] = None,
    stuck_threshold: int = 100
):
```

## Constraints & Requirements Documentation

**Critical for this system:** Module docstrings include Dr. Sutton's constraints and system requirements.

**Example from `order_discovery.py`:**
```
=============================================================================
CRITICAL CONSTRAINT: NO STATE RESET / NO INTERFERENCE
=============================================================================

Dr. Sutton's mandate:
- Environment is a STREAM being sampled, NOT a lab setup to control
- NO stopping the car
- NO braking to baseline
- NO waiting for "stopped" state
- NO forcing system back to known state
```

This pattern used in:
- `intelligence/order_discovery.py`
- `control/system_initializer.py`
- `control/episode_controller.py`
- `control/environment_protocol.py`

---

*Convention analysis: 2026-01-31*
