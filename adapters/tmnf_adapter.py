"""
TMNF ADAPTER — TrackMania Nations Forever via TMInterface 2.x (TCP socket bridge)

This adapter communicates with the AgenticBridge.as AngelScript plugin via TCP.
The plugin is loaded by TMInterface 2.x (ModLoader) and exposes a TCP socket
that pauses the game on each physics tick until Python responds.

REQUIRES:
  - TMinterface/AgenticBridge.as installed in TMInterface Plugins folder
  - TMNF running via TMInterface 2.x (ModLoader)
  - An active race (countdown finished or in progress)

ARCHITECTURE:
  - Background thread reads SCRunStepSync messages from game
  - Main thread calls get_feedbacks(), send_action_dict(), wait_one_tick()
  - Events synchronize the two threads

TMNF INPUT FACTS:
  - Gas:      BINARY only (InputType::Up). No analog throttle in TMNF.
  - Brake:    BINARY only (InputType::Down).
  - Steering: ANALOG (InputType::Steer, range -65536 to +65536).

PROTOCOL:
  Based on Linesight-RL tminterface2.py, extended with analog steer in CSetInputState:
    [int32 type][uint8 left][uint8 right][uint8 accel][uint8 brake][int32 steer_analog]
"""

import logging
import socket
import struct
import threading
import time
import math
from typing import Dict, Optional, Any
from enum import IntEnum, auto

import numpy as np

logger = logging.getLogger(__name__)

# =============================================================================
# PROTOCOL
# =============================================================================

HOST = "127.0.0.1"
DEFAULT_PORT = 8476
TICK_MS = 10  # TMNF physics tick duration in milliseconds

# Analog range for steering
ANALOG_MAX = 65536


class MessageType(IntEnum):
    SC_RUN_STEP_SYNC               = 1   # Game -> Python: new tick (int32 race_time follows)
    SC_CHECKPOINT_COUNT_CHANGED_SYNC = 2 # Game -> Python: checkpoint crossed
    SC_LAP_COUNT_CHANGED_SYNC      = 3   # Game -> Python: lap count changed
    SC_REQUESTED_FRAME_SYNC        = 4
    SC_ON_CONNECT_SYNC             = 5   # Game -> Python: initial handshake
    C_SET_SPEED                    = 6   # Python -> Game: float32 speed
    C_REWIND_TO_STATE              = 7   # Python -> Game: int32 len + bytes
    C_REWIND_TO_CURRENT_STATE      = 8
    C_GET_SIMULATION_STATE         = 9   # Python -> Game: (no payload) -> int32 len + bytes
    C_SET_INPUT_STATE              = 10  # Python -> Game: uint8*4 + int32 steer
    C_GIVE_UP                      = 11  # Python -> Game: restart race
    C_PREVENT_SIMULATION_FINISH    = 12
    C_SHUTDOWN                     = 13  # Python -> Game: disconnect
    C_EXECUTE_COMMAND              = 14  # Python -> Game: int32 len + string bytes
    C_SET_TIMEOUT                  = 15  # Python -> Game: int32 ms (no-op in 2.x)
    C_RACE_FINISHED                = 16


# =============================================================================
# INPUT CONVERSION
# =============================================================================

def float_to_steer(value: float) -> int:
    """Convert float -1.0..+1.0 to int -65536..+65536."""
    return int(max(-1.0, min(1.0, value)) * ANALOG_MAX)


# =============================================================================
# SAVED STATE WRAPPER
# =============================================================================

class SavedState:
    """Wraps raw state bytes from CGetSimulationState for CRewindToState."""

    def __init__(self, data: bytes):
        self.data = data

    def __len__(self) -> int:
        return len(self.data)


# =============================================================================
# FEEDBACK EXTRACTION
# =============================================================================

