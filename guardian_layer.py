"""Guardian evidence fusion: turns raw Guardian incidents into (a) a per-
incident Evidence Confidence Score, (b) a small, capped zone-score bonus for
cells with corroborated incident clusters, and (c) a "comms-degraded" overlay
for cells reached mainly through mesh relay or long delivery delays.

Caption for the comms-degraded layer: "Where the network fails, response is
hardest." — this is the core framing of the whole prototype: Red Zones are
planned from above, distress is confirmed from the ground, and the places
where the network itself fails are flagged because that is where response is
hardest.

Never touches userId/userPhone: those fields are dropped immediately after
loading, whether from the sample file or from Firestore, and are never passed
to Gemini or shown in the UI. Incident IDs are already short and anonymised
(the sample generator's `INC-####` or the raw Firestore document ID).
"""

import json
import os

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

import data_gen
import scoring

DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SAMPLE_PATH = os.path.join(DASHBOARD_DIR, "sample_incidents.json")

EARTH_RADIUS_KM = 6371.0

# YAMNet labels treated as acoustically distress-relevant. Mirrors the
# taxonomy the Flutter app uses (lib/services/yamnet_service.dart
# `_distressLabels`) so the dashboard's independent scoring reasons about the
# same categories — this file does not read or alter that Dart code.
DISTRESS_LABELS = {
    "Screaming",
    "Shout",
    "Yell",
    "Crying, sobbing",
    "Shatter",
    "Siren",
    "Explosion",
    "Groan",
    "Gunshot, gunfire",
}

# Small, editable distress-keyword list for the offline Whisper transcript.
# Mixes English with romanized Hindi/Urdu (how a small/"tiny" Whisper model
# commonly transliterates speech) and native-script forms, in case a future
# model outputs script directly. Not exhaustive — edit freely for a demo.
DISTRESS_KEYWORDS = [
    "help",
    "help me",
    "save me",
    "please help",
    "emergency",
    "bachao",
    "bachao mujhe",
    "madad",
    "madad karo",
    "bacha lo",
    "bacha do",
    "khatra",
    "meherbani",
    "बचाओ",
    "मदद",
    "بچاؤ",
    "مدد",
]

# Keywords used to decide whether a Gemini/offline audioAnalysis report is
# flagging an emergency. Editable; matches the illustrative report text this
# prototype's data_gen.py produces and the real app's ai_service.dart format.
GEMINI_FLAG_KEYWORDS = ["distress", "emergency", "threat", "danger", "critical"]

CLUSTER_BONUS_PER_INCIDENT = 4.0
CLUSTER_BONUS_CAP = scoring.MAX_GUARDIAN_EVIDENCE_BONUS  # shared cap with scoring.py
CLUSTER_EPS_KM_DEFAULT = 0.15
CLUSTER_MIN_SAMPLES_DEFAULT = 2

COMMS_DELAY_THRESHOLD_MINUTES_DEFAULT = 10.0
COMMS_BONUS_PER_INCIDENT_DEFAULT = 2.0
COMMS_BONUS_CAP_DEFAULT = 5.0
COMMS_DEGRADED_CAPTION = "Where the network fails, response is hardest."

_SENSITIVE_FIELDS = ("userId", "userPhone")


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _find_firebaserc(start_dir):
    d = start_dir
    for _ in range(6):
        candidate = os.path.join(d, ".firebaserc")
        if os.path.exists(candidate):
            return candidate
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def get_firebase_project_id():
    """Reads the Firebase project id from .firebaserc, searching upward from
    this file (the prototype lives in <repo>/dashboard/)."""
    path = _find_firebaserc(DASHBOARD_DIR)
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as f:
            config = json.load(f)
        return config.get("projects", {}).get("default")
    except Exception:
        return None


