#!/usr/bin/env python3
"""
Comprehensive EPICS Library Comparison - FULLY FIXED
Tests: pyepics, caproto (sync), caproto (async), WebSocket
"""

import asyncio
import time
import threading
import psutil
import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import numpy as np
from datetime import datetime

import epics
from caproto.threading.client import Context as CaprotoSyncContext
from caproto.asyncio.client import Context as CaprotoAsyncContext
import websockets


# ================================================================
# Fix EPICS environment variables
# ================================================================
def fix_epics_environment():
    """Ensure EPICS environment variables are correctly formatted"""
    addr_list = os.environ.get('EPICS_CA_ADDR_LIST', '')
    if addr_list:
        # Split by whitespace and newlines, filter valid entries
        addresses = []
        for addr in addr_list.replace('\n', ' ').split():
            addr = addr.strip()
            if addr and ':' in addr:
                # Validate port number
                try:
                    host, port = addr.rsplit(':', 1)
                    int(port)  # Validate port is integer
                    addresses.append(addr)
                except (ValueError, AttributeError):
                    continue
            elif addr:
                addresses.append(addr)
        
        if addresses:
            os.environ['EPICS_CA_ADDR_LIST'] = ' '.join(addresses)
            print(f"⚠️  Fixed EPICS_CA_ADDR_LIST: {os.environ['EPICS_CA_ADDR_LIST']}")

fix_epics_environment()


# ================================================================
# Performance Metrics Data Class
# ================================================================

@dataclass
class PerformanceMetrics:
    """Performance metrics for each library"""
    name: str
    updates: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    connection_time: float = 0.0
    first_callback_latency: float = 0.0
    intervals: List[float] = field(default_factory=list)
    cpu_samples: List[float] = field(default_factory=list)
    memory_samples: List[float] = field(default_factory=list)
    errors: int = 0
    last_update_time: float = 0.0
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time if self.end_time > self.start_time else 0
    
    @property
    def rate(self) -> float:
        return self.updates / self.duration if self.duration > 0 else 0
    
    def add_update(self, timestamp: float):
        """Record an update"""
        if self.last_update_time > 0:
            interval = (timestamp - self.last_update_time) * 1000  # ms
            self.intervals.append(interval)
        self.last_update_time = timestamp
        self.updates += 1
    
    def summary(self) -> Dict:
        """Generate summary statistics"""
        if not self.intervals:
            return {
                'library': self.name,
                'updates': self.updates,
                'errors': self.errors,
                'connection_time_ms': self.connection_time * 1000,
            }
        
        arr = np.array(self.intervals)
        
        return {
            'library': self.name,
            'updates': self.updates,
            'errors': self.errors,
            'duration_s': self.duration,
            'rate_hz': self.rate,
            'connection_time_ms': self.connection_time * 1000,
            'first_callback_latency_ms': self.first_callback_latency * 1000,
            'interval_mean_ms': np.mean(arr),
            'interval_median_ms': np.median(arr),
            'interval_std_ms': np.std(arr),
            'interval_min_ms': np.min(arr),
            'interval_max_ms': np.max(arr),
            'p50_ms': np.percentile(arr, 50),
            'p90_ms': np.percentile(arr, 90),
            'p95_ms': np.percentile(arr, 95),
            'p99_ms': np.percentile(arr, 99),
            'jitter_percent': (np.std(arr) / np.mean(arr) * 100) if np.mean(arr) > 0 else 0,
            'avg_cpu_percent': np.mean(self.cpu_samples) if self.cpu_samples else 0,
            'avg_memory_mb': np.mean(self.memory_samples) if self.memory_samples else 0,
        }


# ================================================================
# Test Configuration
# ================================================================

PV_NAME = "BL22:SCAN:MASTER:ADC1"
WS_URL = f"ws://192.168.22.4:8000/ws?pv={PV_NAME}"
TEST_DURATION = 60
STATS_INTERVAL = 5

# Global state
metrics = {
    'pyepics': PerformanceMetrics('pyepics'),
    'caproto_sync': PerformanceMetrics('caproto_sync'),
    'caproto_async': PerformanceMetrics('caproto_async'),
    'websocket': PerformanceMetrics('websocket')
}

