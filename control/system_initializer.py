"""
SYSTEM INITIALIZER

Meeting 24-Jan-2026 requirement: Proper initialization sequence before brain
can operate. Adapter-agnostic (works with TMNF, mock, or any future adapter).

INITIALIZATION SEQUENCE (Sutton Jan 24, 2026):
  "the system won't start before it the experiments"
  "when there is previous knowledge... no need to validate anything"
  "you can print everything to screen like validation started, bins acquired"
  "who defines the time stamp is the environment"
  "this needs to be determined by the system so it's being configured not hard-coded"

  1. Load config (always)
  2. Validate config (INIT-01)
  3. Check prior knowledge (INIT-02) — ASK user if they want to use it
  4. If user says no or no prior knowledge: connect adapter, discover frame
     duration from environment (INIT-06), run bin discovery (INIT-03)
  5. If user says yes: load prior knowledge, still need adapter for frame
     duration discovery (INIT-04, INIT-06)
  6. Print status at each stage (INIT-05)

INIT REQUIREMENTS:
  INIT-01: Refuse to start if config missing or semantically invalid
  INIT-02: Detect existing bin discovery results on disk
  INIT-03: Run bin discovery automatically when no prior knowledge
  INIT-04: When user chooses prior knowledge, load it and skip experimentation
  INIT-05: Print status at each startup stage
  INIT-06: Frame duration DISCOVERED from environment, NEVER hardcoded
"""

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = "config/tmnf_config.json"


