"""Django settings for the fuel route planner.

The service is stateless: no database tables are needed. Station data is loaded
once into memory from routing/data/stations.csv.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")

INSTALLED_APPS = ["routing"]

MIDDLEWARE = [
    "django.middleware.gzip.GZipMiddleware",  # Compress responses (60-70% smaller)
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# No models are used, but Django expects a DATABASES setting.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Cache stores routing responses + geocodes so repeat requests make zero external calls.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "fuel-route-planner",
        "OPTIONS": {"MAX_ENTRIES": 500},
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
STATIC_URL = "static/"

# ---- Fuel route planner configuration ----
FUEL_PLANNER = {
    # Free routing API (OSRM). Swap for a self-hosted instance in production.
    "OSRM_BASE_URL": os.environ.get("OSRM_BASE_URL", "https://router.project-osrm.org"),
    # Free geocoder, only used when an input isn't "lat,lng", a ZIP, or "City, ST".
    "NOMINATIM_URL": os.environ.get("NOMINATIM_URL", "https://nominatim.openstreetmap.org/search"),
    "HTTP_USER_AGENT": os.environ.get("HTTP_USER_AGENT", "FuelRoutePlanner/1.0 (Development; +https://github.com/yourproject; contact@yourdomain.com)"),
    "HTTP_TIMEOUT_SECONDS": 30,  # Increased timeout for slower responses
    "REFERER": "http://localhost:8000",  # Some services require Referer header
    "MAX_RANGE_MILES": 500.0,
    "MPG": 10.0,
    "CORRIDOR_MILES": 10.0,  # max distance a station may sit from the route
    "CACHE_SECONDS": 60 * 60 * 24,
    "MAP_MAX_POINTS": 300,  # route geometry is thinned to this many points in responses (reduced from 1500 for performance)
}
