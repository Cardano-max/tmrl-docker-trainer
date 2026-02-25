/**
 * AgenticBridge.as — AngelScript plugin for TMInterface 2.x
 *
 * TCP socket bridge between TMNF and Python.
 * Based on Linesight-RL's Python_Link.as, extended with analog steer.
 *
 * INSTALL: Copy to Documents\TMInterface\Plugins\AgenticBridge.as
 * PORT:    Set in TMInterface console: set custom_port 8476
 *
 * Protocol: Linesight-compatible + analog steer extension on CSetInputState.
 *   CSetInputState sends: [int32 type][uint8 left][uint8 right][uint8 accel][uint8 brake][int32 steer]
 */

// ============================================================
// Message types (must match Python MessageType enum)
// ============================================================

enum MessageType {
    SCRunStepSync = 1,
    SCCheckpointCountChangedSync = 2,
    SCLapCountChangedSync = 3,
    SCRequestedFrameSync = 4,
    SCOnConnectSync = 5,
    CSetSpeed = 6,
    CRewindToState = 7,
    CRewindToCurrentState = 8,
    CGetSimulationState = 9,
    CSetInputState = 10,
    CGiveUp = 11,
    CPreventSimulationFinish = 12,
    CShutdown = 13,
    CExecuteCommand = 14,
    CSetTimeout = 15,
    CRaceFinished = 16,
    CRequestFrame = 17,
    CResetCamera = 18,
    CSetOnStepPeriod = 19,
    CUnrequestFrame = 20,
    CToggleInterface = 21,
    CIsInMenus = 22,
    CGetInputs = 23,
}

// ============================================================
// State
// ============================================================

const string HOST = "127.0.0.1";
uint16 PORT;
uint RESPONSE_TIMEOUT = 5000;
int on_step_period = 10;
bool on_connect_queued = false;

Net::Socket@ sock = null;
Net::Socket@ clientSock = null;
auto@ simManager = GetSimulationManager();

// ============================================================
// Socket setup
// ============================================================

void Init_Socket() {
    if (@sock is null) {
        @sock = Net::Socket();
        log("[AgenticBridge] Port set to " + PORT);
        sock.Listen(HOST, PORT);
    }
}

void close_connection() {
    @clientSock = null;
    Init_Socket();
    RESPONSE_TIMEOUT = 5000;
}

// ============================================================
// WaitForResponse — poll HandleMessage until expected type
// ============================================================

void WaitForResponse(MessageType type) {
    auto now = Time::Now;

    while (true) {
        auto receivedType = HandleMessage();
        if (receivedType == type) {
            break;
        }
        if (receivedType == MessageType::CShutdown) {
            break;
        }
        if (receivedType == -1 && Time::Now - now > RESPONSE_TIMEOUT) {
            log("[AgenticBridge] Client disconnected due to timeout (" + RESPONSE_TIMEOUT + "ms)");
            close_connection();
            break;
        }
    }
}

// ============================================================
// HandleMessage — process one message from Python
// ============================================================

