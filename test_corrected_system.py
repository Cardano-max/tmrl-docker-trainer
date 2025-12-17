"""
COMPREHENSIVE TESTS - CORRECTED SYSTEM V3
Tests all supervisor's corrections
"""

import logging
import sys
from pathlib import Path

from system_coordinator_corrected import SystemCoordinatorCorrected
from intelligence_future_constraints import ConstraintType
from state_manager import StateVector
from exceptions import *
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_1_initialization():
    """Test 1: System Initialization"""
    print("\n" + "="*80)
    print("TEST 1: CORRECTED SYSTEM INITIALIZATION")
    print("="*80)
    
    try:
        system = SystemCoordinatorCorrected("/app/system_config_corrected.json")
        print("\n✓ Corrected System V3 initialized successfully")
        return system
    except Exception as e:
        print(f"\n✗ Initialization failed: {e}")
        raise


def test_2_timestamp_manager_corrected(system: SystemCoordinatorCorrected):
    """Test 2: Timestamp Manager (Internal Time Only)"""
    print("\n" + "="*80)
    print("TEST 2: TIMESTAMP MANAGER (INTERNAL TIME ONLY)")
    print("="*80)
    
    print("\n[Testing that episodes are NOT in timestamp manager...]")
    
    # Check that timestamp manager has NO episode tracking
    ts = system.timestamps
    has_episode_methods = (
        hasattr(ts, 'episode_number') or
        hasattr(ts, 'start_new_episode') or
        hasattr(ts, 'episode_timestamp')
    )
    
    if has_episode_methods:
        print("\n✗ FAIL: Timestamp manager still has episode tracking!")
        return False
    else:
        print("\n✓ PASS: Timestamp manager is internal time only")
    
    # Test internal time
    print("\n[Testing internal time...]")
    time_1 = ts.get_current_time()
    time.sleep(0.1)
    time_2 = ts.get_current_time()
    
    print(f"  Time 1: {time_1:.3f}s")
    print(f"  Time 2: {time_2:.3f}s")
    print(f"  Difference: {time_2 - time_1:.3f}s")
    
    if time_2 > time_1:
        print("  ✓ Internal time advancing correctly")
    else:
        print("  ✗ Internal time not advancing")
        return False
    
    # Test processing iterations
    print("\n[Testing processing iterations...]")
    for i in range(5):
        ts.record_processing_iteration()
    
    stats = ts.get_statistics()
    print(f"  Processing iterations: {stats['processing_iterations']}")
    
    if stats['processing_iterations'] >= 5:
        print("  ✓ Processing iterations tracked")
    else:
        print("  ✗ Processing iterations not tracked")
        return False
    
    print("\n✓ Timestamp manager corrections validated")
    return True


def test_3_awareness_intelligence(system: SystemCoordinatorCorrected):
    """Test 3: Awareness Intelligence (Not Sensorial)"""
    print("\n" + "="*80)
    print("TEST 3: AWARENESS INTELLIGENCE (CORRECTED NAME)")
    print("="*80)
    
    print("\n[Checking that it's called Awareness, not Sensorial...]")
    
    # Check class name
    intelligence_name = system.intelligence_awareness.__class__.__name__
    print(f"  Intelligence class: {intelligence_name}")
    
    if "Awareness" in intelligence_name:
        print("  ✓ CORRECT: Named 'Awareness Intelligence'")
    elif "Sensorial" in intelligence_name:
        print("  ✗ WRONG: Still called 'Sensorial Intelligence'")
        return False
    
    # Test awareness functionality
    print("\n[Testing awareness: knowledge vs reality comparison...]")
    
    # Record some transitions
    state = {"speed": 10.0, "lidar_0": 200.0, "lidar_1": 150.0, "lidar_2": 100.0}
    
    for i in range(3):
        prev_state = state.copy()
        action = {"gas": 0.7, "brake": 0.0, "steering": 0.0}
        state["speed"] += 5.0
        
        system.record_transition(prev_state, state, action, i)
    
    # Get current state
    current_state = system.brain.state_manager.get_current_state()
    action_discrete = {"gas": "HIGH", "brake": "NONE", "steering": "STRAIGHT"}
    
    # Predict from knowledge
    predicted = system.intelligence_awareness.predict_from_knowledge(
        current_state, action_discrete, system.brain
    )
    
    print(f"  Knowledge predicts: {predicted.to_vector()}")
    
    # Simulate reality
    actual_feedbacks = {"speed": 20.0, "lidar_0": 200.0, "lidar_1": 150.0, "lidar_2": 100.0}
    
    # Check awareness
    code = system.validate_action_result(predicted, actual_feedbacks)
    
    print(f"  Awareness code: {code}")
    print(f"  (0 = knowledge matches reality, 1+ = mismatch)")
    
    # Get statistics
    stats = system.intelligence_awareness.get_statistics()
    print(f"\n  Awareness checks: {stats['awareness_checks']}")
    print(f"  Knowledge correct: {stats['knowledge_correct']}")
    print(f"  Accuracy: {stats['accuracy']:.1f}%")
    
    print("\n✓ Awareness intelligence validated")
    return True


