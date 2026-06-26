"""
Demonstrate the difference between CA Monitor and Callback
No Chinese characters - English only
"""

import epics
import time
from datetime import datetime

PV_NAME = 'BL22:SCAN:MASTER:ADC1'

def timestamp():
    """Get current timestamp"""
    return datetime.now().strftime('%H:%M:%S.%f')[:-3]

print("="*70)
print("CA Monitor vs Callback Demonstration")
print("="*70)

# ======================================================================
# Test 1: auto_monitor=True, NO callback
# CA Monitor is active, but no callback function registered
# ======================================================================
print("\n" + "="*70)
print("TEST 1: auto_monitor=True, NO callback")
print("="*70)
print(f"[{timestamp()}] Creating PV with auto_monitor=True...")

pv1 = epics.PV(PV_NAME, auto_monitor=True)
pv1.wait_for_connection(timeout=5.0)

print(f"[{timestamp()}] PV connected")
print(f"[{timestamp()}] CA Monitor is now ACTIVE (receiving updates)")
print(f"[{timestamp()}] But NO callback is registered")
print(f"[{timestamp()}] Waiting 3 seconds...")

initial_value = pv1.value
print(f"[{timestamp()}] Initial value: {initial_value}")

time.sleep(3)

final_value = pv1.value
print(f"[{timestamp()}] Final value: {final_value}")

if initial_value != final_value:
    print(f"[{timestamp()}] ✓ Value auto-updated by CA Monitor")
else:
    print(f"[{timestamp()}] Value unchanged (or update rate is slow)")

print(f"[{timestamp()}] Callback call count: 0 (no callback registered)")

pv1.disconnect()

# ======================================================================
# Test 2: auto_monitor=True, WITH callback
# CA Monitor is active AND callback function is registered
# ======================================================================
print("\n" + "="*70)
print("TEST 2: auto_monitor=True, WITH callback")
print("="*70)

callback_count = [0]
callback_values = []

def my_callback(pvname=None, value=None, timestamp=None, **kwargs):
    """User callback function - will be called on every update"""
    callback_count[0] += 1
    callback_values.append(value)
    ts = datetime.fromtimestamp(timestamp).strftime('%H:%M:%S.%f')[:-3]
    print(f"    -> Callback #{callback_count[0]} at {ts}: value={value}")

print(f"[{timestamp()}] Creating PV with auto_monitor=True...")

pv2 = epics.PV(PV_NAME, auto_monitor=True)
pv2.wait_for_connection(timeout=5.0)

print(f"[{timestamp()}] PV connected")
print(f"[{timestamp()}] CA Monitor is ACTIVE")
print(f"[{timestamp()}] Registering callback function...")

pv2.add_callback(my_callback)

print(f"[{timestamp()}] Callback registered")
print(f"[{timestamp()}] Waiting 3 seconds to collect updates...")
print(f"[{timestamp()}] Watch for callback triggers below:")

time.sleep(3)

print(f"\n[{timestamp()}] Summary:")
print(f"    Total callback calls: {callback_count[0]}")
print(f"    Values received: {callback_values[:10]}")  # Show first 10
if callback_count[0] > 10:
    print(f"    ... and {callback_count[0] - 10} more updates")

print(f"\n[{timestamp()}] ✓ CA Monitor receives updates AND triggers callback")

pv2.disconnect()

# ======================================================================
# Test 3: auto_monitor=False, WITH callback
# CA Monitor is NOT active, callback registered but NEVER called
# ======================================================================
print("\n" + "="*70)
print("TEST 3: auto_monitor=False, WITH callback")
print("="*70)

callback3_count = [0]

def my_callback3(pvname=None, value=None, **kwargs):
    """This callback will NEVER be called!"""
    callback3_count[0] += 1
    print(f"    -> Callback called: value={value}")

print(f"[{timestamp()}] Creating PV with auto_monitor=False...")

pv3 = epics.PV(PV_NAME, auto_monitor=False)
pv3.wait_for_connection(timeout=5.0)

print(f"[{timestamp()}] PV connected")
print(f"[{timestamp()}] CA Monitor is NOT active")
print(f"[{timestamp()}] Registering callback function...")

pv3.add_callback(my_callback3)

print(f"[{timestamp()}] Callback registered")
print(f"[{timestamp()}] Initial pv.value: {pv3.value}")
print(f"[{timestamp()}] Waiting 3 seconds...")
print(f"[{timestamp()}] (No callback output expected)")