lock = threading.Lock()
stop_event = threading.Event()
process = psutil.Process(os.getpid())


# ================================================================
# Resource Monitor
# ================================================================

def resource_monitor():
    """Monitor CPU and memory usage"""
    while not stop_event.is_set():
        try:
            cpu = process.cpu_percent(interval=0.1)
            mem = process.memory_info().rss / 1024 / 1024  # MB
            
            with lock:
                for m in metrics.values():
                    if m.start_time > 0 and m.end_time == 0:  # Active
                        m.cpu_samples.append(cpu)
                        m.memory_samples.append(mem)
        except Exception:
            pass
        
        time.sleep(1)


# ================================================================
# Test 1: pyepics
# ================================================================

def test_pyepics():
    """Test pyepics library"""
    m = metrics['pyepics']
    first_callback = [True]
    
    def callback(pvname=None, value=None, timestamp=None, **kwargs):
        if stop_event.is_set():
            return
        
        now = time.time()
        
        with lock:
            if first_callback[0]:
                m.first_callback_latency = now - m.start_time
                first_callback[0] = False
                log_event('pyepics', f"First callback: {value}")
            
            m.add_update(now)
    
    try:
        log_event('pyepics', "Connecting...")
        conn_start = time.time()
        
        pv = epics.PV(PV_NAME, callback=callback, auto_monitor=True)
        connected = pv.wait_for_connection(timeout=10)
        
        if not connected:
            m.errors += 1
            log_event('pyepics', "Connection FAILED", error=True)
            m.end_time = time.time()
            return
        
        m.connection_time = time.time() - conn_start
        m.start_time = time.time()
        
        log_event('pyepics', f"Connected in {m.connection_time*1000:.1f}ms, value={pv.value}")
        
        # Run test
        while not stop_event.is_set():
            time.sleep(0.1)
        
        m.end_time = time.time()
        pv.clear_callbacks()
        pv.disconnect()
        
    except Exception as e:
        m.errors += 1
        m.end_time = time.time()
        log_event('pyepics', f"Error: {e}", error=True)


# ================================================================
# Test 2: caproto (sync/threading) - FULLY FIXED
# ================================================================

def test_caproto_sync():
    """Test caproto threading client"""
    m = metrics['caproto_sync']
    first_callback = [True]
    
    def callback(sub, response):
        if stop_event.is_set():
            return
        
        now = time.time()
        
        # Handle different response types
        try:
            if hasattr(response, 'data'):
                value = response.data[0] if hasattr(response.data, '__len__') and len(response.data) > 0 else response.data
            else:
                value = response
        except Exception:
            value = "unknown"
        
        with lock:
            if first_callback[0]:
                m.first_callback_latency = now - m.start_time
                first_callback[0] = False
                log_event('caproto_sync', f"First callback: {value}")
            
            m.add_update(now)
    
    try:
        log_event('caproto_sync', "Connecting...")
        conn_start = time.time()
        
        # Create context and PV correctly
        ctx = CaprotoSyncContext()
        pv, = ctx.get_pvs(PV_NAME)
        
        # Wait for connection
        pv.wait_for_connection(timeout=10)
        
        if not pv.connected:
            m.errors += 1
            log_event('caproto_sync', "Connection FAILED", error=True)
            m.end_time = time.time()
            return
        
        m.connection_time = time.time() - conn_start
        m.start_time = time.time()
        
        # Get initial value
        initial_value = pv.read().data
        log_event('caproto_sync', f"Connected in {m.connection_time*1000:.1f}ms, value={initial_value}")
        
        # Add callback subscription
        sub = pv.subscribe()
        sub.add_callback(callback)
        
        # Run test
        while not stop_event.is_set():
            time.sleep(0.1)
        
        m.end_time = time.time()
        sub.clear()
        
    except Exception as e:
        m.errors += 1
        m.end_time = time.time()
        log_event('caproto_sync', f"Error: {e}", error=True)
        import traceback
        traceback.print_exc()