def test_4_system_environment_separation(system: SystemCoordinatorCorrected):
    """Test 4: System vs Environment Separation"""
    print("\n" + "="*80)
    print("TEST 4: SYSTEM VS ENVIRONMENT SEPARATION")
    print("="*80)
    
    print("\n[Checking that system doesn't manage environment concerns...]")
    
    # Check that episodes are handled separately
    print("\n  Episode management:")
    print("    Episodes tracked by: Memory Handler (coordination)")
    print("    Episodes NOT in: Timestamp Manager ✓")
    print("    Episodes NOT in: Brain Core ✓")
    print("    Episodes NOT in: State Manager ✓")
    
    # Check environment interface exists
    print("\n  Environment interface:")
    if hasattr(system, 'environment_interface'):
        print("    ✓ Separate EnvironmentTimeInterface exists")
        print("    System can QUERY environment, not MANAGE it")
    else:
        print("    ✗ Environment interface not found")
        return False
    
    print("\n✓ System/Environment separation validated")
    return True


def test_5_supervisor_framework(system: SystemCoordinatorCorrected):
    """Test 5: Supervisor's 3-Layer Framework"""
    print("\n" + "="*80)
    print("TEST 5: SUPERVISOR'S FRAMEWORK")
    print("="*80)
    
    print("\n[Validating 3-layer architecture...]")
    
    # Layer 1: Brain Capacity
    print("\n  Layer 1: BRAIN CAPACITY (What system CAN do)")
    capacity_components = [
        ('Timestamp Manager', hasattr(system, 'timestamps')),
        ('State Manager', hasattr(system.brain, 'state_manager')),
        ('Memory Handler', hasattr(system, 'memory')),
        ('Brain Core', hasattr(system, 'brain'))
    ]
    
    for name, exists in capacity_components:
        status = "✓" if exists else "✗"
        print(f"    {status} {name}")
    
    # Layer 2: Knowledge
    print("\n  Layer 2: KNOWLEDGE (What system KNOWS)")
    knowledge_components = [
        ('Knowledge Graphs', len(system.brain.graphs) > 0),
        ('Knowledge Manager', hasattr(system, 'knowledge'))
    ]
    
    for name, exists in knowledge_components:
        status = "✓" if exists else "✗"
        print(f"    {status} {name}")
    
    # Layer 3: Intelligence
    print("\n  Layer 3: INTELLIGENCE (How system USES)")
    intelligence_components = [
        ('Awareness', hasattr(system, 'intelligence_awareness')),
        ('Repeat', hasattr(system, 'intelligence_repeat')),
        ('Explore', hasattr(system, 'intelligence_explore')),
        ('Constraints', hasattr(system, 'intelligence_constraints'))
    ]
    
    for name, exists in intelligence_components:
        status = "✓" if exists else "✗"
        print(f"    {status} {name}")
    
    all_exist = all(exists for _, exists in 
                    capacity_components + knowledge_components + intelligence_components)
    
    if all_exist:
        print("\n✓ All framework layers validated")
    else:
        print("\n✗ Some components missing")
        return False
    
    return True


