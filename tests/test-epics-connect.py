#!/usr/bin/env python3
"""
EPICS Connection Diagnostic with Clock Verification
Check EPICS IOC system clock synchronization
"""
import epics
import os
import sys
import time
from datetime import datetime

PV_NAME = "BL22:SCAN:MASTER:ADC1"

print("=" * 80)
print(" " * 20 + "EPICS Connection & Clock Diagnostic")
print("=" * 80)
print(f"Python version: {sys.version.split()[0]}")
print(f"PV Name: {PV_NAME}")
print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# Show current environment
print("EPICS Environment Variables:")
print("-" * 80)
for var in ["EPICS_CA_AUTO_ADDR_LIST", "EPICS_CA_ADDR_LIST", "EPICS_CA_SERVER_PORT"]:
    value = os.environ.get(var, 'Not set')
    print(f"  {var:<25} = {value}")

print("\n" + "=" * 80)
print("Attempting connection...")
print("-" * 80)

# Connect with timestamp support
pv = epics.PV(PV_NAME, auto_monitor=False, form='time')
connected = pv.wait_for_connection(timeout=8.0)

print(f"\n✅ Connected: {connected}")

if connected:
    print(f"📍 Value:     {pv.value}")
    print(f"🖥️  Host:      {pv.host}")
    print(f"📊 Connected: {pv.connected}")
    print(f"📊 Status:    {pv.status}")
    print(f"📊 Severity:  {pv.severity}")
    
    # Get timestamp information
    print("\n" + "=" * 80)
    print("🕐 Clock Synchronization Test")
    print("=" * 80)
    
    # Sample multiple timestamps
    samples = []
    print("\nCollecting 10 samples (one per 0.3s)...")
    print("-" * 80)
    
    for i in range(10):
        # Get value with timestamp
        value = pv.get(use_monitor=False)
        system_time = time.time()
        ioc_timestamp = pv.timestamp  # Get EPICS timestamp
        
        if ioc_timestamp:
            offset = system_time - ioc_timestamp
            samples.append({
                'system': system_time,
                'ioc': ioc_timestamp,
                'offset': offset,
                'value': value
            })
            
            # Convert to human-readable times
            sys_dt = datetime.fromtimestamp(system_time)
            ioc_dt = datetime.fromtimestamp(ioc_timestamp)
            
            print(f"  Sample {i+1:2d}:")
            print(f"    System Time: {sys_dt.strftime('%H:%M:%S.%f')[:-3]} ({system_time:.6f})")
            print(f"    IOC Time:    {ioc_dt.strftime('%H:%M:%S.%f')[:-3]} ({ioc_timestamp:.6f})")
            print(f"    Offset:      {offset:+8.3f} seconds")
            print(f"    Value:       {value:.6f}")
            print()
        
        time.sleep(0.3)
    
    # Analyze clock offset
    if samples:
        offsets = [s['offset'] for s in samples]
        avg_offset = sum(offsets) / len(offsets)
        min_offset = min(offsets)
        max_offset = max(offsets)
        drift = max_offset - min_offset
        
        print("=" * 80)
        print("📊 Clock Offset Analysis:")
        print("-" * 80)
        print(f"  Average Offset:    {avg_offset:+8.3f} seconds")
        print(f"  Min Offset:        {min_offset:+8.3f} seconds")
        print(f"  Max Offset:        {max_offset:+8.3f} seconds")
        print(f"  Drift (Max-Min):   {drift:8.3f} seconds")
        
        # Human-readable interpretation
        print("\n" + "=" * 80)
        print("🔍 Diagnosis:")
        print("-" * 80)
        
        abs_offset = abs(avg_offset)
        
        if abs_offset < 1.0:
            print(f"  ✅ EXCELLENT: IOC clock is well synchronized (offset = {avg_offset:+.3f}s)")
            status = "GOOD"
        elif abs_offset < 10.0:
            print(f"  ⚠️  WARNING: IOC clock has minor offset ({avg_offset:+.1f} seconds)")
            print("     Recommendation: Sync IOC system clock with NTP")
            status = "WARNING"
        elif abs_offset < 60.0:
            print(f"  ⚠️  WARNING: IOC clock is off by {avg_offset:+.1f} seconds")
            print("     Action required: Sync IOC system clock")
            status = "WARNING"
        else:
            minutes = abs_offset / 60
            print(f"  ❌ CRITICAL: IOC clock is off by {avg_offset:+.1f} seconds ({minutes:+.1f} minutes)!")
            print("     IMMEDIATE ACTION REQUIRED: IOC system clock MUST be synchronized!")
            status = "CRITICAL"
            
            # Show human-readable times for critical offsets
            print(f"\n     📅 Time Comparison:")
            current_system_time = time.time()
            current_ioc_time = current_system_time - avg_offset
            
            sys_dt = datetime.fromtimestamp(current_system_time)
            ioc_dt = datetime.fromtimestamp(current_ioc_time)
            
            print(f"        System Time: {sys_dt.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"        IOC Time:    {ioc_dt.strftime('%Y-%m-%d %H:%M:%S')}")
            
            if avg_offset > 0:
                print(f"        IOC is {abs_offset:.1f}s AHEAD (in the future)")
            else:
                print(f"        IOC is {abs_offset:.1f}s BEHIND (in the past)")
        
        if drift > 0.5:
            print(f"\n  ⚠️  WARNING: Clock drift detected ({drift:.3f}s over ~3 seconds)")
            print("     IOC clock may be unstable or under load")
        else:
            print(f"\n  ✅ Clock is stable (drift = {drift:.3f}s)")
        
        # Recommendations based on status
        print("\n" + "=" * 80)
        print("💡 Recommendations:")
        print("-" * 80)
        
        if status == "GOOD":
            print("  ✅ No action needed. IOC clock is properly synchronized.")
            
        elif status == "WARNING":
            print(f"  1. Check IOC host time (Host: {pv.host}):")
            print(f"     ssh {pv.host.split(':')[0]} 'date'")
            print("\n  2. Compare with system time:")
            print("     date")
            print("\n  3. If offset confirmed, sync IOC clock:")
            print("     sudo ntpdate -u pool.ntp.org")
            
        elif status == "CRITICAL":
            print(f"  🚨 URGENT: Fix IOC clock on {pv.host.split(':')[0]}")
            print("\n  Step 1 - Check current IOC time:")
            print(f"     ssh {pv.host.split(':')[0]} 'date'")
            
            print("\n  Step 2 - Sync with NTP (choose one method):")
            print("     Method A (ntpdate):")
            print("       sudo ntpdate -u pool.ntp.org")
            print("\n     Method B (chrony):")
            print("       sudo chronyc makestep")
            
            print("\n  Step 3 - Enable automatic time sync:")
            print("     sudo systemctl enable --now chronyd")
            
            print("\n  Step 4 - Verify synchronization:")
            print("     timedatectl status")
            print("     date")
            
            print("\n  Step 5 - Test EPICS timestamp again:")
            print("     python test-epics-connect.py")
    
    # Additional PV metadata
    print("\n" + "=" * 80)
    print("📋 PV Metadata:")
    print("-" * 80)
    
    try:
        ctrl_vars = pv.get_ctrlvars()
        if ctrl_vars:
            for key, value in sorted(ctrl_vars.items()):
                print(f"  {key:<25} = {value}")
    except Exception as e:
        print(f"  Could not retrieve metadata: {e}")
    
else:
    print("\n❌ Connection failed!")
    print("\nTroubleshooting steps:")
    print("  1. Verify IOC is running on the network")
    print("  2. Check EPICS_CA_ADDR_LIST is correct")
    print("  3. Test with caget command:")
    print(f"     caget {PV_NAME}")
    print("  4. Check firewall settings (CA ports: 5064-5065)")

print("\n" + "=" * 80)
print("Cleaning up...")
time.sleep(0.5)
pv.disconnect()
print("✅ Test complete")
print("=" * 80)