int HandleMessage() {
    if (clientSock.Available == 0) {
        return -1;
    }

    int type = clientSock.ReadInt32();

    switch (type) {
        // Sync responses (Python acknowledges our sync messages)
        case MessageType::SCRunStepSync:
        case MessageType::SCCheckpointCountChangedSync:
        case MessageType::SCLapCountChangedSync:
        case MessageType::SCOnConnectSync:
            break;

        // CSetSpeed = 6
        case MessageType::CSetSpeed: {
            const float new_speed = clientSock.ReadFloat();
            simManager.SetSpeed(new_speed);
            break;
        }

        // CRewindToState = 7
        case MessageType::CRewindToState: {
            const int32 stateLength = clientSock.ReadInt32();
            const auto stateData = clientSock.ReadBytes(stateLength);
            if (simManager.InRace) {
                SimulationState state(stateData);
                simManager.RewindToState(state);
            }
            break;
        }

        // CRewindToCurrentState = 8
        case MessageType::CRewindToCurrentState: {
            if (simManager.InRace) {
                simManager.RewindToState(simManager.SaveState());
            }
            break;
        }

        // CGetSimulationState = 9
        case MessageType::CGetSimulationState: {
            auto@ state = simManager.SaveState();
            const auto@ data = state.ToArray();
            clientSock.Write(int(data.Length));
            clientSock.Write(data);
            break;
        }

        // CSetInputState = 10 (EXTENDED: binary + analog steer)
        case MessageType::CSetInputState: {
            const bool left = clientSock.ReadUint8() > 0;
            const bool right = clientSock.ReadUint8() > 0;
            const bool accelerate = clientSock.ReadUint8() > 0;
            const bool brake = clientSock.ReadUint8() > 0;
            const int steer = clientSock.ReadInt32();  // Our extension: -65536 to +65536

            if (simManager.InRace) {
                // Binary gas/brake
                simManager.SetInputState(InputType::Up, accelerate ? 1 : 0);
                simManager.SetInputState(InputType::Down, brake ? 1 : 0);

                // Analog steer (takes priority)
                simManager.SetInputState(InputType::Steer, steer);

                // Binary left/right fallback (only if analog steer = 0)
                if (left && steer == 0) {
                    simManager.SetInputState(InputType::Steer, -65536);
                } else if (right && steer == 0) {
                    simManager.SetInputState(InputType::Steer, 65536);
                }
            }
            break;
        }

        // CGiveUp = 11
        case MessageType::CGiveUp: {
            if (simManager.InRace) {
                simManager.GiveUp();
            }
            break;
        }

        // CPreventSimulationFinish = 12
        case MessageType::CPreventSimulationFinish: {
            if (simManager.InRace) {
                simManager.PreventSimulationFinish();
            }
            break;
        }

        // CShutdown = 13
        case MessageType::CShutdown: {
            log("[AgenticBridge] Client disconnected");
            close_connection();
            break;
        }

        // CExecuteCommand = 14
        case MessageType::CExecuteCommand: {
            const int32 bytes_to_read = clientSock.ReadInt32();
            const string command = clientSock.ReadString(bytes_to_read);
            ExecuteCommand(command);
            break;
        }

        // CSetTimeout = 15
        case MessageType::CSetTimeout: {
            const uint new_timeout = clientSock.ReadUint32();
            RESPONSE_TIMEOUT = new_timeout;
            break;
        }

        // CRaceFinished = 16
        case MessageType::CRaceFinished: {
            const int is_race_finished = ((simManager.PlayerInfo.RaceFinished || simManager.TickTime > simManager.RaceTime) ? 1 : 0);
            clientSock.Write(is_race_finished);
            break;
        }

        // CSetOnStepPeriod = 19
        case MessageType::CSetOnStepPeriod: {
            on_step_period = clientSock.ReadInt32();
            break;
        }

        // CIsInMenus = 22
        case MessageType::CIsInMenus: {
            const int response = GetCurrentGameState() == TM::GameState::Menus ? 1 : 0;
            clientSock.Write(response);
            break;
        }

        // CGetInputs = 23
        case MessageType::CGetInputs: {
            TM::InputEventBuffer@ inputs = simManager.get_InputEvents();
            const string input_text = inputs.ToCommandsText();
            clientSock.Write(int32(input_text.Length));
            clientSock.Write(input_text);
            break;
        }

        default: {
            log("[AgenticBridge] Unknown message type: " + type);
            break;
        }
    }

    return type;
}

// ============================================================
// Game callbacks
// ============================================================

void OnRunStep(SimulationManager@ simManager) {
    if (@clientSock is null) {
        return;
    }

    if (simManager.RaceTime % on_step_period == 0 || simManager.TickTime > simManager.RaceTime) {
        clientSock.Write(MessageType::SCRunStepSync);
        clientSock.Write(simManager.RaceTime);
        WaitForResponse(MessageType::SCRunStepSync);
    }
}

void OnCheckpointCountChanged(SimulationManager@ simManager, int current, int target) {
    if (@clientSock is null) return;
    clientSock.Write(MessageType::SCCheckpointCountChangedSync);
    clientSock.Write(current);
    clientSock.Write(target);
    WaitForResponse(MessageType::SCCheckpointCountChangedSync);
}

void OnLapCountChanged(SimulationManager@ simManager, int current, int target) {
    if (@clientSock is null) return;
    clientSock.Write(MessageType::SCLapCountChangedSync);
    clientSock.Write(current);
    clientSock.Write(target);
    WaitForResponse(MessageType::SCLapCountChangedSync);
}

void OnConnect() {
    clientSock.Write(MessageType::SCOnConnectSync);
    WaitForResponse(MessageType::SCOnConnectSync);
}

void OnGameStateChanged(TM::GameState state) {
    if (state == TM::GameState::Menus && on_connect_queued) {
        OnConnect();
        on_connect_queued = false;
    }
}

// ============================================================
// Init: port setup via TMInterface variable system
// ============================================================

void OnQueueProcessed(int fromTime, int toTime, const string &in commandLine, const array<string> &in args) {
    PORT = uint16(GetVariableDouble("custom_port"));
    log("[AgenticBridge] Port from variable: " + PORT);
    Init_Socket();
}

void Main() {
    RegisterVariable("custom_port", 0);
    RegisterCustomCommand("queue_processed", "Internal command", OnQueueProcessed);

    CommandList cmdList;
    cmdList.Content = "queue_processed";
    cmdList.Process();
}

// ============================================================
// Render: accept new TCP connections
// ============================================================

void Render() {
    auto @newSock = sock.Accept(0);
    if (@newSock !is null) {
        @clientSock = @newSock;
        newSock.NoDelay = true;
        log("[AgenticBridge] Client connected (IP: " + clientSock.RemoteIP + ")");
        if (GetCurrentGameState() != TM::GameState::StartUp) {
            OnConnect();
        } else {
            on_connect_queued = true;
        }
    }
}

// ============================================================
// Plugin info
// ============================================================

PluginInfo@ GetPluginInfo() {
    PluginInfo info;
    info.Author = "Sutton Research Team";
    info.Name = "AgenticBridge";
    info.Description = "TCP bridge for Python bin discovery algorithm (based on Linesight Python_Link)";
    info.Version = "1.0";
    return info;
}
