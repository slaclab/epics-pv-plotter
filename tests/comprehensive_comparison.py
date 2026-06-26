#!/usr/bin/env python3
"""
Multi-PV Concurrent Performance Comparison - FULLY FIXED
完全修复版本：彻底解决 EPICS_CA_ADDR_LIST 解析问题
"""

import asyncio
import time
import threading
import psutil
import os
import re
from dataclasses import dataclass, field
from typing import List, Dict
import numpy as np
from datetime import datetime

import epics
from caproto.threading.client import Context as CaprotoSyncContext
from caproto.asyncio.client import Context as CaprotoAsyncContext
import websockets


# ================================================================
# 彻底修复 EPICS 环境变量
# ================================================================

def fix_epics_environment():
    """彻底修复 EPICS 环境变量格式问题"""
    
    # 获取原始值
    addr_list = os.environ.get('EPICS_CA_ADDR_LIST', '')
    
    if not addr_list:
        print("⚠️  EPICS_CA_ADDR_LIST 未设置，使用自动发现")
        os.environ['EPICS_CA_AUTO_ADDR_LIST'] = 'YES'
        return
    
    print(f"🔍 原始 EPICS_CA_ADDR_LIST: {repr(addr_list)}")
    
    # 替换所有换行符为空格
    addr_list = addr_list.replace('\n', ' ').replace('\r', ' ')
    
    # 分割并验证每个地址
    valid_addresses = []
    tokens = addr_list.split()
    
    i = 0
    while i < len(tokens):
        token = tokens[i].strip()
        
        if not token:
            i += 1
            continue
        
        # 检查是否是有效的地址:端口格式
        if ':' in token:
            try:
                host, port = token.rsplit(':', 1)
                port_num = int(port)
                if 1 <= port_num <= 65535:
                    valid_addresses.append(token)
                else:
                    print(f"⚠️  跳过无效端口: {token}")
            except ValueError:
                # 可能是 "host:5064\n5074" 这种情况
                print(f"⚠️  跳过无效格式: {token}")
        else:
            # 纯数字 - 可能是被分割的端口号
            if token.isdigit():
                print(f"⚠️  跳过孤立端口号: {token}")
            else:
                # 纯主机名，添加默认端口
                valid_addresses.append(f"{token}:5064")
        
        i += 1
    
    # 更新环境变量
    if valid_addresses:
        cleaned = ' '.join(valid_addresses)
        os.environ['EPICS_CA_ADDR_LIST'] = cleaned
        print(f"✅ 修复后 EPICS_CA_ADDR_LIST: {cleaned}\n")
    else:
        print("⚠️  没有有效地址，启用自动发现")
        del os.environ['EPICS_CA_ADDR_LIST']
        os.environ['EPICS_CA_AUTO_ADDR_LIST'] = 'YES'
    
    # 设置其他必要的环境变量
    if not os.environ.get('EPICS_CA_SERVER_PORT'):
        os.environ['EPICS_CA_SERVER_PORT'] = '5064'
    
    if not os.environ.get('EPICS_CA_REPEATER_PORT'):
        os.environ['EPICS_CA_REPEATER_PORT'] = '5065'

# 在导入 caproto 之前执行修复
fix_epics_environment()


# ================================================================
# 测试配置
# ================================================================

PV_LIST = [
    "BL22:SCAN:MASTER:ADC1",
    "BL22:SCAN:MASTER:ADC2",
    "BL22:SCAN:MASTER:ADC3",
    "BL22:SCAN:MASTER:ADC4",
    "BL22:SCAN:MASTER:ADC5",
    "BL22:SCAN:MASTER:ADC6",
    "BL22:SCAN:MASTER:ADC7",
    "BL22:SCAN:MASTER:ADC8",
]

NUM_PVS = len(PV_LIST)
TEST_DURATION = 60
WS_BASE_URL = "ws://192.168.22.4:8000/ws"


# ================================================================
# 性能指标
# ================================================================

