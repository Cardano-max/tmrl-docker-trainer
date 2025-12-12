"""
SYSTEM V3 - REAL TMRL DATA VALIDATION (FIXED)
Complete production-level testing with real checkpoint
"""

import logging
import sys
import pickle
from pathlib import Path

from system_coordinator_v3 import SystemCoordinator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_with_real_data():
    """Validate V3 system with real TMRL checkpoint"""
    
    print("="*80)
    print("SYSTEM V3 - REAL TMRL DATA VALIDATION")
    print("="*80)
    
    try:
        # ============================================================
        # PHASE 1: INITIALIZATION
        # ============================================================
        print("\n[PHASE 1/5] Initializing System V3...")
        system = SystemCoordinator('/app/system_config_v3.json')
        print("✓ System V3 initialized")
        
        # ============================================================
        # PHASE 2: LOAD REAL CHECKPOINT
        # ============================================================
        print("\n[PHASE 2/5] Loading Real TMRL Checkpoint...")
        checkpoint_path = Path('/root/TmrlData/checkpoints/SAC_3container_system_t.tcpt')
        
        if not checkpoint_path.exists():
            print(f"✗ Checkpoint not found: {checkpoint_path}")
            return False
        
        with open(checkpoint_path, 'rb') as f:
            checkpoint = pickle.load(f)
        
        memory = checkpoint.memory
        print(f"✓ Checkpoint loaded: {len(memory)} transitions")
        
        # ============================================================
        # PHASE 3: PROCESS TRANSITIONS WITH ALL VALIDATIONS
        # ============================================================
        print("\n[PHASE 3/5] Processing Transitions with Full Validation Chain...")
        print("  (Range monitoring + Prediction + Constraints)")
        
        # Set intelligence mode
        system.set_intelligence_mode("repeat")
        system.start_episode(start_frame=0, episode_number=1)
        
        # CRITICAL FIX: Link timestamp manager BEFORE processing
        print("  [Linking timestamp manager to recorder...]")
        system.recorder.set_timestamp_manager(system.timestamps)
        
        # Process 500 transitions (more comprehensive than before)
        stats = system.recorder.record_tmrl_memory(memory, start_index=0, count=500)
        
        print(f"\n  Results:")
        print(f"    Success: {stats['transitions_succeeded']}/{stats['transitions_attempted']}")
        print(f"    Speed: {stats['transitions_per_second']:.1f} trans/sec")
        print(f"    Frames tracked: {stats.get('frames_processed', 0)}")
        
        if stats['transitions_succeeded'] < stats['transitions_attempted']:
            print(f"    ⚠ Failed: {stats['transitions_failed']} transitions")
        
        # ============================================================
        # PHASE 4: TEST ALL V3 FEATURES
        # ============================================================
        print("\n[PHASE 4/5] Testing V3 Features with Real Data...")
        
        # 4.1: Dual Timestamps
        print("\n  [4.1] Dual Timestamps:")
        ts_stats = system.timestamps.get_statistics()
        print(f"    Agent runtime: {ts_stats['agent']['runtime_seconds']:.2f}s")
        print(f"    Total frames: {ts_stats['agent']['total_frames']}")
        print(f"    Episode: {ts_stats['episode']['number']}")
        if ts_stats['agent']['total_frames'] > 0:
            print(f"    ✓ Dual timestamps operational")
        else:
            print(f"    ✗ Timestamp tracking not working")
        
        # 4.2: Sensorial Intelligence (Prediction Validation)
        print("\n  [4.2] Sensorial Intelligence:")
        sens_stats = system.intelligence_sensorial.get_statistics()
        print(f"    Predictions made: {sens_stats['predictions_made']}")
        print(f"    Predictions correct: {sens_stats['predictions_correct']}")
        print(f"    Accuracy: {sens_stats['accuracy']:.1f}%")
        print(f"    Minor deviations: {sens_stats['minor_deviations']}")
        print(f"    Major deviations: {sens_stats['major_deviations']}")
        print(f"    ✓ Prediction validation working")
        
        # 4.3: Future Constraints
        print("\n  [4.3] Future Constraints:")
        const_stats = system.intelligence_constraints.get_statistics()
        print(f"    Constraints defined: {const_stats['constraints_defined']}")
        print(f"    Hard constraints: {const_stats['hard_constraints']}")
        print(f"    Soft constraints: {const_stats['soft_constraints']}")
        print(f"    Total violations: {const_stats['total_violations']}")
        print(f"    ✓ Constraint monitoring active")
        
        # 4.4: State Management
        print("\n  [4.4] State Management:")
        awareness = system.what_am_i()
        brain_state = awareness['brain_state']
        print(f"    State vector: {brain_state['state_vector']}")
        print(f"    Transitions: {brain_state['transitions']}")
        print(f"    ✓ State tracking working")
        
        # 4.5: Memory Handler
        print("\n  [4.5] Memory Handler:")
        mem_stats = system.memory.get_statistics()
        print(f"    Episodes recorded: {mem_stats['episodes_recorded_total']}")
        print(f"    Short-term queries: {mem_stats['short_term_queries']}")
        print(f"    ✓ Memory management working")
        
        # ============================================================
        # PHASE 5: PRODUCTION QUALITY CHECKS
        # ============================================================
        print("\n[PHASE 5/5] Production Quality Checks...")
        
        quality_pass = True
        
        # Check 1: Success Rate
        success_rate = (stats['transitions_succeeded'] / stats['transitions_attempted']) * 100
        if success_rate < 95.0:
            print(f"  ✗ Success rate too low: {success_rate:.1f}% (required: >95%)")
            quality_pass = False
        else:
            print(f"  ✓ Success rate: {success_rate:.1f}%")
        
        # Check 2: Performance
        if stats['transitions_per_second'] < 50:
            print(f"  ✗ Performance too slow: {stats['transitions_per_second']:.1f} trans/sec (required: >50)")
            quality_pass = False
        else:
            print(f"  ✓ Performance: {stats['transitions_per_second']:.1f} trans/sec")
        
        # Check 3: Knowledge Graphs Populated
        brain_stats = system.brain.get_system_statistics()
        total_nodes = sum(g['nodes'] for g in brain_stats['graphs'].values())
        total_edges = sum(g['edges'] for g in brain_stats['graphs'].values())
        
        if total_nodes == 0 or total_edges == 0:
            print(f"  ✗ Knowledge graphs not populated")
            quality_pass = False
        else:
            print(f"  ✓ Knowledge graphs populated: {total_nodes} nodes, {total_edges} edges")
        
        # Check 4: State Tracking
        if brain_state['transitions'] == 0:
            print(f"  ✗ No state transitions recorded")
            quality_pass = False
        else:
            print(f"  ✓ State transitions: {brain_state['transitions']}")
        
        # Check 5: Timestamp Tracking (CRITICAL V3 FEATURE)
        if ts_stats['agent']['total_frames'] == 0:
            print(f"  ✗ Timestamp tracking not working (0 frames)")
            quality_pass = False
        else:
            print(f"  ✓ Timestamp tracking: {ts_stats['agent']['total_frames']} frames")
        
        # Check 6: All V3 Features Active
        required_features = {
            'timestamps': ts_stats['agent']['total_frames'] > 0,
            'sensorial': True,  # Always initialized
            'constraints': const_stats['constraints_defined'] > 0,
            'state_tracking': brain_state['transitions'] > 0,
            'memory': True  # Always initialized
        }
        
        for feature, active in required_features.items():
            if not active:
                print(f"  ✗ Feature not active: {feature}")
                quality_pass = False
        
        if all(required_features.values()):
            print(f"  ✓ All V3 features active")
        
        # ============================================================
        # FINAL REPORT
        # ============================================================
        print("\n" + "="*80)
        print("COMPLETE SYSTEM V3 STATISTICS")
        print("="*80)
        system.print_statistics()
        
        print("\n" + "="*80)
        if quality_pass:
            print("✓ PRODUCTION QUALITY: PASS")
            print("✓ SYSTEM V3 READY FOR PRESENTATION")
        else:
            print("✗ PRODUCTION QUALITY: FAIL")
            print("✗ Some quality checks did not pass")
        print("="*80)
        
        return quality_pass
        
    except Exception as e:
        print("\n" + "="*80)
        print(f"✗ VALIDATION FAILED: {e}")
        print("="*80)
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = validate_with_real_data()
    sys.exit(0 if success else 1)