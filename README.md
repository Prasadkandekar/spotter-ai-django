# Fuel Route Planner API (Django 6.1)

Given a start and finish inside the USA, the API returns the driving route (GeoJSON + an HTML map),
the cost-optimal places to fuel up (500-mile range), and the total fuel cost at 10 MPG.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate     # Python 3.12+
pip install -r requirements.txt
python manage.py runserver
```

`routing/data/stations.csv` (geocoded prices) is already built and committed. To rebuild it from the raw CSV:
`python manage.py build_stations`. Run tests with `python manage.py test`.

## Endpoints

| Method | URL | Returns |
|---|---|---|
| GET / POST | `/api/route/` | JSON: route GeoJSON, fuel stops, cost summary, `map_url` |
| GET | `/api/route/map/` | HTML page: Leaflet map with route and numbered fuel stops |

Parameters (query string for GET, JSON body for POST):

| Name | Required | Notes |
|---|---|---|
| `start`, `finish` | yes | `"lat,lng"`, a 5-digit ZIP, `"City, ST"`, or any free-text US address |
| `corridor_miles` | no | How far a station may be from the route (default 10, max 50) |

```bash
curl "http://localhost:8000/api/route/?start=Los Angeles, CA&finish=New York, NY"
curl -X POST localhost:8000/api/route/ -H 'Content-Type: application/json' \
     -d '{"start":"Seattle, WA","finish":"Miami, FL"}'
```

Open `map_url` from the response in a browser to see the map. A Postman collection is in `postman_collection.json`.

### Response (abridged)

```json
{
  "start":  {"query": "...", "resolved": "...", "location": {"lat": 0, "lng": 0}},
  "finish": {"...": "..."},
  "route":  {"distance_miles": 2782.0, "duration_hours": 41.5, "geometry": {"type": "LineString", "coordinates": [[-118.2, 34.0], "..."]}},
  "fuel_stops": [
    {"stop": 1, "name": "...", "address": "...", "city": "...", "state": "AZ",
     "location": {"lat": 0, "lng": 0}, "mile_marker": 464.7, "miles_off_route": 5.9,
     "price_per_gallon": 3.139, "gallons_purchased": 6.35, "cost": 19.94}
  ],
  "summary": {"total_gallons_used": 278.2, "total_fuel_cost": 893.25,
              "cost_of_fuel_bought_en_route": 680.3, "cost_of_starting_tank_used": 212.95,
              "number_of_fuel_stops": 11, "...": "..."},
  "map_url": "http://localhost:8000/api/route/map/?start=...&finish=..."
}
```

Errors are `{"error": {"code", "message"}}` with 400 (bad input), 422 (route cannot be fuelled / no route), or 502 (upstream service down).

## Design

**External calls: one per request.** Routing uses the free public OSRM server (`overview=full&geometries=geojson`),
which returns geometry and distance in a single call. Everything else is local:

* The fuel CSV has no coordinates. `build_stations` geocodes each station once (offline, to its city
  centroid via the `zipcodes` package) and writes `routing/data/stations.csv`. Requests never geocode stations.
* `start`/`finish` given as coordinates, ZIP, or `City, ST` are resolved offline. Only other free-text
  addresses use Nominatim (1 call each, cached). Worst case is 3 external calls, the common case is 1.
* Route results and geocodes are cached, so a repeat request, or the `map_url` page, makes zero calls.

**Speed.** Station data lives in memory (warmed at startup). Finding stations near the route is one KD-tree
build over the route vertices and one vectorized query of all stations, then the optimizer runs in O(n).
Planning takes about 7 ms for a coast-to-coast route (excluding the OSRM call).

**Optimizer.** The classic gas-station greedy, which is optimal for one tank with fixed range: at each
station, if a cheaper station is reachable on a full tank, buy just enough to get there; otherwise fill up.
The destination is a free station, so the plan buys exactly what it needs. Tests compare it against an exact
DP on random instances.

## Assumptions (please read)

* **Starting tank:** the vehicle leaves full (500 miles). That fuel is not free: it is priced at the first
  station on the route (`starting_tank_price_per_gallon`) and included in `total_fuel_cost`; the split is shown in
  `cost_of_fuel_bought_en_route` and `cost_of_starting_tank_used`. Change one line in `planner.py` if you prefer a different convention.
* **Duplicate truckstop IDs** (597 IDs have differing prices) are collapsed to the lowest listed price.
* **Station coordinates are city centroids**, not exact exit locations, so `miles_off_route` is approximate and
  the default corridor is a generous 10 miles. Detour fuel is not modelled.
* The 620 Canadian rows in the CSV are dropped. Coordinates input directly are only bounding-box checked
  for being in the USA (southern Canada falls inside the box); text/ZIP/City inputs are US-restricted.
* The public OSRM demo server has a fair-use limit and no SLA. Point `OSRM_BASE_URL` at your own instance
  (or any OSRM-compatible service) for production.

## Layout

```
config/            settings, urls
routing/
  views.py         HTTP layer (GET/POST JSON + HTML map)
  planner.py       orchestration, response shaping
  clients.py       OSRM + Nominatim clients, caching
  stations.py      in-memory store, KD-tree corridor search
  optimizer.py     fuel-stop greedy
  gazetteer.py     offline city/ZIP lookup
  map_html.py      Leaflet page
  management/commands/build_stations.py
  data/stations.csv
  tests/
```

## Loom outline (5 min)

1. Postman: GET `/api/route/` LA to NYC, show stops and `total_fuel_cost`; open `map_url`.
2. POST with a ZIP and a coordinate pair; show a 422 (tiny `corridor_miles`) and a 400 (non-US coordinates).
3. Code tour: `planner.py` (one routing call), `stations.py` (KD-tree), `optimizer.py` (greedy), `build_stations.py`.
4. Mention caching, the assumptions above, and what you would do next (exit-level geocoding, detour cost, per-vehicle tank state).
