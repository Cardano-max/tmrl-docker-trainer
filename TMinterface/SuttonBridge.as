/**
 * SuttonBridge.as — AngelScript plugin for TMInterface 2.x
 *
 * TCP socket bridge between TMNF and Python, based on Linesight-RL's Python_Link.as.
 * Extended with analog steer support for Sutton's bin discovery algorithm.
 *
 * INSTALL:
 *   Copy this file to: %APPDATA%\TMInterface\Plugins\SuttonBridge.as
 *   Or to the Plugins folder in your TMInterface installation directory.
 *
 * PORT: 8476 (configurable via `custom_port` variable in TMInterface console)
 *
 * PROTOCOL:
 *   Matches Linesight-RL protocol exactly, with one extension to CSetInputState:
 *     Original:  [int32 type][uint8 left][uint8 right][uint8 accel][uint8 brake]
 *     Extended:  [int32 type][uint8 left][uint8 right][uint8 accel][uint8 brake][int32 steer_analog]
 *
 * TMNF INPUT FACTS:
 *   Gas:      BINARY only (InputType::Up = on/off). No analog throttle in TMNF.
 *   Brake:    BINARY only (InputType::Down = on/off).
 *   Steering: ANALOG (InputType::Steer, range -65536 to +65536).
 *
 * MESSAGE TYPES (mirror of Python MessageType enum):
 *   SCRunStepSync = 1            Game -> Python: new tick available (int32 race_time)
 *   SCCheckpointCountChangedSync = 2
 *   SCLapCountChangedSync = 3
 *   SCRequestedFrameSync = 4
 *   SCOnConnectSync = 5          Game -> Python: initial handshake
 *   CSetSpeed = 6                Python -> Game: set speed multiplier (float32)
 *   CRewindToState = 7           Python -> Game: rewind to state bytes
 *   CRewindToCurrentState = 8
 *   CGetSimulationState = 9      Python -> Game: request current state bytes
 *   CSetInputState = 10          Python -> Game: set inputs (binary + analog steer)
 *   CGiveUp = 11                 Python -> Game: restart race
 *   CPreventSimulationFinish = 12
 *   CShutdown = 13               Python -> Game: disconnect
 *   CExecuteCommand = 14         Python -> Game: run console command
 *   CSetTimeout = 15             Python -> Game: set step timeout
 *   CRaceFinished = 16
 *   CRequestFrame = 17
 *   CResetCamera = 18
 *   CSetOnStepPeriod = 19
 *   CUnrequestFrame = 20
 *   CToggleInterface = 21
 *   CIsInMenus = 22
 *   CGetInputs = 23
 */

// ============================================================
// Configuration
// ============================================================

const int DEFAULT_PORT = 8476;

// ============================================================
// Plugin entry point
// ============================================================

void RegisterVariable(const string &in name, int defaultValue) {
    RegisterVariable(name, tostring(defaultValue));
}

void Main() {
    RegisterVariable("custom_port", DEFAULT_PORT);
}

// ============================================================
// State
// ============================================================

Net::Socket@ serverSock;
Net::Socket@ clientSock;
bool clientConnected = false;

// ============================================================
// Render() — called every frame. Accepts new TCP connections.
// ============================================================

void Render() {
    // On first call, open the server socket
    if (serverSock is null) {
        int port = Text::ParseInt(GetVariableString("custom_port"));
        @serverSock = Net::Socket();
        if (!serverSock.Listen(port)) {
            warn("[SuttonBridge] Failed to bind port " + port);
            @serverSock = null;
            return;
        }
        log("[SuttonBridge] Listening on port " + port);
    }

    // Accept new client (non-blocking, timeout=0)
    if (!clientConnected) {
        Net::Socket@ incoming = serverSock.Accept(0);
        if (incoming !is null) {
            @clientSock = incoming;
            clientConnected = true;
            log("[SuttonBridge] Client connected");
            // Send handshake
            clientSock.Write(int(5));  // SCOnConnectSync = 5
        }
    }
}

// ============================================================
// OnRunStep() — called every 10ms physics tick. Game is PAUSED here.
// ============================================================

void OnRunStep(SimulationManager@ simManager) {
    if (!clientConnected || clientSock is null) {
        return;
    }

    int raceTime = simManager.RaceTime;

    // Send SCRunStepSync (type=1) + race time
    clientSock.Write(int(1));   // SCRunStepSync
    clientSock.Write(raceTime);

    // Wait for response (game is paused until we return)
    WaitForResponse(simManager, 1);
}

// ============================================================
// OnCheckpointCountChanged() — notify Python
// ============================================================

void OnCheckpointCountChanged(SimulationManager@ simManager, int current, int target) {
    if (!clientConnected || clientSock is null) return;
    clientSock.Write(int(2));   // SCCheckpointCountChangedSync
    clientSock.Write(current);
    clientSock.Write(target);
    WaitForResponse(simManager, 2);
}

// ============================================================
// OnLapCountChanged() — notify Python
// ============================================================

