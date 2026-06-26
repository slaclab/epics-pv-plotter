"""
EPICS Client Library Comparison Test
PV: BL22:SCAN:MASTER:ADC1
Tests: pyepics, caproto, p4p sync/async features and network protocols
"""

import time
import asyncio
from datetime import datetime

PV_NAME = "BL22:SCAN:MASTER:ADC1"
#PV_NAME = "BL22:SRS570_AMP1:SENSITIVITY"


def print_section(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

# ============================================================================
# 1. pyepics - Synchronous + Callback
# ============================================================================
def test_pyepics():
    print_section("1. pyepics (CA - Synchronous Mode)")
    
    try:
        import epics
        
        # Synchronous read
        print(f"\n[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Starting synchronous read...")
        start = time.time()
        
        pv = epics.PV(PV_NAME)
        value = pv.get(timeout=5.0)
        
        elapsed = (time.time() - start) * 1000
        
        if value is not None:
            print(f"✓ Value: {value}")
            print(f"✓ Type: {type(value)}")
            print(f"✓ Time: {elapsed:.2f} ms")
            print(f"✓ Host: {pv.host}")
            print(f"✓ Protocol: Channel Access (CA)")
            
            # Note about the port
            if ':5074' in str(pv.host):
                print(f"  Note: Port 5074 is CA repeater, data on 5064")
        else:
            print("✗ Read timeout")
        
        # Callback mode (non-blocking monitor)
        print(f"\n[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Starting callback monitoring (3 seconds)...")
        
        callback_count = [0]
        
        def monitor_callback(pvname=None, value=None, timestamp=None, **kwargs):
            callback_count[0] += 1
            ts = datetime.fromtimestamp(timestamp).strftime('%H:%M:%S.%f')[:-3]
            print(f"  [{callback_count[0]}] {ts}: {value}")
        
        pv.add_callback(monitor_callback)
        time.sleep(3)
        pv.clear_callbacks()
        
        print(f"✓ Received {callback_count[0]} updates")
        
        # Protocol verification
        print(f"\nProtocol Analysis:")
        print(f"  - CA uses UDP for PV search (broadcast)")
        print(f"  - CA uses TCP for data transfer (virtual circuit)")
        print(f"  - Connected to: {pv.host}")
        
    except ImportError:
        print("✗ pyepics not installed: pip install pyepics")
    except Exception as e:
        print(f"✗ Error: {e}")

# ============================================================================
# 2. caproto - Synchronous Mode
# ============================================================================
def test_caproto_sync():
    print_section("2. caproto (CA - Synchronous Mode)")
    
    try:
        from caproto.sync.client import read
        
        print(f"\n[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Synchronous read...")
        start = time.time()
        
        reading = read(PV_NAME, timeout=5.0)
        elapsed = (time.time() - start) * 1000
        
        print(f"✓ Value: {reading.data}")
        print(f"✓ Type: {type(reading.data)}")
        print(f"✓ Time: {elapsed:.2f} ms")
        print(f"✓ Status: {reading.metadata.status}")
        print(f"✓ Severity: {reading.metadata.severity}")
        print(f"✓ Protocol: Channel Access (CA)")
        
        # Show metadata
        print(f"\nMetadata:")
        print(f"  - Timestamp: {reading.metadata.timestamp}")
        print(f"  - Data type: {reading.metadata.data_type}")
        
    except ImportError:
        print("✗ caproto not installed: pip install caproto")
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

# ============================================================================
# 3. caproto - Asyncio Mode
# ============================================================================
async def test_caproto_async():
    print_section("3. caproto (CA - asyncio Mode)")
    
    try:
        from caproto.asyncio.client import Context as AsyncContext
        
        ctx = AsyncContext()
        
        # Async read
        print(f"\n[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Async read...")
        start = time.time()
        
        # Use the correct method for asyncio
        reading = await ctx.read(PV_NAME, timeout=5.0)
        elapsed = (time.time() - start) * 1000
        
        print(f"✓ Value: {reading.data}")
        print(f"✓ Time: {elapsed:.2f} ms")
        print(f"✓ asyncio native support")
        
        # Async monitoring
        print(f"\n[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Async monitoring (3 seconds)...")
        
        count = [0]
        
        async def monitor():
            subscription = ctx.subscribe(PV_NAME)
            async for reading in subscription:
                count[0] += 1
                print(f"  [{count[0]}] {datetime.now().strftime('%H:%M:%S.%f')[:-3]}: {reading.data}")
                if count[0] >= 3:  # Limit updates
                    break
        
        try:
            await asyncio.wait_for(monitor(), timeout=3.0)
        except asyncio.TimeoutError:
            pass
        
        print(f"✓ Received {count[0]} updates via asyncio")
        
    except ImportError:
        print("✗ caproto not installed")
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

# ============================================================================
# 4. P4P - Synchronous Mode (PVA)
# ============================================================================
def test_p4p_sync():
    print_section("4. P4P (PVA - Synchronous Mode)")
    
    try:
        from p4p.client.thread import Context
        
        # CA protocol (more likely to work with existing IOCs)
        print("\nTrying CA protocol first...")
        ctx_ca = Context('ca', nt=False)
        
        try:
            start = time.time()
            value = ctx_ca.get(PV_NAME, timeout=5.0)
            elapsed = (time.time() - start) * 1000
            
            print(f"✓ Value: {value}")
            print(f"✓ Time: {elapsed:.2f} ms")
            print(f"✓ Protocol: Channel Access (CA) via P4P")
            
            # Try monitoring
            print(f"\nMonitoring (3 seconds)...")
            count = [0]
            
            def mon_cb(value):
                count[0] += 1
                print(f"  [{count[0]}] {datetime.now().strftime('%H:%M:%S.%f')[:-3]}: {value}")
            
            sub = ctx_ca.monitor(PV_NAME, mon_cb)
            time.sleep(3)
            sub.close()
            
            print(f"✓ Received {count[0]} updates")
            
        except Exception as e:
            print(f"✗ CA error: {e}")
        
        # PVA protocol
        print("\n\nTrying PVA protocol...")
        ctx_pva = Context('pva', nt=False)
        
        try:
            start = time.time()
            value = ctx_pva.get(PV_NAME, timeout=5.0)
            elapsed = (time.time() - start) * 1000
            
            print(f"✓ Value: {value}")
            print(f"✓ Time: {elapsed:.2f} ms")
            print(f"✓ Protocol: PVAccess (PVA) - Full TCP")
        except Exception as e:
            print(f"✗ PVA timeout - PV may not support PVA protocol")
            print(f"  (This is normal if IOC doesn't run EPICS 7+)")
            
    except ImportError:
        print("✗ p4p not installed: pip install p4p")
    except Exception as e:
        print(f"✗ Error: {e}")

# ============================================================================
# 5. P4P - Asyncio Mode
# ============================================================================
async def test_p4p_async():
    print_section("5. P4P (PVA - asyncio Mode)")
    
    try:
        from p4p.client.asyncio import Context as AsyncContext
        
        # Try CA first (more likely to succeed)
        print("\nTrying CA protocol (asyncio)...")
        ctx = AsyncContext('ca')
        
        try:
            start = time.time()
            value = await asyncio.wait_for(ctx.get(PV_NAME), timeout=5.0)
            elapsed = (time.time() - start) * 1000
            
            print(f"✓ Value: {value}")
            print(f"✓ Time: {elapsed:.2f} ms")
            print(f"✓ Protocol: Channel Access (CA)")
            print(f"✓ Native asyncio support")
            
        except asyncio.TimeoutError:
            print("✗ CA timeout")
        except Exception as e:
            print(f"✗ CA error: {e}")
        
        # Try PVA
        print("\n\nTrying PVA protocol (asyncio)...")
        ctx_pva = AsyncContext('pva')
        
        try:
            start = time.time()
            value = await asyncio.wait_for(ctx_pva.get(PV_NAME), timeout=5.0)
            elapsed = (time.time() - start) * 1000
            
            print(f"✓ Value: {value}")
            print(f"✓ Time: {elapsed:.2f} ms")
            print(f"✓ Protocol: PVAccess (PVA) - Full TCP")
            
        except asyncio.TimeoutError:
            print("✗ PVA timeout - PV likely doesn't support PVA")
            print("  (This is expected for EPICS base < 7)")
            
    except ImportError:
        print("✗ p4p not installed")
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

# ============================================================================
# 6. Network Protocol Verification
# ============================================================================
def test_protocol_verification():
    print_section("6. Network Protocol Verification")
    
    print("""
Channel Access (CA) Protocol:
    - UDP 5064: PV search broadcast
    - TCP 5064: Virtual circuit data transfer
    - UDP 5065: CA repeater (local only)
    - Search process: UDP broadcast -> Server response -> Establish TCP connection
    
PVAccess (PVA) Protocol:
    - TCP 5075: All communication (search + data)
    - UDP 5076: Beacon broadcast
    - Fully TCP-based, better for firewall environments

Your Result Analysis:
    ✓ pyepics connected successfully via CA
    ✓ Connected to 192.168.22.5:5074 (CA repeater port)
    ✓ Actual data transfer happens on port 5064
    
Verification Method:
    1. Run this script
    2. In another terminal execute:
       sudo tcpdump -i any -nn port 5064 or port 5065 or port 5075
    3. Observe network packets:
       - CA: You'll see UDP 5064 (search) and TCP 5064 (data)
       - PVA: Only TCP 5075 (if server supports it)
    """)
    
    print("\nSimplified verification commands:")
    print("  # Monitor all EPICS traffic")
    print("  sudo tcpdump -i any -nn 'port 5064 or port 5065 or port 5075'")
    print("\n  # Monitor only CA traffic")
    print("  sudo tcpdump -i any -nn 'port 5064'")
    print("\n  # Monitor only PVA traffic")
    print("  sudo tcpdump -i any -nn 'port 5075'")

# ============================================================================
# Main Program
# ============================================================================
def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║          EPICS Python Client Library Comparison Test         ║
║  PV: BL22:SCAN:MASTER:ADC1                                   ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Synchronous tests
    test_pyepics()
    test_caproto_sync()
    test_p4p_sync()
    
    # Asynchronous tests
    print("\n\n" + "█"*60)
    print("  Starting Asynchronous Tests (asyncio)")
    print("█"*60)
    
    asyncio.run(test_caproto_async())
    asyncio.run(test_p4p_async())
    
    # Protocol explanation
    test_protocol_verification()
    
    # Summary
    print_section("Test Summary")
    print("""
Results from your system:
    ✓ pyepics: Working perfectly (CA protocol)
    ✗ caproto: Had parsing issue (library bug or version issue)
    ✗ P4P CA: Timeout (may need EPICS environment variables)
    ✗ P4P PVA: Expected - IOC doesn't support PVA

Key Findings:
    1. Your IOC supports Channel Access (CA) protocol
    2. Connected to 192.168.22.5 successfully
    3. PV value: 15 (integer type)
    4. CA uses both UDP and TCP as expected
    
Library Recommendations for your setup:
    
1. pyepics ⭐ RECOMMENDED
   ✓ Works perfectly on your system
   ✓ Most mature, simplest API
   ✓ Best for your current infrastructure
   
2. caproto
   ⚠ May need version update or bug fix
   ✓ Pure Python advantage
   
3. P4P
   ⚠ Needs EPICS environment configuration
   ⚠ Your IOC doesn't support PVA (EPICS 7)
   ✗ Not recommended unless upgrading to EPICS 7

For your current setup (CA-based IOC):
   → Use pyepics for production
   → Consider caproto for pure-Python deployment after fixing
   → P4P only if migrating to EPICS 7/PVA in the future
    """)

if __name__ == "__main__":
    main()
