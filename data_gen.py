"""Synthetic data generator for the SIH26191 prototype dashboard.

ALL data produced here is ILLUSTRATIVE — a seeded, synthetic stand-in for a
real hazard/habitation survey. Nothing here is a real place, a real incident,
or an official hazard assessment. Regenerating with the same seed always
produces the same numbers, so the demo is reproducible.

The region is a small illustrative hillside area (bounding box below), loosely
shaped like the kind of steep, landslide-prone terrain SIH26191 is about, but
invented for this prototype.
"""

import json
import os
import random
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

import scoring
import vulnerability
from relocation import usable_area_fraction

SEED = 42

GRID_SIZE = 20  # 20x20 cells
CELL_SIZE_DEG = 0.0025  # ~275m per cell at this latitude
ORIGIN_LAT = 30.550  # illustrative hillside region, not a real surveyed site
ORIGIN_LON = 79.560

N_HABITATIONS = 40
N_SAFE_SITES = 3
N_INCIDENTS = 30

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
INCIDENTS_PATH = os.path.join(DATA_DIR, "sample_incidents.json")
# Fixed "sample as-of" time: freshness decay in Sample mode is measured from here, not the clock.
SAMPLE_AS_OF = datetime(2026, 9, 28, 12, 0, 0, tzinfo=timezone.utc)

TRANSCRIPT_POOL = [
    "help me please someone help",
    "I am stuck, the ground is shaking",
    "madad karo please madad karo",
    "bachao mujhe bachao",
    "ghar gir raha hai jaldi aao",
    "bacha lo humein yahan se",
    "mujhe koi rasta nahi mil raha",
    "khatra hai yahan sab log bhaag rahe hain",
    "meherbani karke madad karein",
    "bachao koi hai",
    "",
    "",
    "",
    "testing testing one two",
    "we felt a big tremor just now",
    "landslide near the hill road",
]

YAMNET_LABEL_POOL = [
    "Screaming",
    "Shout",
    "Crying, sobbing",
    "Siren",
    "Shatter",
    "Explosion",
    "Speech",
    "Silence",
    "Rain",
    "Wind",
]

RISK_LEVELS = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
RISK_WEIGHTS = [0.30, 0.40, 0.20, 0.10]
EVENT_TYPES = ["voice_trigger", "sensor_trigger"]
LOCATION_SOURCES = ["gps", "pdr", "last_known"]
LOCATION_SOURCE_WEIGHTS = [0.55, 0.30, 0.15]


def _rng(seed=SEED):
    return np.random.default_rng(seed)


def generate_region_grid(seed=SEED):
    """20x20 illustrative grid: per-cell hazard, slope, vulnerability,
    population density and past-incident count.

    Hazard is built from a few invented "hazard centers" (steep, unstable
    slope patches) so the resulting Red Zones cluster rather than look like
    uniform noise — closer to how a real susceptibility map looks, without
    claiming to model real geology.
    """
    rng = _rng(seed)
    rows, cols = np.meshgrid(np.arange(GRID_SIZE), np.arange(GRID_SIZE), indexing="ij")
    rows = rows.ravel()
    cols = cols.ravel()

    hazard_centers = rng.uniform(2, GRID_SIZE - 2, size=(3, 2))
    hazard = np.zeros(len(rows), dtype=float)
    for cy, cx in hazard_centers:
        dist = np.sqrt((rows - cy) ** 2 + (cols - cx) ** 2)
        hazard += np.exp(-(dist**2) / (2 * (3.5**2)))
    hazard = hazard / hazard.max()
    hazard = np.clip(hazard + rng.normal(0, 0.08, size=len(rows)), 0, 1)

    slope = np.clip(5 + hazard * 30 + rng.normal(0, 5, size=len(rows)), 0, 50)
    vulnerability = np.clip(rng.beta(2, 2, size=len(rows)) * 0.6 + hazard * 0.3, 0, 1)
    pop_density = np.clip(rng.lognormal(mean=3.0, sigma=0.8, size=len(rows)), 1, None)
    past_incidents = rng.poisson(lam=np.clip(hazard * 4, 0.05, None))

    lat = ORIGIN_LAT + (rows + 0.5) * CELL_SIZE_DEG
    lon = ORIGIN_LON + (cols + 0.5) * CELL_SIZE_DEG

    return pd.DataFrame(
        {
            "row": rows,
            "col": cols,
            "cell_id": [f"C{r:02d}-{c:02d}" for r, c in zip(rows, cols)],
            "lat": lat,
            "lon": lon,
            "hazard": hazard,
            "slope_deg": slope,
            "vulnerability": vulnerability,
            "pop_density": pop_density,
            "past_incidents": past_incidents,
        }
    )


