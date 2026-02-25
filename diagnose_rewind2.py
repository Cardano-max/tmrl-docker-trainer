"""Diagnostic: test rewind with 2-tick probe (accounting for input delay)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from adapters.tmnf_adapter import TMNFAdapter

adapter = TMNFAdapter()
print("Connecting...")
if not adapter.connect(port=8476, timeout=15.0):
    print("FAILED"); sys.exit(1)
if not adapter.wait_for_race(timeout=30.0):
    print("No race"); adapter.stop(); sys.exit(1)

# Get car moving
print("Accelerating to 15 km/h...")
fb = adapter.get_feedbacks()
while fb.get('speed', 0) < 15.0:
    adapter.send_action_dict({'gas': 1.0, 'brake': 0.0, 'steering': 0.0})
    adapter.wait_one_tick()
    fb = adapter.get_feedbacks()

save_speed = fb.get('speed', 0)
print(f"SAVE STATE at speed={save_speed:.4f}")
adapter.save_state()

# Let car continue 10 ticks (change state away from save point)
for _ in range(10):
    adapter.send_action_dict({'gas': 1.0, 'brake': 0.0, 'steering': 0.0})
    adapter.wait_one_tick()
fb = adapter.get_feedbacks()
print(f"Speed after 10 more ticks: {fb.get('speed',0):.4f}")

# === Test 1: Rewind + 2-tick probe with gas=0 ===
print("\n=== TEST 1: Rewind + gas=0 (2-tick probe) ===")
adapter.rewind()
# Tick 1: send gas=0 (input loads, replayed input active)
adapter.send_action_dict({'gas': 0.0, 'brake': 0.0, 'steering': 0.0})
adapter.wait_one_tick()
fb_before_1 = adapter.get_feedbacks()
print(f"  fb_before (tick 1): speed={fb_before_1.get('speed',0):.4f}")
# Tick 2: send gas=0 again (our input takes effect)
adapter.send_action_dict({'gas': 0.0, 'brake': 0.0, 'steering': 0.0})
adapter.wait_one_tick()
fb_after_1 = adapter.get_feedbacks()
print(f"  fb_after  (tick 2): speed={fb_after_1.get('speed',0):.4f}")
delta_no_gas = fb_after_1.get('speed',0) - fb_before_1.get('speed',0)
print(f"  Delta (no gas): {delta_no_gas:.6f}")

# === Test 2: Rewind + 2-tick probe with gas=1.0 ===
print("\n=== TEST 2: Rewind + gas=1.0 (2-tick probe) ===")
adapter.rewind()
# Tick 1: send gas=1.0 (input loads, replayed input active)
adapter.send_action_dict({'gas': 1.0, 'brake': 0.0, 'steering': 0.0})
adapter.wait_one_tick()
fb_before_2 = adapter.get_feedbacks()
print(f"  fb_before (tick 1): speed={fb_before_2.get('speed',0):.4f}")
# Tick 2: send gas=1.0 again (our input takes effect)
adapter.send_action_dict({'gas': 1.0, 'brake': 0.0, 'steering': 0.0})
adapter.wait_one_tick()
fb_after_2 = adapter.get_feedbacks()
print(f"  fb_after  (tick 2): speed={fb_after_2.get('speed',0):.4f}")
delta_gas = fb_after_2.get('speed',0) - fb_before_2.get('speed',0)
print(f"  Delta (gas=1.0): {delta_gas:.6f}")

# === Test 3: Rewind + 2-tick probe with steer=1.0 ===
print("\n=== TEST 3: Rewind + steer=1.0 (2-tick probe) ===")
adapter.rewind()
adapter.send_action_dict({'gas': 1.0, 'brake': 0.0, 'steering': 1.0})
adapter.wait_one_tick()
fb_before_3 = adapter.get_feedbacks()
print(f"  fb_before (tick 1): yaw={fb_before_3.get('yaw',0):.6f}")
adapter.send_action_dict({'gas': 1.0, 'brake': 0.0, 'steering': 1.0})
adapter.wait_one_tick()
fb_after_3 = adapter.get_feedbacks()
print(f"  fb_after  (tick 2): yaw={fb_after_3.get('yaw',0):.6f}")
delta_steer = fb_after_3.get('yaw',0) - fb_before_3.get('yaw',0)
print(f"  Delta (steer=1.0): {delta_steer:.6f}")

# === Results ===
print(f"\n{'='*60}")
print(f"  fb_before consistent? {fb_before_1.get('speed',0):.4f} vs {fb_before_2.get('speed',0):.4f}")
print(f"  Delta (no gas):  {delta_no_gas:.6f}")
print(f"  Delta (gas=1.0): {delta_gas:.6f}")
print(f"  Difference:      {delta_gas - delta_no_gas:.6f}")
print(f"  Delta (steer):   {delta_steer:.6f}")
if abs(delta_gas - delta_no_gas) > 0.01:
    print("  >>> REWIND + 2-TICK PROBE WORKS!")
else:
    print("  >>> STILL BROKEN")
print(f"{'='*60}")

adapter.stop()
