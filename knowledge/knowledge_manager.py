"""
KNOWLEDGE MANAGER - Per-Frame Knowledge Graph

SUPERVISOR'S FRAMEWORK (Dr. Sutton 15-01-2026):
- One node PER FRAME (not per discretized interval)
- Store ACTUAL observed values (not discretized)
- Named edges with action values
- Frame number as unique identifier

"The system should be able to record one node per frame"
"The actions have to be by frame not continuously"

Graph Structure:
---------------
Nodes: (:Frame {frame_id, speed, gear, rpm, timestamp})
Edges: -[:ACTION {gas, brake, steering}]->

Example:
--------
(Frame:0 {speed:0.01}) --[:ACTION {gas:0.5}]--> (Frame:1 {speed:5.23})

VERSION HISTORY:
- v1.0: Discretized intervals (7 nodes for all speeds) - DEPRECATED
- v2.0: One node per frame with actual values - CURRENT
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FrameObservation:
    """Single frame observation from environment"""
    frame_id: int
    feedbacks: Dict[str, float]  # speed, gear, rpm, etc.
    timestamp: float


@dataclass
class FrameAction:
    """Action taken at a frame — matches config actions"""
    gas: float = 0.0
    brake: float = 0.0
    steering: float = 0.0
    left: float = 0.0
    right: float = 0.0


@dataclass
class Transition:
    """Complete transition: from_frame --[action]--> to_frame"""
    from_frame: FrameObservation
    action: FrameAction
    to_frame: FrameObservation


class KnowledgeManager:
    """
    Knowledge Graph with one node per frame.

    NO discretization - stores actual observed values.
    Each frame is a unique node.
    Actions are edges between sequential frames.
    """

    def __init__(self, graph_name: str = "knowledge"):
        """
        Initialize knowledge graph.

        Args:
            graph_name: Name for the FalkorDB graph
        """
        self.graph_name = graph_name
        self.graph = None
        self.db = None
        self._connected = False

        # Statistics
        self.stats = {
            'frames_recorded': 0,
            'transitions_recorded': 0,
            'queries_executed': 0,
            'errors': 0
        }

    def connect(self, host: str = 'localhost', port: int = 6379) -> bool:
        """Connect to FalkorDB"""
        try:
            from falkordb import FalkorDB
            self.db = FalkorDB(host=host, port=port)
            self.graph = self.db.select_graph(self.graph_name)
            self._connected = True
            logger.info(f"[KNOWLEDGE] Connected to FalkorDB graph: {self.graph_name}")
            return True
        except Exception as e:
            logger.error(f"[KNOWLEDGE] Connection failed: {e}")
            self._connected = False
            return False

    def is_connected(self) -> bool:
        """Check if connected to database"""
        return self._connected

    def reset(self) -> bool:
        """
        Reset/clear the knowledge graph.

        Call this before testing to ensure clean state.
        """
        if not self._connected:
            logger.error("[KNOWLEDGE] Cannot reset - not connected")
            return False

        try:
            # Delete all nodes and relationships
            self.graph.query("MATCH (n) DETACH DELETE n")

            # Reset stats
            self.stats = {
                'frames_recorded': 0,
                'transitions_recorded': 0,
                'queries_executed': 0,
                'errors': 0
            }

            logger.info("[KNOWLEDGE] Graph reset - all nodes and edges deleted")
            return True

        except Exception as e:
            logger.error(f"[KNOWLEDGE] Reset failed: {e}")
            self.stats['errors'] += 1
            return False

    def record_frame(self, observation: FrameObservation) -> bool:
        """
        Record a single frame observation as a node.

        Args:
            observation: Frame observation with feedbacks

        Returns:
            True if recorded successfully
        """
        if not self._connected:
            logger.error("[KNOWLEDGE] Cannot record - not connected")
            return False

        try:
            # Build properties string
            props = [f"frame_id: {observation.frame_id}"]

            for name, value in observation.feedbacks.items():
                props.append(f"{name}: {value}")

            props.append(f"timestamp: {observation.timestamp}")
            props_str = ", ".join(props)

            # Create node
            query = f"CREATE (:Frame {{{props_str}}})"
            self.graph.query(query)

            self.stats['frames_recorded'] += 1
            logger.debug(f"[KNOWLEDGE] Frame {observation.frame_id} recorded")
            return True

        except Exception as e:
            logger.error(f"[KNOWLEDGE] Failed to record frame: {e}")
            self.stats['errors'] += 1
            return False

    def record_transition(self, transition: Transition) -> bool:
        """
        Record a complete transition: from_frame --[action]--> to_frame

        This creates both frame nodes (if not exist) and the action edge.

        Args:
            transition: Complete transition data

        Returns:
            True if recorded successfully
        """
        if not self._connected:
            logger.error("[KNOWLEDGE] Cannot record - not connected")
            return False

        try:
            from_frame = transition.from_frame
            to_frame = transition.to_frame
            action = transition.action

            # Build from_frame properties
            from_props = [f"frame_id: {from_frame.frame_id}"]
            for name, value in from_frame.feedbacks.items():
                from_props.append(f"{name}: {value}")
            from_props.append(f"timestamp: {from_frame.timestamp}")
            from_props_str = ", ".join(from_props)

            # Build to_frame properties
            to_props = [f"frame_id: {to_frame.frame_id}"]
            for name, value in to_frame.feedbacks.items():
                to_props.append(f"{name}: {value}")
            to_props.append(f"timestamp: {to_frame.timestamp}")
            to_props_str = ", ".join(to_props)

            # Build action properties
            action_props = f"gas: {action.gas}, brake: {action.brake}, steering: {action.steering}, left: {action.left}, right: {action.right}"

            # Use MERGE to create or match nodes, then create edge
            query = f"""
                MERGE (from:Frame {{frame_id: {from_frame.frame_id}}})
                ON CREATE SET {', '.join([f'from.{p.split(":")[0].strip()} = {p.split(":")[1].strip()}' for p in from_props[1:]])}
                MERGE (to:Frame {{frame_id: {to_frame.frame_id}}})
                ON CREATE SET {', '.join([f'to.{p.split(":")[0].strip()} = {p.split(":")[1].strip()}' for p in to_props[1:]])}
                CREATE (from)-[:ACTION {{{action_props}}}]->(to)
            """

            self.graph.query(query)

            self.stats['transitions_recorded'] += 1
            logger.debug(
                f"[KNOWLEDGE] Transition: Frame {from_frame.frame_id} "
                f"--[gas:{action.gas}, brake:{action.brake}, steer:{action.steering}]--> "
                f"Frame {to_frame.frame_id}"
            )
            return True

        except Exception as e:
            logger.error(f"[KNOWLEDGE] Failed to record transition: {e}")
            self.stats['errors'] += 1
            return False

    def record_transition_simple(self,
                                  from_frame_id: int,
                                  from_feedbacks: Dict[str, float],
                                  action: Dict[str, float],
                                  to_frame_id: int,
                                  to_feedbacks: Dict[str, float]) -> bool:
        """
        Simplified transition recording.

        Args:
            from_frame_id: Source frame number
            from_feedbacks: Feedbacks at source frame
            action: Action taken (gas, brake, steering)
            to_frame_id: Target frame number
            to_feedbacks: Feedbacks at target frame

        Returns:
            True if recorded successfully
        """
        import time

        transition = Transition(
            from_frame=FrameObservation(
                frame_id=from_frame_id,
                feedbacks=from_feedbacks,
                timestamp=time.time()
            ),
            action=FrameAction(
                gas=action.get('gas', 0.0),
                brake=action.get('brake', 0.0),
                steering=action.get('steering', 0.0),
                left=action.get('left', 0.0),
                right=action.get('right', 0.0)
            ),
            to_frame=FrameObservation(
                frame_id=to_frame_id,
                feedbacks=to_feedbacks,
                timestamp=time.time()
            )
        )

        return self.record_transition(transition)

    def get_frame(self, frame_id: int) -> Optional[Dict[str, Any]]:
        """
        Get frame observation by ID.

        Args:
            frame_id: Frame number

        Returns:
            Frame data or None if not found
        """
        if not self._connected:
            return None

        try:
            query = f"MATCH (f:Frame {{frame_id: {frame_id}}}) RETURN f"
            result = self.graph.query(query)
            self.stats['queries_executed'] += 1

            if not result.result_set:
                return None

            node = result.result_set[0][0]
            return dict(node.properties)

        except Exception as e:
            logger.error(f"[KNOWLEDGE] Query failed: {e}")
            self.stats['errors'] += 1
            return None

    def get_action_at_frame(self, frame_id: int) -> Optional[Dict[str, float]]:
        """
        Get action taken at a specific frame.

        Args:
            frame_id: Frame number

        Returns:
            Action dict or None if not found
        """
        if not self._connected:
            return None

        try:
            query = f"""
                MATCH (f:Frame {{frame_id: {frame_id}}})-[a:ACTION]->()
                RETURN a.gas, a.brake, a.steering, a.left, a.right
            """
            result = self.graph.query(query)
            self.stats['queries_executed'] += 1

            if not result.result_set:
                return None

            row = result.result_set[0]
            return {
                'gas': row[0],
                'brake': row[1],
                'steering': row[2],
                'left': row[3],
                'right': row[4]
            }

        except Exception as e:
            logger.error(f"[KNOWLEDGE] Query failed: {e}")
            self.stats['errors'] += 1
            return None

    def get_next_frame(self, frame_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the frame that follows after an action.

        Args:
            frame_id: Source frame number

        Returns:
            Next frame data or None
        """
        if not self._connected:
            return None

        try:
            query = f"""
                MATCH (f:Frame {{frame_id: {frame_id}}})-[:ACTION]->(next:Frame)
                RETURN next
            """
            result = self.graph.query(query)
            self.stats['queries_executed'] += 1

            if not result.result_set:
                return None

            node = result.result_set[0][0]
            return dict(node.properties)

        except Exception as e:
            logger.error(f"[KNOWLEDGE] Query failed: {e}")
            self.stats['errors'] += 1
            return None

    def get_transitions_from_frame(self, frame_id: int) -> List[Dict[str, Any]]:
        """
        Get all transitions from a frame.

        Args:
            frame_id: Source frame number

        Returns:
            List of transitions with action and target frame
        """
        if not self._connected:
            return []

        try:
            query = f"""
                MATCH (f:Frame {{frame_id: {frame_id}}})-[a:ACTION]->(next:Frame)
                RETURN a.gas, a.brake, a.steering, a.left, a.right, next.frame_id, next.speed
            """
            result = self.graph.query(query)
            self.stats['queries_executed'] += 1

            transitions = []
            for row in result.result_set:
                transitions.append({
                    'action': {
                        'gas': row[0],
                        'brake': row[1],
                        'steering': row[2],
                        'left': row[3],
                        'right': row[4]
                    },
                    'to_frame_id': row[5],
                    'to_speed': row[6]
                })

            return transitions

        except Exception as e:
            logger.error(f"[KNOWLEDGE] Query failed: {e}")
            self.stats['errors'] += 1
            return []

    def count_frames(self) -> int:
        """Count total frame nodes"""
        if not self._connected:
            return 0

        try:
            result = self.graph.query("MATCH (f:Frame) RETURN count(f)")
            self.stats['queries_executed'] += 1
            return result.result_set[0][0]
        except Exception as e:
            logger.error(f"[KNOWLEDGE] Count failed: {e}")
            return 0

    def count_transitions(self) -> int:
        """Count total action edges"""
        if not self._connected:
            return 0

        try:
            result = self.graph.query("MATCH ()-[a:ACTION]->() RETURN count(a)")
            self.stats['queries_executed'] += 1
            return result.result_set[0][0]
        except Exception as e:
            logger.error(f"[KNOWLEDGE] Count failed: {e}")
            return 0

    def get_statistics(self) -> Dict[str, Any]:
        """Get graph statistics"""
        return {
            'frames': self.count_frames(),
            'transitions': self.count_transitions(),
            'recorded': self.stats.copy()
        }

    def get_all_frames(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get all frames ordered by frame_id.

        Args:
            limit: Maximum number of frames to return

        Returns:
            List of frame data
        """
        if not self._connected:
            return []

        try:
            query = f"""
                MATCH (f:Frame)
                RETURN f.frame_id, f.speed, f.gear, f.rpm, f.timestamp
                ORDER BY f.frame_id
                LIMIT {limit}
            """
            result = self.graph.query(query)
            self.stats['queries_executed'] += 1

            frames = []
            for row in result.result_set:
                frames.append({
                    'frame_id': row[0],
                    'speed': row[1],
                    'gear': row[2],
                    'rpm': row[3],
                    'timestamp': row[4]
                })

            return frames

        except Exception as e:
            logger.error(f"[KNOWLEDGE] Query failed: {e}")
            self.stats['errors'] += 1
            return []

    # -----------------------------------------------------------------
    # ACTION_BIN SUPPORT (Sutton-correct)
    #
    # Bins are CONTROL primitives — agent acts on discovered symbols.
    # Graph structure:
    #   (:ActionBin {bin_id, action, a_min, a_max, label, effect_mean})
    #   (:Frame)-[:ACTION_BIN {bin_id, action, a_min, a_max, label}]->(:Frame)
    # -----------------------------------------------------------------

    def store_action_bins(self, bins_by_action: Dict[str, list]) -> int:
        """
        Store discovered action bins as (:ActionBin) nodes.

        Args:
            bins_by_action: {action_name: [ActionBin.to_dict(), ...]}

        Returns:
            Number of bins stored
        """
        if not self._connected:
            logger.error("[KNOWLEDGE] Cannot store bins - not connected")
            return 0

        count = 0
        try:
            # Clear old bins
            self.graph.query("MATCH (b:ActionBin) DETACH DELETE b")

            for action_name, bins in bins_by_action.items():
                for b in bins:
                    query = (
                        f"CREATE (:ActionBin {{"
                        f"action: '{action_name}', "
                        f"bin_id: {b['bin_id']}, "
                        f"a_min: {b['min']}, "
                        f"a_max: {b['max']}, "
                        f"label: '{b['label']}', "
                        f"effect_mean: {b['effect_mean']}"
                        f"}})"
                    )
                    self.graph.query(query)
                    count += 1

            logger.info(f"[KNOWLEDGE] Stored {count} action bins across {len(bins_by_action)} actions")
            return count

        except Exception as e:
            logger.error(f"[KNOWLEDGE] Failed to store bins: {e}")
            self.stats['errors'] += 1
            return 0

    def resolve_bin(self, action_name: str, value: float,
                    bins_by_action: Dict[str, list]) -> Optional[Dict[str, Any]]:
        """
        Resolve a raw action value to its bin.

        Args:
            action_name: e.g., 'gas'
            value: raw action value
            bins_by_action: {action_name: [ActionBin.to_dict(), ...]}

        Returns:
            Bin dict or None
        """
        bins = bins_by_action.get(action_name, [])
        for b in bins:
            if b['min'] <= value < b['max']:
                return b
        # Fallback: last bin (saturation)
        if bins:
            return bins[-1]
        return None

    def record_transition_binned(
        self,
        from_frame_id: int,
        from_feedbacks: Dict[str, float],
        action: Dict[str, float],
        to_frame_id: int,
        to_feedbacks: Dict[str, float],
        bins_by_action: Dict[str, list]
    ) -> bool:
        """
        Record transition using ACTION_BIN edges (Sutton-correct).

        Instead of:
          (:Frame)-[:ACTION {gas: 0.7}]->(:Frame)

        Records:
          (:Frame)-[:ACTION_BIN {bin_id: 3, action: 'gas', a_min: 0.7, a_max: 1.1,
                                  label: 'HIGH', effect_mean: 0.85}]->(:Frame)

        This is the Sutton requirement: agent acts on discovered symbols,
        not raw floats. Bins are CONTROL primitives.
        """
        if not self._connected:
            logger.error("[KNOWLEDGE] Cannot record - not connected")
            return False

        try:
            import time as _time

            # Build from/to frame props
            from_props = [f"frame_id: {from_frame_id}"]
            for name, value in from_feedbacks.items():
                from_props.append(f"{name}: {value}")
            from_props.append(f"timestamp: {_time.time()}")

            to_props = [f"frame_id: {to_frame_id}"]
            for name, value in to_feedbacks.items():
                to_props.append(f"{name}: {value}")
            to_props.append(f"timestamp: {_time.time()}")

            # Create frame nodes
            from_props_str = ", ".join(from_props)
            to_props_str = ", ".join(to_props)

            # For each action, resolve to bin and create ACTION_BIN edge
            for action_name, action_value in action.items():
                b = self.resolve_bin(action_name, action_value, bins_by_action)
                if b is None:
                    continue

                if abs(action_value) < 1e-8 and b.get('bin_id', -1) == 0:
                    continue  # Skip dead-zone zero actions

                bin_props = (
                    f"bin_id: {b['bin_id']}, "
                    f"action: '{action_name}', "
                    f"raw_value: {action_value}, "
                    f"a_min: {b['min']}, "
                    f"a_max: {b['max']}, "
                    f"label: '{b['label']}', "
                    f"effect_mean: {b['effect_mean']}"
                )

                query = f"""
                    MERGE (from:Frame {{frame_id: {from_frame_id}}})
                    ON CREATE SET {', '.join([f'from.{p.split(":")[0].strip()} = {p.split(":")[1].strip()}' for p in from_props[1:]])}
                    MERGE (to:Frame {{frame_id: {to_frame_id}}})
                    ON CREATE SET {', '.join([f'to.{p.split(":")[0].strip()} = {p.split(":")[1].strip()}' for p in to_props[1:]])}
                    CREATE (from)-[:ACTION_BIN {{{bin_props}}}]->(to)
                """
                self.graph.query(query)

            self.stats['transitions_recorded'] += 1
            return True

        except Exception as e:
            logger.error(f"[KNOWLEDGE] Failed to record binned transition: {e}")
            self.stats['errors'] += 1
            return False

    def count_bin_transitions(self) -> int:
        """Count ACTION_BIN edges"""
        if not self._connected:
            return 0
        try:
            result = self.graph.query("MATCH ()-[a:ACTION_BIN]->() RETURN count(a)")
            self.stats['queries_executed'] += 1
            return result.result_set[0][0]
        except Exception:
            return 0

    def get_bin_transitions_from_frame(self, frame_id: int) -> List[Dict[str, Any]]:
        """Get ACTION_BIN transitions from a frame"""
        if not self._connected:
            return []
        try:
            query = f"""
                MATCH (f:Frame {{frame_id: {frame_id}}})-[a:ACTION_BIN]->(next:Frame)
                RETURN a.bin_id, a.action, a.label, a.raw_value,
                       a.a_min, a.a_max, a.effect_mean,
                       next.frame_id, next.speed
            """
            result = self.graph.query(query)
            self.stats['queries_executed'] += 1

            transitions = []
            for row in result.result_set:
                transitions.append({
                    'bin_id': row[0],
                    'action': row[1],
                    'label': row[2],
                    'raw_value': row[3],
                    'a_min': row[4],
                    'a_max': row[5],
                    'effect_mean': row[6],
                    'to_frame_id': row[7],
                    'to_speed': row[8]
                })
            return transitions

        except Exception as e:
            logger.error(f"[KNOWLEDGE] Query failed: {e}")
            self.stats['errors'] += 1
            return []

    def find_similar_state(self,
                          speed: float,
                          tolerance: float = 1.0) -> List[Dict[str, Any]]:
        """
        Find frames with similar speed (for learning).

        This is how we can find "similar" states without discretization.
        We use a tolerance range instead of bins.

        Args:
            speed: Target speed to find
            tolerance: Speed tolerance (+/- range)

        Returns:
            List of frames within tolerance
        """
        if not self._connected:
            return []

        try:
            min_speed = speed - tolerance
            max_speed = speed + tolerance

            query = f"""
                MATCH (f:Frame)
                WHERE f.speed >= {min_speed} AND f.speed <= {max_speed}
                RETURN f.frame_id, f.speed, f.gear, f.rpm
                ORDER BY abs(f.speed - {speed})
                LIMIT 10
            """
            result = self.graph.query(query)
            self.stats['queries_executed'] += 1

            frames = []
            for row in result.result_set:
                frames.append({
                    'frame_id': row[0],
                    'speed': row[1],
                    'gear': row[2],
                    'rpm': row[3],
                    'distance': abs(row[1] - speed)
                })

            return frames

        except Exception as e:
            logger.error(f"[KNOWLEDGE] Query failed: {e}")
            self.stats['errors'] += 1
            return []


    # -----------------------------------------------------------------
    # REQ-D01: Resolution = min action effect
    # REQ-D03: Do not record beyond system precision
    # -----------------------------------------------------------------

    def round_to_resolution(
        self, value: float, min_delta: float, precision: int = 7
    ) -> float:
        """Round a state value to the knowledge graph resolution.

        REQ-D01: "our minimum is 0.1... does it make sense for me to register
        the position variation in 0.01... no... because the minimum is 0.1"
        REQ-D03: "can I be on 5.15? No... because the precision is 0.1"

        Args:
            value: Raw state value
            min_delta: Minimum action effect (graph interval size)
            precision: Feedback decimal precision
        """
        if min_delta > 0:
            value = round(value / min_delta) * min_delta
        return round(value, precision)

    # -----------------------------------------------------------------
    # REQ-D04: Bins define all possible transitions
    # -----------------------------------------------------------------

    def enumerate_reachable_states(
        self,
        current_speed: float,
        bins_by_action: Dict[str, list],
        min_deltas: Dict[str, float] = None,
    ) -> List[Dict[str, Any]]:
        """Enumerate all reachable next-states from bins.

        REQ-D04: "the system already understands what are the possibilities
        to go from one place to the other in the graph based on the bins"

        Given state S, reachable = S +/- k*min_delta for each bin k.

        Args:
            current_speed: Current speed state
            bins_by_action: Discovered bins per action
            min_deltas: {action_name: min_delta} from discovery

        Returns:
            List of {action, bin_label, bin_id, predicted_speed}
        """
        reachable = []
        for action_name, bins in bins_by_action.items():
            for b in bins:
                if b.get('bin_id', 0) == 0:
                    continue  # Skip dead zone
                effect = b.get('effect_mean', 0)
                if action_name == 'brake':
                    predicted = max(0, current_speed - effect)
                else:
                    predicted = current_speed + effect
                reachable.append({
                    'action': action_name,
                    'bin_label': b.get('label', ''),
                    'bin_id': b.get('bin_id', 0),
                    'predicted_speed': predicted,
                    'effect': effect,
                })
        return reachable


# =============================================================================
# FRAME RECORDER - Records frames from live environment
# =============================================================================

class FrameRecorder:
    """
    Records frames from live environment to knowledge graph.

    Usage:
        recorder = FrameRecorder(knowledge_graph)
        recorder.start_recording()

        # In game loop:
        recorder.record(feedbacks, action)

        recorder.stop_recording()
    """

    def __init__(self, knowledge: KnowledgeManager):
        """
        Initialize frame recorder.

        Args:
            knowledge: KnowledgeManager instance
        """
        self.knowledge = knowledge
        self.current_frame = 0
        self.last_feedbacks = None
        self.last_action = None
        self._recording = False

    def start_recording(self, reset_knowledge: bool = True):
        """
        Start recording frames.

        Args:
            reset_knowledge: If True, clears existing knowledge
        """
        if reset_knowledge:
            self.knowledge.reset()

        self.current_frame = 0
        self.last_feedbacks = None
        self.last_action = None
        self._recording = True

        logger.info("[RECORDER] Started recording")

    def stop_recording(self):
        """Stop recording frames"""
        self._recording = False
        logger.info(
            f"[RECORDER] Stopped. Recorded {self.current_frame} frames, "
            f"{self.knowledge.stats['transitions_recorded']} transitions"
        )

    def record(self, feedbacks: Dict[str, float], action: Dict[str, float]) -> bool:
        """
        Record one frame.

        Call this every frame with current feedbacks and action taken.

        Args:
            feedbacks: Current feedback values (speed, gear, rpm, etc.)
            action: Action being taken (gas, brake, steering)

        Returns:
            True if recorded successfully
        """
        if not self._recording:
            return False

        # If we have a previous frame, record the transition
        if self.last_feedbacks is not None and self.last_action is not None:
            success = self.knowledge.record_transition_simple(
                from_frame_id=self.current_frame - 1,
                from_feedbacks=self.last_feedbacks,
                action=self.last_action,
                to_frame_id=self.current_frame,
                to_feedbacks=feedbacks
            )

            if not success:
                logger.warning(f"[RECORDER] Failed to record frame {self.current_frame}")

        # Store for next frame
        self.last_feedbacks = feedbacks.copy()
        self.last_action = action.copy()
        self.current_frame += 1

        return True

    def is_recording(self) -> bool:
        """Check if currently recording"""
        return self._recording

    def get_frame_count(self) -> int:
        """Get current frame count"""
        return self.current_frame


class EpisodeRecorder:
    """
    Backward compatibility wrapper for FrameRecorder.

    Used by SystemCoordinatorCorrected which expects the old EpisodeRecorder API.
    This wraps the new FrameRecorder to provide compatibility.
    """

    def __init__(self, knowledge: KnowledgeManager, timestamps=None):
        """
        Initialize with knowledge manager and optional timestamps.

        Args:
            knowledge: KnowledgeManager instance
            timestamps: TimestampManager instance (unused in new API, kept for compatibility)
        """
        self.knowledge = knowledge
        self.timestamps = timestamps  # Not used in new per-frame approach
        self.frame_recorder = FrameRecorder(knowledge)
        self._episode_count = 0
        self._frame_count = 0

    def start_episode(self):
        """Start a new episode recording"""
        self._episode_count += 1
        self.frame_recorder.start_recording(reset_knowledge=False)

    def end_episode(self):
        """End current episode recording"""
        self.frame_recorder.stop_recording()

    def record_frame(self, feedbacks: Dict[str, float], action: Dict[str, float]) -> bool:
        """Record a single frame"""
        return self.frame_recorder.record(feedbacks, action)

    def record_tmrl_memory(self, memory, start_index: int = 0, count: int = None) -> int:
        """
        Record frames from TMRL memory format.

        This is a compatibility method for the old API.

        Args:
            memory: TMRL memory object (list of experiences)
            start_index: Starting index in memory
            count: Number of frames to record (None = all)

        Returns:
            Number of frames recorded
        """
        if not memory:
            return 0

        if count is None:
            count = len(memory) - start_index

        recorded = 0
        self.frame_recorder.start_recording(reset_knowledge=False)

        for i in range(start_index, min(start_index + count, len(memory))):
            try:
                # TMRL memory format: (obs, act, rew, terminated, truncated, info)
                obs, act, _, _, _, info = memory[i]

                # Extract feedbacks from observation
                feedbacks = {
                    'speed': float(obs.get('speed', 0)) if isinstance(obs, dict) else 0.0,
                    'gear': float(obs.get('gear', 0)) if isinstance(obs, dict) else 0.0,
                    'rpm': float(obs.get('rpm', 0)) if isinstance(obs, dict) else 0.0
                }

                # Extract action
                if isinstance(act, dict):
                    action = {
                        'gas': float(act.get('gas', 0)),
                        'brake': float(act.get('brake', 0)),
                        'steering': float(act.get('steering', 0))
                    }
                elif hasattr(act, '__iter__'):
                    # Array format: [gas, brake, steering]
                    act_list = list(act)
                    action = {
                        'gas': float(act_list[0]) if len(act_list) > 0 else 0.0,
                        'brake': float(act_list[1]) if len(act_list) > 1 else 0.0,
                        'steering': float(act_list[2]) if len(act_list) > 2 else 0.0
                    }
                else:
                    action = {'gas': 0.0, 'brake': 0.0, 'steering': 0.0}

                if self.frame_recorder.record(feedbacks, action):
                    recorded += 1

            except Exception as e:
                logger.warning(f"[EPISODE_RECORDER] Failed to record frame {i}: {e}")
                continue

        self.frame_recorder.stop_recording()
        self._frame_count += recorded
        return recorded

    def get_episode_count(self) -> int:
        """Get number of episodes recorded"""
        return self._episode_count

    def get_frame_count(self) -> int:
        """Get total frames recorded"""
        return self.frame_recorder.get_frame_count()