void OnLapCountChanged(SimulationManager@ simManager, int current) {
    if (!clientConnected || clientSock is null) return;
    clientSock.Write(int(3));   // SCLapCountChangedSync
    clientSock.Write(current);
    WaitForResponse(simManager, 3);
}

// ============================================================
// WaitForResponse() — dispatch messages until matching type received
// ============================================================

void WaitForResponse(SimulationManager@ simManager, int expectedType) {
    while (clientConnected) {
        int msgType = ReadInt32();
        if (msgType == -1) {
            // Connection dropped or timeout
            log("[SuttonBridge] Client disconnected");
            clientConnected = false;
            return;
        }

        HandleMessage(simManager, msgType);

        if (msgType == expectedType) {
            return;
        }
    }
}

// ============================================================
// HandleMessage() — process a single message from Python
// ============================================================

void HandleMessage(SimulationManager@ simManager, int msgType) {
    // CSetSpeed = 6
    if (msgType == 6) {
        float speed = ReadFloat();
        simManager.SetSpeed(speed);
        return;
    }

    // CRewindToState = 7
    if (msgType == 7) {
        int stateLength = ReadInt32();
        array<uint8> stateData(stateLength);
        clientSock.ReadBytes(stateData, stateLength);
        SimulationState@ state = SimulationState(stateData);
        simManager.RewindToState(state);
        return;
    }

    // CRewindToCurrentState = 8
    if (msgType == 8) {
        // Already at current state — no-op, just acknowledge
        return;
    }

    // CGetSimulationState = 9
    if (msgType == 9) {
        SimulationState@ state = simManager.SaveState();
        array<uint8>@ data = state.ToArray();
        clientSock.Write(int(data.Length));
        clientSock.WriteBytes(data, data.Length);
        return;
    }

    // CSetInputState = 10 (EXTENDED: includes analog steer)
    if (msgType == 10) {
        uint8 left      = ReadUInt8();
        uint8 right     = ReadUInt8();
        uint8 accelerate = ReadUInt8();
        uint8 brake     = ReadUInt8();
        int   steer     = ReadInt32();  // Our extension: analog steer -65536 to +65536

        // Binary inputs (TMNF gas and brake are binary)
        simManager.SetInputState(InputType::Up,    accelerate > 0 ? 1 : 0);
        simManager.SetInputState(InputType::Down,  brake > 0 ? 1 : 0);

        // Analog steer
        simManager.SetInputState(InputType::Steer, steer);

        // left/right as fallback binary steer (overridden by analog above)
        // Kept for protocol compatibility with Linesight tools
        if (left > 0 && steer == 0) {
            simManager.SetInputState(InputType::Steer, -65536);
        } else if (right > 0 && steer == 0) {
            simManager.SetInputState(InputType::Steer, 65536);
        }
        return;
    }

    // CGiveUp = 11
    if (msgType == 11) {
        simManager.GiveUp();
        return;
    }

    // CPreventSimulationFinish = 12
    if (msgType == 12) {
        simManager.PreventSimulationFinish();
        return;
    }

    // CShutdown = 13
    if (msgType == 13) {
        log("[SuttonBridge] Shutdown requested by Python");
        if (clientSock !is null) {
            clientSock.Close();
        }
        clientConnected = false;
        return;
    }

    // CExecuteCommand = 14
    if (msgType == 14) {
        int cmdLen = ReadInt32();
        string cmd = ReadString(cmdLen);
        ExecuteCommand(cmd);
        return;
    }

    // CSetTimeout = 15
    if (msgType == 15) {
        // TMInterface 2.x manages timeout differently — acknowledged but no-op
        int timeout = ReadInt32();
        return;
    }

    // CRaceFinished = 16 (game -> python, not python -> game, but handle gracefully)
    if (msgType == 16) {
        return;
    }

    // Unknown message: log and continue
    warn("[SuttonBridge] Unknown message type: " + msgType);
}

// ============================================================
// Socket read helpers
// ============================================================

int ReadInt32() {
    array<uint8> buf(4);
    if (!clientSock.ReadBytes(buf, 4)) {
        return -1;  // Disconnected or timeout
    }
    int val = int(buf[0])
            | (int(buf[1]) << 8)
            | (int(buf[2]) << 16)
            | (int(buf[3]) << 24);
    return val;
}

uint8 ReadUInt8() {
    array<uint8> buf(1);
    clientSock.ReadBytes(buf, 1);
    return buf[0];
}

float ReadFloat() {
    array<uint8> buf(4);
    clientSock.ReadBytes(buf, 4);
    // Reinterpret bytes as float (little-endian IEEE 754)
    return ReinterpretBytesAsFloat(buf);
}

float ReinterpretBytesAsFloat(array<uint8>@ buf) {
    // Reconstruct float from 4 bytes (little-endian)
    uint bits = uint(buf[0])
              | (uint(buf[1]) << 8)
              | (uint(buf[2]) << 16)
              | (uint(buf[3]) << 24);
    return Math::BitsToFloat(bits);
}

string ReadString(int length) {
    array<uint8> buf(length);
    clientSock.ReadBytes(buf, length);
    string result = "";
    for (int i = 0; i < length; i++) {
        result += string(buf[i]);
    }
    return result;
}