@dataclass
class MultiPVMetrics:
    """多PV性能指标"""
    name: str
    total_updates: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    connection_time: float = 0.0
    
    pv_update_counts: Dict[str, int] = field(default_factory=dict)
    cpu_samples: List[float] = field(default_factory=list)
    memory_samples: List[float] = field(default_factory=list)
    thread_counts: List[int] = field(default_factory=list)
    
    errors: int = 0
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time if self.end_time > self.start_time else 0
    
    @property
    def total_rate(self) -> float:
        return self.total_updates / self.duration if self.duration > 0 else 0
    
    @property
    def avg_rate_per_pv(self) -> float:
        return self.total_rate / NUM_PVS if NUM_PVS > 0 else 0
    
    def summary(self) -> Dict:
        return {
            'library': self.name,
            'num_pvs': NUM_PVS,
            'total_updates': self.total_updates,
            'duration_s': self.duration,
            'total_rate_hz': self.total_rate,
            'avg_rate_per_pv_hz': self.avg_rate_per_pv,
            'connection_time_ms': self.connection_time * 1000,
            'avg_cpu_percent': np.mean(self.cpu_samples) if self.cpu_samples else 0,
            'max_cpu_percent': np.max(self.cpu_samples) if self.cpu_samples else 0,
            'avg_memory_mb': np.mean(self.memory_samples) if self.memory_samples else 0,
            'max_memory_mb': np.max(self.memory_samples) if self.memory_samples else 0,
            'avg_threads': np.mean(self.thread_counts) if self.thread_counts else 0,
            'max_threads': np.max(self.thread_counts) if self.thread_counts else 0,
            'errors': self.errors,
            'pv_update_distribution': self.pv_update_counts
        }


metrics = {
    'pyepics': MultiPVMetrics('pyepics'),
    'caproto_sync': MultiPVMetrics('caproto_sync'),
    'caproto_async': MultiPVMetrics('caproto_async'),
    'websocket': MultiPVMetrics('websocket')
}

lock = threading.Lock()
stop_event = threading.Event()
process = psutil.Process(os.getpid())


# ================================================================
# 资源监控
# ================================================================

def resource_monitor():
    """监控CPU、内存、线程数"""
    while not stop_event.is_set():
        try:
            cpu = process.cpu_percent(interval=0.1)
            mem = process.memory_info().rss / 1024 / 1024
            threads = threading.active_count()
            
            with lock:
                for m in metrics.values():
                    if m.start_time > 0 and m.end_time == 0:
                        m.cpu_samples.append(cpu)
                        m.memory_samples.append(mem)
                        m.thread_counts.append(threads)
        except Exception:
            pass
        
        time.sleep(0.5)


def log_event(library: str, message: str, error: bool = False):
    """日志输出"""
    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    symbol = '❌' if error else '✅'
    print(f"{timestamp} [{library:15}] {symbol} {message}")


# ================================================================
# 测试 1: pyepics
# ================================================================

def test_pyepics_multi():
    """pyepics: 为每个PV创建独立对象"""
    m = metrics['pyepics']
    
    for pv_name in PV_LIST:
        m.pv_update_counts[pv_name] = 0
    
    def make_callback(pv_name):
        def callback(pvname=None, value=None, **kwargs):
            if stop_event.is_set():
                return
            with lock:
                m.total_updates += 1
                m.pv_update_counts[pv_name] += 1
        return callback
    
    try:
        log_event('pyepics', f"连接 {NUM_PVS} 个 PV...")
        conn_start = time.time()
        
        pvs = []
        for pv_name in PV_LIST:
            pv = epics.PV(pv_name, callback=make_callback(pv_name), auto_monitor=True)
            pvs.append(pv)
        
        for pv in pvs:
            pv.wait_for_connection(timeout=10)
        
        m.connection_time = time.time() - conn_start
        m.start_time = time.time()
        
        connected = sum(1 for pv in pvs if pv.connected)
        log_event('pyepics', f"连接成功 {connected}/{NUM_PVS} 个PV，耗时 {m.connection_time*1000:.1f}ms")
        
        while not stop_event.is_set():
            time.sleep(0.1)
        
        m.end_time = time.time()
        
        for pv in pvs:
            pv.clear_callbacks()
            pv.disconnect()
        
    except Exception as e:
        m.errors += 1
        m.end_time = time.time()
        log_event('pyepics', f"错误: {e}", error=True)
        import traceback
        traceback.print_exc()


# ================================================================
# 测试 2: caproto sync
# ================================================================