def generate_habitations(seed=SEED, grid=None):
    """~40 illustrative habitations (settlements), each tied loosely to the
    hazard/vulnerability of the grid cell they sit in.
    """
    if grid is None:
        grid = generate_region_grid(seed)
    rng = _rng(seed + 1)

    lat_span = GRID_SIZE * CELL_SIZE_DEG
    lon_span = GRID_SIZE * CELL_SIZE_DEG
    lats = ORIGIN_LAT + rng.uniform(0.05, 0.95, size=N_HABITATIONS) * lat_span
    lons = ORIGIN_LON + rng.uniform(0.05, 0.95, size=N_HABITATIONS) * lon_span

    rows = np.clip(((lats - ORIGIN_LAT) / CELL_SIZE_DEG).astype(int), 0, GRID_SIZE - 1)
    cols = np.clip(((lons - ORIGIN_LON) / CELL_SIZE_DEG).astype(int), 0, GRID_SIZE - 1)
    cell_lookup = grid.set_index(["row", "col"])

    population = rng.integers(30, 1800, size=N_HABITATIONS)
    vulnerability = []
    for r, c in zip(rows, cols):
        base = cell_lookup.loc[(int(r), int(c)), "vulnerability"]
        vulnerability.append(float(np.clip(base + rng.normal(0, 0.1), 0, 1)))

    # Illustrative livestock heads (separate RNG so other fields are unchanged).
    livestock = _rng(seed + 4).integers(0, np.maximum(2, (population * 0.6).astype(int)))

    names = [f"Habitation {i + 1:02d}" for i in range(N_HABITATIONS)]
    return pd.DataFrame(
        {
            "habitation_id": [f"H{i + 1:02d}" for i in range(N_HABITATIONS)],
            "name": names,
            "lat": lats,
            "lon": lons,
            "row": rows,
            "col": cols,
            "population": population,
            "livestock": livestock,
            "vulnerability": vulnerability,
        }
    )


def generate_safe_sites(seed=SEED, grid=None):
    """3 candidate relocation sites, deliberately placed in the lowest-hazard
    cells of the grid (a real site selection would weigh many more factors;
    this is illustrative)."""
    if grid is None:
        grid = generate_region_grid(seed)
    rng = _rng(seed + 2)

    candidates = grid.sort_values("hazard").head(30).sample(
        n=N_SAFE_SITES, random_state=seed + 2
    )

    area_ha = rng.uniform(4, 16, size=N_SAFE_SITES)
    slope = np.clip(candidates["slope_deg"].values * rng.uniform(0.2, 0.5, size=N_SAFE_SITES), 1, None)

    # Illustrative water/toilet supply (separate RNG so the fields above are
    # unchanged). Each site is sized so a different resource is the tightest:
    # the "binding" one gets ~0.5x the people the area could hold, the others ~1.6x.
    rng_res = _rng(seed + 3)
    binding = rng_res.permutation(["area", "water", "sanitation"])[:N_SAFE_SITES]
    usable_people = np.array(
        [a * 10_000 * usable_area_fraction(s, h) / 3.5 for a, s, h in zip(area_ha, slope, candidates["hazard"].values)]
    )
    f_water = np.where(binding == "water", 0.5, 1.6)
    f_toilet = np.where(binding == "sanitation", 0.5, 1.6)
    water_l_per_day = np.round(usable_people * 15 * f_water, -2)
    toilets = np.ceil(usable_people / 20 * f_toilet).astype(int)

    return pd.DataFrame(
        {
            "site_id": [f"S{i + 1}" for i in range(N_SAFE_SITES)],
            "name": [f"Candidate Site {i + 1}" for i in range(N_SAFE_SITES)],
            "lat": candidates["lat"].values,
            "lon": candidates["lon"].values,
            "area_ha": area_ha,
            "slope_deg": slope,
            "hazard": candidates["hazard"].values,
            "water_l_per_day": water_l_per_day,
            "toilets": toilets,
        }
    )


def _sample_transcript(rng):
    return rng.choice(TRANSCRIPT_POOL)


