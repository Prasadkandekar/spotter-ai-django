"""Thin clients for the two free external services. Both are cached and both fail with clean PlanErrors."""
import hashlib
import time

import numpy as np
import requests
from django.conf import settings
from django.core.cache import cache

from .errors import PlanError
from .gazetteer import in_usa, parse_location_offline

METERS_PER_MILE = 1609.344
_session = requests.Session()  # keep-alive: reuses the TLS connection between requests
_last_nominatim_call = 0  # Rate limiting: Nominatim requires 1 request per second max


def _cfg():
    return settings.FUEL_PLANNER


def geocode(text: str):
    """Resolve a user-supplied location to (lat, lon, label).

    Order: coordinates / ZIP / "City, ST" (offline, zero network) -> Nominatim (1 call, cached).
    """
    text = (text or "").strip()
    if not text:
        raise PlanError("Location is empty.", code="invalid_location")

    hit = parse_location_offline(text)
    if hit:
        lat, lon, label = hit
    else:
        key = "geo:" + hashlib.sha1(text.lower().encode()).hexdigest()
        cached = cache.get(key)
        if cached is None:
            # Rate limiting: Nominatim requires max 1 request per second
            global _last_nominatim_call
            elapsed = time.time() - _last_nominatim_call
            if elapsed < 1.0:
                time.sleep(1.0 - elapsed)
            _last_nominatim_call = time.time()
            
            try:
                headers = {
                    "User-Agent": _cfg()["HTTP_USER_AGENT"],
                    "Referer": _cfg().get("REFERER", "http://localhost:8000")
                }
                r = _session.get(
                    _cfg()["NOMINATIM_URL"],
                    params={"q": text, "format": "jsonv2", "limit": 1, "countrycodes": "us"},
                    headers=headers,
                    timeout=_cfg()["HTTP_TIMEOUT_SECONDS"],
                )
                r.raise_for_status()
                data = r.json()
            except requests.RequestException as exc:
                raise PlanError(f"Geocoding service unavailable: {exc}", status=502, code="geocoder_unavailable")
            if not data:
                raise PlanError(f"Could not find a US location for '{text}'.", code="location_not_found")
            cached = (float(data[0]["lat"]), float(data[0]["lon"]), data[0].get("display_name", text))
            cache.set(key, cached, _cfg()["CACHE_SECONDS"])
        lat, lon, label = cached

    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise PlanError(f"Invalid coordinates for '{text}'.", code="invalid_location")
    if not in_usa(lat, lon):
        raise PlanError(f"'{text}' is not within the USA.", code="outside_usa")
    return lat, lon, label


def fetch_route(start, finish):
    """ONE call to OSRM returns the full driving geometry + distance. Cached per start/finish pair.

    Returns dict(coords=np.ndarray[(N,2) lat,lon], miles=float, duration_hours=float).
    """
    key = "route:%.4f,%.4f:%.4f,%.4f" % (start[0], start[1], finish[0], finish[1])
    cached = cache.get(key)
    if cached is not None:
        return cached

    url = "{base}/route/v1/driving/{slon},{slat};{flon},{flat}".format(
        base=_cfg()["OSRM_BASE_URL"].rstrip("/"), slon=start[1], slat=start[0], flon=finish[1], flat=finish[0]
    )
    try:
        headers = {
            "User-Agent": _cfg()["HTTP_USER_AGENT"],
            "Referer": _cfg().get("REFERER", "http://localhost:8000")
        }
        r = _session.get(
            url,
            params={"overview": "full", "geometries": "geojson", "steps": "false", "alternatives": "false"},
            headers=headers,
            timeout=_cfg()["HTTP_TIMEOUT_SECONDS"],
        )
        data = r.json()
    except (requests.RequestException, ValueError) as exc:
        raise PlanError(f"Routing service unavailable: {exc}", status=502, code="router_unavailable")

    if data.get("code") != "Ok" or not data.get("routes"):
        msg = data.get("message") or data.get("code") or "no route"
        raise PlanError(f"No drivable route found between those locations ({msg}).", status=422, code="no_route")

    route = data["routes"][0]
    lonlat = np.asarray(route["geometry"]["coordinates"], dtype=float)
    result = {
        "coords": lonlat[:, ::-1].copy(),  # -> lat, lon
        "miles": route["distance"] / METERS_PER_MILE,
        "duration_hours": route["duration"] / 3600.0,
    }
    cache.set(key, result, _cfg()["CACHE_SECONDS"])
    return result