class InitializationStatus(Enum):
    """Status of initialization stages."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class InitializationResult:
    """Result of initialization sequence."""
    success: bool
    has_prior_knowledge: bool
    bins_acquired: Dict[str, Any]
    frame_duration_ms: float
    stages: Dict[str, InitializationStatus]
    errors: List[str]
    warnings: List[str]


class SystemInitializer:
    """
    System initialization sequence (Sutton Jan 24, 2026).

    Sequence:
      1. Load config
      2. Validate config (INIT-01)
      3. Check prior knowledge (INIT-02) — ask user
      4. Connect adapter (needed for frame duration discovery)
      5. Discover frame duration from environment (INIT-06)
      6. If no prior knowledge (or user declines): run bin discovery (INIT-03)
      7. Print status at each stage (INIT-05)

    Sutton quotes:
      "the system won't start before it the experiments"
      "when there is previous knowledge... no need to validate anything"
      "who defines the time stamp is the environment"
    """

    def __init__(self, config_path: str = None, adapter=None,
                 user_input_fn=None):
        """
        Args:
            config_path: Path to JSON config file.
                         Default: config/tmnf_config.json
            adapter: Pre-created environment adapter (any object with
                     get_feedbacks() and send_action_dict()).
                     If None, the initializer creates a TMNFAdapter from
                     config when needed.
            user_input_fn: Function to ask user questions. Signature:
                          user_input_fn(prompt: str) -> str
                          Default: built-in input() for interactive use.
                          Tests can inject a lambda to simulate user responses.
        """
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self._injected_adapter = adapter
        self._user_input = user_input_fn or input

        self.config: Optional[Dict] = None
        self.frame_duration_ms: float = 0.0
        self.bins: Dict[str, Any] = {}
        self.errors: List[str] = []
        self.warnings: List[str] = []

        self.stages: Dict[str, InitializationStatus] = {
            'config_load':           InitializationStatus.NOT_STARTED,
            'config_validation':     InitializationStatus.NOT_STARTED,
            'prior_knowledge_check': InitializationStatus.NOT_STARTED,
            'adapter_connect':       InitializationStatus.NOT_STARTED,
            'frame_duration_discovery': InitializationStatus.NOT_STARTED,
            'bin_acquisition':       InitializationStatus.NOT_STARTED,
        }

    # -------------------------------------------------------------------------
    # STATUS PRINTING (INIT-05)
    # -------------------------------------------------------------------------

    def _print_status(self, stage: str, status: str, detail: str = ""):
        """Print formatted status line.

        Symbols:
          [~] starting / in progress
          [+] ok / completed
          [X] failed
          [o] skipped
          [!] warning
        """
        symbol = {
            'start': '~',
            'ok':    '+',
            'fail':  'X',
            'skip':  'o',
            'warn':  '!'
        }.get(status, '-')

        msg = f"  [{symbol}] {stage}"
        if detail:
            msg += f": {detail}"
        print(msg)
        logger.info(msg)

    # -------------------------------------------------------------------------
    # STAGE 1: LOAD CONFIG
    # -------------------------------------------------------------------------

    def _load_config(self) -> bool:
        """Load and parse JSON config. Returns False on any failure."""
        self.stages['config_load'] = InitializationStatus.IN_PROGRESS
        self._print_status("Config load", "start", self.config_path)

        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)

            self.stages['config_load'] = InitializationStatus.COMPLETED
            self._print_status("Config loaded", "ok",
                               f"v{self.config.get('version', 'unknown')}")
            return True

        except FileNotFoundError:
            msg = f"Config file not found: {self.config_path}"
            self.errors.append(msg)
            self.stages['config_load'] = InitializationStatus.FAILED
            self._print_status("Config load", "fail", "File not found")
            return False

        except json.JSONDecodeError as e:
            msg = f"Invalid JSON in config: {e}"
            self.errors.append(msg)
            self.stages['config_load'] = InitializationStatus.FAILED
            self._print_status("Config load", "fail", "Invalid JSON")
            return False

    # -------------------------------------------------------------------------
    # STAGE 2: VALIDATE CONFIG (INIT-01)
    # -------------------------------------------------------------------------

    def _validate_config(self) -> bool:
        """Use ConfigValidator to validate actions, feedbacks, environment.

        Sutton Jan 24: "when you create wrong information on the config
        the system should be able to detect it"

        Returns False if validation raises.
        """
        self.stages['config_validation'] = InitializationStatus.IN_PROGRESS
        self._print_status("Config validation", "start")

        try:
            from utils.validators import ConfigValidator
            ConfigValidator.validate_config(self.config)

        except Exception as e:
            msg = f"Config validation failed: {e}"
            self.errors.append(msg)
            self.stages['config_validation'] = InitializationStatus.FAILED
            self._print_status("Config validation", "fail", str(e))
            return False

        actions = self.config.get('actions', {})
        feedbacks = self.config.get('feedbacks', {})

        self.stages['config_validation'] = InitializationStatus.COMPLETED
        self._print_status("Config validated", "ok",
                           f"{len(actions)} actions, {len(feedbacks)} feedbacks")
        return True

    # -------------------------------------------------------------------------
    # STAGE 3: CHECK PRIOR KNOWLEDGE (INIT-02) — ASK USER
    # -------------------------------------------------------------------------

    def _check_prior_knowledge(self) -> bool:
        """Detect prior knowledge and ASK user if they want to use it.

        Sutton Jan 24: "check if there is any graph with information...
        if there is, system starts from there"

        But user decides — they may want to re-run experimentation.

        Returns True if prior knowledge found AND user chose to use it.
        """
        self.stages['prior_knowledge_check'] = InitializationStatus.IN_PROGRESS
        self._print_status("Prior knowledge check", "start")

        prior_cfg = self.config.get('prior_knowledge', {})
        results_dir = prior_cfg.get('results_dir', '.')
        results_pattern = prior_cfg.get(
            'results_pattern', 'tmnf_phase_a_results_*.json'
        )

        try:
            from knowledge.prior_knowledge import PriorKnowledgeManager
            pk_manager = PriorKnowledgeManager(
                results_dir=results_dir,
                results_pattern=results_pattern
            )

            if not pk_manager.has_prior_knowledge():
                self.stages['prior_knowledge_check'] = InitializationStatus.COMPLETED
                self._print_status("Prior knowledge", "ok",
                                   "None found (fresh start)")
                return False

            # Found prior knowledge — show what's available
            data = pk_manager.load_latest()
            if data is None:
                self.stages['prior_knowledge_check'] = InitializationStatus.COMPLETED
                self._print_status("Prior knowledge", "ok",
                                   "None found (fresh start)")
                return False

            bins = pk_manager.load_bins_from_results(data)
            bin_summary = ", ".join(
                f"{name}={info.get('bins', '?')} bins"
                for name, info in bins.items()
            )

            # ASK the user
            print()
            print(f"  Prior knowledge found: {bin_summary}")
            response = self._user_input(
                "  Use prior knowledge? (y = use it, n = re-run experimentation): "
            )

            if response.strip().lower() in ('y', 'yes', ''):
                self.bins = bins
                self.stages['prior_knowledge_check'] = InitializationStatus.COMPLETED
                self._print_status("Prior knowledge loaded", "ok",
                                   f"{len(self.bins)} actions ({bin_summary})")
                return True
            else:
                self.stages['prior_knowledge_check'] = InitializationStatus.COMPLETED
                self._print_status("Prior knowledge", "ok",
                                   "User chose to re-run experimentation")
                return False

        except Exception as e:
            msg = f"Prior knowledge check error: {e}"
            self.warnings.append(msg)
            self.stages['prior_knowledge_check'] = InitializationStatus.FAILED
            self._print_status("Prior knowledge check", "warn", str(e))
            return False

    # -------------------------------------------------------------------------
    # STAGE 4: CONNECT ADAPTER
    # -------------------------------------------------------------------------

    def _connect_adapter(self):
        """Connect to the game environment adapter.

        If adapter was injected at construction, use it directly.
        Otherwise, create a TMNFAdapter from config.

        Returns the connected adapter, or None if connection failed.
        """
        self.stages['adapter_connect'] = InitializationStatus.IN_PROGRESS

        # Use pre-injected adapter (tests, live mode with pre-built adapter)
        if self._injected_adapter is not None:
            adapter = self._injected_adapter
            self._print_status("Adapter", "ok", "Using pre-built adapter")
            self.stages['adapter_connect'] = InitializationStatus.COMPLETED
            return adapter

        # Create adapter from config
        env_cfg = self.config.get('environment', {})
        host = env_cfg.get('host', '127.0.0.1')
        port = env_cfg.get('port', 8476)

        self._print_status("Adapter connect", "start", f"TMNF TCP {host}:{port}")

        try:
            from adapters.tmnf_adapter import TMNFAdapter
            adapter = TMNFAdapter(host=host, port=port)
            connected = adapter.connect(timeout=5.0)

            if connected:
                self.stages['adapter_connect'] = InitializationStatus.COMPLETED
                self._print_status("Adapter connected", "ok", f"{host}:{port}")
                return adapter
            else:
                msg = f"Could not connect to TMNF adapter at {host}:{port}"
                self.errors.append(msg)
                self.stages['adapter_connect'] = InitializationStatus.FAILED
                self._print_status("Adapter connect", "fail",
                                   "Connection refused")
                return None

        except Exception as e:
            msg = f"Adapter error: {e}"
            self.errors.append(msg)
            self.stages['adapter_connect'] = InitializationStatus.FAILED
            self._print_status("Adapter connect", "fail", str(e))
            return None

    # -------------------------------------------------------------------------
    # STAGE 5: DISCOVER FRAME DURATION FROM ENVIRONMENT (INIT-06)
    # -------------------------------------------------------------------------

    def _discover_frame_duration(self, adapter) -> bool:
        """Discover frame duration by measuring the environment.

        Sutton Feb 16: "who defines the time stamp is the environment"
        Sutton Jan 24: "determined by the system so it's being configured
                        not hard-coded"

        Method: read race_time, advance one tick, read race_time again.
        Delta = frame duration in ms.

        Returns True if discovered successfully.
        """
        self.stages['frame_duration_discovery'] = InitializationStatus.IN_PROGRESS
        self._print_status("Frame duration discovery", "start",
                           "Measuring environment tick rate")

        try:
            # Read race_time before tick
            fb_before = adapter.get_feedbacks()
            race_time_before = fb_before.get('race_time', None)

            if race_time_before is None:
                msg = "Environment does not report race_time — cannot discover frame duration"
                self.errors.append(msg)
                self.stages['frame_duration_discovery'] = InitializationStatus.FAILED
                self._print_status("Frame duration discovery", "fail",
                                   "No race_time in feedbacks")
                return False

            # Advance one tick
            # Send neutral action so we don't affect the car
            action_names = list(self.config.get('actions', {}).keys())
            neutral_action = {name: 0.0 for name in action_names}
            adapter.send_action_dict(neutral_action)
            if hasattr(adapter, 'wait_one_tick'):
                adapter.wait_one_tick()
            else:
                time.sleep(0.05)  # fallback for non-TMNF adapters

            # Read race_time after tick
            fb_after = adapter.get_feedbacks()
            race_time_after = fb_after.get('race_time', None)

            if race_time_after is None:
                msg = "race_time disappeared after tick"
                self.errors.append(msg)
                self.stages['frame_duration_discovery'] = InitializationStatus.FAILED
                self._print_status("Frame duration discovery", "fail", msg)
                return False

            delta_ms = race_time_after - race_time_before
            if delta_ms <= 0:
                msg = f"Invalid frame duration: {delta_ms}ms (race_time didn't advance)"
                self.errors.append(msg)
                self.stages['frame_duration_discovery'] = InitializationStatus.FAILED
                self._print_status("Frame duration discovery", "fail", msg)
                return False

            self.frame_duration_ms = float(delta_ms)
            self.stages['frame_duration_discovery'] = InitializationStatus.COMPLETED
            self._print_status("Frame duration discovered", "ok",
                               f"{self.frame_duration_ms:.0f}ms "
                               f"(from environment, not hardcoded)")
            return True

        except Exception as e:
            msg = f"Frame duration discovery error: {e}"
            self.errors.append(msg)
            self.stages['frame_duration_discovery'] = InitializationStatus.FAILED
            self._print_status("Frame duration discovery", "fail", str(e))
            return False

    # -------------------------------------------------------------------------
    # STAGE 6: ACQUIRE BINS via ExperimentationCoordinator (INIT-03)
    # -------------------------------------------------------------------------

    def _acquire_bins(self, adapter) -> bool:
        """Run Sutton's downward sweep algorithm via ExperimentationCoordinator.

        Sutton Jan 24: "the system won't start before it the experiments"

        wait_fn: uses adapter.wait_one_tick if available (TMNF TCP sync),
                 falls back to time.sleep for non-TMNF adapters.
        frame_duration_ms discovered from environment (INIT-06).

        Returns True if discovery completed successfully.
        """
        self.stages['bin_acquisition'] = InitializationStatus.IN_PROGRESS
        self._print_status("Bin acquisition", "start",
                           "Sutton downward sweep algorithm")

        try:
            from intelligence.intelligence_experimentation import ExperimentationCoordinator

            frame_duration_s = self.frame_duration_ms / 1000.0

            # Use adapter.wait_one_tick if available (TMNF TCP sync requirement).
            # Fall back to time.sleep for adapters that don't have it.
            # NOTE: ExperimentationCoordinator calls wait_fn(frame_duration_s)
            # with one arg, but adapter.wait_one_tick() takes zero args.
            # Wrap it to accept and ignore the duration argument.
            raw_wait = getattr(adapter, 'wait_one_tick', None)
            if raw_wait is not None:
                wait_fn = lambda _duration, _w=raw_wait: _w()
            else:
                wait_fn = lambda duration: time.sleep(duration)

            coordinator = ExperimentationCoordinator(
                actions_config=self.config['actions'],
                send_action_fn=adapter.send_action_dict,
                get_feedbacks_fn=adapter.get_feedbacks,
                wait_fn=wait_fn,
                reset_fn=None,  # No reset -- stream environment (Sutton)
                frame_duration_s=frame_duration_s
            )

            self._print_status("ExperimentationCoordinator", "ok",
                               "Sutton downward sweep (Phase A algorithm)")

            discovered = coordinator.run_full_experimentation()

            # Convert ActionBin dicts to our standard format
            for action_name, bin_list in discovered.items():
                result = coordinator.intelligence.discovery_results.get(action_name)
                self.bins[action_name] = {
                    'min': result.a_min_effective if result else 0.0,
                    'max': result.a_max_effective if result else 1.0,
                    'bins': len(bin_list),
                    'bin_details': bin_list,
                    'source': 'experimentation',
                    'success': result.success if result else False,
                }

            # Save results for next run
            prior_cfg = self.config.get('prior_knowledge', {})
            results_dir = prior_cfg.get('results_dir', '.')
            try:
                from knowledge.prior_knowledge import PriorKnowledgeManager
                pk_manager = PriorKnowledgeManager(results_dir=results_dir)
                save_data = {
                    name: {
                        'max': info['max'],
                        'min': info['min'],
                        'bins': info['bins'],
                        'bin_details': info['bin_details'],
                    }
                    for name, info in self.bins.items()
                }
                pk_manager.save_results(save_data)
            except Exception as save_err:
                self.warnings.append(f"Could not save results: {save_err}")

            self.stages['bin_acquisition'] = InitializationStatus.COMPLETED
            self._print_status("Bins acquired", "ok",
                               f"{len(self.bins)} actions via Phase A algorithm")
            return True

        except Exception as e:
            import traceback
            msg = f"Bin acquisition error: {e}"
            self.errors.append(msg)
            self.stages['bin_acquisition'] = InitializationStatus.FAILED
            self._print_status("Bin acquisition", "fail", str(e))
            logger.error(f"[BIN ACQUISITION] {e}\n{traceback.format_exc()}")
            return False

    # -------------------------------------------------------------------------
    # REPORT READY (INIT-05)
    # -------------------------------------------------------------------------

    def _report_ready(self, has_prior: bool):
        """Print final summary when all stages complete."""
        source = "prior knowledge" if has_prior else "discovered"
        print()
        print("=" * 60)
        print("SYSTEM READY")
        print(f"  Frame duration : {self.frame_duration_ms:.0f}ms "
              f"(discovered from environment)")
        print(f"  Bins source    : {source}")
        for action_name, info in self.bins.items():
            n = info.get('bins', '?')
            print(f"  {action_name:12s} : {n} bin(s)")
        print("=" * 60)

    # -------------------------------------------------------------------------
    # FAIL RESULT HELPER
    # -------------------------------------------------------------------------

    def _fail_result(self) -> InitializationResult:
        """Build a failed InitializationResult from current state."""
        return InitializationResult(
            success=False,
            has_prior_knowledge=False,
            bins_acquired={},
            frame_duration_ms=self.frame_duration_ms,
            stages=self.stages,
            errors=self.errors,
            warnings=self.warnings,
        )

    # -------------------------------------------------------------------------
    # PUBLIC: INITIALIZE
    # -------------------------------------------------------------------------

    def initialize(self) -> InitializationResult:
        """
        Run full initialization sequence.

        Returns InitializationResult with success status, bins, and
        stage details for every startup stage.
        """
        print("=" * 60)
        print("SYSTEM INITIALIZATION")
        print("  Sutton Jan 24: 'the system won't start before it the experiments'")
        print("=" * 60)

        # Stage 1: Load config (always)
        if not self._load_config():
            return self._fail_result()

        # Stage 2: Validate config (INIT-01)
        if not self._validate_config():
            return self._fail_result()

        # Stage 3: Check prior knowledge (INIT-02) — asks user
        has_prior = self._check_prior_knowledge()

        # We always need the adapter for frame duration discovery (INIT-06)
        # unless we're in offline-only mode (no adapter, prior knowledge only)
        adapter = self._connect_adapter()

        if adapter is not None:
            # Stage 5: Discover frame duration from environment (INIT-06)
            # Sutton: "who defines the time stamp is the environment"
            if not self._discover_frame_duration(adapter):
                return self._fail_result()
        else:
            # No adapter available
            if has_prior:
                # Offline mode with prior knowledge — can't discover frame
                # duration without environment. Skip it.
                self.stages['frame_duration_discovery'] = InitializationStatus.SKIPPED
                self._print_status("Frame duration discovery", "skip",
                                   "No adapter (offline mode)")
            else:
                # No prior knowledge AND no adapter = can't proceed
                self._print_status("Bin acquisition", "fail",
                                   "No adapter (is the game running?)")
                self.stages['bin_acquisition'] = InitializationStatus.FAILED
                return self._fail_result()

        if has_prior:
            # INIT-04: User chose prior knowledge, skip experimentation
            self.stages['bin_acquisition'] = InitializationStatus.SKIPPED
            self._print_status("Bin acquisition", "skip",
                               "Using prior knowledge (user choice)")
        else:
            # INIT-03: Must acquire bins before system can operate
            if not self._acquire_bins(adapter):
                return self._fail_result()

        # All stages done -- report ready (INIT-05)
        self._report_ready(has_prior)

        success = all(
            s in (InitializationStatus.COMPLETED, InitializationStatus.SKIPPED)
            for s in self.stages.values()
        )

        return InitializationResult(
            success=success,
            has_prior_knowledge=has_prior,
            bins_acquired=self.bins,
            frame_duration_ms=self.frame_duration_ms,
            stages=self.stages,
            errors=self.errors,
            warnings=self.warnings,
        )

    # -------------------------------------------------------------------------
    # ACCESSORS
    # -------------------------------------------------------------------------

    def get_bins(self) -> Dict:
        """Return acquired bins."""
        return self.bins

    def get_frame_duration_ms(self) -> float:
        """Return frame duration in ms (discovered from environment)."""
        return self.frame_duration_ms