def _firestore_value(field):
    if field is None:
        return None
    if "nullValue" in field:
        return None
    if "stringValue" in field:
        return field["stringValue"]
    if "integerValue" in field:
        return int(field["integerValue"])
    if "doubleValue" in field:
        return float(field["doubleValue"])
    if "booleanValue" in field:
        return field["booleanValue"]
    if "timestampValue" in field:
        return field["timestampValue"]
    if "arrayValue" in field:
        return [_firestore_value(v) for v in field["arrayValue"].get("values", [])]
    if "mapValue" in field:
        return {k: _firestore_value(v) for k, v in field["mapValue"].get("fields", {}).items()}
    return None


def _parse_firestore_doc(doc):
    fields = doc.get("fields", {})
    row = {k: _firestore_value(v) for k, v in fields.items()}
    row["incident_id"] = doc["name"].split("/")[-1]
    return row


def load_incidents_from_firestore(project_id, collection="emergency_logs", page_size=200, timeout_s=8):
    """Reads emergency_logs via the Firestore REST API (no SDK/auth needed
    while the prototype's rules are open). Raises on any HTTP/network error —
    callers should catch and fall back to sample data."""
    import requests

    url = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents/{collection}"
    resp = requests.get(url, params={"pageSize": page_size}, timeout=timeout_s)
    resp.raise_for_status()
    documents = resp.json().get("documents", [])
    rows = [_parse_firestore_doc(d) for d in documents]
    return pd.DataFrame(rows)


def _strip_sensitive_fields(df):
    cols_to_drop = [c for c in _SENSITIVE_FIELDS if c in df.columns]
    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)
    return df


def load_sample_incidents(path=None):
    path = path or DEFAULT_SAMPLE_PATH
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    records = data["incidents"] if isinstance(data, dict) else data  # older files were a bare list
    return _strip_sensitive_fields(pd.DataFrame(records))


def sample_as_of(path=None):
    """The fixed 'sample as-of' time stored in the sample file (tz-aware UTC
    Timestamp). Sample-mode freshness decay is measured from here so results do
    not change with the calendar. Falls back to the newest report timestamp for
    files without the field."""
    path = path or DEFAULT_SAMPLE_PATH
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and data.get("as_of"):
        return pd.Timestamp(data["as_of"]).tz_convert("UTC") if pd.Timestamp(data["as_of"]).tzinfo else pd.Timestamp(data["as_of"], tz="UTC")
    records = data["incidents"] if isinstance(data, dict) else data
    stamps = pd.to_datetime([r.get("timestamp") for r in records if r.get("timestamp")], utc=True)
    return stamps.max() if len(stamps) else pd.Timestamp("2026-01-01", tz="UTC")


def load_incidents(mode="sample", sample_path=None):
    """mode='sample' (default) reads sample_incidents.json. mode='live' tries
    Firestore first and falls back to sample data on any error (missing
    project id, network error, empty collection). Returns (DataFrame, source)
    where source is one of 'sample', 'live', 'sample_fallback'.
    """
    if mode == "live":
        try:
            project_id = get_firebase_project_id()
            if not project_id:
                raise RuntimeError("No Firebase project id found in .firebaserc")
            df = load_incidents_from_firestore(project_id)
            if df.empty:
                raise RuntimeError("Firestore emergency_logs returned no documents")
            return _strip_sensitive_fields(df), "live"
        except Exception:
            return load_sample_incidents(sample_path), "sample_fallback"
    return load_sample_incidents(sample_path), "sample"


def drop_invalid_fixes(df):
    """Drops rows with a null or (0.0, 0.0) position — see data_gen.py and
    Phase 1 of BUILD_LOG.md for why both cases occur in real data."""
    if df.empty:
        return df.copy()
    lat = pd.to_numeric(df["latitude"], errors="coerce")
    lon = pd.to_numeric(df["longitude"], errors="coerce")
    valid = lat.notna() & lon.notna() & ~((lat == 0.0) & (lon == 0.0))
    out = df[valid].copy()
    out["latitude"] = lat[valid]
    out["longitude"] = lon[valid]
    return out


UNLOCATED_REASON_NULL = "no position reported (null)"
UNLOCATED_REASON_ZERO = "placeholder 0,0 fix"