def test_caproto_sync_multi():
    """caproto sync: 使用单个Context管理多个PV"""
    m = metrics['caproto_sync']
    
    for pv_name in PV_LIST:
        m.pv_update_counts[pv_name] = 0
    
    def make_callback(pv_name):
        def callback(sub, response):
            if stop_event.is_set():
                return
            with lock:
                m.total_updates += 1
                m.pv_update_counts[pv_name] += 1
        return callback
    
    try:
        log_event('caproto_sync', f"连接 {NUM_PVS} 个 PV...")
        conn_start = time.time()
        
        ctx = CaprotoSyncContext()
        pvs = ctx.get_pvs(*PV_LIST)
        
        for pv in pvs:
            pv.wait_for_connection(timeout=10)
        
        m.connection_time = time.time() - conn_start
        m.start_time = time.time()
        
        connected = sum(1 for pv in pvs if pv.connected)
        log_event('caproto_sync', f"连接成功 {connected}/{NUM_PVS} 个PV，耗时 {m.connection_time*1000:.1f}ms")
        
        for pv, pv_name in zip(pvs, PV_LIST):
            sub = pv.subscribe()
            sub.add_callback(make_callback(pv_name))
        
        while not stop_event.is_set():
            time.sleep(0.1)
        
        m.end_time = time.time()
        
    except Exception as e:
        m.errors += 1
        m.end_time = time.time()
        log_event('caproto_sync', f"错误: {e}", error=True)
        import traceback
        traceback.print_exc()


# ================================================================
# 测试 3: caproto async
# ================================================================

async def test_caproto_async_multi():
    """caproto async: 单线程异步处理所有PV"""
    m = metrics['caproto_async']
    
    for pv_name in PV_LIST:
        m.pv_update_counts[pv_name] = 0
    
    try:
        log_event('caproto_async', f"连接 {NUM_PVS} 个 PV...")
        conn_start = time.time()
        
        ctx = CaprotoAsyncContext()
        pvs = await asyncio.wait_for(ctx.get_pvs(*PV_LIST), timeout=15.0)
        
        m.connection_time = time.time() - conn_start
        m.start_time = time.time()
        
        log_event('caproto_async', f"连接成功 {len(pvs)}/{NUM_PVS} 个PV，耗时 {m.connection_time*1000:.1f}ms")
        
        async def monitor_pv(pv, pv_name):
            subscription = pv.subscribe()
            async for event in subscription:
                if stop_event.is_set():
                    break
                with lock:
                    m.total_updates += 1
                    m.pv_update_counts[pv_name] += 1
        
        tasks = [asyncio.create_task(monitor_pv(pv, name)) 
                 for pv, name in zip(pvs, PV_LIST)]
        
        while not stop_event.is_set():
            await asyncio.sleep(0.1)
        
        for task in tasks:
            task.cancel()
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        m.end_time = time.time()
        
    except Exception as e:
        m.errors += 1
        m.end_time = time.time()
        log_event('caproto_async', f"错误: {e}", error=True)
        import traceback
        traceback.print_exc()


# ================================================================
# 测试 4: WebSocket
# ================================================================

async def test_websocket_multi():
    """WebSocket: 为每个PV创建独立连接"""
    m = metrics['websocket']
    
    for pv_name in PV_LIST:
        m.pv_update_counts[pv_name] = 0
    
    conn_start = time.time()
    m.start_time = time.time()
    
    try:
        log_event('websocket', f"连接 {NUM_PVS} 个 PV...")

        async def monitor_pv(pv_name):
            """监控单个PV"""
            url = f"{WS_BASE_URL}?pv={pv_name}"
            try:
                async with websockets.connect(url, ping_interval=20) as ws:
                    while not stop_event.is_set():
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                            with lock:
                                m.total_updates += 1
                                m.pv_update_counts[pv_name] += 1
                        except asyncio.TimeoutError:
                            continue
            except Exception as e:
                log_event('websocket', f"{pv_name} 错误: {e}", error=True)
                m.errors += 1

        tasks = [asyncio.create_task(monitor_pv(name)) for name in PV_LIST]

        # 等待至少一个连接建立
        await asyncio.sleep(0.5)

        m.connection_time = time.time() - conn_start
        log_event('websocket', f"启动 {NUM_PVS} 个WebSocket连接，耗时 {m.connection_time*1000:.1f}ms")

        while not stop_event.is_set():
            await asyncio.sleep(0.1)

        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)

        m.end_time = time.time()

    except Exception as e:
        m.errors += 1
        m.end_time = time.time()
        log_event('websocket', f"错误: {e}", error=True)
        import traceback
        traceback.print_exc()


# ================================================================
# 统计打印
# ================================================================