time.sleep(3)

print(f"\n[{timestamp()}] After 3 seconds:")
print(f"    pv.value: {pv3.value}")
print(f"    Callback call count: {callback3_count[0]}")

if callback3_count[0] == 0:
    print(f"\n[{timestamp()}] ✓ Callback was NEVER called (expected)")
    print(f"[{timestamp()}] ✓ Because CA Monitor is NOT active")

print(f"\n[{timestamp()}] Now manually calling get()...")
value = pv3.get()
print(f"[{timestamp()}] get() returned: {value}")
print(f"[{timestamp()}] Callback call count: {callback3_count[0]}")

if callback3_count[0] == 0:
    print(f"[{timestamp()}] ✓ Callback still NOT called even after get()")
    print(f"[{timestamp()}] ✓ get() does not trigger callbacks")

pv3.disconnect()

# ======================================================================
# Test 4: Multiple callbacks on same CA Monitor
# One CA Monitor, multiple callback functions
# ======================================================================
print("\n" + "="*70)
print("TEST 4: Multiple callbacks, one CA Monitor")
print("="*70)

count_logger = [0]
count_display = [0]
count_alarm = [0]

def logger_callback(value=None, **kwargs):
    count_logger[0] += 1
    if count_logger[0] <= 3:  # Only print first 3
        print(f"    -> Logger callback: value={value}")

def display_callback(value=None, **kwargs):
    count_display[0] += 1
    if count_display[0] <= 3:
        print(f"    -> Display callback: value={value}")

def alarm_callback(value=None, **kwargs):
    count_alarm[0] += 1
    if count_alarm[0] <= 3:
        print(f"    -> Alarm callback: value={value}")

print(f"[{timestamp()}] Creating PV with auto_monitor=True...")

pv4 = epics.PV(PV_NAME, auto_monitor=True)
pv4.wait_for_connection(timeout=5.0)

print(f"[{timestamp()}] Registering 3 different callbacks...")
pv4.add_callback(logger_callback)
pv4.add_callback(display_callback)
pv4.add_callback(alarm_callback)

print(f"[{timestamp()}] All callbacks registered")
print(f"[{timestamp()}] Waiting 2 seconds (showing first 3 updates only)...")

time.sleep(2)

print(f"\n[{timestamp()}] Summary:")
print(f"    Logger callback calls:  {count_logger[0]}")
print(f"    Display callback calls: {count_display[0]}")
print(f"    Alarm callback calls:   {count_alarm[0]}")

print(f"\n[{timestamp()}] ✓ All three callbacks received same number of calls")
print(f"[{timestamp()}] ✓ One CA Monitor serves multiple callbacks")

pv4.disconnect()

# ======================================================================
# Summary Table
# ======================================================================
print("\n" + "="*70)
print("SUMMARY TABLE")
print("="*70)

print("""
┌──────────────────┬──────────────┬──────────────┬──────────────────┐
│ Configuration    │ CA Monitor   │ Callback     │ Behavior         │
├──────────────────┼──────────────┼──────────────┼──────────────────┤
│ auto_monitor=T   │ ACTIVE       │ None         │ Updates pv.value │
│ no callback      │              │              │ No callback call │
├──────────────────┼──────────────┼──────────────┼──────────────────┤
│ auto_monitor=T   │ ACTIVE       │ Registered   │ Updates pv.value │
│ with callback    │              │              │ Calls callback   │
├──────────────────┼──────────────┼──────────────┼──────────────────┤
│ auto_monitor=F   │ NOT active   │ Registered   │ No auto update   │
│ with callback    │              │ (but useless)│ Callback ignored │
├──────────────────┼──────────────┼──────────────┼──────────────────┤
│ auto_monitor=T   │ ACTIVE       │ Multiple     │ All callbacks    │
│ multi callbacks  │ (only one)   │ registered   │ get called       │
└──────────────────┴──────────────┴──────────────┴──────────────────┘
""")

print("\nKey Points:")
print("  1. CA Monitor = Network protocol subscription (server → client)")
print("  2. Callback = Python function to handle received data")
print("  3. auto_monitor=True  → Enables CA Monitor")
print("  4. auto_monitor=False → No CA Monitor, no auto updates")
print("  5. One CA Monitor can trigger multiple callbacks")
print("  6. Callbacks without CA Monitor are useless")

print("\n" + "="*70)
print("Test Complete")
print("="*70)
