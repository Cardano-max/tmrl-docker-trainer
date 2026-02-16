# Coding Conventions

**Analysis Date:** 2026-02-16

## Naming Patterns

**Files:**
- PascalCase with descriptive names: `BrainArchitecture`, `SystemCoordinator`, `ExperimentationIntelligence`
- Module files use snake_case: `brain_core.py`, `state_manager.py`, `intelligence_experimentation.py`
- Test files: `test_delta_discovery.py`, `demo_test_harness.py`
- Config files with suffixes: `*_corrected.py` for versioned implementations

**Functions:**
- snake_case for all functions: `record_transition()`, `query_transition_target()`, `discretize_all()`
- Private methods prefixed with underscore: `_create_indices()`, `_discretize_single_cached()`, `_load_config()`
- Exception handlers prefixed with underscore: `_handle_sense_state()`, `_handle_do_action()`
- Query functions prefixed with verb: `query_`, `get_`, `check_`, `count_`, `verify_`

**Variables:**
- snake_case for all variables: `current_feedbacks`, `action_discrete`, `state_manager`
- UPPERCASE_CONSTANT for module-level constants
- Prefix private attributes with underscore: `self._graphs`, `self._bin_lookup`, `self._interval_params`
- Short abbreviations used in specific contexts: `db` (database), `intel` (intelligence), `fb` (feedbacks)

**Types:**
- PascalCase for classes: `DisjointActionValidator`, `ActionDiscretizer`, `FeedbackDiscretizer`, `KnowledgeGraph`
- PascalCase for enums: `OrderIntent`, `ConstraintType`, `ExperimentationPhase`, `DiscoverySource`
- PascalCase for dataclasses: `Order`, `Response`, `DecisionPackage`, `StateVector`, `ActionBin`, `ProbeResult`

## Code Style

**Formatting:**
- Line length: No strict limit observed, but typically under 100 characters
- Indentation: 4 spaces (Python standard)
- Blank lines: 2 lines between top-level functions/classes, 1 line between methods
- No trailing whitespace

**Linting:**
- No `.flake8`, `.pylintrc`, or `setup.cfg` found in codebase
- Convention appears manually enforced through code review
- Type hints used extensively but not enforced by mypy config

## Import Organization

**Order:**
1. Standard library (json, logging, math, time, typing, pathlib, itertools, functools, etc.)
2. Third-party (falkordb, numpy if available)
3. Relative imports from project (core.*, utils.*, intelligence.*, control.*)
4. Relative submodule imports (`.state_manager`, `.timestamp_manager_corrected`)

**Examples from `core/brain_core.py`:**
```python
import json
import logging
import math
import time
from typing import Dict, List, Optional, Any, Tuple, Set
from pathlib import Path
from itertools import product
from functools import lru_cache
from falkordb import FalkorDB

from utils.exceptions import (...)
from utils.validators import ConfigValidator, InputValidator
from .state_manager import StateManager, StateVector
```

**Path Aliases:**
- Relative imports within package: `.state_manager`, `.timestamp_manager_corrected`
- Absolute imports: `from utils.exceptions import ...`, `from core.brain_core import ...`
- Conditional imports for optional dependencies: `try: import numpy; except ImportError: HAS_NUMPY = False`

## Error Handling

**Patterns:**
- Custom exception hierarchy with base class `SystemException` in `utils/exceptions.py`
- Specific exceptions: `ConfigurationError`, `BrainCapacityError`, `DiscretizationError`, `GraphOperationError`, `ValidationError`, `DatabaseConnectionError`
- Try-except blocks catch specific exceptions, not bare `except:`
- Retry logic with configurable attempts and delays in graph operations:
  ```python
  def _execute_with_retry(self, operation: callable, *args, **kwargs) -> Any:
      last_exception = None
      for attempt in range(self.retry_attempts):
          try:
              result = operation(*args, **kwargs)
              return result
          except Exception as e:
              if attempt < self.retry_attempts - 1:
                  time.sleep(self.retry_delay)
  ```
- Validation errors raised with descriptive messages including context
- GraphOperationError catches and wraps database errors with retry context