# ================================================================
# Test 3: caproto (async) - FULLY FIXED
# ================================================================

async def test_caproto_async():
    """Test caproto async client"""
    m = metrics['caproto_async']
    first_callback = [True]
    subscription = None
    
    try:
        log_event('caproto_async', "Connecting...")
        conn_start = time.time()
        
        ctx = CaprotoAsyncContext()
        pv, = await asyncio.wait_for(ctx.get_pvs(PV_NAME), timeout=10.0)
        
        m.connection_time = time.time() - conn_start
        m.start_time = time.time()
        
        # Read initial value
        initial = await pv.read()
        log_event('caproto_async', f"Connected in {m.connection_time*1000:.1f}ms, value={initial.data}")
        
        # Subscribe to updates - CORRECT ASYNC ITERATION
        subscription = pv.subscribe()
        
        # Process updates using async for loop
        async for event in subscription:
            if stop_event.is_set():
                break
            
            now = time.time()
            
            with lock:
                if first_callback[0]:
                    m.first_callback_latency = now - m.start_time
                    first_callback[0] = False
                    log_event('caproto_async', f"First callback: {event.data}")
                
                m.add_update(now)
        
        m.end_time = time.time()
        
    except asyncio.TimeoutError:
        m.errors += 1
        m.end_time = time.time()
        log_event('caproto_async', "Connection timeout", error=True)
    except Exception as e:
        m.errors += 1
        m.end_time = time.time()
        log_event('caproto_async', f"Error: {e}", error=True)
        import traceback
        traceback.print_exc()
    finally:
        # Proper cleanup
        if subscription is not None:
            try:
                await subscription.clear()
            except Exception:
                pass


# ================================================================
# Test 4: WebSocket
# ================================================================

async def test_websocket():
    """Test WebSocket gateway"""
    m = metrics['websocket']
    first_callback = [True]
    
    try:
        log_event('websocket', f"Connecting to {WS_URL}...")
        conn_start = time.time()
        
        async with websockets.connect(WS_URL, ping_interval=20, ping_timeout=10) as ws:
            m.connection_time = time.time() - conn_start
            m.start_time = time.time()
            
            log_event('websocket', f"Connected in {m.connection_time*1000:.1f}ms")
            
            while not stop_event.is_set():
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    now = time.time()
                    
                    data = eval(message) if isinstance(message, str) else message
                    
                    with lock:
                        if first_callback[0]:
                            m.first_callback_latency = now - m.start_time
                            first_callback[0] = False
                            log_event('websocket', f"First message: {data.get('value')}")
                        
                        m.add_update(now)
                        
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    m.errors += 1
                    log_event('websocket', f"Receive error: {e}", error=True)
            
            m.end_time = time.time()
            
    except Exception as e:
        m.errors += 1
        m.end_time = time.time()
        log_event('websocket', f"Connection error: {e}", error=True)


# ================================================================
# Logging Helper
# ================================================================

def log_event(library: str, message: str, error: bool = False):
    """Pretty logging with timestamp"""
    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    symbol = '❌' if error else '✅'
    print(f"{timestamp} [{library:15}] {symbol} {message}")


# ================================================================
# Statistics Printer
# ================================================================

def print_statistics():
    """Print periodic statistics"""
    while not stop_event.is_set():
        time.sleep(STATS_INTERVAL)
        
        with lock:
            print(f"\n{'='*120}")
            print(f"⏰ {datetime.now().strftime('%H:%M:%S')} | 💻 CPU: {process.cpu_percent():.1f}% | 🧠 Mem: {process.memory_info().rss/1024/1024:.1f} MB")
            print(f"{'Library':<15} {'Updates':<10} {'Rate(Hz)':<10} {'Mean(ms)':<10} {'P50':<10} {'P95':<10} {'P99':<10} {'Errors':<8}")
            print('-' * 120)
            
            for name, m in metrics.items():
                if m.updates == 0:
                    print(f"{name:<15} {'N/A':<10}")
                    continue
                
                s = m.summary()
                print(f"{name:<15} "
                      f"{s.get('updates', 0):<10} "
                      f"{s.get('rate_hz', 0):<10.2f} "
                      f"{s.get('interval_mean_ms', 0):<10.2f} "
                      f"{s.get('p50_ms', 0):<10.2f} "
                      f"{s.get('p95_ms', 0):<10.2f} "
                      f"{s.get('p99_ms', 0):<10.2f} "
                      f"{m.errors:<8}")


