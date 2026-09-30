"""Open-Meteo connectors: rainfall forecast, river discharge (Flood API), and
elevation-derived slope, for the Phase 6 hazard scenario. All three endpoints
are free and require no API key. Attribution required by their terms:
"Open-Meteo (CC BY 4.0)" — https://open-meteo.com/en/license

Endpoints were verified live (via curl) against the region's coordinates
before being hardcoded here — see BUILD_LOG.md, Phase 6 pre-work.
"""

import math
from datetime import datetime, timedelta, timezone

import requests

from . import region
from .base import DEFAULT_TIMEOUT_S, fetch_with_fallback

SOURCE_ATTRIBUTION = "Open-Meteo (CC BY 4.0)"

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FLOOD_URL = "https://flood-api.open-meteo.com/v1/flood"
ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"

# Offset (degrees) for the 4 neighbor points used to estimate slope from
# elevation — ~1.1km at this latitude. Small enough to reflect local terrain,
# large enough that Open-Meteo's underlying DEM resolution can distinguish
# the points.
ELEVATION_SAMPLE_OFFSET_DEG = 0.01
METERS_PER_DEGREE_LAT = 111_111.0


def _sample_rainfall_forecast():
    """ILLUSTRATIVE fallback: 72 hours of light, steady rain — not a real forecast."""
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    times = [(start + timedelta(hours=h)).isoformat() for h in range(72)]
    precipitation = [1.2 if h % 6 < 2 else 0.0 for h in range(72)]
    return {"hourly": {"time": times, "precipitation": precipitation}, "illustrative": True}


def _sample_river_discharge():
    """ILLUSTRATIVE fallback: mild, flat 7-day discharge — not a real forecast."""
    start = datetime(2026, 1, 1, tzinfo=timezone.utc).date()
    times = [(start + timedelta(days=d)).isoformat() for d in range(7)]
    discharge = [3.0 + 0.1 * d for d in range(7)]
    return {"daily": {"time": times, "river_discharge": discharge}, "illustrative": True}


def _sample_elevation():
    """ILLUSTRATIVE fallback: a moderate Himalayan-style elevation profile."""
    return {"elevations": [1800.0, 1750.0, 1850.0, 1780.0, 1820.0], "offset_deg": ELEVATION_SAMPLE_OFFSET_DEG}


def fetch_rainfall_forecast(lat=region.REGION_LAT, lon=region.REGION_LON, timeout_s=DEFAULT_TIMEOUT_S):
    def _fetch():
        resp = requests.get(
            FORECAST_URL,
            params={"latitude": lat, "longitude": lon, "hourly": "precipitation", "forecast_days": 3, "timezone": "UTC"},
            timeout=timeout_s,
        )
        resp.raise_for_status()
        return resp.json()

    return fetch_with_fallback(f"open_meteo_forecast_{lat}_{lon}", _fetch, _sample_rainfall_forecast, SOURCE_ATTRIBUTION)


def fetch_river_discharge(lat=region.REGION_LAT, lon=region.REGION_LON, timeout_s=DEFAULT_TIMEOUT_S):
    def _fetch():
        resp = requests.get(
            FLOOD_URL,
            params={"latitude": lat, "longitude": lon, "daily": "river_discharge", "forecast_days": 7},
            timeout=timeout_s,
        )
        resp.raise_for_status()
        return resp.json()

    return fetch_with_fallback(f"open_meteo_flood_{lat}_{lon}", _fetch, _sample_river_discharge, SOURCE_ATTRIBUTION)


def fetch_elevation_slope(lat=region.REGION_LAT, lon=region.REGION_LON, timeout_s=DEFAULT_TIMEOUT_S):
    def _fetch():
        offset = ELEVATION_SAMPLE_OFFSET_DEG
        lats = [lat, lat + offset, lat - offset, lat, lat]
        lons = [lon, lon, lon, lon + offset, lon - offset]
        resp = requests.get(
            ELEVATION_URL,
            params={"latitude": ",".join(str(v) for v in lats), "longitude": ",".join(str(v) for v in lons)},
            timeout=timeout_s,
        )
        resp.raise_for_status()
        elevations = resp.json()["elevation"]
        return {"elevations": elevations, "offset_deg": offset}

    return fetch_with_fallback(f"open_meteo_elevation_{lat}_{lon}", _fetch, _sample_elevation, SOURCE_ATTRIBUTION)


def total_precipitation_mm(forecast_data, hours=24):
    """Sum of the next `hours` of hourly precipitation (mm). 0.0 on any
    missing/malformed data rather than raising."""
    try:
        values = forecast_data["hourly"]["precipitation"][:hours]
        return float(sum(v for v in values if v is not None))
    except Exception:
        return 0.0


def peak_river_discharge(flood_data, days=3):
    """Max daily river discharge (m^3/s) over the next `days`."""
    try:
        values = flood_data["daily"]["river_discharge"][:days]
        return float(max(v for v in values if v is not None))
    except Exception:
        return 0.0


def max_slope_degrees(elevation_data):
    """Max slope (degrees) between the center point and its 4 sampled
    neighbors, from elevation differences over the known offset distance."""
    try:
        elevations = elevation_data["elevations"]
        offset_deg = elevation_data["offset_deg"]
        center = elevations[0]
        horizontal_m = offset_deg * METERS_PER_DEGREE_LAT
        if horizontal_m <= 0:
            return 0.0
        return max(
            math.degrees(math.atan2(abs(e - center), horizontal_m)) for e in elevations[1:]
        )
    except Exception:
        return 0.0
