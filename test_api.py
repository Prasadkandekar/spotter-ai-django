"""Quick API testing script for Fuel Route Planner"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

def print_section(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def test_basic_route():
    """Test basic GET request"""
    print_section("Test 1: Basic Route (Chicago to Dallas)")
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/route/",
            params={
                "start": "Chicago, IL",
                "finish": "Dallas, TX"
            },
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Success!")
            print(f"\nRoute Details:")
            print(f"  From: {data['start']['resolved']}")
            print(f"  To: {data['finish']['resolved']}")
            print(f"  Distance: {data['route']['distance_miles']} miles")
            print(f"  Duration: {data['route']['duration_hours']} hours")
            print(f"\nFuel Summary:")
            print(f"  Number of stops: {len(data['fuel_stops'])}")
            print(f"  Total gallons: {data['summary']['total_gallons_used']}")
            print(f"  Total cost: ${data['summary']['total_fuel_cost']}")
            print(f"  Average price: ${data['summary']['average_price_per_gallon']}/gal")
            print(f"  Stations considered: {data['summary']['stations_considered']}")
            
            if data['fuel_stops']:
                print(f"\nFuel Stops:")
                for stop in data['fuel_stops']:
                    print(f"  Stop {stop['stop']}: {stop['city']}, {stop['state']}")
                    print(f"    Mile marker: {stop['mile_marker']}")
                    print(f"    Price: ${stop['price_per_gallon']}/gal")
                    print(f"    Purchase: {stop['gallons_purchased']} gal = ${stop['cost']}")
            
            print(f"\nMap URL: {data['map_url']}")
            return True
        else:
            print(f"✗ Failed: {response.text}")
            return False
    except requests.exceptions.ConnectionError:
        print("✗ Connection Error: Is the server running?")
        print("   Start it with: python manage.py runserver")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_post_route():
    """Test POST request"""
    print_section("Test 2: POST Request (Seattle to Miami)")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/route/",
            json={
                "start": "Seattle, WA",
                "finish": "Miami, FL",
                "corridor_miles": 15
            },
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Success!")
            print(f"  Distance: {data['route']['distance_miles']} miles")
            print(f"  Fuel stops: {len(data['fuel_stops'])}")
            print(f"  Total cost: ${data['summary']['total_fuel_cost']}")
            return True
        else:
            print(f"✗ Failed: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_coordinates():
    """Test with coordinates"""
    print_section("Test 3: Using Coordinates (LA to NYC)")
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/route/",
            params={
                "start": "34.0522,-118.2437",  # Los Angeles
                "finish": "40.7128,-74.0060"   # New York
            },
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Success!")
            print(f"  Start resolved to: {data['start']['resolved']}")
            print(f"  Finish resolved to: {data['finish']['resolved']}")
            print(f"  Distance: {data['route']['distance_miles']} miles")
            print(f"  Total cost: ${data['summary']['total_fuel_cost']}")
            return True
        else:
            print(f"✗ Failed: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_zip_codes():
    """Test with ZIP codes"""
    print_section("Test 4: Using ZIP Codes (SF to Boston)")
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/route/",
            params={
                "start": "94103",  # San Francisco
                "finish": "02101"  # Boston
            },
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Success!")
            print(f"  Start ZIP resolved to: {data['start']['resolved']}")
            print(f"  Finish ZIP resolved to: {data['finish']['resolved']}")
            print(f"  Distance: {data['route']['distance_miles']} miles")
            return True
        else:
            print(f"✗ Failed: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_error_handling():
    """Test error responses"""
    print_section("Test 5: Error Handling")
    
    tests = [
        {
            "name": "Missing parameters",
            "params": {},
            "expected_code": 400
        },
        {
            "name": "Non-US location (Paris)",
            "params": {"start": "48.8566,2.3522", "finish": "Dallas, TX"},
            "expected_code": 400
        },
        {
            "name": "Invalid corridor (> 50)",
            "params": {"start": "Chicago, IL", "finish": "Dallas, TX", "corridor_miles": 100},
            "expected_code": 400
        },
        {
            "name": "Invalid corridor (negative)",
            "params": {"start": "Chicago, IL", "finish": "Dallas, TX", "corridor_miles": -5},
            "expected_code": 400
        }
    ]
    
    for test in tests:
        print(f"\n  Testing: {test['name']}")
        try:
            response = requests.get(
                f"{BASE_URL}/api/route/",
                params=test['params'],
                timeout=30
            )
            
            if response.status_code == test['expected_code']:
                error_data = response.json()
                print(f"    ✓ Got expected {test['expected_code']} error")
                print(f"    Error code: {error_data['error']['code']}")
                print(f"    Message: {error_data['error']['message']}")
            else:
                print(f"    ✗ Expected {test['expected_code']}, got {response.status_code}")
        except Exception as e:
            print(f"    ✗ Error: {e}")

def test_performance():
    """Test response time"""
    print_section("Test 6: Performance")
    
    try:
        import time
        
        print("Running 5 requests to measure performance...")
        times = []
        
        for i in range(5):
            start = time.time()
            response = requests.get(
                f"{BASE_URL}/api/route/",
                params={
                    "start": "Chicago, IL",
                    "finish": "Dallas, TX"
                },
                timeout=30
            )
            elapsed = (time.time() - start) * 1000  # Convert to ms
            times.append(elapsed)
            print(f"  Request {i+1}: {elapsed:.0f}ms (Status: {response.status_code})")
        
        if times:
            avg_time = sum(times) / len(times)
            print(f"\n  Average response time: {avg_time:.0f}ms")
            print(f"  Min: {min(times):.0f}ms, Max: {max(times):.0f}ms")
            
            # First request includes routing call, subsequent ones are cached
            if len(times) > 1:
                cached_avg = sum(times[1:]) / len(times[1:])
                print(f"  Cached response avg: {cached_avg:.0f}ms")
    except Exception as e:
        print(f"✗ Error: {e}")

def main():
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 58 + "║")
    print("║" + "  FUEL ROUTE PLANNER API - TEST SUITE".center(58) + "║")
    print("║" + " " * 58 + "║")
    print("╚" + "═" * 58 + "╝")
    print(f"\nStarted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Testing endpoint: {BASE_URL}")
    
    # Run all tests
    results = {
        "Basic Route (GET)": test_basic_route(),
        "POST Request": test_post_route(),
        "Coordinates": test_coordinates(),
        "ZIP Codes": test_zip_codes(),
    }
    
    test_error_handling()
    test_performance()
    
    # Summary
    print_section("Test Summary")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
    
    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

if __name__ == "__main__":
    main()