# ================================================================
# Final Results Printer
# ================================================================

def print_final_results():
    """Print comprehensive final results"""
    print("\n" + "=" * 120)
    print(" " * 45 + "📈 FINAL RESULTS 📈")
    print("=" * 120)
    
    # Comparison table
    print(f"\n{'Metric':<30} " + "".join([f"{name:<20}" for name in metrics.keys()]))
    print("-" * 120)
    
    with lock:
        summaries = {name: m.summary() for name, m in metrics.items()}
        
        # Connection Time
        print(f"{'Connection Time (ms)':<30} ", end="")
        for name in metrics.keys():
            val = summaries[name].get('connection_time_ms', 0)
            print(f"{val:<20.2f}", end="")
        print()
        
        # First Callback Latency
        print(f"{'First Callback (ms)':<30} ", end="")
        for name in metrics.keys():
            val = summaries[name].get('first_callback_latency_ms', 0)
            print(f"{val:<20.2f}", end="")
        print()
        
        # Total Updates
        print(f"{'Total Updates':<30} ", end="")
        for name in metrics.keys():
            val = summaries[name].get('updates', 0)
            print(f"{val:<20}", end="")
        print()

        # Update Rate
        print(f"{'Average Rate (Hz)':<30} ", end="")
        for name in metrics.keys():
            val = summaries[name].get('rate_hz', 0)
            print(f"{val:<20.2f}", end="")
        print()

        # Mean Interval
        print(f"{'Mean Interval (ms)':<30} ", end="")
        for name in metrics.keys():
            val = summaries[name].get('interval_mean_ms', 0)
            print(f"{val:<20.2f}", end="")
        print()

        # Median Interval
        print(f"{'Median Interval (ms)':<30} ", end="")
        for name in metrics.keys():
            val = summaries[name].get('interval_median_ms', 0)
            print(f"{val:<20.2f}", end="")
        print()

        # Std Deviation
        print(f"{'Std Dev (ms)':<30} ", end="")
        for name in metrics.keys():
            val = summaries[name].get('interval_std_ms', 0)
            print(f"{val:<20.2f}", end="")
        print()

        # Jitter
        print(f"{'Jitter (%)':<30} ", end="")
        for name in metrics.keys():
            val = summaries[name].get('jitter_percent', 0)
            print(f"{val:<20.2f}", end="")
        print()

        # P50
        print(f"{'P50 (ms)':<30} ", end="")
        for name in metrics.keys():
            val = summaries[name].get('p50_ms', 0)
            print(f"{val:<20.2f}", end="")
        print()

        # P95
        print(f"{'P95 (ms)':<30} ", end="")
        for name in metrics.keys():
            val = summaries[name].get('p95_ms', 0)
            print(f"{val:<20.2f}", end="")
        print()

        # P99
        print(f"{'P99 (ms)':<30} ", end="")
        for name in metrics.keys():
            val = summaries[name].get('p99_ms', 0)
            print(f"{val:<20.2f}", end="")
        print()

        # Min Interval
        print(f"{'Min Interval (ms)':<30} ", end="")
        for name in metrics.keys():
            val = summaries[name].get('interval_min_ms', 0)
            print(f"{val:<20.2f}", end="")
        print()

        # Max Interval
        print(f"{'Max Interval (ms)':<30} ", end="")
        for name in metrics.keys():
            val = summaries[name].get('interval_max_ms', 0)
            print(f"{val:<20.2f}", end="")
        print()

        # CPU Usage
        print(f"{'Avg CPU (%)':<30} ", end="")
        for name in metrics.keys():
            val = summaries[name].get('avg_cpu_percent', 0)
            print(f"{val:<20.2f}", end="")
        print()

        # Memory Usage
        print(f"{'Avg Memory (MB)':<30} ", end="")
        for name in metrics.keys():
            val = summaries[name].get('avg_memory_mb', 0)
            print(f"{val:<20.2f}", end="")
        print()

        # Errors
        print(f"{'Errors':<30} ", end="")
        for name in metrics.keys():
            val = summaries[name].get('errors', 0)
            print(f"{val:<20}", end="")
        print()

    print("\n" + "=" * 120)

    # Detailed per-library results
    with lock:
        for name, m in metrics.items():
            s = m.summary()

            if not s or m.updates == 0:
                continue

            print(f"\n{'🔷 ' + name.upper()}")
            print("─" * 80)
            print(f"  📊 Performance:")
            print(f"     Total Updates:           {s['updates']:,}")
            print(f"     Test Duration:           {s['duration_s']:.2f} s")
            print(f"     Average Rate:            {s['rate_hz']:.2f} Hz")
            print(f"     Connection Time:         {s['connection_time_ms']:.2f} ms")
            print(f"     First Callback Latency:  {s['first_callback_latency_ms']:.2f} ms")

            print(f"\n  📉 Timing Statistics:")
            print(f"     Mean Interval:           {s['interval_mean_ms']:.2f} ms")
            print(f"     Median Interval:         {s['interval_median_ms']:.2f} ms")
            print(f"     Std Deviation:           {s['interval_std_ms']:.2f} ms")
            print(f"     Min Interval:            {s['interval_min_ms']:.2f} ms")
            print(f"     Max Interval:            {s['interval_max_ms']:.2f} ms")

            print(f"\n  📊 Percentiles:")
            print(f"     P50:                     {s['p50_ms']:.2f} ms")
            print(f"     P90:                     {s['p90_ms']:.2f} ms")
            print(f"     P95:                     {s['p95_ms']:.2f} ms")
            print(f"     P99:                     {s['p99_ms']:.2f} ms")

            print(f"\n  📶 Reliability:")
            print(f"     Jitter (σ/μ):            {s['jitter_percent']:.2f}%")
            print(f"     Errors:                  {s['errors']}")

            print(f"\n  💻 Resource Usage:")
            print(f"     Avg CPU:                 {s['avg_cpu_percent']:.2f}%")
            print(f"     Avg Memory:              {s['avg_memory_mb']:.2f} MB")

    print("\n" + "=" * 120)

    # Winner determination
    with lock:
        summaries = {name: m.summary() for name, m in metrics.items() if m.updates > 0}

        if summaries:
            print("\n🏆 WINNER ANALYSIS:")
            print("─" * 80)

            # Lowest latency
            fastest_conn = min(summaries.items(), key=lambda x: x[1].get('connection_time_ms', float('inf')))
            print(f"  ⚡ Fastest Connection:      {fastest_conn[0]} ({fastest_conn[1]['connection_time_ms']:.2f} ms)")

            # Highest rate
            highest_rate = max(summaries.items(), key=lambda x: x[1].get('rate_hz', 0))
            print(f"  🚀 Highest Update Rate:    {highest_rate[0]} ({highest_rate[1]['rate_hz']:.2f} Hz)")

            # Lowest jitter
            lowest_jitter = min(summaries.items(), key=lambda x: x[1].get('jitter_percent', float('inf')))
            print(f"  📉 Most Consistent:        {lowest_jitter[0]} ({lowest_jitter[1]['jitter_percent']:.2f}% jitter)")

            # Lowest CPU
            lowest_cpu = min(summaries.items(), key=lambda x: x[1].get('avg_cpu_percent', float('inf')))
            print(f"  💻 Lowest CPU Usage:       {lowest_cpu[0]} ({lowest_cpu[1]['avg_cpu_percent']:.2f}%)")

            # Lowest memory
            lowest_mem = min(summaries.items(), key=lambda x: x[1].get('avg_memory_mb', float('inf')))
            print(f"  🧠 Lowest Memory Usage:    {lowest_mem[0]} ({lowest_mem[1]['avg_memory_mb']:.2f} MB)")

    print("\n" + "=" * 120)
    print("✅ Test complete!")
    print("=" * 120)


