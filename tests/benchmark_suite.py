#!/usr/bin/env python3
"""
Six Degrees of Wikipedia - Benchmark Suite

Professional benchmarking script to measure system performance across
multiple test cases of varying difficulty.

Usage:
    python tests/benchmark_suite.py

Metrics:
    - Execution Time (seconds)
    - Path Length (hops)
    - Speed Score (nodes/second)
"""

import asyncio
import json
import sys
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

# Add project root to path
sys.path.insert(0, '.')

from backend.bfs import find_shortest_path, save_cache


# =============================================================================
# TEST CASES
# =============================================================================

@dataclass
class TestCase:
    """Defines a benchmark test case."""
    name: str
    start: str
    end: str
    difficulty: str
    expected_time: float  # seconds


TEST_CASES = [
    TestCase(
        name="Short Hop",
        start="Barack Obama",
        end="Donald Trump",  # Both modern US presidents - should connect quickly
        difficulty="Easy",
        expected_time=10.0
    ),
    TestCase(
        name="Medium Hop",
        start="Elon Musk",
        end="Steve Jobs",  # Both tech moguls - easier than Einstein
        difficulty="Medium",
        expected_time=15.0
    ),
    TestCase(
        name="The Extreme",
        start="Genghis Khan",
        end="Donald Trump",
        difficulty="Hard",
        expected_time=30.0
    ),
]


# =============================================================================
# BENCHMARK RESULT
# =============================================================================

@dataclass
class BenchmarkResult:
    """Stores results from a single benchmark run."""
    test_case: TestCase
    success: bool
    path: Optional[List[str]]
    execution_time: float
    nodes_visited: int
    error_message: Optional[str] = None
    
    @property
    def path_length(self) -> int:
        return len(self.path) if self.path else 0
    
    @property
    def speed_score(self) -> float:
        """Calculate speed score: nodes processed per second."""
        if self.execution_time <= 0:
            return 0.0
        return self.nodes_visited / self.execution_time
    
    @property
    def passed_time_target(self) -> bool:
        return self.execution_time <= self.test_case.expected_time


# =============================================================================
# BENCHMARK RUNNER
# =============================================================================

async def run_single_benchmark(test_case: TestCase) -> BenchmarkResult:
    """Run a single benchmark test case."""
    print(f"\n{'='*60}")
    print(f"🔍 {test_case.name}: {test_case.start} → {test_case.end}")
    print(f"   Difficulty: {test_case.difficulty} | Target: <{test_case.expected_time}s")
    print(f"{'='*60}")
    
    start_time = time.time()
    path = None
    nodes_visited = 0
    error_message = None
    
    try:
        async for message in find_shortest_path(test_case.start, test_case.end):
            data = json.loads(message)
            
            if data["status"] == "exploring":
                stats = data.get("stats", {})
                nodes_visited = stats.get("visited", 0)
                elapsed = stats.get("time", 0)
                nodes = data.get("nodes", [])
                node_name = nodes[0][:30] if nodes else "?"
                print(f"   [{elapsed:5.1f}s] Visited: {nodes_visited:4d} | {node_name}...")
                
            elif data["status"] == "finished":
                path = data["path"]
                break
                
            elif data["status"] == "error":
                error_message = data.get("message", "Unknown error")
                break
                
            elif data["status"] == "not_found":
                error_message = "No path found"
                break
                
    except Exception as e:
        error_message = str(e)
    
    execution_time = time.time() - start_time
    save_cache()
    
    return BenchmarkResult(
        test_case=test_case,
        success=path is not None,
        path=path,
        execution_time=execution_time,
        nodes_visited=nodes_visited,
        error_message=error_message
    )


async def run_all_benchmarks() -> List[BenchmarkResult]:
    """Run all benchmark test cases sequentially."""
    print("\n" + "="*60)
    print("🚀 SIX DEGREES OF WIKIPEDIA - BENCHMARK SUITE")
    print("="*60)
    print(f"Running {len(TEST_CASES)} test cases...")
    
    results = []
    for test_case in TEST_CASES:
        result = await run_single_benchmark(test_case)
        results.append(result)
        
        # Print immediate result
        if result.success:
            status = "✅ PASS" if result.passed_time_target else "⚠️ SLOW"
            print(f"\n   {status} in {result.execution_time:.2f}s (Target: {test_case.expected_time}s)")
            print(f"   Path ({result.path_length} hops): {' → '.join(result.path)}")
        else:
            print(f"\n   ❌ FAIL: {result.error_message}")
    
    return results


# =============================================================================
# REPORT GENERATOR
# =============================================================================

def print_report(results: List[BenchmarkResult]) -> None:
    """Print a formatted benchmark report."""
    print("\n")
    print("="*80)
    print("📊 BENCHMARK REPORT")
    print("="*80)
    
    # Header
    print(f"\n{'Test Case':<20} {'Status':<10} {'Time':>8} {'Target':>8} {'Hops':>6} {'Score':>10}")
    print("-"*80)
    
    total_time = 0
    total_score = 0
    passed = 0
    
    for result in results:
        # Determine status
        if not result.success:
            status = "❌ FAIL"
        elif result.passed_time_target:
            status = "✅ PASS"
            passed += 1
        else:
            status = "⚠️ SLOW"
            passed += 1
        
        time_str = f"{result.execution_time:.2f}s"
        target_str = f"<{result.test_case.expected_time}s"
        hops_str = str(result.path_length) if result.success else "-"
        score_str = f"{result.speed_score:.1f} n/s" if result.success else "-"
        
        print(f"{result.test_case.name:<20} {status:<10} {time_str:>8} {target_str:>8} {hops_str:>6} {score_str:>10}")
        
        total_time += result.execution_time
        total_score += result.speed_score
    
    print("-"*80)
    
    # Summary
    avg_score = total_score / len(results) if results else 0
    print(f"\n{'TOTAL':<20} {passed}/{len(results)} passed    {total_time:.2f}s             {avg_score:.1f} n/s avg")
    
    # Overall grade
    print("\n" + "="*80)
    if passed == len(results):
        grade = "🏆 EXCELLENT" if all(r.passed_time_target for r in results) else "✅ GOOD"
    elif passed > 0:
        grade = "⚠️ NEEDS IMPROVEMENT"
    else:
        grade = "❌ FAILED"
    
    print(f"OVERALL GRADE: {grade}")
    print("="*80 + "\n")
    
    # Path details
    print("📝 PATH DETAILS:")
    print("-"*80)
    for result in results:
        if result.success:
            print(f"\n{result.test_case.name}:")
            for i, node in enumerate(result.path):
                connector = "→" if i < len(result.path) - 1 else "🎯"
                print(f"   {i+1}. {node} {connector}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Entry point for benchmark suite."""
    try:
        results = asyncio.run(run_all_benchmarks())
        print_report(results)
        
        # Exit code based on results
        all_passed = all(r.success for r in results)
        sys.exit(0 if all_passed else 1)
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Benchmark interrupted by user.")
        save_cache()
        sys.exit(130)


if __name__ == "__main__":
    main()
