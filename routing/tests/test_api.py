from unittest import mock

import numpy as np
from django.core.cache import cache
from django.test import TestCase

from routing import clients
from routing.gazetteer import parse_location_offline


def fake_route(start, finish):
    """Straight great-circle-ish polyline with ~2 mile spacing; stands in for the OSRM call."""
    n = 2000
    lat = np.linspace(start[0], finish[0], n)
    lon = np.linspace(start[1], finish[1], n)
    coords = np.stack([lat, lon], axis=1)
    from routing.stations import route_cumulative_miles

    miles = float(route_cumulative_miles(coords)[-1]) * 1.15
    return {"coords": coords, "miles": miles, "duration_hours": miles / 60}


class RouteApiTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_offline_parsing(self):
        self.assertIsNotNone(parse_location_offline("Chicago, IL"))
        self.assertIsNotNone(parse_location_offline("90210"))
        self.assertEqual(parse_location_offline("40.7,-74.0")[:2], (40.7, -74.0))
        self.assertIsNone(parse_location_offline("somewhere vague"))

    @mock.patch("routing.clients.fetch_route", side_effect=fake_route)
    @mock.patch("routing.planner.fetch_route", side_effect=fake_route)
    def test_cross_country_plan(self, planner_route, _):
        r = self.client.get("/api/route/", {"start": "Los Angeles, CA", "finish": "New York, NY", "corridor_miles": 40})
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertEqual(planner_route.call_count, 1)  # exactly one routing call
        stops = body["fuel_stops"]
        self.assertGreaterEqual(len(stops), 4)  # ~2,800 road miles with a 500-mile range
        marks = [s["mile_marker"] for s in stops]
        self.assertEqual(marks, sorted(marks))
        # consecutive stops (and first/last legs) never exceed the 500 mile range
        pts = [0] + marks + [body["route"]["distance_miles"]]
        self.assertTrue(all(b - a <= 500.01 for a, b in zip(pts, pts[1:])), pts)
        s = body["summary"]
        self.assertAlmostEqual(s["total_gallons_used"], body["route"]["distance_miles"] / 10, places=1)
        self.assertAlmostEqual(s["total_fuel_cost"], s["cost_of_fuel_bought_en_route"] + s["cost_of_starting_tank_used"], places=1)
        self.assertEqual(body["route"]["geometry"]["type"], "LineString")
        self.assertLessEqual(len(body["route"]["geometry"]["coordinates"]), 1500)

    @mock.patch("routing.planner.fetch_route", side_effect=fake_route)
    def test_map_page_and_post(self, _):
        r = self.client.post(
            "/api/route/", {"start": "Chicago, IL", "finish": "Dallas, TX", "corridor_miles": 40}, content_type="application/json"
        )
        self.assertEqual(r.status_code, 200, r.content)
        m = self.client.get("/api/route/map/", {"start": "Chicago, IL", "finish": "Dallas, TX", "corridor_miles": 40})
        self.assertEqual(m.status_code, 200)
        self.assertIn("leaflet", m.content.decode().lower())

    def test_validation_errors(self):
        self.assertEqual(self.client.get("/api/route/").status_code, 400)
        r = self.client.get("/api/route/", {"start": "48.85,2.35", "finish": "Chicago, IL"})  # Paris
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"]["code"], "outside_usa")
        r = self.client.post("/api/route/", "not json", content_type="application/json")
        self.assertEqual(r.json()["error"]["code"], "invalid_json")

    @mock.patch("routing.planner.fetch_route", side_effect=fake_route)
    def test_unreachable_route_returns_422(self, _):
        # Corridor of 0.5 mi around a straight line leaves gaps > 500 mi -> clean 422, not a crash.
        r = self.client.get("/api/route/", {"start": "Seattle, WA", "finish": "Miami, FL", "corridor_miles": 0.5})
        self.assertEqual(r.status_code, 422)
        self.assertIn(r.json()["error"]["code"], {"unreachable", "no_stations"})