def split_unlocated(df):
    """Returns the rows drop_invalid_fixes() removes, with a `unlocated_reason`
    column and a `completeness` label of "partial". Scored (ECS) and comms-flagged
    like any other report, but never clustered or attached to a grid cell."""
    if df.empty:
        out = df.copy()
        out["unlocated_reason"] = []
        out["completeness"] = []
        return out
    lat = pd.to_numeric(df["latitude"], errors="coerce")
    lon = pd.to_numeric(df["longitude"], errors="coerce")
    missing = lat.isna() | lon.isna()
    zero = ~missing & (lat == 0.0) & (lon == 0.0)
    out = df[missing | zero].copy()
    out["unlocated_reason"] = np.where(missing[missing | zero], UNLOCATED_REASON_NULL, UNLOCATED_REASON_ZERO)
    out["completeness"] = "partial"
    return out


def score_unlocated(df, delay_threshold_minutes=COMMS_DELAY_THRESHOLD_MINUTES_DEFAULT, now=None):
    """Partial (unlocated) incidents with ECS + comms-degraded flag."""
    part = split_unlocated(df)
    part = compute_incident_ecs(part, now=now)
    return flag_comms_degraded(part, delay_threshold_minutes=delay_threshold_minutes)


def unlocated_summary(scored_partial):
    """Counts + reasons only — no personal data."""
    if scored_partial.empty:
        return {"count": 0, "relayed_count": 0, "reasons": {}}
    return {
        "count": int(len(scored_partial)),
        "relayed_count": int(scored_partial["comms_degraded"].sum()),
        "reasons": {k: int(v) for k, v in scored_partial["unlocated_reason"].value_counts().items()},
    }


# ---------------------------------------------------------------------------
# Evidence Confidence Score per incident
# ---------------------------------------------------------------------------


def _age_hours(timestamp_value, now):
    try:
        ts = pd.Timestamp(timestamp_value)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        else:
            ts = ts.tz_convert("UTC")
        return max((now - ts).total_seconds() / 3600.0, 0.0)
    except Exception:
        return 0.0


def compute_incident_ecs(df, now=None, halflife_hours=scoring.DEFAULT_FRESHNESS_HALFLIFE_HOURS):
    """Adds `ecs` (float) and `ecs_breakdown` (dict) columns."""
    if df.empty:
        out = df.copy()
        out["ecs"] = []
        out["ecs_breakdown"] = []
        return out

    if now is None:
        now = pd.Timestamp.now(tz="UTC")
    else:
        now = pd.Timestamp(now)
        now = now.tz_localize("UTC") if now.tzinfo is None else now.tz_convert("UTC")

    ecs_values = []
    breakdowns = []
    for _, row in df.iterrows():
        sensor_trigger = row.get("eventType") == "sensor_trigger"

        events = row.get("audioEvents") or []
        yamnet_hit = any(
            isinstance(e, dict) and e.get("label") in DISTRESS_LABELS for e in events
        )

        transcript = str(row.get("transcript") or "").lower()
        whisper_hit = any(kw.lower() in transcript for kw in DISTRESS_KEYWORDS)

        analysis_text = str(row.get("audioAnalysis") or "").lower()
        gemini_hit = any(kw in analysis_text for kw in GEMINI_FLAG_KEYWORDS)

        age_hours = _age_hours(row.get("timestamp"), now)

        score, breakdown = scoring.evidence_confidence_score(
            row.get("locationSource"),
            row.get("accuracyM"),
            sensor_trigger=sensor_trigger,
            yamnet_distress_label=yamnet_hit,
            whisper_keyword_hit=whisper_hit,
            gemini_emergency_flag=gemini_hit,
            age_hours=age_hours,
            halflife_hours=halflife_hours,
        )
        ecs_values.append(score)
        breakdowns.append(breakdown)

    out = df.copy()
    out["ecs"] = ecs_values
    out["ecs_breakdown"] = breakdowns
    return out