def _sample_audio_events(rng):
    n = rng.integers(0, 4)
    if n == 0:
        return []
    labels = rng.choice(YAMNET_LABEL_POOL, size=n, replace=False)
    return [
        {"label": str(lbl), "score": round(float(rng.uniform(0.5, 0.98)), 2)}
        for lbl in labels
    ]


def generate_incidents(seed=SEED, grid=None, habitations=None):
    """~30 illustrative Guardian incidents (mirrors the shape of a real
    `emergency_logs` Firestore document, minus userId/userPhone, which the
    dashboard never touches — see guardian_layer.py)."""
    if grid is None:
        grid = generate_region_grid(seed)
    if habitations is None:
        habitations = generate_habitations(seed, grid)

    py_rng = random.Random(seed + 3)
    rng = np.random.default_rng(seed + 3)

    lat_span = GRID_SIZE * CELL_SIZE_DEG
    lon_span = GRID_SIZE * CELL_SIZE_DEG

    now = SAMPLE_AS_OF
    rows = []
    n_null_fix = 3
    n_zero_fix = 3
    n_valid = N_INCIDENTS - n_null_fix - n_zero_fix

    fix_kinds = (["null"] * n_null_fix) + (["zero"] * n_zero_fix) + (["valid"] * n_valid)
    py_rng.shuffle(fix_kinds)

    # Deliberately corroborate two habitations with 3 tightly-clustered
    # reports each, so the DBSCAN corroboration bonus in guardian_layer.py
    # has clusters to find (a fully random scatter over ~40 habitations
    # rarely produces one on its own), AND so Phase 4b's with/without-
    # Guardian-evidence comparison has at least one real tier flip to show:
    # pick the habitations sitting just *below* the short-term/immediate RPI
    # boundaries (using default weights/thresholds, no evidence bonus), so a
    # modest corroboration bonus can visibly push them into the next tier.
    # Falls back to a hazard-biased random pick if no such habitation exists
    # for a boundary on this seed.
    baseline_scores = [
        scoring.zone_risk_score(r["hazard"], r["vulnerability"], r["past_incidents"])[0]
        for _, r in grid.iterrows()
    ]
    baseline_grid = grid.assign(_zone_score=baseline_scores)
    baseline_lookup = baseline_grid.set_index(["row", "col"])
    baseline_zone_score = [
        baseline_lookup.loc[(int(r), int(c)), "_zone_score"]
        for r, c in zip(habitations["row"], habitations["col"])
    ]
    # The pipeline scores habitations with the vulnerability index, so the
    # baseline must use it too (same default weights) to pick the right ones.
    vi_habitations = vulnerability.apply_index(
        vulnerability.add_components(habitations, seed), vulnerability.DEFAULT_VI_WEIGHTS
    )
    baseline_raw_rpi = [
        scoring.relocation_priority_raw(z, v, p)
        for z, v, p in zip(baseline_zone_score, vi_habitations["vulnerability"], habitations["population"])
    ]
    baseline_rpi = scoring.relocation_priority_index(baseline_raw_rpi)
    scored_habitations = habitations.assign(_baseline_rpi=baseline_rpi)

    below_short = scored_habitations[
        scored_habitations["_baseline_rpi"] < scoring.RPI_SHORT_TERM_THRESHOLD
    ].sort_values("_baseline_rpi", ascending=False)
    below_immediate = scored_habitations[
        (scored_habitations["_baseline_rpi"] >= scoring.RPI_SHORT_TERM_THRESHOLD)
        & (scored_habitations["_baseline_rpi"] < scoring.RPI_IMMEDIATE_THRESHOLD)
    ].sort_values("_baseline_rpi", ascending=False)

    boundary_picks = []
    if not below_short.empty:
        boundary_picks.append(below_short.index[0])
    if not below_immediate.empty:
        boundary_picks.append(below_immediate.index[0])

    if len(boundary_picks) >= 2:
        cluster_indices = boundary_picks[:2]
    else:
        cell_lookup = grid.set_index(["row", "col"])
        hab_hazard = [
            cell_lookup.loc[(int(r), int(c)), "hazard"] for r, c in zip(habitations["row"], habitations["col"])
        ]
        fallback = (
            habitations.assign(_cell_hazard=hab_hazard)
            .sort_values("_cell_hazard", ascending=False)
            .head(12)
            .sample(n=2 - len(boundary_picks), random_state=seed + 3)
            .index.tolist()
        )
        cluster_indices = boundary_picks + fallback
    cluster_habitations = habitations.loc[cluster_indices]
    cluster_plan = (
        [cluster_habitations.index[0]] * 3
        + [cluster_habitations.index[1]] * 3
        + [None] * (n_valid - 6)
    )
    py_rng.shuffle(cluster_plan)
    valid_slot = 0

    for i, kind in enumerate(fix_kinds):
        incident_id = f"INC-{i + 1:04d}"
        occurred_at = now - timedelta(minutes=int(rng.integers(1, 60 * 24 * 5)))

        relayed = bool(rng.uniform() < 0.25)
        delay_minutes = float(rng.uniform(2, 45)) if relayed else 0.0
        arrived_at = occurred_at + timedelta(minutes=delay_minutes)

        if kind == "null":
            lat, lon = None, None
            location_source = "none"
            accuracy_m = None
            accuracy_is_estimate = False
        elif kind == "zero":
            # Illustrates old/buggy client data that wrote 0.0/0.0 instead of
            # null — dashboards must filter this out by coordinate value, not
            # just by locationSource.
            lat, lon = 0.0, 0.0
            location_source = str(rng.choice(LOCATION_SOURCES, p=LOCATION_SOURCE_WEIGHTS))
            accuracy_m = float(rng.uniform(10, 60))
            accuracy_is_estimate = location_source == "pdr"
        else:
            cluster_hab_idx = cluster_plan[valid_slot]
            valid_slot += 1
            if cluster_hab_idx is not None:
                near = habitations.loc[cluster_hab_idx]
                jitter_scale = CELL_SIZE_DEG * 0.05  # ~14m, well within DBSCAN's cluster radius
            else:
                near = habitations.sample(n=1, random_state=int(rng.integers(0, 1_000_000))).iloc[0]
                jitter_scale = CELL_SIZE_DEG * 0.6
            lat = float(near["lat"] + rng.normal(0, jitter_scale))
            lon = float(near["lon"] + rng.normal(0, jitter_scale))
            location_source = str(rng.choice(LOCATION_SOURCES, p=LOCATION_SOURCE_WEIGHTS))
            if location_source == "gps":
                accuracy_m = float(rng.uniform(5, 25))
                accuracy_is_estimate = False
            elif location_source == "pdr":
                accuracy_m = float(15 + rng.uniform(0, 40))
                accuracy_is_estimate = True
            else:  # last_known
                accuracy_m = float(rng.uniform(20, 80))
                accuracy_is_estimate = False

        transcript = _sample_transcript(rng)
        audio_events = _sample_audio_events(rng)
        risk_level = str(rng.choice(RISK_LEVELS, p=RISK_WEIGHTS))
        event_type = "voice_trigger" if transcript else "sensor_trigger"

        if audio_events:
            best = max(audio_events, key=lambda e: e["score"])
            audio_analysis = (
                f"[ILLUSTRATIVE ANALYSIS] Acoustic Event: {best['label']} "
                f"({best['score']:.2f}). Transcript: "
                f"\"{transcript if transcript else 'No speech detected'}\"."
            )
        else:
            audio_analysis = (
                f"[ILLUSTRATIVE ANALYSIS] Transcript: "
                f"\"{transcript if transcript else 'No speech detected'}\"."
            )

        rows.append(
            {
                "incident_id": incident_id,
                "latitude": lat,
                "longitude": lon,
                "locationSource": location_source,
                "accuracyM": accuracy_m,
                "accuracyIsEstimate": accuracy_is_estimate,
                "riskLevel": risk_level,
                "eventType": event_type,
                "transcript": transcript,
                "audioEvents": audio_events,
                "audioAnalysis": audio_analysis,
                "relayedByMesh": relayed,
                "originTimestamp": occurred_at.isoformat(),
                "relayedAt": arrived_at.isoformat() if relayed else None,
                "timestamp": arrived_at.isoformat(),
            }
        )

    return pd.DataFrame(rows)


def write_sample_incidents(path=INCIDENTS_PATH, seed=SEED):
    grid = generate_region_grid(seed)
    habitations = generate_habitations(seed, grid)
    incidents = generate_incidents(seed, grid, habitations)
    records = json.loads(incidents.to_json(orient="records"))
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"as_of": SAMPLE_AS_OF.isoformat(), "incidents": records}, f, indent=2, ensure_ascii=False)
    return path


if __name__ == "__main__":
    out_path = write_sample_incidents()
    print(f"Wrote {N_INCIDENTS} illustrative incidents to {out_path}")
