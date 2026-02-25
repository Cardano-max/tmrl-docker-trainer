"""Quick diagnostic: does SetInputState actually move the car?"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adapters.tmnf_adapter import TMNFAdapter

adapter = TMNFAdapter()
print("Connecting...")
if not adapter.connect(port=8476, timeout=15.0):
    print("FAILED to connect")
    sys.exit(1)

print("Waiting for race...")
if not adapter.wait_for_race(timeout=30.0):
    print("No race detected")
    adapter.stop()
    sys.exit(1)

print("Connected! Running 50 ticks with gas=1.0...")
print()

for i in range(50):
    fb = adapter.get_feedbacks()
    speed = fb.get('speed', 0)
    pos_x = fb.get('pos_x', 0)
    pos_z = fb.get('pos_z', 0)
    yaw = fb.get('yaw', 0)
    print(f"  tick {i:3d}: speed={speed:8.4f} km/h  pos=({pos_x:.1f}, {pos_z:.1f})  yaw={yaw:.4f}")

    # Send full gas
    adapter.send_action_dict({'gas': 1.0, 'brake': 0.0, 'steering': 0.0})
    adapter.wait_one_tick()

print()
print("Now 10 ticks with steer=1.0 (full right)...")
for i in range(10):
    fb = adapter.get_feedbacks()
    speed = fb.get('speed', 0)
    yaw = fb.get('yaw', 0)
    print(f"  tick {i:3d}: speed={speed:8.4f} km/h  yaw={yaw:.6f}")

    adapter.send_action_dict({'gas': 1.0, 'brake': 0.0, 'steering': 1.0})
    adapter.wait_one_tick()

print()
print("Now 10 ticks with brake=1.0...")
for i in range(10):
    fb = adapter.get_feedbacks()
    speed = fb.get('speed', 0)
    print(f"  tick {i:3d}: speed={speed:8.4f} km/h")

    adapter.send_action_dict({'gas': 0.0, 'brake': 1.0, 'steering': 0.0})
    adapter.wait_one_tick()

fb = adapter.get_feedbacks()
print(f"\nFinal: speed={fb.get('speed',0):.4f} km/h")
adapter.stop()
print("Done.")
