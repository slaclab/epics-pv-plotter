#!/usr/bin/env python3
"""
EPICS Performance Comparison: pyepics vs WebSocket (caproto)
Enhanced version with percentile statistics and outlier detection
"""

import asyncio
import json
import time
import threading
import psutil
from collections import deque
import statistics
import websockets
import epics
import numpy as np

PV_NAME = "BL22:SCAN:MASTER:ADC1"
WS_URL = f"ws://192.168.22.4:8082?pv={PV_NAME}"
TEST_DURATION = 60
PRINT_INTERVAL = 5

stats = {
    'pyepics': {
        'count': 0, 
        'times': deque(maxlen=20000), 
        'intervals': deque(maxlen=20000),
        'values': deque(maxlen=1000)
    },
    'websocket': {
        'count': 0, 
        'times': deque(maxlen=20000), 
        'intervals': deque(maxlen=20000),
        'values': deque(maxlen=1000)
    }
}

lock = threading.Lock()
stop_event = threading.Event()
first_timestamp = {'pyepics': None, 'websocket': None}


def pyepics_callback(pvname=None, value=None, timestamp=None, **kwargs):
    if stop_event.is_set():
        return
    
    now = time.time()
    
    with lock:
        if first_timestamp['pyepics'] is None and timestamp:
            first_timestamp['pyepics'] = (timestamp, now)
            offset = now - timestamp
            print(f"\n[pyepics] First callback:")
            print(f"  IOC timestamp: {timestamp:.6f}")
            print(f"  System time:   {now:.6f}")
            print(f"  Clock offset:  {offset:.3f} seconds")
            if abs(offset) > 10:
                print(f"  ⚠️  WARNING: Large clock offset detected!")
        
        if stats['pyepics']['times']:
            interval = (now - stats['pyepics']['times'][-1]) * 1000
            stats['pyepics']['intervals'].append(interval)
        
        stats['pyepics']['count'] += 1
        stats['pyepics']['times'].append(now)
        stats['pyepics']['values'].append(value)


async def websocket_listener():
    try:
        print(f"\n🔌 Connecting to WebSocket: {WS_URL}")
        
        async with websockets.connect(WS_URL, ping_interval=20, ping_timeout=10) as ws:
            print("✅ WebSocket connected!")
            
            msg_count = 0
            last_value = None
            duplicate_count = 0
            
            while not stop_event.is_set():
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    now = time.time()
                    
                    if isinstance(message, str):
                        data = eval(message)
                    else:
                        data = message
                    
                    msg_count += 1
                    current_value = data.get('value')
                    
                    # Detect duplicates
                    if current_value == last_value:
                        duplicate_count += 1
                    last_value = current_value
                    
                    with lock:
                        if first_timestamp['websocket'] is None:
                            ws_ts = data.get('timestamp', now)
                            first_timestamp['websocket'] = (ws_ts, now)
                            offset = now - ws_ts
                            print(f"\n[websocket] First message:")
                            print(f"  WS timestamp:  {ws_ts:.6f}")
                            print(f"  System time:   {now:.6f}")
                            print(f"  Clock offset:  {offset:.3f} seconds")
                            print(f"  Initial value: {current_value}")
                        
                        if stats['websocket']['times']:
                            interval = (now - stats['websocket']['times'][-1]) * 1000
                            stats['websocket']['intervals'].append(interval)
                        
                        stats['websocket']['count'] += 1
                        stats['websocket']['times'].append(now)
                        stats['websocket']['values'].append(current_value)
                        
                        if msg_count % 100 == 0:
                            dup_rate = (duplicate_count / msg_count) * 100
                            print(f"[websocket] {msg_count} msgs, {duplicate_count} duplicates ({dup_rate:.1f}%)")
                
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    print(f"⚠️  Error: {e}")
                    continue
                    
    except Exception as e:
        print(f"❌ WebSocket error: {type(e).__name__}: {e}")


def calculate_statistics(intervals):
    """Calculate comprehensive statistics"""
    if not intervals:
        return None
    
    arr = np.array(list(intervals))
    
    return {
        'mean': np.mean(arr),
        'median': np.median(arr),
        'std': np.std(arr),
        'min': np.min(arr),
        'max': np.max(arr),
        'p1': np.percentile(arr, 1),
        'p5': np.percentile(arr, 5),
        'p95': np.percentile(arr, 95),
        'p99': np.percentile(arr, 99),
        'count': len(arr)
    }


def print_statistics():
    """Print periodic statistics"""
    while not stop_event.is_set():
        time.sleep(PRINT_INTERVAL)
        
        with lock:
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory().percent
            
            print(f"\n{'='*120}")
            print(f"⏰ {time.strftime('%H:%M:%S')} | 💻 CPU: {cpu:5.1f}% | 🧠 Mem: {mem:5.1f}%")
            print(f"{'Method':<12} {'Updates':<8} {'Rate':<8} "
                  f"{'Mean(ms)':<10} {'Median':<10} {'Std':<10} {'P1-P99(ms)':<25}")
            print('-' * 120)
            
            for method in ['pyepics', 'websocket']:
                s = stats[method]
                count = s['count']
                
                if len(s['times']) >= 2:
                    duration = s['times'][-1] - s['times'][0]
                    rate = (count - 1) / duration if duration > 0 else 0.0
                else:
                    rate = 0.0
                
                st = calculate_statistics(s['intervals'])
                
                if st:
                    print(f"{method:<12} {count:<8} {rate:<8.2f} "
                          f"{st['mean']:<10.2f} {st['median']:<10.2f} {st['std']:<10.2f} "
                          f"{st['p1']:.1f} - {st['p99']:.1f}")
                else:
                    print(f"{method:<12} {count:<8} {rate:<8.2f} {'N/A':<10}")


