#!/usr/bin/env python3
"""
Watchdog Benchmark - Hang Detection & Force Kill

This script acts as an external watchdog to prove that the BFS engine
respects timeouts and never hangs indefinitely.

Features:
- Runs test cases with hard timeout enforcement
- Force-kills any task exceeding 50 seconds
- Reports PASS/FAIL/HANG status for each test
"""

import asyncio
import json
import sys
import time
from dataclasses import dataclass
from typing import List, Optional

sys.path.insert(0, '.')

from backend.bfs import find_shortest_path, save_cache


# =============================================================================
# CONFIGURATION
# =============================================================================

WATCHDOG_TIMEOUT = 50  # Force kill after this many seconds


@dataclass
class TestCase:
    name: str
    start: str
    end: str
    max_time: float


TEST_CASES = [
    TestCase("Easy: Obama → Trump", "Barack Obama", "Donald Trump", 15.0),
    TestCase("Medium: Musk → Jobs", "Elon Musk", "Steve Jobs", 30.0),
    TestCase("Hard: Genghis Khan → Trump", "Genghis Khan", "Donald Trump", 45.0),
]


@dataclass
class TestResult:
    name: str
    status: str  # PASS, FAIL, TIMEOUT, HANG
    path: Optional[List[str]]
    time: float
    message: str


# =============================================================================
# WATCHDOG RUNNER
# =============================================================================

async def run_single_test(test: TestCase) -> TestResult:
    """Run a single test with watchdog timeout."""
    
    print(f"\n{'='*60}")
    print(f"🔍 {test.name}")
    print(f"   {test.start} → {test.end}")
    print(f"   Watchdog timeout: {WATCHDOG_TIMEOUT}s")
    print(f"{'='*60}")
    
    start_time = time.time()
    path = None
    status = "FAIL"
    message = ""
    
    async def execute_search():
        nonlocal path, status, message
        try:
            async for msg_str in find_shortest_path(test.start, test.end):
                msg = json.loads(msg_str)
                elapsed = time.time() - start_time
                
                if msg["status"] == "exploring":
                    stats = msg.get("stats", {})
                    nodes = msg.get("nodes", ["?"])
                    print(f"   [{elapsed:5.1f}s] V:{stats.get('visited', 0):4d} | {nodes[0][:30]}...")
                    
                elif msg["status"] == "finished":
                    path = msg["path"]
                    status = "PASS"
                    message = f"Path found: {len(path)} hops"
                    return
                    
                elif msg["status"] == "error":
                    status = "TIMEOUT" if "timeout" in msg.get("message", "").lower() else "FAIL"
                    message = msg.get("message", "Unknown error")
                    return
                    
                elif msg["status"] == "not_found":
                    status = "FAIL"
                    message = "No path found"
                    return
                    
        except Exception as e:
            status = "FAIL"
            message = str(e)
    
    try:
        # WATCHDOG: Force kill after WATCHDOG_TIMEOUT seconds
        await asyncio.wait_for(execute_search(), timeout=WATCHDOG_TIMEOUT)
    except asyncio.TimeoutError:
        status = "HANG"
        message = f"WATCHDOG KILL: Task exceeded {WATCHDOG_TIMEOUT}s"
    
    elapsed = time.time() - start_time
    save_cache()
    
    return TestResult(
        name=test.name,
        status=status,
        path=path,
        time=elapsed,
        message=message
    )


async def run_all_tests() -> List[TestResult]:
    """Run all tests sequentially."""
    
    print("\n" + "="*60)
    print("🐕 WATCHDOG BENCHMARK - HANG DETECTION")
    print(f"   Watchdog timeout: {WATCHDOG_TIMEOUT}s per test")
    print("="*60)
    
    results = []
    
    for test in TEST_CASES:
        result = await run_single_test(test)
        results.append(result)
        
        # Print immediate result
        icon = {"PASS": "✅", "FAIL": "❌", "TIMEOUT": "⏱️", "HANG": "🔴"}.get(result.status, "?")
        print(f"\n   {icon} {result.status} in {result.time:.2f}s")
        print(f"   {result.message}")
        
        if result.path:
            print(f"   Path: {' → '.join(result.path)}")
    
    return results


def print_report(results: List[TestResult]):
    """Print final summary report."""
    
    print("\n")
    print("="*70)
    print("📊 WATCHDOG REPORT")
    print("="*70)
    
    print(f"\n{'Test':<35} {'Status':<10} {'Time':>10} {'Result':<15}")
    print("-"*70)
    
    passed = 0
    for r in results:
        icon = {"PASS": "✅", "FAIL": "❌", "TIMEOUT": "⏱️", "HANG": "🔴"}.get(r.status, "?")
        time_str = f"{r.time:.2f}s"
        
        if r.status == "PASS":
            passed += 1
            result_str = f"{len(r.path)} hops"
        elif r.status == "HANG":
            result_str = "FORCE KILLED"
        else:
            result_str = r.message[:15]
        
        print(f"{r.name:<35} {icon} {r.status:<7} {time_str:>10} {result_str:<15}")
    
    print("-"*70)
    
    # Summary
    total = len(results)
    hangs = sum(1 for r in results if r.status == "HANG")
    
    print(f"\n{'SUMMARY':<35} {passed}/{total} passed")
    
    if hangs > 0:
        print(f"{'':35} 🔴 {hangs} HANG(s) DETECTED - Watchdog intervened!")
        grade = "❌ FAILED - HANG DETECTED"
    elif passed == total:
        grade = "✅ ALL TESTS PASSED - No hangs detected"
    else:
        grade = "⚠️ SOME TESTS FAILED - But no hangs"
    
    print(f"\n{'VERDICT':<35} {grade}")
    print("="*70 + "\n")
    
    return hangs == 0 and passed == total


def main():
    """Main entry point."""
    try:
        results = asyncio.run(run_all_tests())
        success = print_report(results)
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
        save_cache()
        sys.exit(130)


if __name__ == "__main__":
    main()
