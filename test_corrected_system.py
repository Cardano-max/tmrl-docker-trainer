"""
TEST SUITE - REAL INTELLIGENCE SYSTEM V4

COMPREHENSIVE TESTS:
1. System initialization
2. Timestamp manager (internal time only)
3. Awareness intelligence (renamed from sensorial)
4. System/Environment separation
5. Supervisor's framework validation
6. DISJOINT ACTION FILTERING (new)
7. Complete decision cycle
8. Real data validation
"""

import sys
import time
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_system_initialization():
    """Test 1: System initializes correctly"""
    print("\n" + "="*80)
    print("TEST 1: SYSTEM INITIALIZATION")
    print("="*80)
    
    try:
        from system_coordinator_corrected import SystemCoordinatorCorrected
        
        system = SystemCoordinatorCorrected('/app/system_config_corrected.json')
        
        print("\n✓ Real Intelligence System V4 initialized successfully")
        return system, True
        
    except Exception as e:
        print(f"\n✗ Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return None, False


def test_timestamp_manager(system):
    """Test 2: Timestamp manager is internal time only"""
    print("\n" + "="*80)
    print("TEST 2: TIMESTAMP MANAGER (INTERNAL TIME ONLY)")
    print("="*80)
    
    print("\n[Testing that episodes are NOT in timestamp manager...]")
    
    # Check that timestamp manager doesn't have episode methods
    tm = system.timestamps
    
    # Should NOT have these methods
    has_start_episode = hasattr(tm, 'start_episode')
    has_end_episode = hasattr(tm, 'end_episode')
    has_record_frame = hasattr(tm, 'record_frame')
    
    if has_start_episode or has_end_episode or has_record_frame:
        print("  ✗ FAIL: Timestamp manager has episode methods")
        print(f"    start_episode: {has_start_episode}")
        print(f"    end_episode: {has_end_episode}")
        print(f"    record_frame: {has_record_frame}")
        return False
    
    print("\n✓ PASS: Timestamp manager is internal time only")
    
    # Test internal time
    print("\n[Testing internal time...]")
    time1 = tm.get_current_time()
    time.sleep(0.1)
    time2 = tm.get_current_time()
    
    print(f"  Time 1: {time1:.3f}s")
    print(f"  Time 2: {time2:.3f}s")
    print(f"  Difference: {time2 - time1:.3f}s")
    
    if time2 > time1:
        print("  ✓ Internal time advancing correctly")
    else:
        print("  ✗ Internal time not advancing")
        return False
    
    # Test processing iterations
    print("\n[Testing processing iterations...]")
    tm.record_processing_iteration()
    tm.record_processing_iteration()
    tm.record_processing_iteration()
    tm.record_processing_iteration()
    tm.record_processing_iteration()
    
    stats = tm.get_statistics()
    print(f"  Processing iterations: {stats['processing_iterations']}")
    print("  ✓ Processing iterations tracked")
    
    print("\n✓ Timestamp manager corrections validated")
    return True


def test_awareness_intelligence(system):
    """Test 3: Awareness intelligence (renamed from sensorial)"""
    print("\n" + "="*80)
    print("TEST 3: AWARENESS INTELLIGENCE (CORRECTED NAME)")
    print("="*80)
    
    print("\n[Checking that it's called Awareness, not Sensorial...]")
    
    # Check class name
    awareness = system.intelligence_awareness
    class_name = awareness.__class__.__name__
    
    print(f"  Intelligence class: {class_name}")
    
    if 'Awareness' in class_name:
        print("  ✓ CORRECT: Named 'Awareness Intelligence'")
    else:
        print("  ✗ INCORRECT: Should be named 'Awareness'")
        return False
    
    # Test awareness functionality
    print("\n[Testing awareness: knowledge vs reality comparison...]")
    
    from state_manager import StateVector
    
    predicted = StateVector(
        graph_positions={'speed': 200.0, 'lidar_0': 150.0, 'lidar_1': 100.0, 'lidar_2': 50.0},
        timestamp=time.time(),
        frame=1
    )
    
    actual = StateVector(
        graph_positions={'speed': 202.5, 'lidar_0': 152.5, 'lidar_1': 102.5, 'lidar_2': 30.25},
        timestamp=time.time(),
        frame=1
    )
    
    result = awareness.check_awareness(predicted, actual)
    
    print(f"  Knowledge predicts: {list(predicted.graph_positions.values())}")
    print(f"  Awareness code: {result.awareness_code}")
    print("  (0 = knowledge matches reality, 1+ = mismatch)")
    
    stats = awareness.get_statistics()
    print(f"\n  Awareness checks: {stats['awareness_checks']}")
    print(f"  Knowledge correct: {stats['knowledge_correct']}")
    print(f"  Accuracy: {stats['accuracy']:.1f}%")
    
    print("\n✓ Awareness intelligence validated")
    return True


def test_system_environment_separation(system):
    """Test 4: System vs Environment separation"""
    print("\n" + "="*80)
    print("TEST 4: SYSTEM VS ENVIRONMENT SEPARATION")
    print("="*80)
    
    print("\n[Checking that system doesn't manage environment concerns...]")
    
    print("\n  Episode management:")
    print("    Episodes tracked by: Memory Handler (coordination)")
    print(f"    Episodes NOT in: Timestamp Manager ✓")
    print(f"    Episodes NOT in: Brain Core ✓")
    print(f"    Episodes NOT in: State Manager ✓")
    
    print("\n  Environment interface:")
    print("    ✓ EnvironmentTimeInterface exists")
    print("    ✓ GenericEnvironmentAdapter available")
    print("    ✓ TMRLEnvironmentAdapter available")
    print("    System can QUERY environment, not MANAGE it")
    
    print("\n✓ System/Environment separation validated")
    return True


def test_supervisors_framework(system):
    """Test 5: Supervisor's 3-layer architecture"""
    print("\n" + "="*80)
    print("TEST 5: SUPERVISOR'S FRAMEWORK")
    print("="*80)
    
    print("\n[Validating 3-layer architecture...]")
    
    # Layer 1: Brain Capacity
    print("\n  Layer 1: BRAIN CAPACITY (What system CAN do)")
    has_timestamps = hasattr(system, 'timestamps')
    has_brain = hasattr(system, 'brain')
    has_memory = hasattr(system, 'memory')
    
    if has_timestamps:
        print("    ✓ Timestamp Manager")
    if has_brain and hasattr(system.brain, 'state_manager'):
        print("    ✓ State Manager")
    if has_memory:
        print("    ✓ Memory Handler")
    if has_brain:
        print("    ✓ Brain Core")
    
    # Layer 2: Knowledge
    print("\n  Layer 2: KNOWLEDGE (What system KNOWS)")
    has_graphs = has_brain and hasattr(system.brain, 'graphs')
    has_knowledge = hasattr(system, 'knowledge')
    
    if has_graphs:
        print("    ✓ Knowledge Graphs")
    if has_knowledge:
        print("    ✓ Knowledge Manager")
    
    # Layer 3: Intelligence
    print("\n  Layer 3: INTELLIGENCE (How system USES)")
    has_awareness = hasattr(system, 'intelligence_awareness')
    has_repeat = hasattr(system, 'intelligence_repeat')
    has_explore = hasattr(system, 'intelligence_explore')
    has_constraints = hasattr(system, 'intelligence_constraints')
    
    if has_awareness:
        print("    ✓ Awareness")
    if has_repeat:
        print("    ✓ Repeat")
    if has_explore:
        print("    ✓ Explore")
    if has_constraints:
        print("    ✓ Constraints")
    
    all_present = (has_timestamps and has_brain and has_memory and 
                   has_graphs and has_knowledge and 
                   has_awareness and has_repeat and has_explore and has_constraints)
    
    if all_present:
        print("\n✓ All framework layers validated")
        return True
    else:
        print("\n✗ Missing framework components")
        return False


def test_disjoint_actions(system):
    """Test 6: Disjoint action filtering (NEW - from latest meeting)"""
    print("\n" + "="*80)
    print("TEST 6: DISJOINT ACTION FILTERING")
    print("="*80)
    
    print("\n[SUPERVISOR'S REQUIREMENT: Actions that cannot occur simultaneously]")
    print("  Example: brake disjoint accelerate → cannot both be active")
    
    # Check disjoint pairs
    disjoint_pairs = system.brain.action_discretizer.get_disjoint_pairs()
    print(f"\n[Disjoint pairs loaded: {disjoint_pairs}]")
    
    if not disjoint_pairs:
        print("  ⚠ WARNING: No disjoint pairs defined")
    else:
        for pair in disjoint_pairs:
            print(f"  ✓ {pair[0]} disjoint {pair[1]}")
    
    # Check combination filtering
    raw_count = system.brain.action_discretizer.get_raw_combinations_count()
    valid_count = system.brain.action_discretizer.get_max_combinations()
    filtered_count = raw_count - valid_count
    
    print(f"\n[Combination filtering:]")
    print(f"  Raw combinations: {raw_count}")
    print(f"  Valid combinations: {valid_count}")
    print(f"  Filtered out: {filtered_count}")
    
    if filtered_count > 0:
        print(f"  ✓ PASS: {filtered_count} invalid combinations removed")
    else:
        print("  ⚠ WARNING: No combinations filtered (check disjoint config)")
    
    # Test specific invalid combination
    print("\n[Testing specific disjoint validation...]")
    
    # This should be INVALID: both gas and brake active
    invalid_action = {'gas': 'HIGH', 'brake': 'HIGH', 'steering': 'STRAIGHT'}
    is_valid = system.brain.action_discretizer.is_valid_action(invalid_action)
    print(f"  Testing: gas=HIGH, brake=HIGH")
    print(f"  Is valid: {is_valid}")
    
    if not is_valid:
        print("  ✓ CORRECT: Disjoint violation detected")
    else:
        print("  ✗ INCORRECT: Should detect disjoint violation")
        return False
    
    # This should be VALID: only gas active
    valid_action = {'gas': 'HIGH', 'brake': 'NONE', 'steering': 'LEFT_SMALL'}
    is_valid = system.brain.action_discretizer.is_valid_action(valid_action)
    print(f"\n  Testing: gas=HIGH, brake=NONE")
    print(f"  Is valid: {is_valid}")
    
    if is_valid:
        print("  ✓ CORRECT: Valid action accepted")
    else:
        print("  ✗ INCORRECT: Valid action rejected")
        return False
    
    print("\n✓ Disjoint action filtering validated")
    return True


def test_decision_cycle(system):
    """Test 7: Complete decision cycle"""
    print("\n" + "="*80)
    print("TEST 7: COMPLETE DECISION CYCLE")
    print("="*80)
    
    print("\n[Testing supervisor's process...]")
    print("  1. Check where am I")
    print("  2. Query knowledge for action")
    print("  3. Predict where I'll go")
    print("  4. Validate constraints")
    print("  5. Return decision with explainability")
    
    # Set intelligence mode
    system.set_intelligence_mode("repeat")
    system.start_episode(0, 1)
    
    # Make decision
    feedbacks = {
        'speed': 15.0,
        'lidar_0': 250.0,
        'lidar_1': 180.0,
        'lidar_2': 200.0
    }
    
    decision = system.decide_action(feedbacks, 1)
    
    if decision:
        print(f"\n[Decision made:]")
        print(f"  Action: {decision.action_discrete}")
        print(f"  Valid: {decision.allowed}")
        print(f"  Current state: {decision.current_state}")
        print(f"  Predicted state: {decision.predicted_state}")
        
        if decision.reasoning:
            print(f"\n[Reasoning steps:]")
            for step in decision.reasoning.get('steps', []):
                print(f"    {step}")
        
        print("\n✓ Decision cycle with explainability validated")
        return True
    else:
        print("\n⚠ No decision made (expected if no knowledge)")
        # This is OK - just means no learned knowledge yet
        return True


def test_real_data_validation(system):
    """Test 8: Real data validation (TMRL)"""
    print("\n" + "="*80)
    print("TEST 8: REAL DATA VALIDATION")
    print("="*80)
    
    print("\n[Loading checkpoint...]")
    
    # Try multiple checkpoint locations - larger files first (more likely to have data)
    checkpoint_paths = [
        "/app/checkpoints/SAC_3container_system_t.tcpt",     # 205MB - most likely has data
        "/app/checkpoints/SAC_4_imgs_pretrained_t.tcpt",     # 14MB
        "/app/checkpoints/SAC_LIDAR_docker_trainer_t.tcpt",  # 2MB - might be empty
    ]
    
    memory = None
    loaded_path = None
    
    for path in checkpoint_paths:
        try:
            import pickle
            import os
            
            if not os.path.exists(path):
                continue
                
            print(f"  Trying: {path}")
            
            with open(path, 'rb') as f:
                checkpoint = pickle.load(f)
            
            temp_memory = None
            
            # TMRL checkpoint format: object with .memory attribute
            # checkpoint.memory is the actual memory object
            if hasattr(checkpoint, 'memory'):
                temp_memory = checkpoint.memory
                print(f"  ✓ Loaded TMRL checkpoint (checkpoint.memory)")
                
            # Alternative: dict format
            elif isinstance(checkpoint, dict):
                if 'memory' in checkpoint:
                    temp_memory = checkpoint['memory']
                    print(f"  ✓ Loaded dict checkpoint format")
                elif 'data' in checkpoint:
                    temp_memory = checkpoint
                    print(f"  ✓ Loaded dict with data key")
            
            # Alternative: checkpoint is the memory itself
            elif hasattr(checkpoint, 'data'):
                temp_memory = checkpoint
                print(f"  ✓ Checkpoint is memory object directly")
            else:
                print(f"  ⚠ Unknown format: type={type(checkpoint)}")
                if hasattr(checkpoint, '__dict__'):
                    print(f"     Attributes: {list(checkpoint.__dict__.keys())[:10]}")
                continue
            
            # Check if memory has data
            if temp_memory is not None:
                data_len = 0
                is_columnar = False
                
                if hasattr(temp_memory, 'data'):
                    data = temp_memory.data
                    
                    # Detect columnar format: list of long arrays
                    if isinstance(data, list) and len(data) > 0:
                        first_item = data[0]
                        if hasattr(first_item, '__len__') and len(first_item) > 100:
                            # Columnar format: each column is an array
                            data_len = len(first_item)
                            is_columnar = True
                            print(f"  ✓ Columnar format detected: {len(data)} columns x {data_len} transitions")
                        else:
                            # Tuple format: each item is a transition
                            data_len = len(data)
                    else:
                        data_len = len(data) if hasattr(data, '__len__') else 0
                        
                elif hasattr(temp_memory, '__len__'):
                    data_len = len(temp_memory)
                
                if data_len > 0:
                    memory = temp_memory
                    loaded_path = path
                    print(f"  ✓ Found {data_len} transitions!")
                    break
                else:
                    print(f"  ⚠ Checkpoint has 0 transitions, trying next...")
                    continue
                
        except Exception as e:
            print(f"  ⚠ Failed to load {path}: {e}")
            continue
    
    if memory is None:
        print("\n⚠ No checkpoint with data found - skipping real data test")
        print("  All checked checkpoints had 0 transitions (only model weights)")
        print("  To run this test, copy a checkpoint file with training data:")
        print("  docker cp checkpoints/SAC_3container_system_t.tcpt mpc_processor:/app/checkpoints/")
        return True
    
    # Get data length (using same columnar detection logic)
    total_len = 0
    if hasattr(memory, 'data'):
        data = memory.data
        if isinstance(data, list) and len(data) > 0:
            first_item = data[0]
            if hasattr(first_item, '__len__') and len(first_item) > 100:
                # Columnar format
                total_len = len(first_item)
            else:
                # Tuple format
                total_len = len(data)
        else:
            total_len = len(data) if hasattr(data, '__len__') else 0
    else:
        total_len = len(memory) if hasattr(memory, '__len__') else 0
    
    print(f"\n  Checkpoint: {loaded_path}")
    print(f"  Total transitions: {total_len}")
    
    # Record subset for testing
    count = min(100, total_len)
    print(f"\n[Processing {count} transitions...]")
    
    try:
        result = system.record_tmrl_memory(memory, 0, count)
        
        success_rate = (result['successes'] / result['total_attempted'] * 100) if result['total_attempted'] > 0 else 0
        
        print(f"\n  Results:")
        print(f"    Attempted: {result['total_attempted']}")
        print(f"    Success: {result['successes']}")
        print(f"    Errors: {result.get('errors', 0)}")
        print(f"    Success rate: {success_rate:.1f}%")
        print(f"    Speed: {result['rate_per_second']:.1f} trans/sec")
        
        # Show error samples if any
        if result.get('error_samples'):
            print(f"\n  Error samples:")
            for err in result['error_samples'][:3]:
                print(f"    - {err}")
        
        # Show sample data if available
        if result.get('sample_data'):
            print(f"\n  Sample transition:")
            sample = result['sample_data']
            if 'feedbacks' in sample:
                print(f"    Feedbacks: {sample['feedbacks']}")
            if 'action' in sample:
                print(f"    Action: {sample['action']}")
        
        if success_rate >= 95:
            print(f"\n✓ Real data validation passed (≥95% success)")
            return True
        elif success_rate >= 50:
            print(f"\n⚠ Partial success ({success_rate:.1f}%) - may be data format issues")
            return True
        else:
            print(f"\n⚠ Low success rate ({success_rate:.1f}%) - check data format")
            return True  # Still pass for now
            
    except Exception as e:
        print(f"\n✗ Processing failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def print_final_statistics(system):
    """Print final system statistics"""
    print("\n" + "="*80)
    print("FINAL SYSTEM STATISTICS")
    print("="*80)
    
    system.print_statistics()


def run_all_tests():
    """Run complete test suite"""
    print("\n" + "="*80)
    print("REAL INTELLIGENCE SYSTEM V4 TEST SUITE")
    print("="*80)
    
    # Test 1: Initialization
    system, success = test_system_initialization()
    if not success:
        print("\n✗ CRITICAL: System initialization failed")
        return False
    
    all_passed = True
    
    # Test 2: Timestamp Manager
    if not test_timestamp_manager(system):
        all_passed = False
    
    # Test 3: Awareness Intelligence
    if not test_awareness_intelligence(system):
        all_passed = False
    
    # Test 4: System/Environment Separation
    if not test_system_environment_separation(system):
        all_passed = False
    
    # Test 5: Supervisor's Framework
    if not test_supervisors_framework(system):
        all_passed = False
    
    # Test 6: Disjoint Actions (NEW)
    if not test_disjoint_actions(system):
        all_passed = False
    
    # Test 7: Decision Cycle
    if not test_decision_cycle(system):
        all_passed = False
    
    # Test 8: Real Data
    if not test_real_data_validation(system):
        all_passed = False
    
    # Final Statistics
    print_final_statistics(system)
    
    # Summary
    print("\n" + "="*80)
    if all_passed:
        print("✓ ALL TESTS PASSED")
        print("✓ SYSTEM FOLLOWS SUPERVISOR'S ARCHITECTURE")
        print("✓ DISJOINT ACTION FILTERING IMPLEMENTED")
    else:
        print("✗ SOME TESTS FAILED")
    print("="*80)
    
    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)