# ---------------------------------------------------------------------------
# Clustering & cell mapping
# ---------------------------------------------------------------------------


def nearest_cell_id(lat, lon):
    row = int(np.clip((lat - data_gen.ORIGIN_LAT) / data_gen.CELL_SIZE_DEG, 0, data_gen.GRID_SIZE - 1))
    col = int(np.clip((lon - data_gen.ORIGIN_LON) / data_gen.CELL_SIZE_DEG, 0, data_gen.GRID_SIZE - 1))
    return f"C{row:02d}-{col:02d}"


def cluster_incidents(df, eps_km=CLUSTER_EPS_KM_DEFAULT, min_samples=CLUSTER_MIN_SAMPLES_DEFAULT):
    """DBSCAN over incident coordinates (haversine metric). cluster_id == -1
    means "no cluster" (an isolated report, or too few nearby reports)."""
    out = df.copy()
    if out.empty:
        out["cluster_id"] = pd.Series(dtype=int)
        return out

    coords = np.radians(out[["latitude", "longitude"]].to_numpy(dtype=float))
    eps_rad = eps_km / EARTH_RADIUS_KM
    labels = DBSCAN(eps=eps_rad, min_samples=min_samples, metric="haversine").fit_predict(coords)
    out["cluster_id"] = labels
    return out


def add_cluster_keys(df):
    """Adds a run-stable `cluster_key` (centroid cell + lowest incident id);
    "" for unclustered rows. Used to persist reviewer status (review.py)."""
    out = df.copy()
    out["cluster_key"] = ""
    if out.empty or "cluster_id" not in out.columns:
        return out
    for cid, g in out[out["cluster_id"] >= 0].groupby("cluster_id"):
        cell = nearest_cell_id(float(g["latitude"].mean()), float(g["longitude"].mean()))
        out.loc[g.index, "cluster_key"] = f"{cell}|{min(g['incident_id'].astype(str))}"
    return out


def cluster_zone_bonuses(
    clustered_df,
    bonus_per_incident=CLUSTER_BONUS_PER_INCIDENT,
    bonus_cap=CLUSTER_BONUS_CAP,
    dismissed_keys=None,
):
    """Corroboration bonus per grid cell: clusters of >=2 distinct incidents
    raise their cell's Zone Risk Score, capped at `bonus_cap` (shared default
    with scoring.MAX_GUARDIAN_EVIDENCE_BONUS so the two stay consistent
    unless the UI deliberately overrides one)."""
    bonuses = {}
    if clustered_df.empty or "cluster_id" not in clustered_df.columns:
        return bonuses

    for cluster_id, group in clustered_df.groupby("cluster_id"):
        if cluster_id == -1:
            continue
        n_distinct = group["incident_id"].nunique() if "incident_id" in group else len(group)
        if n_distinct < 2:
            continue
        if dismissed_keys and "cluster_key" in group and group["cluster_key"].iloc[0] in dismissed_keys:
            continue  # reviewer dismissed this cluster: no score bonus
        raw_bonus = float(group["ecs"].sum()) * bonus_per_incident
        bonus = float(np.clip(raw_bonus, 0, bonus_cap))

        centroid_lat = float(group["latitude"].mean())
        centroid_lon = float(group["longitude"].mean())
        cell_id = nearest_cell_id(centroid_lat, centroid_lon)
        bonuses[cell_id] = max(bonuses.get(cell_id, 0.0), bonus)

    return bonuses


# ---------------------------------------------------------------------------
# Comms-degraded overlay
# ---------------------------------------------------------------------------


