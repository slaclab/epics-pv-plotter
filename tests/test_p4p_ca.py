#!/usr/bin/env python3
"""Test p4p CA monitor"""
import time
from p4p.client.thread import Context

# Set EPICS environment
import os
os.environ['EPICS_CA_ADDR_LIST'] = '192.168.22.5:5074'
os.environ['EPICS_CA_AUTO_ADDR_LIST'] = 'NO'

ctx = Context('ca')
pv_name = 'BL22:SCAN:MASTER:ADC1'

print(f"Testing p4p CA for {pv_name}")
print("=" * 60)

# Test 1: Get value
print("\n1. Testing ctx.get()...")
try:
    value = ctx.get(pv_name)
    print(f"✅ Get succeeded: {value}")
except Exception as e:
    print(f"❌ Get failed: {e}")

# Test 2: Monitor
print("\n2. Testing ctx.monitor()...")
callback_count = 0

def my_callback(value):
    global callback_count
    callback_count += 1
    print(f"🔔 Callback #{callback_count}: {value} (type: {type(value)})")

try:
    sub = ctx.monitor(pv_name, my_callback, notify_disconnect=True)
    print("✅ Monitor subscription created")
    print("Waiting 10 seconds for callbacks...")
    time.sleep(10)
    print(f"\nTotal callbacks received: {callback_count}")
    sub.close()
except Exception as e:
    print(f"❌ Monitor failed: {e}")

print("\nTest complete!")
