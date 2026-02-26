"""
Prior Knowledge Detection and Loading

Sutton Jan 24: "when there is previous knowledge... no need to validate
anything because the previous knowledge knows everything"
"check if there is any graph with information... if there is, system starts from there"

Phase 1: Prior knowledge = saved bin discovery JSON files on disk.
Phase 3+: Will also check FalkorDB graphs.

JSON result files are created by test_phase_a_tmnf.py (save_results function)
and follow the naming pattern: tmnf_phase_a_results_YYYYMMDD_HHMMSS.json
"""

import glob
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PriorKnowledgeManager:
    """
    Detects and loads prior knowledge from disk.

    Sutton Jan 24: "when there is previous knowledge... no need to validate
    anything because the previous knowledge knows everything"

    Phase 1: Prior knowledge = saved bin discovery JSON files.
    Phase 3+: Will also check FalkorDB graphs.
    """

    def __init__(
        self,
        results_dir: str = ".",
        results_pattern: str = "tmnf_phase_a_results_*.json"
    ):
        """
        Initialize the prior knowledge manager.

        Args:
            results_dir: Directory to search for saved result files.
            results_pattern: Glob pattern matching result filenames.
        """
        self.results_dir = results_dir
        self.results_pattern = results_pattern

    def _find_result_files(self) -> List[str]:
        """Return all matching result files sorted by filename descending (newest first).

        Filename contains timestamp (YYYYMMDD_HHMMSS), so lexicographic descending
        gives newest first.
        """
        pattern = os.path.join(self.results_dir, self.results_pattern)
        files = glob.glob(pattern)
        # Sort descending by filename so newest timestamp comes first
        files.sort(reverse=True)
        return files

    def has_prior_knowledge(self) -> bool:
        """Check if any prior bin discovery results exist on disk.

        Returns:
            True if at least one valid result file is found.
        """
        files = self._find_result_files()
        for filepath in files:
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                if 'results' in data and isinstance(data['results'], dict):
                    return True
            except (json.JSONDecodeError, IOError, OSError) as e:
                logger.warning(f"[PRIOR_KNOWLEDGE] Skipping corrupt file {filepath}: {e}")
                continue
        return False

    def load_latest(self) -> Optional[Dict]:
        """Load the most recent bin discovery results from disk.

        Sorts result files by filename (timestamp embedded) to find the latest.

        Returns:
            Parsed JSON dict of the most recent valid result file, or None if
            no valid results exist.
        """
        files = self._find_result_files()
        for filepath in files:
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                if 'results' in data and isinstance(data['results'], dict):
                    logger.info(f"[PRIOR_KNOWLEDGE] Loaded prior knowledge from: {filepath}")
                    return data
            except (json.JSONDecodeError, IOError, OSError) as e:
                logger.warning(f"[PRIOR_KNOWLEDGE] Skipping corrupt file {filepath}: {e}")
                continue
        logger.info("[PRIOR_KNOWLEDGE] No prior knowledge found on disk")
        return None

    def load_bins_from_results(self, results: Dict) -> Dict[str, Any]:
        """Extract bins dict from a results JSON file.

        Converts the raw results dict (from test_phase_a_tmnf.py save_results)
        into the format expected by SystemInitializer:

            {
                'gas':      {'min': ..., 'max': ..., 'bins': N, 'bin_details': [...], 'source': 'prior_knowledge'},
                'brake':    {...},
                'steering': {...}
            }

        Args:
            results: Parsed JSON dict loaded from a result file (must contain 'results' key).

        Returns:
            Dict mapping action_name -> bin info dict, or empty dict if extraction fails.
        """
        raw_results = results.get('results', {})
        if not isinstance(raw_results, dict):
            logger.warning("[PRIOR_KNOWLEDGE] 'results' key is not a dict -- returning empty")
            return {}

        bins_out: Dict[str, Any] = {}
        for action_name, action_data in raw_results.items():
            if not isinstance(action_data, dict):
                logger.warning(
                    f"[PRIOR_KNOWLEDGE] Action '{action_name}' data is not a dict -- skipping"
                )
                continue

            entry = {
                'min':         action_data.get('min'),
                'max':         action_data.get('max'),
                'bins':        action_data.get('bins'),
                'bin_details': action_data.get('bin_details', []),
                'source':      'prior_knowledge',
            }

            # Copy any extra fields that callers might use (probes, time, input_type, etc.)
            for extra_key in ('probes', 'time', 'delta_max', 'delta_0', 'input_type'):
                if extra_key in action_data:
                    entry[extra_key] = action_data[extra_key]

            bins_out[action_name] = entry

        return bins_out

    def get_all_results(self) -> List[Dict]:
        """Return all saved result files as parsed dicts, sorted newest first.

        Returns:
            List of parsed JSON dicts. Corrupt/unreadable files are skipped.
        """
        files = self._find_result_files()
        results = []
        for filepath in files:
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                if 'results' in data and isinstance(data['results'], dict):
                    results.append(data)
            except (json.JSONDecodeError, IOError, OSError) as e:
                logger.warning(f"[PRIOR_KNOWLEDGE] Skipping corrupt file {filepath}: {e}")
                continue
        return results

    def save_results(self, results: Dict, metadata: Dict = None) -> str:
        """Save bin discovery results to disk in the standard format.

        This is the canonical save function that replaces the ad-hoc save_results()
        in test_phase_a_tmnf.py. Uses the same naming pattern so load_latest() finds it.

        Args:
            results: Dict mapping action_name -> bin discovery results.
                     Example: {'gas': {'max': 1.0, 'min': 0.001, 'bins': 2, ...}}
            metadata: Optional additional metadata to include in the file.

        Returns:
            Path to the saved file.
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"tmnf_phase_a_results_{timestamp}.json"
        filepath = os.path.join(self.results_dir, filename)

        output: Dict[str, Any] = {
            'timestamp':     timestamp,
            'environment':   'TMNF',
            'interface':     'TMInterface 2.x (TCP bridge)',
            'tick_ms':       10,
            'deterministic': True,
            'algorithm':     'sutton_downward_sweep',
        }

        if metadata:
            output.update(metadata)

        output['results'] = results

        os.makedirs(self.results_dir, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(output, f, indent=2, default=str)

        logger.info(f"[PRIOR_KNOWLEDGE] Results saved to: {filepath}")
        return filepath
