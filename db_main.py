"""
Database Main - Analyzes transitions and sends config to trainer
Real bidirectional communication for knowledge graph research
"""
import os
import json
import time
from datetime import datetime

BASE_PATH = "/shared-data"
TRANSITIONS_DIR = os.path.join(BASE_PATH, "transitions")
DB_STORE_DIR = os.path.join(BASE_PATH, "db_store")
DB_TO_TRAINER_DIR = os.path.join(BASE_PATH, "db_to_trainer")

os.makedirs(DB_STORE_DIR, exist_ok=True)
os.makedirs(DB_TO_TRAINER_DIR, exist_ok=True)

PROCESSED_FILE = os.path.join(DB_STORE_DIR, "processed_files.json")
KG_FILE = os.path.join(DB_STORE_DIR, "kg_transitions.jsonl")
CONFIG_FILE = os.path.join(DB_TO_TRAINER_DIR, "config.json")

def load_processed():
    """Load list of already processed files"""
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_processed(processed):
    """Save processed files list"""
    with open(PROCESSED_FILE, "w") as f:
        json.dump(list(processed), f)

def process_new_transitions(processed):
    """Read new transitions and append to KG store"""
    try:
        if not os.path.exists(TRANSITIONS_DIR):
            return 0, processed
        
        files = sorted(os.listdir(TRANSITIONS_DIR))
        new_files = [f for f in files if f.endswith(".json") and f not in processed]
        
        if not new_files:
            return 0, processed
        
        count = 0
        with open(KG_FILE, "a") as kg_out:
            for fname in new_files:
                path = os.path.join(TRANSITIONS_DIR, fname)
                try:
                    with open(path, "r") as f:
                        trans = json.load(f)
                    
                    # Build KG-style edge record
                    edge = {
                        "transition_id": trans.get("transition_id"),
                        "timestamp": trans.get("timestamp"),
                        "state_speed": trans.get("state", {}).get("speed"),
                        "state_lidar": trans.get("state", {}).get("lidar"),
                        "action_gas": trans.get("action", {}).get("gas"),
                        "action_brake": trans.get("action", {}).get("brake"),
                        "action_steering": trans.get("action", {}).get("steering"),
                        "reward": trans.get("reward"),
                        "next_state_speed": trans.get("next_state", {}).get("speed"),
                        "done": trans.get("done", False)
                    }
                    
                    kg_out.write(json.dumps(edge) + "\n")
                    processed.add(fname)
                    count += 1
                    
                except Exception as e:
                    print(f"[DB] Error processing {fname}: {e}")
        
        save_processed(processed)
        if count > 0:
            print(f"[DB] ✓ Appended {count} transitions to KG store")
        return count, processed
        
    except Exception as e:
        print(f"[DB] Error in process_new_transitions: {e}")
        return 0, processed

def analyze_and_update_config():
    """
    Analyze KG data and generate config for trainer
    Real logic: compute statistics and derive training parameters
    """
    try:
        if not os.path.exists(KG_FILE):
            return
        
        # Read all transitions
        rewards = []
        speeds = []
        steering_actions = []
        
        with open(KG_FILE, "r") as f:
            for line in f:
                try:
                    edge = json.loads(line)
                    
                    r = edge.get("reward")
                    if isinstance(r, (int, float)):
                        rewards.append(r)
                    
                    s = edge.get("state_speed")
                    if isinstance(s, (int, float)):
                        speeds.append(s)
                    
                    st = edge.get("action_steering")
                    if isinstance(st, (int, float)):
                        steering_actions.append(st)
                        
                except:
                    continue
        
        if not rewards:
            return
        
        # Compute statistics
        avg_reward = sum(rewards) / len(rewards)
        avg_speed = sum(speeds) / len(speeds) if speeds else 0
        avg_steering = sum(steering_actions) / len(steering_actions) if steering_actions else 0
        
        # Derive training parameters (REAL logic)
        reward_scale = 1.0
        if avg_reward < 0:
            reward_scale = 0.5  # Penalize poor performance
        elif avg_reward < 1.0:
            reward_scale = 0.8
        elif avg_reward > 10.0:
            reward_scale = 1.2  # Boost good performance
        
        # Determine constraints based on behavior
        constraints = []
        if avg_speed > 100:
            constraints.append("high_speed_warning")
        if abs(avg_steering) > 0.5:
            constraints.append("aggressive_steering")
        if avg_reward > 5.0:
            constraints.append("good_performance")
        
        # Build config
        config = {
            "timestamp": datetime.now().isoformat(),
            "num_transitions_analyzed": len(rewards),
            "statistics": {
                "avg_reward": round(avg_reward, 4),
                "avg_speed": round(avg_speed, 4),
                "avg_steering": round(avg_steering, 4)
            },
            "trainer_parameters": {
                "reward_scale": reward_scale,
                "constraints": constraints
            },
            "metadata": {
                "generated_by": "database_analyzer",
                "version": "1.0"
            }
        }
        
        # Write config for trainer
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        
        print(f"[DB] ✓ Updated trainer config:")
        print(f"     Analyzed {len(rewards)} transitions")
        print(f"     Avg reward: {avg_reward:.4f}")
        print(f"     Reward scale: {reward_scale}")
        print(f"     Constraints: {constraints}")
        
    except Exception as e:
        print(f"[DB] Error in analyze_and_update_config: {e}")

def main_loop():
    """Main database analysis loop"""
    print("="*60)
    print("[DB] Database analyzer starting...")
    print(f"[DB] Watching: {TRANSITIONS_DIR}")
    print(f"[DB] KG store: {KG_FILE}")
    print(f"[DB] Config output: {CONFIG_FILE}")
    print("="*60)
    
    processed = load_processed()
    cycle = 0
    
    while True:
        try:
            cycle += 1
            
            # Process new transitions
            count, processed = process_new_transitions(processed)
            
            # Update config if we processed new data
            if count > 0:
                analyze_and_update_config()
            
            # Status update every 10 cycles
            if cycle % 10 == 0:
                total = len(processed)
                print(f"[DB] Status: {total} transitions processed total")
            
            time.sleep(5)
            
        except KeyboardInterrupt:
            print("[DB] Shutting down...")
            break
        except Exception as e:
            print(f"[DB] Error in main loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main_loop()