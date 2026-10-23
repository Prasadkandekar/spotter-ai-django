"""In-memory station store + fast corridor search along a route."""
import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

EARTH_RADIUS_MI = 3958.8
STATIONS_CSV = Path(__file__).resolve().parent / "data" / "stations.csv"


def to_xyz(lat, lon):
    """Lat/lon (degrees) -> 3D unit-sphere coords. Chord distance is monotonic in great-circle distance,
    which lets a KD-tree answer 'within N miles' queries accurately anywhere in the US."""
    lat, lon = np.radians(np.asarray(lat, dtype=float)), np.radians(np.asarray(lon, dtype=float))
    c = np.cos(lat)
    return np.stack([c * np.cos(lon), c * np.sin(lon), np.sin(lat)], axis=-1)


def haversine_miles(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_MI * np.arcsin(np.sqrt(a))


@dataclass(frozen=True)
class StationStore:
    ids: np.ndarray
    names: list
    addresses: list
    cities: list
    states: list
    prices: np.ndarray
    lats: np.ndarray
    lons: np.ndarray
    xyz: np.ndarray

    def __len__(self):
        return len(self.ids)

    def nearest_to_point(self, lat, lon):
        d = haversine_miles(lat, lon, self.lats, self.lons)
        i = int(np.argmin(d))
        return i, float(d[i])


@lru_cache(maxsize=1)
def get_store() -> StationStore:
    rows = list(csv.DictReader(open(STATIONS_CSV, newline="", encoding="utf-8")))
    if not rows:
        raise RuntimeError(f"{STATIONS_CSV} is empty - run `python manage.py build_stations`")
    lats = np.array([float(r["lat"]) for r in rows])
    lons = np.array([float(r["lon"]) for r in rows])
    return StationStore(
        ids=np.array([int(r["id"]) for r in rows]),
        names=[r["name"] for r in rows],
        addresses=[r["address"] for r in rows],
        cities=[r["city"] for r in rows],
        states=[r["state"] for r in rows],
        prices=np.array([float(r["price"]) for r in rows]),
        lats=lats,
        lons=lons,
        xyz=to_xyz(lats, lons),
    )


def route_cumulative_miles(coords: np.ndarray) -> np.ndarray:
    """coords: (N,2) array of [lat, lon]. Returns cumulative distance (miles) at each vertex."""
    seg = haversine_miles(coords[:-1, 0], coords[:-1, 1], coords[1:, 0], coords[1:, 1])
    return np.concatenate([[0.0], np.cumsum(seg)])


def stations_along_route(store: StationStore, coords: np.ndarray, cum: np.ndarray, corridor_miles: float):
    """Return stations within `corridor_miles` of the route as arrays (store_idx, route_mile, off_route_miles).

    One KD-tree is built over the route vertices (~ms for 100k points) and queried with all stations.
    Each station is snapped to its nearest route vertex, which gives its position along the route.
    """
    # Cheap bounding-box prefilter so the KD-tree only sees plausible stations.
    pad = corridor_miles / 69.0 + 0.1
    lat_lo, lat_hi = coords[:, 0].min() - pad, coords[:, 0].max() + pad
    lon_lo, lon_hi = coords[:, 1].min() - pad * 1.6, coords[:, 1].max() + pad * 1.6
    mask = (store.lats >= lat_lo) & (store.lats <= lat_hi) & (store.lons >= lon_lo) & (store.lons <= lon_hi)
    cand = np.flatnonzero(mask)
    if cand.size == 0:
        return np.array([], dtype=int), np.array([]), np.array([])

    tree = cKDTree(to_xyz(coords[:, 0], coords[:, 1]))
    chord_limit = 2 * np.sin(corridor_miles / EARTH_RADIUS_MI / 2)
    dist, vidx = tree.query(store.xyz[cand], distance_upper_bound=chord_limit)
    ok = np.isfinite(dist)
    cand, dist, vidx = cand[ok], dist[ok], vidx[ok]
    off_miles = 2 * EARTH_RADIUS_MI * np.arcsin(np.clip(dist / 2, 0, 1))
    pos = cum[vidx]
    order = np.argsort(pos, kind="stable")
    return cand[order], pos[order], off_miles[order]
