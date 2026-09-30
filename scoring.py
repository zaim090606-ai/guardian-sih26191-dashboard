"""Three named scores used across the SIH26191 prototype dashboard.

All three are illustrative, adjustable formulas built for a hackathon demo,
not a validated risk model. Every function returns a plain float alongside a
"why" breakdown dict so the UI can show what drove a number.

1. Zone Risk Score       (0-100, per grid cell)   -> zone_risk_score()
2. Evidence Confidence Score (0-1, per incident)   -> evidence_confidence_score()
3. Relocation Priority Index (0-100, per habitation) -> relocation_priority_index()
"""

import numpy as np

# ---------------------------------------------------------------------------
# 1. Zone Risk Score
# ---------------------------------------------------------------------------

DEFAULT_ZONE_WEIGHTS = {"hazard": 0.5, "vulnerability": 0.3, "history": 0.2}
DEFAULT_RED_THRESHOLD = 66
DEFAULT_AMBER_THRESHOLD = 33
DEFAULT_HISTORY_CAP = 6  # past_incidents at/above this count -> history component = 1.0
MAX_GUARDIAN_EVIDENCE_BONUS = 15  # points; caps how much confirmed ground evidence can add


def normalize_history(past_incidents, history_cap=DEFAULT_HISTORY_CAP):
    """Scales a raw past-incident count to 0-1 by an adjustable cap."""
    return float(np.clip(np.asarray(past_incidents, dtype=float) / history_cap, 0, 1))


def zone_risk_score(
    hazard,
    vulnerability,
    past_incidents,
    *,
    hazard_scenario_multiplier=1.0,
    weights=None,
    history_cap=DEFAULT_HISTORY_CAP,
    guardian_evidence_bonus=0.0,
):
    """Zone Risk Score (0-100) for one grid cell.

    score = 100 * (w_hazard * hazard * hazard_scenario_multiplier
                   + w_vulnerability * vulnerability
                   + w_history * normalize_history(past_incidents))
            + capped guardian_evidence_bonus

    - hazard_scenario_multiplier: adjustable slider (e.g. simulating a wetter
      monsoon scenario); multiplies the hazard component only, clipped so the
      component itself never exceeds 1.0 before weighting.
    - guardian_evidence_bonus: raw bonus from corroborated ground evidence
      (see guardian_layer.py); capped here at MAX_GUARDIAN_EVIDENCE_BONUS so a
      cluster of reports can raise a cell's score but not dominate it.
    """
    w = {**DEFAULT_ZONE_WEIGHTS, **(weights or {})}
    hazard_component = float(np.clip(hazard * hazard_scenario_multiplier, 0, 1))
    vulnerability_component = float(np.clip(vulnerability, 0, 1))
    history_component = normalize_history(past_incidents, history_cap)

    base = 100 * (
        w["hazard"] * hazard_component
        + w["vulnerability"] * vulnerability_component
        + w["history"] * history_component
    )
    bonus = float(np.clip(guardian_evidence_bonus, 0, MAX_GUARDIAN_EVIDENCE_BONUS))
    score = float(np.clip(base + bonus, 0, 100))

    breakdown = {
        "hazard_component": hazard_component,
        "hazard_scenario_multiplier": hazard_scenario_multiplier,
        "hazard_weighted_points": 100 * w["hazard"] * hazard_component,
        "vulnerability_component": vulnerability_component,
        "vulnerability_weighted_points": 100 * w["vulnerability"] * vulnerability_component,
        "history_component": history_component,
        "history_weighted_points": 100 * w["history"] * history_component,
        "base_score": base,
        "guardian_evidence_bonus_applied": bonus,
        "guardian_evidence_bonus_cap": MAX_GUARDIAN_EVIDENCE_BONUS,
        "weights": w,
        "final_score": score,
    }
    return score, breakdown


def zone_tier(score, red_threshold=DEFAULT_RED_THRESHOLD, amber_threshold=DEFAULT_AMBER_THRESHOLD):
    """Red / Amber / Green tier for a Zone Risk Score."""
    if score >= red_threshold:
        return "Red"
    if score >= amber_threshold:
        return "Amber"
    return "Green"


# ---------------------------------------------------------------------------
# 2. Evidence Confidence Score
# ---------------------------------------------------------------------------

