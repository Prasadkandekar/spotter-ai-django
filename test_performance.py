"""Performance benchmarking script for Fuel Route Planner API"""
import time
import requests
import sys
from statistics import mean, stdev

BASE_URL = "http://localhost:8000"

def benchmark_route(start, finish, corridor_miles=None, runs=5, warmup=1):
    """Benchmark a specific route with multiple runs"""
    times = []
    sizes = []
    
    params = {"start": start, "finish": finish}
    if corridor_miles:
        params["corridor_miles"] = corridor_miles
    
    print(f"Benchmarking: {start} → {finish}")
    if corridor_miles:
        print(f"Corridor: {corridor_miles} miles")
    
    # Warmup run (not counted)
    for i in range(warmup):
        print(f"  Warmup {i+1}...", end=" ")
        try:
            response = requests.get(f"{BASE_URL}/api/route/", params=params, timeout=60)
            print(f"✓ {response.status_code}")
        except Exception as e:
            print(f"✗ {e}")
            return None
    
    # Actual benchmark runs
    for i in range(runs):
        try:
            start_time = time.time()
            response = requests.get(f"{BASE_URL}/api/route/", params=params, timeout=60)
            elapsed = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                data = response.json()
                size = len(response.content)
                sizes.append(size)
                times.append(elapsed)
                
                print(f"  Run {i+1}/{runs}: {elapsed:6.0f}ms | "
                      f"{size/1024:6.1f}KB | "
                      f"{data['route']['distance_miles']:6.1f} mi | "
                      f"{len(data['fuel_stops'])} stops")
            else:
                print(f"  Run {i+1}/{runs}: ERROR {response.status_code}")
                return None
        except Exception as e:
            print(f"  Run {i+1}/{runs}: ERROR - {e}")
            return None
    
    if times:
        avg_time = mean(times)
        avg_size = mean(sizes)
        std_time = stdev(times) if len(times) > 1 else 0
        
        print(f"\n  📊 Results:")
        print(f"     Average:  {avg_time:6.0f}ms")
        print(f"     Min:      {min(times):6.0f}ms")
        print(f"     Max:      {max(times):6.0f}ms")
        print(f"     Std Dev:  {std_time:6.1f}ms")
        print(f"     Size:     {avg_size/1024:6.1f}KB")
        print(f"     Throughput: {1000/avg_time:.2f} req/sec")
        
        return {
            "avg": avg_time,
            "min": min(times),
            "max": max(times),
            "std": std_time,
            "size": avg_size,
            "times": times
        }
    
    return None


def test_cached_performance():
    """Test caching performance by running the same query multiple times"""
    print("\n" + "="*70)
    print("CACHE PERFORMANCE TEST")
    print("="*70)
    
    route = {"start": "Chicago, IL", "finish": "Dallas, TX"}
    
    print("\n🔥 First Request (Cold Cache):")
    result1 = benchmark_route(**route, runs=1, warmup=0)
    
    print("\n💨 Subsequent Requests (Warm Cache):")
    result2 = benchmark_route(**route, runs=5, warmup=0)
    
    if result1 and result2:
        speedup = result1["avg"] / result2["avg"]
        print(f"\n  ⚡ Cache Speedup: {speedup:.1f}x faster!")


def comprehensive_benchmark():
    """Run comprehensive benchmarks across different route types"""
    
    print("\n" + "="*70)
    print("FUEL ROUTE PLANNER - PERFORMANCE BENCHMARK")
    print("="*70)
    print(f"Target: {BASE_URL}")
    print("="*70)
    
    test_cases = [
        {
            "name": "Short Route (Under 500 miles)",
            "start": "Chicago, IL",
            "finish": "Indianapolis, IN",
            "expected_time": "1500-2000ms",
        },
        {
            "name": "Medium Route (500-1500 miles)",
            "start": "Chicago, IL",
            "finish": "Dallas, TX",
            "expected_time": "2000-2500ms",
        },
        {
            "name": "Long Route (1500-2500 miles)",
            "start": "San Francisco, CA",
            "finish": "Denver, CO",
            "expected_time": "2500-3000ms",
        },
        {
            "name": "Cross-Country (2500+ miles)",
            "start": "94103",
            "finish": "40.7128,-74.0060",
            "corridor_miles": 15,
            "expected_time": "3000-4000ms",
        },
    ]
    
    results = []
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{'='*70}")
        print(f"TEST {i}/{len(test_cases)}: {test['name']}")
        print(f"Expected: {test['expected_time']}")
        print('='*70)
        
        result = benchmark_route(
            test["start"],
            test["finish"],
            test.get("corridor_miles"),
            runs=3,
            warmup=1
        )
        
        if result:
            results.append({**test, **result})
    
    # Summary
    if results:
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        
        total_avg = mean([r["avg"] for r in results])
        total_size = mean([r["size"] for r in results])
        
        print(f"\n{'Route Type':<30} {'Avg Time':>12} {'Response Size':>15}")
        print("-" * 70)
        for r in results:
            print(f"{r['name']:<30} {r['avg']:>10.0f}ms {r['size']/1024:>12.1f}KB")
        
        print("-" * 70)
        print(f"{'Overall Average':<30} {total_avg:>10.0f}ms {total_size/1024:>12.1f}KB")
        
        print("\n📈 Performance Grade:")
        if total_avg < 1000:
            grade = "A+ (Excellent!)"
        elif total_avg < 2000:
            grade = "A (Very Good)"
        elif total_avg < 3000:
            grade = "B (Good)"
        elif total_avg < 4000:
            grade = "C (Acceptable)"
        else:
            grade = "D (Needs Optimization)"
        
        print(f"   {grade} - Average response time: {total_avg:.0f}ms")
        
        print("\n💡 Optimization Recommendations:")
        if total_avg > 2000:
            print("   • Consider self-hosting OSRM (can reduce to 400-600ms)")
        if total_size / 1024 > 100:
            print(f"   • Response size is {total_size/1024:.0f}KB - consider further optimization")
        if any(r["avg"] > 5000 for r in results):
            print("   • Some routes are very slow - check OSRM server health")
    
    return results


def quick_test():
    """Quick single test for development"""
    print("\n" + "="*70)
    print("QUICK PERFORMANCE TEST")
    print("="*70)
    
    benchmark_route(
        "Chicago, IL",
        "Dallas, TX",
        runs=3,
        warmup=1
    )


if __name__ == "__main__":
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "quick":
            quick_test()
        elif len(sys.argv) > 1 and sys.argv[1] == "cache":
            test_cached_performance()
        else:
            comprehensive_benchmark()
            test_cached_performance()
    except KeyboardInterrupt:
        print("\n\n⚠️  Benchmark interrupted by user")
    except requests.exceptions.ConnectionError:
        print("\n\n❌ ERROR: Cannot connect to server")
        print("   Make sure Django is running: python manage.py runserver")
    except Exception as e:
        print(f"\n\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