def main():
    print("=" * 120)
    print(" " * 45 + "EPICS Performance Comparison")
    print("=" * 120)
    print(f"📍 PV Name:        {PV_NAME}")
    print(f"🌐 WebSocket URL:  {WS_URL}")
    print(f"⏱️  Test Duration:  {TEST_DURATION} seconds")
    print(f"📊 Report Interval: {PRINT_INTERVAL} seconds")
    print("=" * 120)
    
    # Setup pyepics
    print("\n📡 Initializing pyepics (Channel Access)...")
    pv = epics.PV(PV_NAME, callback=pyepics_callback, auto_monitor=True, form='time')
    connected = pv.wait_for_connection(timeout=10)
    
    if not connected:
        print("❌ Failed to connect to EPICS PV")
        return
    
    print(f"✅ pyepics connected | Initial value: {pv.value}")
    
    # Start statistics thread
    stats_thread = threading.Thread(target=print_statistics, daemon=True)
    stats_thread.start()
    
    # Start WebSocket listener
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ws_task = loop.create_task(websocket_listener())
    
    try:
        print(f"\n🏁 Starting {TEST_DURATION}s test...\n")
        start = time.time()
        
        while time.time() - start < TEST_DURATION:
            loop.run_until_complete(asyncio.sleep(0.1))
            
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
    finally:
        stop_event.set()
        pv.clear_callbacks()
        pv.disconnect()
        
        try:
            loop.run_until_complete(asyncio.wait_for(ws_task, timeout=2))
        except:
            pass
        loop.close()
        
        # Print final results
        print("\n" + "=" * 120)
        print(" " * 50 + "📈 FINAL RESULTS 📈")
        print("=" * 120)
        
        with lock:
            for method in ['pyepics', 'websocket']:
                s = stats[method]
                count = s['count']
                
                print(f"\n{'🔷 ' + method.upper()}")
                print("─" * 60)
                
                if len(s['times']) >= 2:
                    duration = s['times'][-1] - s['times'][0]
                    rate = (count - 1) / duration if duration > 0 else 0.0
                    expected_interval = 1000 / rate if rate > 0 else 0
                    
                    print(f"  📊 Total Updates:      {count:,}")
                    print(f"  ⏱️  Test Duration:      {duration:.2f} s")
                    print(f"  🔄 Average Rate:       {rate:.2f} Hz")
                    print(f"  ⏳ Expected Interval:  {expected_interval:.2f} ms")
                    
                    st = calculate_statistics(s['intervals'])
                    if st:
                        jitter = (st['std'] / st['mean'] * 100) if st['mean'] > 0 else 0
                        
                        print(f"\n  📉 Interval Statistics:")
                        print(f"     Mean:             {st['mean']:.2f} ms")
                        print(f"     Median:           {st['median']:.2f} ms")
                        print(f"     Std Dev:          {st['std']:.2f} ms")
                        print(f"     Min:              {st['min']:.2f} ms")
                        print(f"     Max:              {st['max']:.2f} ms")
                        print(f"\n  📊 Percentiles:")
                        print(f"     P1:               {st['p1']:.2f} ms")
                        print(f"     P5:               {st['p5']:.2f} ms")
                        print(f"     P95:              {st['p95']:.2f} ms")
                        print(f"     P99:              {st['p99']:.2f} ms")
                        print(f"\n  📶 Jitter (σ/μ):       {jitter:.2f}%")
                        
                        # Outlier detection
                        outliers = sum(1 for x in s['intervals'] if x > st['p99'] or x < st['p1'])
                        outlier_pct = (outliers / len(s['intervals'])) * 100
                        print(f"  ⚠️  Outliers (>P99 or <P1): {outliers} ({outlier_pct:.1f}%)")
                    
                    if first_timestamp[method]:
                        ioc_ts, sys_ts = first_timestamp[method]
                        offset = sys_ts - ioc_ts
                        print(f"\n  🕐 Clock Offset:       {offset:.3f} s")
                        if abs(offset) > 10:
                            print(f"     ⚠️  WARNING: Large offset - IOC clock needs sync!")
                    
                    # Value statistics
                    if s['values']:
                        vals = list(s['values'])
                        print(f"\n  📊 Value Range:")
                        print(f"     Min:              {min(vals):.6f}")
                        print(f"     Max:              {max(vals):.6f}")
                        print(f"     Mean:             {statistics.mean(vals):.6f}")
                else:
                    print(f"  ❌ No data received")
        
        print("\n" + "=" * 120)
        print("✅ Test complete!")
        print("=" * 120)


if __name__ == "__main__":
    main()
