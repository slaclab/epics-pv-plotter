#!/usr/bin/env python3
"""
Test IOC timestamp vs local server time
"""

import asyncio
import time
from datetime import datetime
from caproto.asyncio.client import Context

async def main():
    print("=" * 70)
    print("🕐 IOC Timestamp Test")
    print("=" * 70)
    print()
    
    # Connect to PV
    ctx = Context()
    pv_name = 'BL22:SCAN:MASTER:ADC1'
    
    print(f"📡 Connecting to PV: {pv_name}")
    
    try:
        # Get PV with timeout
        pv, = await asyncio.wait_for(
            ctx.get_pvs(pv_name), 
            timeout=5.0
        )
        
        # Read with timestamp
        reading = await pv.read(data_type='time')
        
        # Get local time
        local_timestamp = time.time()
        local_datetime = datetime.fromtimestamp(local_timestamp)
        
        # Get IOC timestamp
        ioc_timestamp = reading.metadata.timestamp
        ioc_datetime = datetime.fromtimestamp(ioc_timestamp)
        
        # Calculate difference
        time_diff = local_timestamp - ioc_timestamp
        
        # Display results
        print()
        print("📊 Results:")
        print("-" * 70)
        print(f"🖥️  Local Server Time: {local_datetime.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
        print(f"    Unix Timestamp:    {local_timestamp:.6f}")
        print()
        print(f"📡 IOC Timestamp:      {ioc_datetime.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
        print(f"    Unix Timestamp:    {ioc_timestamp:.6f}")
        print()
        print(f"⏱️  Time Difference:   {time_diff:.3f} seconds")
        print("-" * 70)
        print()
        
        # Interpretation
        if abs(time_diff) < 1:
            print("✅ Times are synchronized (difference < 1 second)")
        elif abs(time_diff) < 5:
            print("⚠️  Minor time drift (1-5 seconds)")
        else:
            print("❌ Significant time drift detected")
            if time_diff > 0:
                print(f"   → Local time is {abs(time_diff):.1f} seconds AHEAD")
                print(f"   → IOC time is {abs(time_diff):.1f} seconds BEHIND")
            else:
                print(f"   → Local time is {abs(time_diff):.1f} seconds BEHIND")
                print(f"   → IOC time is {abs(time_diff):.1f} seconds AHEAD")
        
        print()
        print("=" * 70)
        
    except asyncio.TimeoutError:
        print(f"❌ Connection timeout: Unable to connect to {pv_name}")
        print("   Please check:")
        print("   1. PV name is correct")
        print("   2. IOC is running")
        print("   3. Network connection is working")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    asyncio.run(main())