def print_statistics():
    """定期打印统计"""
    while not stop_event.is_set():
        time.sleep(5)

        with lock:
            print(f"\n{'='*140}")
            print(f"⏰ {datetime.now().strftime('%H:%M:%S')} | "
                  f"💻 CPU: {process.cpu_percent():.1f}% | "
                  f"🧠 Mem: {process.memory_info().rss/1024/1024:.1f}MB | "
                  f"🧵 Threads: {threading.active_count()}")
            print(f"{'Library':<15} {'Updates':<10} {'Rate(Hz)':<12} {'Per-PV(Hz)':<12} {'CPU%':<8} {'Mem(MB)':<10} {'Threads':<10}")
            print('-' * 140)

            for name, m in metrics.items():
                if m.total_updates == 0:
                    print(f"{name:<15} {'N/A':<10}")
                    continue

                s = m.summary()
                print(f"{name:<15} "
                      f"{s['total_updates']:<10} "
                      f"{s['total_rate_hz']:<12.2f} "
                      f"{s['avg_rate_per_pv_hz']:<12.2f} "
                      f"{s['avg_cpu_percent']:<8.1f} "
                      f"{s['avg_memory_mb']:<10.1f} "
                      f"{s['avg_threads']:<10.1f}")


# ================================================================
# 最终结果
# ================================================================

