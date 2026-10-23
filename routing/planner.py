"""Orchestrates: geocode -> single route call -> corridor search -> optimizer -> response dict."""
import numpy as np
from django.conf import settings

from .clients import fetch_route, geocode
from .errors import PlanError
from .optimizer import plan_fuel_stops
from .stations import get_store, route_cumulative_miles, stations_along_route


def _thin(coords: np.ndarray, max_points: int) -> np.ndarray:
    n = len(coords)
    if n <= max_points:
        return coords
    idx = np.unique(np.linspace(0, n - 1, max_points).astype(int))
    return coords[idx]


def build_plan(start_text: str, finish_text: str, corridor_miles=None) -> dict:
    cfg = settings.FUEL_PLANNER
    corridor = float(corridor_miles or cfg["CORRIDOR_MILES"])
    if not (0 < corridor <= 50):
        raise PlanError("corridor_miles must be between 0 and 50.", code="invalid_parameter")

    s_lat, s_lon, s_label = geocode(start_text)
    f_lat, f_lon, f_label = geocode(finish_text)

    route = fetch_route((s_lat, s_lon), (f_lat, f_lon))  # <- the only routing-API call
    coords = route["coords"]
    cum = route_cumulative_miles(coords)
    # OSRM's road distance is authoritative; our haversine sum is within ~0.1% so rescale to match it.
    scale = route["miles"] / cum[-1] if cum[-1] > 0 else 1.0
    cum = cum * scale
    total_miles = float(route["miles"])

    store = get_store()
    idx, pos, off = stations_along_route(store, coords, cum, corridor)
    if len(idx) == 0:
        raise PlanError(
            "No fuel stations found near this route. Try a larger corridor_miles.", status=422, code="no_stations"
        )

    start_price = float(store.prices[idx[0]])  # tank at departure valued at the first station's price
    plan = plan_fuel_stops(
        positions=pos,
        prices=store.prices[idx],
        total_miles=total_miles,
        start_price=start_price,
        max_range=cfg["MAX_RANGE_MILES"],
        mpg=cfg["MPG"],
    )

    stops = []
    for n, s in enumerate(plan.stops, start=1):
        si = int(idx[s.node])
        stops.append(
            {
                "stop": n,
                "station_id": int(store.ids[si]),
                "name": store.names[si],
                "address": store.addresses[si],
                "city": store.cities[si],
                "state": store.states[si],
                "location": {"lat": float(store.lats[si]), "lng": float(store.lons[si])},
                "mile_marker": round(s.mile, 1),
                "miles_off_route": round(float(off[s.node]), 1),
                "price_per_gallon": round(s.price, 3),
                "gallons_purchased": round(s.gallons, 1),
                "cost": round(s.cost, 2),
            }
        )

    total_cost = plan.purchase_cost + plan.initial_tank_cost
    total_gallons = total_miles / cfg["MPG"]
    thin = _thin(coords, cfg["MAP_MAX_POINTS"])

    return {
        "start": {"query": start_text, "resolved": s_label, "location": {"lat": round(s_lat, 5), "lng": round(s_lon, 5)}},
        "finish": {"query": finish_text, "resolved": f_label, "location": {"lat": round(f_lat, 5), "lng": round(f_lon, 5)}},
        "route": {
            "distance_miles": round(total_miles, 1),
            "duration_hours": round(route["duration_hours"], 2),
            "geometry": {"type": "LineString", "coordinates": [[round(float(lo), 4), round(float(la), 4)] for la, lo in thin]},
        },
        "fuel_stops": stops,
        "summary": {
            "vehicle_range_miles": cfg["MAX_RANGE_MILES"],
            "vehicle_mpg": cfg["MPG"],
            "total_gallons_used": round(total_gallons, 2),
            "total_fuel_cost": round(total_cost, 2),
            "cost_of_fuel_bought_en_route": round(plan.purchase_cost, 2),
            "cost_of_starting_tank_used": round(plan.initial_tank_cost, 2),
            "starting_tank_price_per_gallon": round(start_price, 4),
            "average_price_per_gallon": round(total_cost / total_gallons, 4) if total_gallons else None,
            "number_of_fuel_stops": len(stops),
            "stations_considered": int(len(idx)),
        
        },
    }
