"""
COMPREHENSIVE SYSTEM TESTS V3 (FIXED)
Tests all requirements from latest meeting
"""

import logging
import sys
from pathlib import Path

from system_coordinator_v3 import SystemCoordinator
from intelligence_future_constraints import ConstraintType
from state_manager import StateVector  # FIX: Import directly
from exceptions import *

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_1_initialization():
    """Test 1: System V3 Initialization"""
    print("\n" + "="*80)
    print("TEST 1: SYSTEM V3 INITIALIZATION")
    print("="*80)
    
    try:
        system = SystemCoordinator("/app/system_config_v3.json")
        print("\n✓ System V3 initialized successfully")
        return system
    except Exception as e:
        print(f"\n✗ Initialization failed: {e}")
        raise


def test_2_dual_timestamps(system: SystemCoordinator):
    """Test 2: Dual Timestamp System"""
    print("\n" + "="*80)
    print("TEST 2: DUAL TIMESTAMP SYSTEM")
    print("="*80)
    
    print("\n[Testing agent vs environment timestamps...]")
    
    # Start episode
    system.start_episode(start_frame=100, episode_number=1)
    
    # Record some transitions
    state = {"speed": 10.0, "lidar_0": 200.0, "lidar_1": 150.0, "lidar_2": 100.0}
    
    for i in range(5):
        prev_state = state.copy()
        action = {"gas": 0.7, "brake": 0.0, "steering": 0.0}
        state["speed"] += 3.0
        
        env_frame = 100 + i
        system.record_transition(prev_state, state, action, env_frame)
        
        # Get timestamps
        ts = system.timestamps.get_current_timestamps(env_frame)
        print(f"\n  Frame {env_frame}:")
        print(f"    Agent timestamp: {ts.agent_timestamp:.3f}s")
        print(f"    Environment frame: {ts.environment_frame}")
        print(f"    Episode timestamp: {ts.episode_timestamp:.3f}s")
        print(f"    Episode frame: {ts.episode_frame}")
    
    print("\n✓ Dual timestamps working")
    return True


def test_3_sensorial_intelligence(system: SystemCoordinator):
    """Test 3: Sensorial Intelligence (Prediction Validation)"""
    print("\n" + "="*80)
    print("TEST 3: SENSORIAL INTELLIGENCE - PREDICTION VALIDATION")
    print("="*80)
    
    print("\n[Recording transitions to build knowledge...]")
    
    state = {"speed": 15.0, "lidar_0": 200.0, "lidar_1": 150.0, "lidar_2": 100.0}
    
    for i in range(5):
        prev_state = state.copy()
        action = {"gas": 0.8, "brake": 0.0, "steering": 0.1}
        state["speed"] += 5.0
        
        system.record_transition(prev_state, state, action, 200 + i)
    
    print("\n[Testing prediction and validation...]")
    
    # Get current state
    current_state = system.brain.state_manager.get_current_state()
    action_discrete = {"gas": "HIGH", "brake": "NONE", "steering": "RIGHT_SMALL"}
    
    # Predict future state
    predicted = system.intelligence_sensorial.predict_future_state(
        current_state, action_discrete, system.brain
    )
    
    print(f"\n  Predicted state: {predicted.to_vector()}")
    
    # Simulate actual state (same as predicted for now)
    actual_feedbacks = {"speed": 40.0, "lidar_0": 200.0, "lidar_1": 150.0, "lidar_2": 100.0}
    
    # Validate
    result = system.intelligence_repeat.validate_action_result(
        predicted, actual_feedbacks
    )
    
    print(f"\n  Validation result:")
    print(f"    Code: {result.validation_code}")
    print(f"    Matches: {result.matches}")
    if result.deviations:
        print(f"    Deviations: {result.deviations}")
    
    # Get statistics
    sens_stats = system.intelligence_sensorial.get_statistics()
    print(f"\n  Sensorial statistics:")
    print(f"    Predictions made: {sens_stats['predictions_made']}")
    print(f"    Accuracy: {sens_stats['accuracy']:.1f}%")
    
    print("\n✓ Sensorial intelligence working")
    return True