def print_final_results():
    """打印详细的最终结果"""
    print("\n" + "=" * 140)
    print(" " * 55 + "📈 多PV并发测试 - 最终结果 📈")
    print("=" * 140)

    with lock:
        summaries = {name: m.summary() for name, m in metrics.items()}

        print(f"\n{'指标':<30} " + "".join([f"{name:<25}" for name in metrics.keys()]))
        print("-" * 140)

        print(f"{'PV数量':<30} ", end="")
        for name in metrics.keys():
            print(f"{summaries[name].get('num_pvs', 0):<25}", end="")
        print()

        print(f"{'连接时间 (ms)':<30} ", end="")
        for name in metrics.keys():
            val = summaries[name].get('connection_time_ms', 0)
            print(f"{val:<25.2f}", end="")
        print()

        print(f"{'总更新数':<30} ", end="")
        for name in metrics.keys():
            val = summaries[name].get('total_updates', 0)
            print(f"{val:<25,}", end="")
        print()

        print(f"{'总速率 (Hz)':<30} ", end="")
        for name in metrics.keys():
            val = summaries[name].get('total_rate_hz', 0)
            print(f"{val:<25.2f}", end="")
        print()

        print(f"{'单PV平均速率 (Hz)':<30} ", end="")
        for name in metrics.keys():
            val = summaries[name].get('avg_rate_per_pv_hz', 0)
            print(f"{val:<25.2f}", end="")
        print()

        print(f"{'平均CPU (%)':<30} ", end="")
        for name in metrics.keys():
            val = summaries[name].get('avg_cpu_percent', 0)
            print(f"{val:<25.2f}", end="")
        print()

        print(f"{'峰值CPU (%)':<30} ", end="")
        for name in metrics.keys():
            val = summaries[name].get('max_cpu_percent', 0)
            print(f"{val:<25.2f}", end="")
        print()

        print(f"{'平均内存 (MB)':<30} ", end="")
        for name in metrics.keys():
            val = summaries[name].get('avg_memory_mb', 0)
            print(f"{val:<25.2f}", end="")
        print()

        print(f"{'峰值内存 (MB)':<30} ", end="")
        for name in metrics.keys():
            val = summaries[name].get('max_memory_mb', 0)
            print(f"{val:<25.2f}", end="")
        print()

        print(f"{'平均线程数':<30} ", end="")
        for name in metrics.keys():
            val = summaries[name].get('avg_threads', 0)
            print(f"{val:<25.1f}", end="")
        print()

        print(f"{'峰值线程数':<30} ", end="")
        for name in metrics.keys():
            val = summaries[name].get('max_threads', 0)
            print(f"{val:<25}", end="")
        print()

        print(f"{'错误数':<30} ", end="")
        for name in metrics.keys():
            val = summaries[name].get('errors', 0)
            print(f"{val:<25}", end="")
        print()

    print("\n" + "=" * 140)

    # 详细分析每个库
    with lock:
        for name, m in metrics.items():
            s = m.summary()
            if m.total_updates == 0:
                continue

            print(f"\n{'🔷 ' + name.upper()}")
            print("─" * 100)
            print(f"  📊 性能指标:")
            print(f"     总更新数:              {s['total_updates']:,}")
            print(f"     测试时长:              {s['duration_s']:.2f} s")
            print(f"     总速率:                {s['total_rate_hz']:.2f} Hz")
            print(f"     单PV平均速率:          {s['avg_rate_per_pv_hz']:.2f} Hz")
            print(f"     连接时间:              {s['connection_time_ms']:.2f} ms")

            print(f"\n  💻 资源使用:")
            print(f"     平均CPU:               {s['avg_cpu_percent']:.2f}%")
            print(f"     峰值CPU:               {s['max_cpu_percent']:.2f}%")
            print(f"     平均内存:              {s['avg_memory_mb']:.2f} MB")
            print(f"     峰值内存:              {s['max_memory_mb']:.2f} MB")
            print(f"     平均线程数:            {s['avg_threads']:.1f}")
            print(f"     峰值线程数:            {int(s['max_threads'])}")

            print(f"\n  📈 每个PV的更新分布:")
            pv_dist = s['pv_update_distribution']
            if pv_dist:
                counts = list(pv_dist.values())
                print(f"     最小更新数:            {min(counts)}")
                print(f"     最大更新数:            {max(counts)}")
                print(f"     平均更新数:            {np.mean(counts):.1f}")
                print(f"     标准差:                {np.std(counts):.1f}")

    print("\n" + "=" * 140)

    # 获胜者分析
    with lock:
        valid_summaries = {name: m.summary() for name, m in metrics.items() if m.total_updates > 0}

        if valid_summaries:
            print("\n🏆 性能对比分析:")
            print("─" * 100)

            fastest_conn = min(valid_summaries.items(),
                             key=lambda x: x[1].get('connection_time_ms', float('inf')))
            print(f"  ⚡ 最快连接:            {fastest_conn[0]} ({fastest_conn[1]['connection_time_ms']:.2f} ms)")

            highest_total = max(valid_summaries.items(),
                              key=lambda x: x[1].get('total_rate_hz', 0))
            print(f"  🚀 最高总速率:          {highest_total[0]} ({highest_total[1]['total_rate_hz']:.2f} Hz)")

            lowest_cpu = min(valid_summaries.items(),
                           key=lambda x: x[1].get('avg_cpu_percent', float('inf')))
            print(f"  💻 最低CPU使用:         {lowest_cpu[0]} ({lowest_cpu[1]['avg_cpu_percent']:.2f}%)")

            lowest_mem = min(valid_summaries.items(),
                           key=lambda x: x[1].get('avg_memory_mb', float('inf')))
            print(f"  🧠 最低内存使用:        {lowest_mem[0]} ({lowest_mem[1]['avg_memory_mb']:.2f} MB)")

            lowest_thread = min(valid_summaries.items(),
                              key=lambda x: x[1].get('avg_threads', float('inf')))
            print(f"  🧵 最少线程数:          {lowest_thread[0]} ({lowest_thread[1]['avg_threads']:.1f})")

            # 资源效率
            print(f"\n  📊 资源效率排名 (更新数/资源消耗):")
            efficiency = {}
            for name, s in valid_summaries.items():
                cpu = s.get('avg_cpu_percent', 1)
                mem = s.get('avg_memory_mb', 1)
                updates = s.get('total_updates', 0)
                eff = updates / (cpu * mem) if cpu > 0 and mem > 0 else 0
                efficiency[name] = eff

            for i, (name, eff) in enumerate(sorted(efficiency.items(),
                                                   key=lambda x: x[1],
                                                   reverse=True), 1):
                symbol = "⭐" if i == 1 else " "
                print(f"     {i}. {symbol} {name:<15} 效率: {eff:.2f}")

    print("\n" + "=" * 140)

    # 推荐建议
    print("\n💡 推荐建议:")
    print("─" * 100)

    with lock:
        if len(valid_summaries) >= 2:
            thread_counts = {name: s['avg_threads'] for name, s in valid_summaries.items()}
            min_threads = min(thread_counts.values())
            max_threads = max(thread_counts.values())

            cpu_usage = {name: s['avg_cpu_percent'] for name, s in valid_summaries.items()}
            min_cpu = min(cpu_usage.values())
            max_cpu = max(cpu_usage.values())

            mem_usage = {name: s['avg_memory_mb'] for name, s in valid_summaries.items()}
            min_mem = min(mem_usage.values())
            max_mem = max(mem_usage.values())

            if max_threads > min_threads * 1.5:
                print(f"  ✓ 线程数差异: {min_threads:.0f} vs {max_threads:.0f} "
                      f"(节省 {((max_threads-min_threads)/max_threads*100):.0f}%)")

            if max_cpu > min_cpu * 1.3:
                print(f"  ✓ CPU差异: {min_cpu:.1f}% vs {max_cpu:.1f}% "
                      f"(节省 {max_cpu - min_cpu:.1f}%)")

            if max_mem > min_mem * 1.1:
                print(f"  ✓ 内存差异: {min_mem:.1f}MB vs {max_mem:.1f}MB "
                      f"(节省 {max_mem - min_mem:.1f}MB)")

            print(f"\n  📌 针对 {NUM_PVS} 个PV的场景推荐:")

            # 找出最优方案
            best_efficiency = max(efficiency.items(), key=lambda x: x[1])
            print(f"    🏆 综合最优: {best_efficiency[0]} (效率: {best_efficiency[1]:.2f})")

            if NUM_PVS >= 10:
                print(f"    → 大规模场景建议使用 caproto_async 或 caproto_sync")
            elif NUM_PVS >= 5:
                print(f"    → 中等规模建议使用 caproto_sync 或 websocket")
            else:
                print(f"    → 小规模场景可使用任意库，差异不大")

    print("\n" + "=" * 140)
    print("✅ 测试完成!")
    print("=" * 140)


