"""USGS earthquake and GDACS multi-hazard event connectors, filtered to the
region.

USGS's own bbox query parameters were confirmed reliable (verified live: an
exact-region query returned a correctly-empty FeatureCollection, not an
error or unfiltered global list). GDACS's server-side `country`/`bbox`
parameters were confirmed UNRELIABLE (verified live: `country=IND` also
returned Indonesian events, apparent substring matching on the country name;
an explicit `bbox` param returned a Mexican cyclone) — so GDACS results are
always re-filtered client-side against `region.py`'s bounding box here,
regardless of what query parameters are sent.
"""

from datetime import datetime, timedelta, timezone

import requests

from . import region
from .base import DEFAULT_TIMEOUT_S, fetch_with_fallback

USGS_SOURCE = "USGS Earthquake Hazards Program"
GDACS_SOURCE = "GDACS (Global Disaster Alert and Coordination System)"

USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
GDACS_URL = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"

GDACS_EVENT_TYPES = ("EQ", "TC", "FL", "VO", "DR")

# GDACS's own API is genuinely slow (~13s measured live, even with the
# country pre-filter) — a longer, connector-specific timeout rather than a
# false promise of speed. Still bounded, so the dashboard never hangs.
GDACS_TIMEOUT_S = 20


def _sample_earthquakes():
    """ILLUSTRATIVE fallback: one small, clearly-labelled sample earthquake."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "mag": 3.8,
                    "place": "ILLUSTRATIVE sample event near Joshimath, India",
                    "time": 1735689600000,
                    "url": "https://earthquake.usgs.gov/",
                },
                "geometry": {"type": "Point", "coordinates": [79.6, 30.58, 10.0]},
            }
        ],
        "illustrative": True,
    }


def _sample_gdacs_events():
    """ILLUSTRATIVE fallback: one small, clearly-labelled sample flood alert."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "eventtype": "FL",
                    "name": "ILLUSTRATIVE sample flood alert, Uttarakhand",
                    "alertlevel": "Orange",
                    "htmldescription": "Illustrative sample GDACS event, not a real alert.",
                },
                "geometry": {"type": "Point", "coordinates": [79.5, 30.4]},
            }
        ],
        "illustrative": True,
    }


def fetch_earthquakes(days=30, min_magnitude=2.5, timeout_s=DEFAULT_TIMEOUT_S):
    def _fetch():
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        resp = requests.get(
            USGS_URL,
            params={
                "format": "geojson",
                "starttime": start.strftime("%Y-%m-%d"),
                "endtime": end.strftime("%Y-%m-%d"),
                "minlatitude": region.REGION_BBOX["min_lat"],
                "maxlatitude": region.REGION_BBOX["max_lat"],
                "minlongitude": region.REGION_BBOX["min_lon"],
                "maxlongitude": region.REGION_BBOX["max_lon"],
                "minmagnitude": min_magnitude,
            },
            timeout=timeout_s,
        )
        resp.raise_for_status()
        return resp.json()

    return fetch_with_fallback(f"usgs_eq_{days}_{min_magnitude}", _fetch, _sample_earthquakes, USGS_SOURCE)


def _feature_point(feature):
    geom = feature.get("geometry") or {}
    if geom.get("type") == "Point":
        coords = geom.get("coordinates") or []
        if len(coords) >= 2:
            return coords[1], coords[0]  # (lat, lon)
    return None


def _feature_in_region(feature):
    point = _feature_point(feature)
    if point is not None:
        return region.point_in_region(*point)
    bbox = feature.get("bbox")
    if bbox and len(bbox) >= 4:
        return region.bbox_intersects_region(bbox[0], bbox[1], bbox[2], bbox[3])
    return False


def fetch_gdacs_events(event_types=GDACS_EVENT_TYPES, timeout_s=GDACS_TIMEOUT_S):
    def _fetch():
        # country=IND is sent only to cut down the response size/latency —
        # confirmed unreliable for correctness (it substring-matches, so it
        # also returns e.g. Indonesia). The client-side bbox filter below is
        # what actually decides region membership.
        resp = requests.get(
            GDACS_URL, params={"eventlist": ";".join(event_types), "country": "IND"}, timeout=timeout_s
        )
        resp.raise_for_status()
        data = resp.json()
        filtered = [f for f in data.get("features", []) if _feature_in_region(f)]
        return {**data, "features": filtered}

    return fetch_with_fallback("gdacs_events", _fetch, _sample_gdacs_events, GDACS_SOURCE)


def events_in_region(usgs_data, gdacs_data):
    """Normalizes both sources' already-region-filtered features into one
    flat list of plain dicts for scenario.py / the UI."""
    events = []
    for f in (usgs_data or {}).get("features", []) or []:
        props = f.get("properties", {}) or {}
        point = _feature_point(f)
        events.append(
            {
                "source": "USGS",
                "type": "earthquake",
                "magnitude": props.get("mag"),
                "place": props.get("place"),
                "lat": point[0] if point else None,
                "lon": point[1] if point else None,
                "time": props.get("time"),
                "url": props.get("url"),
            }
        )
    for f in (gdacs_data or {}).get("features", []) or []:
        props = f.get("properties", {}) or {}
        point = _feature_point(f)
        events.append(
            {
                "source": "GDACS",
                "type": props.get("eventtype"),
                "name": props.get("name"),
                "alert_level": props.get("alertlevel"),
                "lat": point[0] if point else None,
                "lon": point[1] if point else None,
            }
        )
    return events


def max_earthquake_magnitude(usgs_data):
    try:
        mags = [f["properties"]["mag"] for f in usgs_data.get("features", []) if f["properties"].get("mag") is not None]
        return float(max(mags)) if mags else 0.0
    except Exception:
        return 0.0
