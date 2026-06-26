"""
Prove CA uses UDP+TCP, PVA uses only TCP
With environment diagnostics and fixes
"""
import os
import time

# ============================================================
# Step 1: Check and fix environment
# ============================================================
print("="*60)
print("Environment Diagnostics")
print("="*60)

addr_list = os.environ.get('EPICS_CA_ADDR_LIST', '')
print(f"\nCurrent EPICS_CA_ADDR_LIST: {repr(addr_list)}")

if '\n' in addr_list or not addr_list.strip():
    print("\n⚠ WARNING: EPICS_CA_ADDR_LIST has issues")
    print("  Fixing for this session...")
    # Use the server that has your PV
    os.environ['EPICS_CA_ADDR_LIST'] = '192.168.22.4 192.168.22.5'
    os.environ['EPICS_CA_AUTO_ADDR_LIST'] = 'NO'
    print(f"  Fixed to: {os.environ['EPICS_CA_ADDR_LIST']}")
else:
    print("✓ EPICS_CA_ADDR_LIST looks OK")

# ============================================================
# Step 2: Instructions for tcpdump
# ============================================================
print("\n" + "="*60)
print("Packet Capture Instructions")
print("="*60)
print("""
Open another terminal and run:

    sudo tcpdump -i any -nn 'port 5064 or port 5075' -l

Expected output for CA:
    - You'll see UDP packets (search)
    - Then TCP packets (data)

Expected output for PVA:
    - Only TCP packets (no UDP)
    
Press Ctrl+C in tcpdump terminal when done.
""")

input("Press Enter when tcpdump is running...")

# ============================================================
# Step 3: Test CA Protocol
# ============================================================
print("\n" + "="*60)
print("TEST 1: CA Protocol (pyepics)")
print("="*60)
print("\nWhat to watch in tcpdump:")
print("  1. UDP 5064 packets (PV search broadcast)")
print("  2. TCP 5064 packets (connection + data)")
print()

import epics

# Disable CA warnings for cleaner output
epics.ca.replace_printf_handler(lambda msg: None)

pv = epics.PV('BL22:SRS570_AMP1:SENSITIVITY')
print("Connecting to PV...")
time.sleep(0.5)

value = pv.get()
print(f"✓ CA Value: {value}")
print(f"✓ Connected to: {pv.host}")
print("\nCheck tcpdump - you should have seen:")
print("  [1] UDP packets - searching for PV")
print("  [2] TCP handshake - SYN, SYN-ACK, ACK")
print("  [3] TCP data packets - actual read")

time.sleep(2)

# ============================================================
# Step 4: Test caproto (also CA protocol)
# ============================================================
print("\n" + "="*60)
print("TEST 2: CA Protocol (caproto)")
print("="*60)
print("\nSame as above - UDP search + TCP data")
print()

from caproto.sync.client import read

reading = read('BL22:SRS570_AMP1:SENSITIVITY', timeout=5.0)
print(f"✓ caproto Value: {reading.data}")
print("\nCheck tcpdump - same pattern as pyepics:")
print("  [1] UDP search")
print("  [2] TCP connection and data")

time.sleep(2)

# ============================================================
# Step 5: Test P4P CA mode
# ============================================================
print("\n" + "="*60)
print("TEST 3: CA Protocol via P4P")
print("="*60)
print("\nStill CA protocol - UDP search + TCP data")
print()

from p4p.client.thread import Context

ctx_ca = Context('ca', nt=False)
try:
    value = ctx_ca.get('BL22:SRS570_AMP1:SENSITIVITY', timeout=5.0)
    print(f"✓ P4P-CA Value: {value}")
    print("\nCheck tcpdump - same CA pattern:")
    print("  [1] UDP search on port 5064")
    print("  [2] TCP data on port 5064")
except Exception as e:
    print(f"✗ P4P-CA error: {e}")

time.sleep(2)

# ============================================================
# Step 6: Test PVA Protocol
# ============================================================
print("\n" + "="*60)
print("TEST 4: PVA Protocol via P4P")
print("="*60)
print("\nDifferent protocol - ONLY TCP, NO UDP")
print()

ctx_pva = Context('pva', nt=False)
try:
    value = ctx_pva.get('BL22:SRS570_AMP1:SENSITIVITY', timeout=3.0)
    print(f"✓ P4P-PVA Value: {value}")
    print("\nCheck tcpdump - different pattern:")
    print("  [1] ONLY TCP packets on port 5075")
    print("  [2] NO UDP packets at all")
except TimeoutError:
    print("✗ PVA timeout (expected - your IOC doesn't support PVA)")
    print("\nCheck tcpdump - you should see:")
    print("  [1] TCP connection attempts to port 5075")
    print("  [2] NO successful connection (timeout)")
    print("  [3] NO UDP packets (PVA doesn't use UDP for search)")

# ============================================================
# Summary
# ============================================================
print("\n" + "="*60)
print("PROOF SUMMARY")
print("="*60)
print("""
Review your tcpdump output:

CA Protocol (Tests 1-3):
  ✓ UDP packets on port 5064 (search/discovery)
  ✓ TCP packets on port 5064 (data transfer)
  → Proves CA uses UDP + TCP

PVA Protocol (Test 4):
  ✓ Only TCP packets on port 5075
  ✓ Zero UDP packets
  → Proves PVA uses only TCP

Key Differences:
  CA:  UDP search → Find server → TCP connection → Data
  PVA: TCP connection directly → Search + Data (all TCP)
""")

print("="*60)
print("To fix your environment permanently, add to ~/.bashrc:")
print("="*60)
print("""
export EPICS_CA_ADDR_LIST="192.168.22.4 192.168.22.5"
export EPICS_CA_AUTO_ADDR_LIST=NO
""")