# ================================================================
# 主函数
# ================================================================

def main():
    """主测试流程"""

    print("=" * 140)
    print(" " * 50 + "多PV并发性能对比测试")
    print("=" * 140)
    print(f"📍 测试PV数量 :       {NUM_PVS}")
    print(f"📋 PV列表:           {', '.join(PV_LIST[:3])}{'...' if NUM_PVS > 3 else ''}")
    print(f"⏱️  测试时长:         {TEST_DURATION} 秒")
    print(f"🌐 WebSocket URL:    {WS_BASE_URL}")
    print("=" * 140)
    print("\n🔬 测试库:")
    print("   1. pyepics        - 每个PV独立对象 (多线程)")
    print("   2. caproto_sync   - 共享Context (多线程)")
    print("   3. caproto_async  - 单线程异步 (理论上最省资源)")
    print("   4. websocket      - 多连接 (每PV一个WebSocket)")
    print("\n" + "=" * 140)
    
    # 启动监控
    monitor_thread = threading.Thread(target=resource_monitor, daemon=True)
    monitor_thread.start()
    
    stats_thread = threading.Thread(target=print_statistics, daemon=True)
    stats_thread.start()
    
    # 启动测试
    threads = []
    
    # pyepics
    t1 = threading.Thread(target=test_pyepics_multi, daemon=True, name="pyepics")
    t1.start()
    threads.append(t1)
    
    # caproto sync
    t2 = threading.Thread(target=test_caproto_sync_multi, daemon=True, name="caproto_sync")
    t2.start()
    threads.append(t2)
    
    # async tests
    async def run_async_tests():
        tasks = [
            asyncio.create_task(test_caproto_async_multi()),
            asyncio.create_task(test_websocket_multi())
        ]
        
        while not stop_event.is_set():
            await asyncio.sleep(0.1)
        
        for task in tasks:
            if not task.done():
                task.cancel()
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    def run_async_wrapper():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_async_tests())
        finally:
            try:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.close()
            except Exception:
                pass
    
    t3 = threading.Thread(target=run_async_wrapper, daemon=True, name="async_tests")
    t3.start()
    threads.append(t3)
    
    # 运行测试
    try:
        print(f"\n🏁 开始测试 {TEST_DURATION} 秒...\n")
        start_time = time.time()
        
        while time.time() - start_time < TEST_DURATION:
            time.sleep(0.5)
            
            alive_threads = [t for t in threads if t.is_alive()]
            if not alive_threads:
                log_event("SYSTEM", "所有线程提前终止", error=True)
                break
    
    except KeyboardInterrupt:
        print("\n⚠️  用户中断测试")
    
    finally:
        print("\n🛑 停止测试...")
        stop_event.set()
        
        print("⏳ 等待线程完成...")
        for t in threads:
            t.join(timeout=5)
        
        time.sleep(1)
        
        print_final_results()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ 致命错误: {e}")
        import traceback
        traceback.print_exc()