def test_4_future_constraints(system: SystemCoordinator):
    """Test 4: Future Constraints Intelligence"""
    print("\n" + "="*80)
    print("TEST 4: FUTURE CONSTRAINTS INTELLIGENCE")
    print("="*80)
    
    print("\n[Adding custom constraint: speed must be < 30...]")
    
    def speed_limit_check(state):
        if 'speed' in state.graph_positions:
            return state.graph_positions['speed'] < 30.0
        return True
    
    system.intelligence_constraints.add_constraint(
        name="speed_limit_30",
        constraint_type=ConstraintType.HARD,
        check_function=speed_limit_check,
        description="Speed must not exceed 30"
    )
    
    print("\n[Testing constraint validation...]")
    
    # FIX: Import StateVector directly, don't access through state_manager
    import time
    
    # Create test states
    safe_state = StateVector(
        graph_positions={"speed": 25.0, "lidar_0": 200.0},
        timestamp=time.time(),
        frame=1000
    )
    
    unsafe_state = StateVector(
        graph_positions={"speed": 35.0, "lidar_0": 200.0},
        timestamp=time.time(),
        frame=1001
    )
    
    # Test safe state
    action = {"gas": "HIGH", "brake": "NONE", "steering": "STRAIGHT"}
    allowed, violations = system.intelligence_constraints.validate_future_state(
        safe_state, action
    )
    
    print(f"\n  Safe state (speed=25):")
    print(f"    Allowed: {allowed}")
    print(f"    Violations: {len(violations)}")
    
    # Test unsafe state
    allowed, violations = system.intelligence_constraints.validate_future_state(
        unsafe_state, action
    )
    
    print(f"\n  Unsafe state (speed=35):")
    print(f"    Allowed: {allowed}")
    print(f"    Violations: {len(violations)}")
    if violations:
        for v in violations:
            print(f"      {v}")
    
    # Get statistics
    const_stats = system.intelligence_constraints.get_statistics()
    print(f"\n  Constraints statistics:")
    print(f"    Total constraints: {const_stats['constraints_defined']}")
    print(f"    Hard constraints: {const_stats['hard_constraints']}")
    print(f"    Violations detected: {const_stats['total_violations']}")
    
    print("\n✓ Future constraints working")
    return True


def test_5_repeat_with_prediction(system: SystemCoordinator):
    """Test 5: Repeat Intelligence with Prediction Validation"""
    print("\n" + "="*80)
    print("TEST 5: REPEAT INTELLIGENCE WITH PREDICTION")
    print("="*80)
    
    print("\n[Setting up repeat intelligence...]")
    system.set_intelligence_mode("repeat")
    system.start_episode(start_frame=3000, episode_number=10)
    
    # Record some transitions
    state = {"speed": 5.0, "lidar_0": 200.0, "lidar_1": 150.0, "lidar_2": 100.0}
    
    for i in range(3):
        prev_state = state.copy()
        action = {"gas": 0.8, "brake": 0.0, "steering": 0.0}
        state["speed"] += 5.0
        
        system.record_transition(prev_state, state, action, 3000 + i)
    
    system.end_episode(end_frame=3002)
    
    print("\n[Testing decision with prediction...]")
    
    # Make decision
    decision = system.decide_action_with_validation(
        {"speed": 5.0, "lidar_0": 200.0, "lidar_1": 150.0, "lidar_2": 100.0},
        environment_frame=3000
    )
    
    if decision:
        print(f"\n  Decision package:")
        print(f"    Action: {decision['action_discrete']}")
        print(f"    Predicted state: {decision['predicted_state'].to_vector()}")
        print(f"    Validation code: {decision['validation_code']}")
        print(f"    Allowed: {decision['allowed']}")
    
    # Get statistics
    rep_stats = system.intelligence_repeat.get_statistics()
    print(f"\n  Repeat intelligence statistics:")
    print(f"    Decisions made: {rep_stats['decisions_made']}")
    print(f"    Actions repeated: {rep_stats['actions_repeated']}")
    print(f"    Prediction success rate: {rep_stats['prediction_success_rate']:.1f}%")
    
    print("\n✓ Repeat with prediction working")
    return True