LOCATION_QUALITY_BASE = {"gps": 1.0, "pdr": 0.6, "last_known": 0.3, "none": 0.0}
MODALITY_BONUS_EACH = 0.08
MODALITY_BONUS_CAP = 0.30
DEFAULT_FRESHNESS_HALFLIFE_HOURS = 24.0
DEFAULT_FRESHNESS_FLOOR = 0.3  # decay never drops evidence weight below this


def _accuracy_scale(accuracy_m):
    """Illustrative accuracy penalty: ~10m -> ~1.0, ~100m+ -> ~0.4, unknown -> 0.6."""
    if accuracy_m is None:
        return 0.6
    return float(np.clip(1.2 - float(accuracy_m) / 120.0, 0.4, 1.0))


def location_quality_component(location_source, accuracy_m):
    base = LOCATION_QUALITY_BASE.get(location_source, 0.0)
    if base == 0.0:
        return 0.0
    return base * _accuracy_scale(accuracy_m)


def freshness_factor(
    age_hours,
    halflife_hours=DEFAULT_FRESHNESS_HALFLIFE_HOURS,
    floor=DEFAULT_FRESHNESS_FLOOR,
):
    decay = 0.5 ** (max(age_hours, 0) / halflife_hours)
    return float(np.clip(decay, floor, 1.0))


def evidence_confidence_score(
    location_source,
    accuracy_m,
    *,
    sensor_trigger=False,
    yamnet_distress_label=False,
    whisper_keyword_hit=False,
    gemini_emergency_flag=False,
    age_hours=0.0,
    halflife_hours=DEFAULT_FRESHNESS_HALFLIFE_HOURS,
):
    """Evidence Confidence Score (0-1) for one incident, combining
    independent signals: location quality, modality support, and freshness.
    """
    location_component = location_quality_component(location_source, accuracy_m)

    modality_hits = {
        "sensor_trigger": sensor_trigger,
        "yamnet_distress_label": yamnet_distress_label,
        "whisper_keyword_hit": whisper_keyword_hit,
        "gemini_emergency_flag": gemini_emergency_flag,
    }
    modality_component = float(
        np.clip(sum(MODALITY_BONUS_EACH for v in modality_hits.values() if v), 0, MODALITY_BONUS_CAP)
    )

    freshness = freshness_factor(age_hours, halflife_hours)
    raw = location_component + modality_component
    score = float(np.clip(raw * freshness, 0, 1))

    breakdown = {
        "location_source": location_source,
        "accuracy_m": accuracy_m,
        "location_component": location_component,
        "modality_hits": modality_hits,
        "modality_component": modality_component,
        "modality_cap": MODALITY_BONUS_CAP,
        "age_hours": age_hours,
        "freshness_factor": freshness,
        "raw_before_freshness": raw,
        "final_score": score,
    }
    return score, breakdown


# ---------------------------------------------------------------------------
# 3. Relocation Priority Index
# ---------------------------------------------------------------------------

RPI_IMMEDIATE_THRESHOLD = 66
RPI_SHORT_TERM_THRESHOLD = 33


def relocation_priority_raw(zone_score, vulnerability, population):
    """zone_score (0-100) x vulnerability (0-1) x population -> unnormalised."""
    return float(zone_score) * float(vulnerability) * float(population)


def relocation_priority_index(raw_values):
    """Normalises a batch of raw RPI values to 0-100 relative to the largest
    value in the cohort (so the most urgent habitation in this run scores 100).
    """
    raw = np.asarray(raw_values, dtype=float)
    if raw.size == 0 or raw.max() <= 0:
        return np.zeros_like(raw)
    return 100.0 * raw / raw.max()


def rpi_tier(
    rpi,
    immediate_threshold=RPI_IMMEDIATE_THRESHOLD,
    short_term_threshold=RPI_SHORT_TERM_THRESHOLD,
):
    if rpi >= immediate_threshold:
        return "immediate"
    if rpi >= short_term_threshold:
        return "short-term"
    return "medium-term"


def relocation_priority_breakdown(zone_score, vulnerability, population, rpi, tier):
    return {
        "zone_score": zone_score,
        "vulnerability": vulnerability,
        "population": population,
        "raw_product": relocation_priority_raw(zone_score, vulnerability, population),
        "rpi": rpi,
        "tier": tier,
        "immediate_threshold": RPI_IMMEDIATE_THRESHOLD,
        "short_term_threshold": RPI_SHORT_TERM_THRESHOLD,
    }
