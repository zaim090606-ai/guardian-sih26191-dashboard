"""Reviewer status per incident cluster (Pending / Confirmed / Dismissed + note),
persisted to dashboard/review_state.json (git-ignored, local to this machine).

Cluster ids from DBSCAN are not stable between runs, so a cluster is keyed by
its centroid grid cell plus its lowest incident id (`cluster_key`). Dismissed
clusters contribute no zone-score bonus (see guardian_layer.cluster_zone_bonuses).
Illustrative: statuses are a reviewer's judgement on sample data, not verified fact.
"""

import json
import os

import pandas as pd

REVIEW_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "review_state.json")
STATUSES = ("Pending", "Confirmed", "Dismissed")
SEVERITY = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def load_review_state(path=None):
    """{cluster_key: {"status": ..., "note": ...}}; {} if missing or unreadable."""
    try:
        with open(path or REVIEW_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_review(cluster_key, status, note="", path=None):
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    state = load_review_state(path)
    state[cluster_key] = {"status": status, "note": note}
    with open(path or REVIEW_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    return state


def dismissed_keys(state):
    return {k for k, v in (state or {}).items() if v.get("status") == "Dismissed"}


def triage_queue(incidents, state=None):
    """One row per real cluster (cluster_id >= 0), sorted by
    confidence x severity, highest first. Confidence = mean ECS of members;
    severity = highest riskLevel among members (LOW 1 .. CRITICAL 4)."""
    cols = ["cluster_key", "cluster_id", "n_reports", "confidence", "severity",
            "triage_score", "status", "note"]
    if incidents.empty or "cluster_key" not in incidents.columns:
        return pd.DataFrame(columns=cols)
    state = state or {}
    rows = []
    for cid, g in incidents[incidents["cluster_id"] >= 0].groupby("cluster_id"):
        key = g["cluster_key"].iloc[0]
        sev = int(g["riskLevel"].map(lambda r: SEVERITY.get(str(r).upper(), 1)).max())
        conf = float(g["ecs"].mean())
        entry = state.get(key, {})
        rows.append({
            "cluster_key": key, "cluster_id": int(cid), "n_reports": int(len(g)),
            "confidence": round(conf, 3), "severity": sev,
            "triage_score": round(conf * sev, 3),
            "status": entry.get("status", "Pending"), "note": entry.get("note", ""),
        })
    out = pd.DataFrame(rows, columns=cols)
    return out.sort_values("triage_score", ascending=False).reset_index(drop=True)