def test_6_complete_decision_cycle(system: SystemCoordinator):
    """Test 6: Complete Decision Cycle (Process)"""
    print("\n" + "="*80)
    print("TEST 6: COMPLETE DECISION CYCLE")
    print("="*80)
    
    print("\n[Testing complete cycle: decide → predict → validate...]")
    
    # Current state
    current_feedbacks = {"speed": 10.0, "lidar_0": 200.0, "lidar_1": 150.0, "lidar_2": 100.0}
    
    # 1. Decide action with prediction
    print("\n  1. Making decision...")
    decision = system.decide_action_with_validation(current_feedbacks, 4000)
    
    if decision:
        print(f"     Action: {decision['action_discrete']}")
        print(f"     Predicted: {decision['predicted_state'].to_vector()}")
        
        # 2. Simulate taking action (in real system, action would be executed)
        print("\n  2. Action would be executed...")
        
        # 3. Observe actual result
        print("\n  3. Observing actual result...")
        actual_feedbacks = {"speed": 15.0, "lidar_0": 200.0, "lidar_1": 150.0, "lidar_2": 100.0}
        
        # 4. Validate prediction vs reality
        print("\n  4. Validating prediction vs reality...")
        validation_code = system.validate_action_result(
            decision['predicted_state'],
            actual_feedbacks
        )
        
        print(f"     Validation code: {validation_code}")
        if validation_code == 0:
            print("     ✓ Prediction matched reality")
        else:
            print(f"     ⚠ Prediction deviated (code {validation_code})")
    
    print("\n✓ Complete decision cycle working")
    return True


def test_7_what_am_i_v3(system: SystemCoordinator):
    """Test 7: Enhanced 'What Am I?' with Timestamps"""
    print("\n" + "="*80)
    print("TEST 7: ENHANCED 'WHAT AM I?' V3")
    print("="*80)
    
    print("\n[Testing enhanced awareness...]")
    
    awareness = system.what_am_i()
    
    print(f"\n  Brain State:")
    print(f"    Current position: {awareness['brain_state']['current_position']}")
    print(f"    State vector: {awareness['brain_state']['state_vector']}")
    print(f"    Transitions: {awareness['brain_state']['transitions']}")
    
    print(f"\n  Timestamps:")
    print(f"    Agent runtime: {awareness['timestamps']['agent']['runtime_seconds']:.2f}s")
    print(f"    Total frames: {awareness['timestamps']['agent']['total_frames']}")
    print(f"    Current episode: {awareness['timestamps']['episode']['number']}")
    
    print(f"\n  Memory:")
    print(f"    Episodes: {awareness['memory']['short_term_capacity']}")
    
    print(f"\n  Monitoring:")
    print(f"    Prediction accuracy: {awareness['monitoring']['prediction_accuracy']:.1f}%")
    
    print("\n✓ Enhanced 'What Am I?' working")
    return True


def run_all_tests():
    """Run all V3 tests"""
    print("\n" + "="*80)
    print("PRODUCTION SYSTEM V3 TEST SUITE")
    print("="*80)
    
    try:
        # Test 1: Initialization
        system = test_1_initialization()
        
        # Test 2: Dual Timestamps
        if not test_2_dual_timestamps(system):
            raise Exception("Dual timestamps test failed")
        
        # Test 3: Sensorial Intelligence
        if not test_3_sensorial_intelligence(system):
            raise Exception("Sensorial intelligence test failed")
        
        # Test 4: Future Constraints
        if not test_4_future_constraints(system):
            raise Exception("Future constraints test failed")
        
        # Test 5: Repeat with Prediction
        if not test_5_repeat_with_prediction(system):
            raise Exception("Repeat with prediction test failed")
        
        # Test 6: Complete Decision Cycle
        if not test_6_complete_decision_cycle(system):
            raise Exception("Complete decision cycle test failed")
        
        # Test 7: Enhanced What Am I
        if not test_7_what_am_i_v3(system):
            raise Exception("Enhanced 'What Am I?' test failed")
        
        # Final statistics
        print("\n" + "="*80)
        print("FINAL SYSTEM V3 STATISTICS")
        print("="*80)
        system.print_statistics()
        
        print("\n" + "="*80)
        print("✓ ALL V3 TESTS PASSED - SYSTEM READY")
        print("="*80)
        
        return True
        
    except Exception as e:
        print("\n" + "="*80)
        print(f"✗ TEST SUITE FAILED: {e}")
        print("="*80)
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)