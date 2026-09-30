"""Derives an illustrative hazard-scenario intensity multiplier (the same
number `scoring.zone_risk_score`'s `hazard_scenario_multiplier` argument
takes) from live rainfall, river discharge, terrain slope, official alerts,
and recent seismic/GDACS events. The sidebar slider always remains available
as a manual override — this module only supplies the DEFAULT value plus a
"why" explanation; nothing here forces the slider to follow it.

Thresholds and weights below are illustrative, adjustable constants, not a
calibrated hazard model — same spirit as scoring.py's weights.
"""

from . import events, open_meteo, sachet

DEFAULT_MULTIPLIER = 1.0
MIN_MULTIPLIER = 0.5
MAX_MULTIPLIER = 2.0

RAIN_HEAVY_MM_24H = 50.0  # 24h forecast rainfall at/above this = "heavy"
DISCHARGE_HIGH_M3S = 20.0  # peak 3-day river discharge at/above this = "high"
SLOPE_STEEP_DEG = 25.0  # local terrain slope at/above this = "steep"
EARTHQUAKE_NOTABLE_MAG = 4.0  # magnitude at/above this = "notable"

# Each triggered signal adds this much to the baseline multiplier.
SIGNAL_WEIGHTS = {
    "heavy_rain": 0.25,
    "high_discharge": 0.20,
    "steep_slope": 0.15,
    "active_alert": 0.25,
    "notable_earthquake": 0.15,
}


def gather_signals():
    """Calls every Phase 6 connector once. Each already has its own
    live/cached/sample fallback — this function never raises."""
    return {
        "rainfall": open_meteo.fetch_rainfall_forecast(),
        "discharge": open_meteo.fetch_river_discharge(),
        "elevation": open_meteo.fetch_elevation_slope(),
        "alerts": sachet.fetch_alerts_for_region(),
        "quakes": events.fetch_earthquakes(),
        "gdacs": events.fetch_gdacs_events(),
    }


def derive_scenario(signals):
    """Computes the illustrative hazard-scenario multiplier and a "why"
    breakdown from a signals dict (as returned by gather_signals())."""
    rain_24h = open_meteo.total_precipitation_mm(signals["rainfall"].data, hours=24)
    discharge_peak = open_meteo.peak_river_discharge(signals["discharge"].data, days=3)
    slope = open_meteo.max_slope_degrees(signals["elevation"].data)
    n_alerts = len(signals["alerts"].data or [])
    max_mag = events.max_earthquake_magnitude(signals["quakes"].data or {})
    n_gdacs = len((signals["gdacs"].data or {}).get("features", []) or [])

    triggers = {
        "heavy_rain": rain_24h >= RAIN_HEAVY_MM_24H,
        "high_discharge": discharge_peak >= DISCHARGE_HIGH_M3S,
        "steep_slope": slope >= SLOPE_STEEP_DEG,
        "active_alert": (n_alerts > 0) or (n_gdacs > 0),
        "notable_earthquake": max_mag >= EARTHQUAKE_NOTABLE_MAG,
    }

    bump = sum(SIGNAL_WEIGHTS[key] for key, hit in triggers.items() if hit)
    multiplier = max(MIN_MULTIPLIER, min(MAX_MULTIPLIER, DEFAULT_MULTIPLIER + bump))

    reasons = []
    if triggers["heavy_rain"]:
        reasons.append(f"Heavy rain forecast: {rain_24h:.1f}mm in the next 24h (>= {RAIN_HEAVY_MM_24H}mm threshold).")
    if triggers["high_discharge"]:
        reasons.append(
            f"High river discharge forecast: {discharge_peak:.1f} m³/s peak over the next 3 days "
            f"(>= {DISCHARGE_HIGH_M3S} m³/s threshold)."
        )
    if triggers["steep_slope"]:
        reasons.append(f"Steep local terrain: {slope:.1f}° (>= {SLOPE_STEEP_DEG}° threshold).")
    if triggers["active_alert"]:
        sachet_label = "sample SACHET alert(s)" if signals["alerts"].status == "sample" else "official SACHET alert(s)"
        reasons.append(f"{n_alerts} {sachet_label} and {n_gdacs} GDACS event(s) active for the region.")
    if triggers["notable_earthquake"]:
        reasons.append(f"Notable recent earthquake: magnitude {max_mag:.1f} (>= {EARTHQUAKE_NOTABLE_MAG} threshold).")
    if not reasons:
        reasons.append("No live signal crossed its threshold; using the baseline multiplier.")

    return {
        "multiplier": multiplier,
        "triggers": triggers,
        "reasons": reasons,
        "raw_signals": {
            "rain_24h_mm": rain_24h,
            "discharge_peak_m3s": discharge_peak,
            "slope_deg": slope,
            "n_sachet_alerts": n_alerts,
            "n_gdacs_events": n_gdacs,
            "max_earthquake_magnitude": max_mag,
        },
        "data_sources": {name: result.status for name, result in signals.items()},
    }


def effective_multiplier(derived_multiplier, override=None):
    """The sidebar slider (`override`) always wins when set; the derived
    value is only the default shown before the user touches the slider."""
    return derived_multiplier if override is None else override
