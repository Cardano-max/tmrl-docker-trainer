"""
TMRL Enhanced Trainer with Database Feedback
Real bidirectional communication for knowledge graph research
FIXED: Resumes transition numbering from existing files
"""
import os
import json
import time
import numpy as np
from datetime import datetime
import sys
import traceback

DATABASE_PATH = os.getenv('DATABASE_PATH', '/shared-data')

class TransitionLogger:
    """Logs complete SARS' transitions with database feedback"""
    
    def __init__(self, base_path):
        self.base_path = base_path
        
        # FIX: Check existing files and continue numbering
        transitions_dir = f"{base_path}/transitions"
        os.makedirs(transitions_dir, exist_ok=True)
        
        # Find highest existing transition ID
        existing_files = []
        if os.path.exists(transitions_dir):
            try:
                existing_files = [f for f in os.listdir(transitions_dir) 
                                if f.startswith('transition_') and f.endswith('.json')]
            except:
                pass
        
        if existing_files:
            # Extract numbers from filenames
            ids = []
            for f in existing_files:
                try:
                    # transition_00012345.json -> 12345
                    num = int(f.split('_')[1].split('.')[0])
                    ids.append(num)
                except:
                    continue
            
            if ids:
                self.logged_count = max(ids)
                print(f"[DATABASE] ✓ Resuming from transition {self.logged_count} (found {len(existing_files)} existing files)")
            else:
                self.logged_count = 0
        else:
            self.logged_count = 0
            print(f"[DATABASE] Starting fresh - no existing transitions found")
        
        self.last_memory_size = None
        self.initialized = False
        
        # DATABASE FEEDBACK SYSTEM
        self.db_config = {"reward_scale": 1.0, "constraints": []}
        self.config_path = os.path.join(base_path, "db_to_trainer", "config.json")
        self.last_config_check = 0
        
        os.makedirs(f"{base_path}/metrics", exist_ok=True)
        
        print("[DATABASE] Transition Logger initialized with feedback system")
    
    def _serialize(self, obj):
        """Convert to JSON"""
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.floating, np.integer)):
            return float(obj)
        elif isinstance(obj, (list, tuple)):
            return [self._serialize(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: self._serialize(v) for k, v in obj.items()}
        else:
            return obj
    
    def _load_db_config(self):
        """Load configuration from database analyzer"""
        try:
            current_time = time.time()
            # Check every 30 seconds to avoid excessive file I/O
            if current_time - self.last_config_check < 30:
                return
            
            self.last_config_check = current_time
            
            if os.path.exists(self.config_path):
                with open(self.config_path, "r") as f:
                    cfg = json.load(f)
                
                # Extract trainer parameters
                old_scale = self.db_config.get("reward_scale", 1.0)
                new_scale = cfg.get("trainer_parameters", {}).get("reward_scale", 1.0)
                
                # Notify if config changed
                if old_scale != new_scale:
                    print(f"[DATABASE] ✓ DB feedback received: reward_scale {old_scale} → {new_scale}")
                    stats = cfg.get("statistics", {})
                    print(f"[DATABASE]   Based on: {cfg.get('num_transitions_analyzed', 0)} transitions")
                    print(f"[DATABASE]   Avg reward: {stats.get('avg_reward', 0):.4f}")
                
                # Update internal config
                self.db_config = {
                    "reward_scale": new_scale,
                    "constraints": cfg.get("trainer_parameters", {}).get("constraints", []),
                    "statistics": cfg.get("statistics", {}),
                    "timestamp": cfg.get("timestamp", "")
                }
                
        except Exception as e:
            # Silent fail - use default config
            pass
    
    def log_new_transitions(self, memory):
        """Log new transitions"""
        try:
            current_size = len(memory)
            
            # Initialize on first call
            if not self.initialized:
                self.last_memory_size = current_size
                self.initialized = True
                print(f"[DATABASE] Starting logging from memory position {current_size}")
                # Try to load config immediately
                self._load_db_config()
                return
            
            # Check for new transitions
            if current_size > self.last_memory_size:
                new_count = current_size - self.last_memory_size
                print(f"[DATABASE] Logging {new_count} new transitions (memory: {self.last_memory_size} → {current_size})")
                
                # Log each new transition
                logged_this_batch = 0
                for idx in range(self.last_memory_size, current_size):
                    try:
                        transition = memory.get_transition(idx)
                        self.log_transition(transition, idx)
                        logged_this_batch += 1
                        
                        # Progress every 100
                        if logged_this_batch % 100 == 0:
                            print(f"[DATABASE]   ... {logged_this_batch}/{new_count} done")
                            
                    except Exception as e:
                        print(f"[DATABASE] Error at idx {idx}: {e}")
                        traceback.print_exc()
                        continue
                
                self.last_memory_size = current_size
                print(f"[DATABASE] ✓ Batch complete! Total logged: {self.logged_count}")
        
        except Exception as e:
            print(f"[DATABASE] ERROR in log_new_transitions: {e}")
            traceback.print_exc()
    
    def log_transition(self, trans, idx):
        """Log single transition with database feedback"""
        try:
            # Load DB config periodically
            self._load_db_config()
            
            self.logged_count += 1
            filename = f"{self.base_path}/transitions/transition_{self.logged_count:08d}.json"
            
            # Unpack transition
            obs = trans[0] if len(trans) > 0 else None
            act = trans[1] if len(trans) > 1 else None
            rew = trans[2] if len(trans) > 2 else 0.0
            next_obs = trans[3] if len(trans) > 3 else None
            done = trans[4] if len(trans) > 4 else False
            truncated = trans[5] if len(trans) > 5 else False
            
            # APPLY DATABASE FEEDBACK
            reward_scale = float(self.db_config.get("reward_scale", 1.0))
            adjusted_reward = float(rew) * reward_scale
            
            # Build transition data with feedback
            data = {
                'transition_id': self.logged_count,
                'memory_idx': idx,
                'timestamp': datetime.now().isoformat(),
                
                'state': self._parse_obs(obs),
                'action': self._parse_action(act),
                
                'reward': float(rew),
                'adjusted_reward': adjusted_reward,  # ← USING DB FEEDBACK!
                
                'db_feedback': {
                    'reward_scale': reward_scale,
                    'constraints': self.db_config.get("constraints", []),
                    'statistics': self.db_config.get("statistics", {}),
                    'last_update': self.db_config.get("timestamp", "")
                },
                
                'next_state': self._parse_obs(next_obs),
                'done': bool(done),
                'truncated': bool(truncated)
            }
            
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            print(f"[DATABASE] Error logging: {e}")
            traceback.print_exc()
    
    def _parse_obs(self, obs):
        """Parse TMRL observation (speed + LIDAR)"""
        try:
            if obs is None:
                return None
            
            result = {"type": "tmrl_lidar"}
            
            if isinstance(obs, tuple) and len(obs) >= 2:
                speed = obs[0]
                lidar = obs[1]
                
                # Parse speed
                if isinstance(speed, np.ndarray):
                    result['speed'] = float(speed[0]) if len(speed) > 0 else 0.0
                
                # Parse LIDAR
                if isinstance(lidar, np.ndarray):
                    result['lidar'] = lidar.tolist()
            
            return result
        except:
            return {"error": "parse_failed"}
    
    def _parse_action(self, act):
        """Parse action [gas, brake, steering]"""
        try:
            if act is None:
                return None
            
            if isinstance(act, np.ndarray) and len(act) >= 3:
                return {
                    'gas': float(act[0]),
                    'brake': float(act[1]),
                    'steering': float(act[2])
                }
            return {"raw": self._serialize(act)}
        except:
            return {"error": "parse_failed"}

# Initialize
print("="*60)
print("[DATABASE] Initializing Production Logger with Feedback...")
print("="*60)
logger = TransitionLogger(DATABASE_PATH)

with open(f"{DATABASE_PATH}/status.json", 'w') as f:
    json.dump({
        'status': 'production_with_feedback',
        'timestamp': datetime.now().isoformat(),
        'version': '2.1_fixed_numbering'
    }, f, indent=2)

# Patch TMRL
print("[TRAINER] Patching TMRL...")

from tmrl.training_offline import TrainingOffline

original_run_epoch = TrainingOffline.run_epoch

def patched_run_epoch(self, interface):
    """Patched version with logging"""
    
    print("[DATABASE] ═══ run_epoch called ═══")
    
    # Call original
    result = original_run_epoch(self, interface)
    
    # Log transitions
    print("[DATABASE] ═══ Logging transitions ═══")
    try:
        if hasattr(self, 'memory'):
            logger.log_new_transitions(self.memory)
        else:
            print("[DATABASE] ERROR: No memory attribute!")
    except Exception as e:
        print(f"[DATABASE] EXCEPTION in logging: {e}")
        traceback.print_exc()
    
    return result

TrainingOffline.run_epoch = patched_run_epoch
print("[TRAINER] ✓ Patch applied - ready for DB feedback")
print("="*60)

# Start TMRL
import argparse
from tmrl import __main__ as tmrl_main_module

parser = argparse.ArgumentParser()
parser.add_argument('--server', action='store_true')
parser.add_argument('--trainer', action='store_true')
parser.add_argument('--worker', action='store_true')
parser.add_argument('--test', action='store_true')
parser.add_argument('--benchmark', action='store_true')
parser.add_argument('--expert', action='store_true')
parser.add_argument('--wandb', action='store_true')
parser.add_argument('--profile', action='store_true')

sys.argv = ['tmrl', '--trainer']
args = parser.parse_args()

print("[TRAINER] Starting TMRL main...")
tmrl_main_module.main(args)