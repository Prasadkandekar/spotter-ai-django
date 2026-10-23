"""Offline US gazetteer (city/state and ZIP -> lat/lng) built on the `zipcodes` package.

Used for two things:
  1. Geocoding fuel stations once, at build time (`manage.py build_stations`).
  2. Resolving "City, ST" / ZIP inputs at request time without any network call.
"""
import re
from functools import lru_cache

import zipcodes

# Contiguous US + AK + HI bounding boxes, used to validate coordinates are in the USA.
US_BOXES = [
    (24.4, 49.5, -125.0, -66.9),   # contiguous
    (51.0, 71.6, -170.0, -129.0),  # Alaska (mainland + panhandle)
    (18.8, 22.4, -160.6, -154.7),  # Hawaii
]

_ABBREV = [
    (r"^st\.?\s", "saint "),
    (r"^ste\.?\s", "sainte "),
    (r"^ft\.?\s", "fort "),
    (r"^mt\.?\s", "mount "),
]


def normalize_city(name: str) -> str:
    n = re.sub(r"\s+", " ", str(name).strip().lower())
    for pat, rep in _ABBREV:
        n = re.sub(pat, rep, n)
    return re.sub(r"[^a-z0-9]", "", n)  # drop spaces/punctuation: "De Forest" == "DeForest"


def in_usa(lat: float, lon: float) -> bool:
    return any(a <= lat <= b and c <= lon <= d for a, b, c, d in US_BOXES)


@lru_cache(maxsize=1)
def _city_index() -> dict:
    acc: dict[tuple[str, str], list[tuple[float, float]]] = {}
    for z in zipcodes.list_all():
        try:
            lat, lon = float(z["lat"]), float(z["long"])
        except (TypeError, ValueError, KeyError):
            continue
        acc.setdefault((normalize_city(z["city"]), z["state"]), []).append((lat, lon))
    return {
        k: (sum(p[0] for p in v) / len(v), sum(p[1] for p in v) / len(v)) for k, v in acc.items()
    }


def lookup_city(city: str, state: str):
    """Return (lat, lon) of the city's centroid, or None."""
    return _city_index().get((normalize_city(city), str(state).strip().upper()))


def lookup_zip(zip_code: str):
    matches = zipcodes.matching(zip_code)
    if not matches:
        return None
    try:
        return float(matches[0]["lat"]), float(matches[0]["long"])
    except (TypeError, ValueError, KeyError):
        return None


_COORD_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*[,;\s]\s*(-?\d+(?:\.\d+)?)\s*$")
_ZIP_RE = re.compile(r"^\s*(\d{5})(?:-\d{4})?\s*$")
_CITY_ST_RE = re.compile(r"^\s*([A-Za-z.'\- ]+?)\s*,\s*([A-Za-z]{2})\s*(?:,?\s*(?:USA|US|United States))?\s*$")


def parse_location_offline(text: str):
    """Resolve 'lat,lng', 'ZIP' or 'City, ST' without any network call. Returns (lat, lon, label) or None."""
    m = _COORD_RE.match(text)
    if m:
        lat, lon = float(m.group(1)), float(m.group(2))
        return lat, lon, f"{lat:.5f},{lon:.5f}"
    m = _ZIP_RE.match(text)
    if m:
        hit = lookup_zip(m.group(1))
        if hit:
            return hit[0], hit[1], m.group(1)
        return None
    m = _CITY_ST_RE.match(text)
    if m:
        hit = lookup_city(m.group(1), m.group(2))
        if hit:
            return hit[0], hit[1], f"{m.group(1).strip().title()}, {m.group(2).upper()}"
    return None