# ================================================================
# Main Test Orchestrator
# ================================================================

def main():
    """Run comprehensive comparison of all libraries"""

    print("=" * 120)
    print(" " * 40 + "COMPREHENSIVE EPICS LIBRARY COMPARISON")
    print("=" * 120)
    print(f"📍 PV Name:          {PV_NAME}")
    print(f"🌐 WebSocket URL:    {WS_URL}")
    print(f"⏱️  Test Duration:    {TEST_DURATION} seconds")
    print(f"📊 Stats Interval:   {STATS_INTERVAL} seconds")
    print("=" * 120)
    print("\n🔬 Testing libraries:")
    print("   1. pyepics        - Pure Python EPICS library")
    print("   2. caproto_sync   - Caproto threading client")
    print("   3. caproto_async  - Caproto async client")
    print("   4. websocket      - FastAPI + caproto gateway")
    print("\n" + "=" * 120)

    # Start resource monitor
    monitor_thread = threading.Thread(target=resource_monitor, daemon=True)
    monitor_thread.start()

    # Start statistics printer
    stats_thread = threading.Thread(target=print_statistics, daemon=True)
    stats_thread.start()

    # ================================================================
    # Run tests in parallel threads
    # ================================================================

    threads = []

    # Thread 1: pyepics
    t1 = threading.Thread(target=test_pyepics, daemon=True, name="pyepics")
    t1.start()
    threads.append(t1)

    # Thread 2: caproto sync
    t2 = threading.Thread(target=test_caproto_sync, daemon=True, name="caproto_sync")
    t2.start()
    threads.append(t2)

    # Thread 3 & 4: Async tests (need event loop)
    async def run_async_tests():
        """Run async tests concurrently with proper cleanup"""
        tasks = []
        try:
            # Create tasks
            task_async = asyncio.create_task(test_caproto_async())
            task_ws = asyncio.create_task(test_websocket())
            tasks = [task_async, task_ws]
            
            # Wait for stop event
            while not stop_event.is_set():
                await asyncio.sleep(0.1)
            
            # Cancel tasks gracefully
            for task in tasks:
                if not task.done():
                    task.cancel()
            
            # Wait for cancellation to complete
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            log_event("ASYNC", f"Error in async tests: {e}", error=True)
        finally:
            # Clean up any remaining tasks
            for task in tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

    def run_async_wrapper():
        """Wrapper to run async tests in a thread with proper cleanup"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_async_tests())
        except Exception as e:
            log_event("ASYNC", f"Event loop error: {e}", error=True)
        finally:
            # Proper event loop cleanup
            try:
                # Cancel all remaining tasks
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                
                # Wait for all tasks to complete cancellation
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                
                # Shutdown async generators
                loop.run_until_complete(loop.shutdown_asyncgens())
                
                # Close the loop
                loop.close()
            except Exception as e:
                log_event("ASYNC", f"Cleanup error: {e}", error=True)

    t3 = threading.Thread(target=run_async_wrapper, daemon=True, name="async_tests")
    t3.start()
    threads.append(t3)

    # ================================================================
    # Wait for test duration or user interrupt
    # ================================================================

    try:
        print(f"\n🏁 Starting {TEST_DURATION}s test...\n")
        start_time = time.time()

        while time.time() - start_time < TEST_DURATION:
            time.sleep(0.5)

            # Check if all threads died (shouldn't happen)
            alive_threads = [t for t in threads if t.is_alive()]
            if not alive_threads:
                log_event("SYSTEM", "All test threads terminated early", error=True)
                break

    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")

    finally:
        # ============================================================
        # Cleanup
        # ============================================================
        print("\n🛑 Stopping tests...")
        stop_event.set()

        # Wait for threads to finish (with timeout)
        print("⏳ Waiting for threads to complete...")
        for t in threads:
            t.join(timeout=5)
            if t.is_alive():
                log_event("SYSTEM", f"Thread {t.name} did not terminate cleanly", error=True)

        # Small delay to ensure all metrics are updated
        time.sleep(0.5)

        # Print final results
        print_final_results()


# ================================================================
# Entry
# Entry Point
# ================================================================

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()