def flag_comms_degraded(df, delay_threshold_minutes=COMMS_DELAY_THRESHOLD_MINUTES_DEFAULT):
    """Adds `relay_delay_minutes` and `comms_degraded` columns. An incident is
    comms-degraded if it arrived via mesh relay at all, or if its delivery
    delay (relayedAt - originTimestamp) exceeds the threshold."""
    out = df.copy()
    if out.empty:
        out["relay_delay_minutes"] = []
        out["comms_degraded"] = []
        return out

    delays = []
    for _, row in out.iterrows():
        relayed_at = row.get("relayedAt")
        origin_at = row.get("originTimestamp")
        if relayed_at and origin_at:
            try:
                delay = (pd.Timestamp(relayed_at) - pd.Timestamp(origin_at)).total_seconds() / 60.0
            except Exception:
                delay = 0.0
        else:
            delay = 0.0
        delays.append(max(delay, 0.0))

    out["relay_delay_minutes"] = delays
    relayed = out.get("relayedByMesh", False).fillna(False) if "relayedByMesh" in out else False
    out["comms_degraded"] = (relayed == True) | (out["relay_delay_minutes"] > delay_threshold_minutes)  # noqa: E712
    return out


def comms_degraded_cell_bonuses(
    flagged_df,
    bonus_per_incident=COMMS_BONUS_PER_INCIDENT_DEFAULT,
    bonus_cap=COMMS_BONUS_CAP_DEFAULT,
):
    """Small, capped priority bump per cell for comms-degraded incidents —
    kept as a separate, smaller cap from the evidence-corroboration bonus
    since it's about response difficulty, not confirmation strength."""
    bonuses = {}
    if flagged_df.empty or "comms_degraded" not in flagged_df.columns:
        return bonuses

    degraded = flagged_df[flagged_df["comms_degraded"] == True]  # noqa: E712
    for _, row in degraded.iterrows():
        cell_id = nearest_cell_id(row["latitude"], row["longitude"])
        bonuses[cell_id] = float(np.clip(bonuses.get(cell_id, 0.0) + bonus_per_incident, 0, bonus_cap))

    return bonuses


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def build_guardian_overlay(
    grid_df,
    incidents_df,
    *,
    cluster_eps_km=CLUSTER_EPS_KM_DEFAULT,
    cluster_min_samples=CLUSTER_MIN_SAMPLES_DEFAULT,
    cluster_bonus_per_incident=CLUSTER_BONUS_PER_INCIDENT,
    cluster_bonus_cap=CLUSTER_BONUS_CAP,
    comms_delay_threshold_minutes=COMMS_DELAY_THRESHOLD_MINUTES_DEFAULT,
    comms_bonus_per_incident=COMMS_BONUS_PER_INCIDENT_DEFAULT,
    comms_bonus_cap=COMMS_BONUS_CAP_DEFAULT,
    now=None,
    dismissed_keys=None,
):
    """Full Phase 3 pipeline: filter -> ECS -> cluster -> bonuses.

    Returns (grid_with_bonuses, incidents_with_ecs_and_clusters).
    `grid_with_bonuses` gets two new columns: `guardian_evidence_bonus`
    (feed into scoring.zone_risk_score's `guardian_evidence_bonus` arg) and
    `comms_degraded_bonus` (a separate, smaller capped bump — see
    COMMS_DEGRADED_CAPTION).
    """
    clean = drop_invalid_fixes(incidents_df)
    with_ecs = compute_incident_ecs(clean, now=now)
    clustered = cluster_incidents(with_ecs, eps_km=cluster_eps_km, min_samples=cluster_min_samples)
    flagged = flag_comms_degraded(clustered, delay_threshold_minutes=comms_delay_threshold_minutes)
    flagged = add_cluster_keys(flagged)

    evidence_bonus = cluster_zone_bonuses(
        flagged, bonus_per_incident=cluster_bonus_per_incident, bonus_cap=cluster_bonus_cap,
        dismissed_keys=dismissed_keys,
    )
    comms_bonus = comms_degraded_cell_bonuses(
        flagged, bonus_per_incident=comms_bonus_per_incident, bonus_cap=comms_bonus_cap
    )

    grid = grid_df.copy()
    grid["guardian_evidence_bonus"] = grid["cell_id"].map(evidence_bonus).fillna(0.0)
    grid["comms_degraded_bonus"] = grid["cell_id"].map(comms_bonus).fillna(0.0)

    return grid, flagged