def _extract_feedbacks_from_sim_state(state_bytes: bytes, race_time: int) -> Dict[str, float]:
    """
    Parse binary SimStateData from TMInterface into a feedbacks dict.

    TMInterface SimStateData binary layout (version-dependent offsets).
    We extract the fields we need using known offsets from the tminterface
    Python package structs (SimStateData). Fields that cannot be parsed
    safely are omitted (partial state is acceptable for discovery).

    Falls back to minimal feedbacks dict on any parse error.
    """
    try:
        from tminterface.structs import SimStateData, CheckpointData
        state = SimStateData(state_bytes)
        # Resize checkpoint arrays to avoid access-out-of-bounds
        try:
            state.cp_data.resize(CheckpointData.cp_states_field, state.cp_data.cp_states_length)
            state.cp_data.resize(CheckpointData.cp_times_field, state.cp_data.cp_times_length)
        except Exception:
            pass

        return _parse_sim_state(state, race_time)
    except Exception as e:
        logger.debug(f"[TMNF] SimStateData parse error: {e}")
        return {'speed': 0.0, 'pos_x': 0.0, 'pos_y': 0.0, 'pos_z': 0.0,
                'race_time': float(race_time)}


def _parse_sim_state(state, race_time: int) -> Dict[str, float]:
    """Extract telemetry fields from a parsed SimStateData object."""
    try:
        pos = state.position
        vel = state.velocity
        ypr = state.yaw_pitch_roll

        # Speed from velocity vector (m/s -> km/h)
        speed_ms = math.sqrt(vel[0]**2 + vel[1]**2 + vel[2]**2)
        speed_kmh = speed_ms * 3.6

        car = state.scene_mobil
        dyna = state.dyna.current_state
        sync = car.sync_vehicle_state

        fb = {
            # Speed
            'speed':          speed_kmh,
            'display_speed':  float(state.display_speed),
            'speed_forward':  sync.speed_forward,
            'speed_sideward': sync.speed_sideward,

            # Position (world coordinates)
            'pos_x': pos[0],
            'pos_y': pos[1],
            'pos_z': pos[2],

            # Velocity vector (m/s)
            'velocity_x': vel[0],
            'velocity_y': vel[1],
            'velocity_z': vel[2],

            # Orientation (radians)
            'yaw':   ypr[0],
            'pitch': ypr[1],
            'roll':  ypr[2],

            # Applied inputs (confirmation of what game received)
            'input_gas':   sync.input_gas,
            'input_brake': sync.input_brake,
            'input_steer': sync.input_steer,

            # Engine
            'rpm':            sync.rpm,
            'gear':           float(car.engine.gear),
            'max_rpm':        car.engine.max_rpm,
            'actual_rpm':     car.engine.actual_rpm,
            'braking_factor': car.engine.braking_factor,

            # Forces (from rigid body dynamics)
            'force_x':   dyna.force[0],
            'force_y':   dyna.force[1],
            'force_z':   dyna.force[2],
            'torque_x':  dyna.torque[0],
            'torque_y':  dyna.torque[1],
            'torque_z':  dyna.torque[2],

            # Angular speed
            'angular_speed_x': dyna.angular_speed[0],
            'angular_speed_y': dyna.angular_speed[1],
            'angular_speed_z': dyna.angular_speed[2],

            # Race info
            'race_time': float(race_time),
            'finished':  1.0 if state.player_info.race_finished else 0.0,
        }

        # Wheel contact (4 wheels)
        try:
            for i, wheel in enumerate(state.simulation_wheels):
                rt = wheel.real_time_state
                fb[f'wheel_{i}_ground']   = 1.0 if rt.has_ground_contact else 0.0
                fb[f'wheel_{i}_sliding']  = 1.0 if rt.is_sliding else 0.0
                fb[f'wheel_{i}_material'] = float(rt.contact_material_id)
                fb[f'wheel_{i}_damper']   = rt.damper_absorb
        except Exception:
            pass

        return fb

    except Exception as e:
        logger.error(f"[TMNF] State extraction error: {e}")
        return {'speed': 0.0, 'pos_x': 0.0, 'pos_y': 0.0, 'pos_z': 0.0,
                'race_time': float(race_time)}


# =============================================================================
# TMNF SOCKET CLIENT (background thread)
# =============================================================================