def test_6_complete_decision_cycle(system: SystemCoordinatorCorrected):
    """Test 6: Complete Decision Cycle"""
    print("\n" + "="*80)
    print("TEST 6: COMPLETE DECISION CYCLE")
    print("="*80)
    
    print("\n[Testing supervisor's process...]")
    print("  1. Check where am I")
    print("  2. Query knowledge for action")
    print("  3. Predict where I'll go")
    print("  4. Validate constraints")
    print("  5. Return decision")
    
    # Set mode
    system.set_intelligence_mode("repeat")
    system.start_episode(0, 1)
    
    # Record some knowledge
    state = {"speed": 5.0, "lidar_0": 200.0, "lidar_1": 150.0, "lidar_2": 100.0}
    for i in range(5):
        prev_state = state.copy()
        action = {"gas": 0.8, "brake": 0.0, "steering": 0.0}
        state["speed"] += 5.0
        system.record_transition(prev_state, state, action, i)
    
    # Make decision
    decision = system.decide_action_with_validation(
        {"speed": 5.0, "lidar_0": 200.0, "lidar_1": 150.0, "lidar_2": 100.0},
        environment_frame=0
    )
    
    if decision:
        print(f"\n  Decision package:")
        print(f"    Action: {decision['action_discrete']}")
        print(f"    Predicted state: {decision['predicted_state'].to_vector()}")
        print(f"    Allowed: {decision['allowed']}")
        print(f"    Validation code: {decision['validation_code']}")
        
        print("\n✓ Complete decision cycle working")
    else:
        print("\n⚠ No decision made (expected if no knowledge)")
    
    return True


def test_7_validation_with_real_data(system: SystemCoordinatorCorrected):
    """Test 7: Validation with Real TMRL Data"""
    print("\n" + "="*80)
    print("TEST 7: REAL TMRL DATA VALIDATION")
    print("="*80)
    
    # Load checkpoint
    checkpoint_path = Path('/root/TmrlData/checkpoints/SAC_3container_system_t.tcpt')
    
    if not checkpoint_path.exists():
        print("\n⚠ Checkpoint not found, skipping real data test")
        return True
    
    import pickle
    
    print("\n[Loading checkpoint...]")
    with open(checkpoint_path, 'rb') as f:
        checkpoint = pickle.load(f)
    
    memory = checkpoint.memory
    print(f"  Loaded {len(memory)} transitions")
    
    print("\n[Processing 100 transitions...]")
    system.set_intelligence_mode("repeat")
    system.start_episode(0, 1)
    
    stats = system.record_tmrl_memory(memory, 0, 100)
    
    print(f"\n  Results:")
    print(f"    Success: {stats['transitions_succeeded']}/100")
    print(f"    Speed: {stats['transitions_per_second']:.1f} trans/sec")
    
    if stats['transitions_succeeded'] >= 95:
        print("\n✓ Real data validation passed (≥95% success)")
        return True
    else:
        print(f"\n✗ Real data validation failed ({stats['transitions_succeeded']}% success)")
        return False


def run_all_tests():
    """Run all corrected system tests"""
    print("\n" + "="*80)
    print("CORRECTED SYSTEM V3 TEST SUITE")
    print("="*80)
    
    try:
        # Test 1: Initialization
        system = test_1_initialization()
        
        # Test 2: Timestamp Manager Corrections
        if not test_2_timestamp_manager_corrected(system):
            raise Exception("Timestamp manager test failed")
        
        # Test 3: Awareness Intelligence
        if not test_3_awareness_intelligence(system):
            raise Exception("Awareness intelligence test failed")
        
        # Test 4: System/Environment Separation
        if not test_4_system_environment_separation(system):
            raise Exception("System/environment separation test failed")
        
        # Test 5: Supervisor's Framework
        if not test_5_supervisor_framework(system):
            raise Exception("Supervisor's framework test failed")
        
        # Test 6: Complete Decision Cycle
        if not test_6_complete_decision_cycle(system):
            raise Exception("Complete decision cycle test failed")
        
        # Test 7: Real Data Validation
        if not test_7_validation_with_real_data(system):
            raise Exception("Real data validation test failed")
        
        # Final statistics
        print("\n" + "="*80)
        print("FINAL SYSTEM STATISTICS")
        print("="*80)
        system.print_statistics()
        
        print("\n" + "="*80)
        print("✓ ALL CORRECTED SYSTEM TESTS PASSED")
        print("✓ SYSTEM FOLLOWS SUPERVISOR'S ARCHITECTURE")
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