## Logging

**Framework:** Python's built-in `logging` module

**Patterns:**
- Initialized at module level with `logging.getLogger(__name__)`
- Centralized config at application entry point:
  ```python
  logging.basicConfig(
      level=logging.INFO,
      format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  )
  ```
- Four levels used: DEBUG, INFO, WARNING, ERROR
- INFO level used for major system events
- WARNING used for non-critical issues (e.g., missing NO_ACTION combination)
- ERROR used for failures that need attention
- DEBUG used sparingly for detailed operation traces (index creation, debug queries)

**Common patterns:**
- `logger.info(f"[COMPONENT] Message here")` - component prefix in brackets
- `logger.warning(f"[COMPONENT] Warning: details")` - includes component context
- `logger.error(f"[COMPONENT] Error: {exception_details}")` - includes error details
- Informational separators: `logger.info("="*80)` for section headers
- Status indicators with checkmarks: `logger.info("✓ Configuration loaded")`

## Comments

**When to Comment:**
- Docstrings for all public classes and methods (triple quotes)
- Module-level docstrings at file start explaining purpose and context
- Inline comments rare; code is self-documenting through naming
- Comments used for non-obvious logic or SUPERVISOR requirements
- Comments reference meeting transcripts and requirements

**JSDoc/Docstring Pattern:**
- Triple-quoted docstrings with description, optional Args/Returns sections
- Supervisor context included in docstrings when relevant:
  ```python
  def get_no_action_combination(self) -> Optional[Dict[str, str]]:
      """
      Get the NO_ACTION combination (all actions at neutral/NONE)

      SUPERVISOR (meeting_transcript_0901.txt):
      "Part of the combination of action should be no action whatsoever"
      "The reason for that is because especially cars you have inertia"
      """
  ```
- Capitalized variable names in docstrings match code exactly
- Args/Returns use type hints inline

## Function Design

**Size:**
- Small, focused functions (15-40 lines typical)
- Single responsibility per function
- Query functions return data; action functions return boolean success
- Private helper methods extract complex logic

**Parameters:**
- Named parameters used extensively
- Type hints for all parameters
- Optional parameters have defaults (`retry_attempts: int = 3`)
- No positional-only parameters (all named or keyword-arg)

**Return Values:**
- Explicit return types via type hints
- Query functions return `Optional[Type]` when no result possible
- Action functions return `bool` indicating success/failure
- Complex returns use dataclasses: `DecisionPackage`, `ActionBin`, `ProbeResult`
- Errors raise exceptions rather than returning error codes
- Multiple return values via tuple (rare): `(state_manager: StateManager, was_updated: bool)`

## Module Design

**Exports:**
- `__init__.py` files re-export public classes from submodules:
  ```python
  # core/__init__.py
  from .brain_core import BrainArchitecture
  from .state_manager import StateManager, StateVector
  ```
- No explicit `__all__` lists; all non-underscore members are public

**Barrel Files:**
- Used in `core/__init__.py`, `utils/__init__.py`, `adapters/__init__.py`
- Collect related classes for convenient importing
- Enables `from core import BrainArchitecture` instead of `from core.brain_core import BrainArchitecture`

## Special Patterns

**Context-Specific Abbreviations:**
- `fb` = feedback/feedbacks (in context where unambiguous)
- `intel` = intelligence module
- `db` = database
- `env` = environment
- `config` = configuration dictionary
- `stmt` = statement (rarely used)

**Method Prefixes:**
- `get_*`: Query/retrieve data, return result
- `set_*`: Mutate state, return success boolean
- `check_*`: Validate condition, return boolean
- `create_*`: Instantiate new object, return created object
- `is_*`: Boolean check, return boolean
- `query_*`: Database/knowledge query, return result or None
- `validate_*`: Check validity, raise exception on failure

**Supervisor's Ontology:**
- Comments reference Dr. Sutton's ontology concepts
- ALL-CAPS for ontology terms: CAPACITY, KNOWLEDGE, INTELLIGENCE
- Ontology terms used as design documentation in docstrings

---

*Convention analysis: 2026-02-16*