class _TMNFSocketClient:
    """
    Low-level TCP client. Runs in a background thread, reads messages from
    the AgenticBridge.as plugin.

    Synchronization:
      - tick_ready: set when SCRunStepSync arrives (main thread unblocks)
      - tick_ack:   set when main thread is done processing (background unblocks)
    """

    def __init__(self, host: str = HOST, port: int = DEFAULT_PORT):
        self._host = host
        self._port = port
        self._sock: Optional[socket.socket] = None
        self._lock = threading.Lock()

        # Connection state
        self._connected = False

        # Current tick state (written by background, read by main)
        self._race_time: int = -1
        self._state_bytes: Optional[bytes] = None
        self._feedbacks: Dict[str, float] = {}

        # Saved state for rewind
        self._saved_state: Optional[SavedState] = None

        # Threading events
        self.tick_ready = threading.Event()   # Background -> Main: tick available
        self.tick_ack   = threading.Event()   # Main -> Background: done, advance game

        # Statistics
        self.ticks_processed: int = 0
        self.actions_applied: int = 0

        # Pending action (set by main before tick_ack)
        self._pending_action: Optional[Dict] = None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self, timeout: float = 60.0) -> bool:
        """Connect to AgenticBridge.as TCP server. Returns True on success."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                sock.settimeout(5.0)
                sock.connect((self._host, self._port))
                sock.settimeout(None)   # Blocking after connect
                self._sock = sock
                self._connected = True
                logger.info(f"[TMNF] Connected to {self._host}:{self._port}")
                return True
            except (ConnectionRefusedError, OSError):
                time.sleep(0.5)

        logger.error(f"[TMNF] Connection timeout after {timeout}s")
        return False

    def disconnect(self):
        """Send shutdown and close socket."""
        if self._sock and self._connected:
            try:
                self._send_raw(struct.pack("i", int(MessageType.C_SHUTDOWN)))
            except Exception:
                pass
            try:
                self._sock.close()
            except Exception:
                pass
        self._connected = False
        # Unblock any waiting threads
        self.tick_ready.set()
        self.tick_ack.set()

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------

    def run_receive_loop(self):
        """
        Background thread: reads messages from game and processes them.

        On each SCRunStepSync:
          1. Read full simulation state (CGetSimulationState)
          2. Signal main thread (tick_ready)
          3. Wait for main thread to provide action (tick_ack)
          4. Apply pending action (CSetInputState)
          5. Respond to game (send SCRunStepSync ack) — game unpauses
        """
        try:
            # Wait for initial handshake (SCOnConnectSync = 5)
            msg_type = self._read_int32()
            if msg_type == int(MessageType.SC_ON_CONNECT_SYNC):
                logger.info("[TMNF] Handshake received (SCOnConnectSync)")
                # Ack handshake — plugin WaitForResponse expects this
                self._send_raw(struct.pack("i", int(MessageType.SC_ON_CONNECT_SYNC)))
            else:
                logger.warning(f"[TMNF] Expected handshake (5), got {msg_type}")

            while self._connected:
                msg_type = self._read_int32()
                if msg_type is None:
                    logger.info("[TMNF] Connection closed by game")
                    break

                self._dispatch(msg_type)

        except Exception as e:
            if self._connected:
                logger.error(f"[TMNF] Receive loop error: {e}", exc_info=True)
        finally:
            self._connected = False
            self.tick_ready.set()   # Unblock main thread if waiting

    def _dispatch(self, msg_type: int):
        """Dispatch a message received from the game."""
        if msg_type == int(MessageType.SC_RUN_STEP_SYNC):
            self._handle_run_step()

        elif msg_type == int(MessageType.SC_CHECKPOINT_COUNT_CHANGED_SYNC):
            current = self._read_int32()
            target  = self._read_int32()
            logger.debug(f"[TMNF] Checkpoint {current}/{target}")
            # Ack checkpoint — game is waiting
            self._send_raw(struct.pack("i", int(MessageType.SC_CHECKPOINT_COUNT_CHANGED_SYNC)))

        elif msg_type == int(MessageType.SC_LAP_COUNT_CHANGED_SYNC):
            current = self._read_int32()
            logger.debug(f"[TMNF] Lap {current}")
            self._send_raw(struct.pack("i", int(MessageType.SC_LAP_COUNT_CHANGED_SYNC)))

        else:
            logger.debug(f"[TMNF] Unhandled message type: {msg_type}")

    def _handle_run_step(self):
        """
        Process one physics tick.

        SCRunStepSync arrives -> read state -> signal main -> wait for action
        -> apply action -> ack SCRunStepSync -> game unpauses.
        """
        race_time = self._read_int32()
        self._race_time = race_time

        # Fetch simulation state from game
        state_bytes = self._fetch_simulation_state()
        if state_bytes:
            self._state_bytes = state_bytes
            self._feedbacks = _extract_feedbacks_from_sim_state(state_bytes, race_time)

        self.ticks_processed += 1

        # Signal main thread: tick data is ready
        self.tick_ready.set()

        # Wait for main thread to provide action (timeout = 30s)
        got_action = self.tick_ack.wait(timeout=30.0)
        self.tick_ack.clear()

        if got_action and self._pending_action is not None:
            self._send_set_input_state(self._pending_action)
            self._pending_action = None
            self.actions_applied += 1

        # Respond to SCRunStepSync — this unpauses the game
        self._send_raw(struct.pack("i", int(MessageType.SC_RUN_STEP_SYNC)))

    # ------------------------------------------------------------------
    # Commands: Python -> Game
    # ------------------------------------------------------------------

    def _fetch_simulation_state(self) -> Optional[bytes]:
        """Send CGetSimulationState, read state bytes back."""
        try:
            self._send_raw(struct.pack("i", int(MessageType.C_GET_SIMULATION_STATE)))
            length = self._read_int32()
            if length is None or length <= 0:
                return None
            data = self._recv_exact(length)
            return data
        except Exception as e:
            logger.error(f"[TMNF] CGetSimulationState error: {e}")
            return None

    def _send_set_input_state(self, action: Dict):
        """
        Send CSetInputState (extended protocol with analog steer).

        Layout: [int32 type][uint8 left][uint8 right][uint8 accel][uint8 brake][int32 steer]

        Faithful uint8 quantization (Sutton: "first find the system's precision"):
          float [0,1] -> round(val * 255) -> uint8 [0,255]
          The plugin treats uint8 > 0 as ON, so the TRUE system boundary
          is at the rounding threshold: ~1/510 rounds to 0, ~1/255 rounds to 1.
          Discovery finds this boundary at ~0.00392 (1/255) instead of the
          old hardcoded > 0.0 which hid the real wire resolution.
        """
        gas_val   = action.get('gas', 0.0)
        brake_val = action.get('brake', 0.0)
        steer_val = action.get('steering', 0.0)

        # Faithful uint8 quantization — no hardcoded > 0.0 threshold.
        # The discovery algorithm finds the real boundary at ~1/255 = 0.00392.
        # (Sutton: "bins figured out by the system")
        accel = np.uint8(min(255, max(0, round(gas_val * 255))))
        brake = np.uint8(min(255, max(0, round(brake_val * 255))))

        # Digital left/right steering (Linesight-RL compatible, faithful uint8)
        left  = np.uint8(min(255, max(0, round(action.get('left', 0) * 255))))
        right = np.uint8(min(255, max(0, round(action.get('right', 0) * 255))))

        steer = np.int32(float_to_steer(steer_val))

        payload = struct.pack(
            "iBBBBi",
            int(MessageType.C_SET_INPUT_STATE),
            int(left), int(right), int(accel), int(brake),
            int(steer)
        )
        self._send_raw(payload)

    def fetch_state_now(self) -> Optional[bytes]:
        """Fetch current simulation state (call only from main thread during tick)."""
        return self._fetch_simulation_state()

    def send_rewind_to_state(self, state: SavedState):
        """Send CRewindToState with saved bytes."""
        header = struct.pack("ii", int(MessageType.C_REWIND_TO_STATE), len(state.data))
        self._send_raw(header + state.data)

    def send_set_speed(self, speed: float):
        """Send CSetSpeed."""
        self._send_raw(struct.pack("if", int(MessageType.C_SET_SPEED), np.float32(speed)))

    def send_give_up(self):
        """Send CGiveUp (restart race)."""
        self._send_raw(struct.pack("i", int(MessageType.C_GIVE_UP)))

    def send_execute_command(self, command: str):
        """Send CExecuteCommand."""
        encoded = command.encode('utf-8')
        header = struct.pack("ii", int(MessageType.C_EXECUTE_COMMAND), len(encoded))
        self._send_raw(header + encoded)

    # ------------------------------------------------------------------
    # Socket primitives
    # ------------------------------------------------------------------

    def _send_raw(self, data: bytes):
        """Send raw bytes to socket (thread-safe)."""
        with self._lock:
            if self._sock and self._connected:
                self._sock.sendall(data)

    def _recv_exact(self, n: int) -> Optional[bytes]:
        """Receive exactly n bytes (MSG_WAITALL not supported on Windows)."""
        buf = b''
        while len(buf) < n:
            try:
                chunk = self._sock.recv(n - len(buf))
                if not chunk:
                    return None
                buf += chunk
            except Exception:
                return None
        return buf

    def _read_int32(self) -> Optional[int]:
        """Read 4 bytes from socket, return int32. Returns None on error."""
        data = self._recv_exact(4)
        if not data or len(data) < 4:
            return None
        return struct.unpack("i", data)[0]


# =============================================================================
# TMNF ADAPTER — Public API
# =============================================================================

class TMNFAdapter:
    """
    Adapter connecting ExperimentationCoordinator (Sutton algorithm) to TMNF
    via TMInterface 2.x AngelScript TCP bridge.

    Public API (same as old mmap-based adapter):
      connect(port)          -> TCP connect to AgenticBridge.as plugin
      get_feedbacks()        -> Dict[str, float] (speed, position, yaw, etc.)
      send_action_dict(a)    -> sends CSetInputState (binary gas/brake + analog steer)
      wait_one_tick()        -> advances game one 10ms physics tick
      save_state()           -> saves current SimStateData bytes
      rewind()               -> rewinds to saved state
      set_speed(float)       -> game speed multiplier
      give_up()              -> restart race
      is_connected()         -> bool
      stop()                 -> disconnect and clean up

    TMNF Input quantization (faithful uint8):
      gas:      float [0,1] -> round(val*255) -> uint8 [0,255]
                Plugin: uint8 > 0 = gas ON. Boundary at ~1/255 = 0.00392.
      brake:    float [0,1] -> round(val*255) -> uint8 [0,255]
                Plugin: uint8 > 0 = brake ON. Boundary at ~1/255 = 0.00392.
      left:     float [0,1] -> round(val*255) -> uint8 [0,255]
                Plugin: uint8 > 0 = key ON. Boundary at ~1/255 = 0.00392.
      right:    float [0,1] -> round(val*255) -> uint8 [0,255]
                Plugin: uint8 > 0 = key ON. Boundary at ~1/255 = 0.00392.
      steering: float [-1,+1] -> int(val*65536) -> int32 [-65536,+65536]

    Threading model:
      Background thread (_recv_thread) runs _TMNFSocketClient.run_receive_loop().
      Main thread calls adapter methods sequentially.
      Events tick_ready / tick_ack synchronize them.
    """

    def __init__(self):
        self._client: Optional[_TMNFSocketClient] = None
        self._recv_thread: Optional[threading.Thread] = None
        self._running = False

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self, port: int = DEFAULT_PORT, timeout: float = 60.0) -> bool:
        """
        Connect to AgenticBridge.as TCP plugin.

        Blocks until connection is established or timeout expires.
        The game must be running with the plugin loaded and a race active.

        Args:
            port:    TCP port (default 8476, matches AgenticBridge.as DEFAULT_PORT)
            timeout: Maximum seconds to wait for connection

        Returns:
            True if connected successfully, False on timeout.
        """
        logger.info(f"[TMNF_ADAPTER] Connecting to port {port}...")
        logger.info("[TMNF_ADAPTER] Make sure TMNF is running with AgenticBridge.as plugin loaded")

        self._client = _TMNFSocketClient(host=HOST, port=port)

        if not self._client.connect(timeout=timeout):
            return False

        # Start background receive loop
        self._running = True
        self._recv_thread = threading.Thread(
            target=self._client.run_receive_loop,
            name="tmnf-recv",
            daemon=True
        )
        self._recv_thread.start()

        logger.info("[TMNF_ADAPTER] Connected. Waiting for first tick...")
        return True

    def wait_for_race(self, timeout: float = 120.0) -> bool:
        """
        Wait until the race is running (race_time >= 0).

        The game sends SCRunStepSync messages only during an active race.
        Block here until we see the first tick.

        Returns:
            True when race is running, False on timeout.
        """
        logger.info("[TMNF_ADAPTER] Waiting for race to start...")
        t0 = time.time()
        while True:
            if not self._client._connected:
                logger.error("[TMNF_ADAPTER] Disconnected while waiting for race")
                return False
            if self._client.ticks_processed > 0:
                logger.info(f"[TMNF_ADAPTER] Race active at t={self._client._race_time}ms")
                return True
            if time.time() - t0 > timeout:
                logger.error(f"[TMNF_ADAPTER] Race start timeout ({timeout}s)")
                return False
            # Wait for first tick signal
            self._client.tick_ready.wait(timeout=1.0)

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def get_feedbacks(self) -> Dict[str, float]:
        """
        Return current tick's telemetry dict.

        Must be called AFTER wait_one_tick() or at start of tick window.
        Does NOT advance the game — call wait_one_tick() to do that.

        Returns dict with keys including:
          speed (km/h), pos_x/y/z, velocity_x/y/z,
          yaw/pitch/roll (radians), race_time (ms),
          input_gas, input_brake, input_steer, rpm, gear, ...
        """
        self._client.tick_ready.wait(timeout=10.0)
        return dict(self._client._feedbacks)

    def send_action_dict(self, action: Dict[str, float]) -> bool:
        """
        Queue an action to apply this tick.

        Call this before wait_one_tick(). The action is sent to the game
        when wait_one_tick() releases the tick.

        Args:
            action: Dict with keys:
              'gas':      0.0 to 1.0  (>0.001 = full gas, binary in TMNF)
              'brake':    0.0 to 1.0  (>0.001 = full brake, binary in TMNF)
              'steering': -1.0 to +1.0 (analog, maps to -65536..+65536)

        Returns:
            True always (action queued).
        """
        self._client._pending_action = {
            'gas':      action.get('gas', 0.0),
            'brake':    action.get('brake', 0.0),
            'steering': action.get('steering', 0.0),
            'left':     action.get('left', 0.0),
            'right':    action.get('right', 0.0),
        }
        return True

    def wait_one_tick(self):
        """
        Advance the game by one 10ms physics tick.

        Flow:
          1. Clears tick_ready (we've consumed current tick's state)
          2. Sets tick_ack (tells background thread: apply action, ack game)
          3. Waits for tick_ready (blocks until next tick's state arrives)

        After this returns, get_feedbacks() will return the new state.
        """
        # Clear current tick's signal
        self._client.tick_ready.clear()

        # Release background thread to apply action and ack game
        self._client.tick_ack.set()

        # Wait for next tick's state
        self._client.tick_ready.wait(timeout=10.0)

    # ------------------------------------------------------------------
    # TMInterface-specific features
    # ------------------------------------------------------------------

    def save_state(self) -> bool:
        """
        Save current simulation state for later rewind.

        The state is saved from the most recently received tick's bytes.
        Use before a probe sequence to enable independent probes:
        each probe rewinds to the same starting state (Pong-like).

        Returns:
            True if state was saved, False if no state available yet.
        """
        if self._client._state_bytes is not None:
            self._client._saved_state = SavedState(self._client._state_bytes)
            logger.info(f"[TMNF_ADAPTER] State saved at t={self._client._race_time}ms "
                        f"({len(self._client._saved_state)} bytes)")
            return True
        logger.warning("[TMNF_ADAPTER] No state bytes available to save")
        return False

    def rewind(self) -> bool:
        """
        Rewind to previously saved state.

        After rewind the game is at the EXACT same state as when save_state()
        was called. Fully deterministic — same action will produce same delta.

        Must be called during a tick window (between tick_ready and tick_ack).

        Returns:
            True if rewind was sent, False if no saved state or not connected.
        """
        if self._client._saved_state is None:
            logger.error("[TMNF_ADAPTER] No saved state to rewind to")
            return False

        if not self._client._connected:
            logger.error("[TMNF_ADAPTER] Not connected")
            return False

        self._client.send_rewind_to_state(self._client._saved_state)
        # Update local feedbacks to reflect saved state
        self._client._feedbacks = _extract_feedbacks_from_sim_state(
            self._client._saved_state.data,
            self._client._race_time
        )
        logger.debug("[TMNF_ADAPTER] Rewound to saved state")
        return True

    def get_full_state(self) -> Optional[SavedState]:
        """Return raw saved state (for advanced use)."""
        return self._client._saved_state

    def give_up(self):
        """Restart the current race (CGiveUp)."""
        if self._client and self._client._connected:
            self._client.send_give_up()

    def set_speed(self, speed: float):
        """Set game speed multiplier (1.0 = real-time, 5.0 = 5x faster)."""
        if self._client and self._client._connected:
            self._client.send_set_speed(speed)

    def execute_command(self, command: str):
        """Execute a TMInterface console command."""
        if self._client and self._client._connected:
            self._client.send_execute_command(command)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def is_connected(self) -> bool:
        """Return True if TCP connection to plugin is active."""
        return bool(self._client and self._client._connected)

    def get_statistics(self) -> Dict[str, Any]:
        """Return adapter statistics dict."""
        if not self._client:
            return {'connected': False}
        return {
            'connected':       self._client._connected,
            'race_time_ms':    self._client._race_time,
            'ticks_processed': self._client.ticks_processed,
            'actions_applied': self._client.actions_applied,
            'has_saved_state': self._client._saved_state is not None,
            'port':            self._client._port,
        }

    def get_wire_precision(self) -> Dict[str, Dict[str, Any]]:
        """Return wire precision metadata for each action channel.

        PURE DATA method (no TCP connection needed). Reports the known
        wire format from the AgenticBridge.as protocol:
          - gas/brake/left/right: uint8 [0, 255], float step = 1/255
          - steering: int32 [-65536, +65536], float step = 1/65536

        Sutton: "First, find the system's precision. Based on that,
        find what is small and what is large."

        Returns dict keyed by action channel name. Each value contains:
          wire_type:  str   ('uint8' or 'int32')
          wire_bits:  int   (8 or 32)
          wire_min:   int   (0 or -65536)
          wire_max:   int   (255 or 65536)
          float_min:  float (0.0 or -1.0)
          float_max:  float (1.0)
          float_step: float (1/255 or 1/65536)
        """
        uint8_info = {
            'wire_type':  'uint8',
            'wire_bits':  8,
            'wire_min':   0,
            'wire_max':   255,
            'float_min':  0.0,
            'float_max':  1.0,
            'float_step': 1.0 / 255,
        }
        int32_steer_info = {
            'wire_type':  'int32',
            'wire_bits':  32,
            'wire_min':   -ANALOG_MAX,
            'wire_max':   ANALOG_MAX,
            'float_min':  -1.0,
            'float_max':  1.0,
            'float_step': 1.0 / ANALOG_MAX,
        }
        return {
            'gas':      dict(uint8_info),
            'brake':    dict(uint8_info),
            'left':     dict(uint8_info),
            'right':    dict(uint8_info),
            'steering': dict(int32_steer_info),
        }

    def stop(self):
        """Disconnect from plugin and stop background thread."""
        self._running = False
        if self._client:
            self._client.disconnect()
        logger.info("[TMNF_ADAPTER] Stopped")
