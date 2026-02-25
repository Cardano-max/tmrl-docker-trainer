"""Diagnostic: does rewind + input work together?"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adapters.tmnf_adapter import TMNFAdapter

adapter = TMNFAdapter()
print("Connecting...")
if not adapter.connect(port=8476, timeout=15.0):
    print("FAILED"); sys.exit(1)

print("Waiting for race...")
if not adapter.wait_for_race(timeout=30.0):
    print("No race"); adapter.stop(); sys.exit(1)

# Step 1: Gas for 20 ticks to get speed up
print("\n=== Step 1: Gas for 20 ticks ===")
for i in range(20):
    fb = adapter.get_feedbacks()
    if i % 5 == 0:
        print(f"  tick {i}: speed={fb.get('speed',0):.4f}")
    adapter.send_action_dict({'gas': 1.0, 'brake': 0.0, 'steering': 0.0})
    adapter.wait_one_tick()

fb = adapter.get_feedbacks()
save_speed = fb.get('speed', 0)
print(f"\n=== Step 2: SAVE STATE at speed={save_speed:.4f} km/h ===")
adapter.save_state()

# Step 3: Gas for 10 more ticks (speed should increase beyond saved)
print("\n=== Step 3: Gas for 10 more ticks (speed increases) ===")
for i in range(10):
    adapter.send_action_dict({'gas': 1.0, 'brake': 0.0, 'steering': 0.0})
    adapter.wait_one_tick()
    fb = adapter.get_feedbacks()
    print(f"  tick {i}: speed={fb.get('speed',0):.4f}")

print(f"\n  Speed before rewind: {fb.get('speed',0):.4f}")

# Step 4: REWIND
print("\n=== Step 4: REWIND to saved state ===")
adapter.rewind()
fb = adapter.get_feedbacks()
print(f"  Speed after rewind (local): {fb.get('speed',0):.4f} (expect ~{save_speed:.4f})")

# Step 5: One tick with NO input
print("\n=== Step 5: One tick with NO input (action=0) ===")
adapter.send_action_dict({'gas': 0.0, 'brake': 0.0, 'steering': 0.0})
adapter.wait_one_tick()
fb_no_gas = adapter.get_feedbacks()
print(f"  Speed after 1 tick, no gas: {fb_no_gas.get('speed',0):.4f}")

# Step 6: REWIND again
print("\n=== Step 6: REWIND again ===")
adapter.rewind()

# Step 7: One tick with GAS
print("=== Step 7: One tick with gas=1.0 ===")
adapter.send_action_dict({'gas': 1.0, 'brake': 0.0, 'steering': 0.0})
adapter.wait_one_tick()
fb_gas = adapter.get_feedbacks()
print(f"  Speed after 1 tick, gas=1.0: {fb_gas.get('speed',0):.4f}")

delta_no_gas = fb_no_gas.get('speed',0) - save_speed
delta_gas = fb_gas.get('speed',0) - save_speed
print(f"\n=== RESULTS ===")
print(f"  Saved speed:     {save_speed:.4f}")
print(f"  Delta (no gas):  {delta_no_gas:.6f}")
print(f"  Delta (gas=1.0): {delta_gas:.6f}")
print(f"  Difference:      {delta_gas - delta_no_gas:.6f}")
if abs(delta_gas - delta_no_gas) > 0.001:
    print("  >>> REWIND + INPUT WORKS!")
else:
    print("  >>> PROBLEM: gas has no effect after rewind")

adapter.stop()
print("Done.")
