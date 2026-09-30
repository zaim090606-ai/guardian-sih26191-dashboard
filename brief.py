"""Gemini-generated brief for a state disaster management authority.

The brief is built ONLY from computed numbers (a summary dict of scores/
counts) passed to Gemini as JSON — never from raw incident text, transcripts,
or any per-person field. Cluster summaries, if included, are one-line
sentences built from structured evidence fields (counts, average confidence,
tier) only, never quoted transcript/audio text.

Reads GEMINI_API_KEY from the environment (never hardcoded — see
BUILD_LOG.md's NEEDS-HUMAN note about the key found hardcoded in the Flutter
app, which this file does not reuse). Reuses the same model name already
used elsewhere in this repo (lib/services/ai_service.dart: 'gemini-1.5-flash').
With no key, or on any API error, falls back to a plain template brief built
from the same summary dict, so the demo never breaks for lack of a key or
network access.
"""

import json
import os
from datetime import datetime, timezone

MODEL_NAME = "gemini-1.5-flash"  # matches lib/services/ai_service.dart


def summarize_clusters(clustered_incidents_df):
    """One-line-ready cluster summaries from structured fields only (no
    transcript/audio text). Returns a list of dicts; `to_sentence()` turns
    one into the actual one-line string."""
    if clustered_incidents_df.empty or "cluster_id" not in clustered_incidents_df.columns:
        return []

    summaries = []
    for cluster_id, group in clustered_incidents_df.groupby("cluster_id"):
        if cluster_id == -1:
            continue
        n_distinct = group["incident_id"].nunique() if "incident_id" in group else len(group)
        if n_distinct < 2:
            continue
        summaries.append(
            {
                "cluster_id": int(cluster_id),
                "n_incidents": int(n_distinct),
                "avg_ecs": round(float(group["ecs"].mean()), 2),
                "any_comms_degraded": bool(group.get("comms_degraded", False).any())
                if "comms_degraded" in group
                else False,
                "centroid_lat": round(float(group["latitude"].mean()), 5),
                "centroid_lon": round(float(group["longitude"].mean()), 5),
            }
        )
    return summaries


def _cluster_sentence(c):
    degraded = " (reached via mesh relay/delayed delivery)" if c["any_comms_degraded"] else ""
    return (
        f"Cluster {c['cluster_id']}: {c['n_incidents']} corroborating reports near "
        f"({c['centroid_lat']}, {c['centroid_lon']}), average evidence confidence "
        f"{c['avg_ecs']:.2f}{degraded}."
    )


def _template_brief(summary, cluster_summaries):
    lines = [
        "STATE DISASTER MANAGEMENT AUTHORITY BRIEFING (TEMPLATE — Gemini unavailable)",
        f"Generated: {summary.get('generated_at', datetime.now(timezone.utc).isoformat())}",
        "All figures below are illustrative, computed from synthetic/sample data.",
        "",
        f"Zones assessed: {summary.get('n_red_zones', 0)} Red, "
        f"{summary.get('n_amber_zones', 0)} Amber, {summary.get('n_green_zones', 0)} Green "
        f"(hazard-scenario multiplier: {summary.get('hazard_scenario_multiplier', 1.0)}x).",
        f"Habitations assessed: {summary.get('n_habitations', 0)} "
        f"(total population {summary.get('total_population', 0)}).",
        f"Relocation priority: {summary.get('immediate_tier_count', 0)} immediate, "
        f"{summary.get('short_term_tier_count', 0)} short-term, "
        f"{summary.get('medium_term_tier_count', 0)} medium-term.",
        f"Candidate safe-site capacity: {summary.get('total_safe_site_capacity', 0)} people; "
        f"{summary.get('unallocated_population', 0)} people currently unallocated to any site.",
        f"Guardian ground evidence: {summary.get('n_incidents_considered', 0)} incidents considered, "
        f"{summary.get('n_comms_degraded_incidents', 0)} reached only via mesh relay or with a long delay.",
    ]
    if cluster_summaries:
        lines.append("")
        lines.append("Corroborated incident clusters:")
        lines.extend(f"- {_cluster_sentence(c)}" for c in cluster_summaries)
    lines.append("")
    lines.append(
        "This is a hackathon prototype brief on illustrative data — not a real-time "
        "national hazard map or a guaranteed-delivery system."
    )
    return "\n".join(lines)


def _build_prompt(summary, cluster_summaries):
    cluster_lines = "\n".join(_cluster_sentence(c) for c in (cluster_summaries or []))
    return f"""You are drafting a short briefing for a State Disaster Management Authority.
Use ONLY the computed figures below (illustrative/sample data from a hazard-mapping
prototype). Do not invent any numbers not present here. Keep it factual, concise
(150-200 words), and clearly label it as based on illustrative/sample data, not a
real-time national assessment.

COMPUTED SUMMARY (JSON):
{json.dumps(summary, indent=2, default=str)}

CORROBORATED INCIDENT CLUSTERS (one line each, may be empty):
{cluster_lines if cluster_lines else "(none)"}

Write the briefing now."""


def generate_brief(summary, cluster_summaries=None, api_key=None):
    """summary: dict of computed numbers (zone tier counts, RPI tier counts,
    capacities, etc — see app.py's `build_brief_summary()`). cluster_summaries:
    optional list from `summarize_clusters()`. Returns the brief text; never
    raises.
    """
    summary = dict(summary)
    summary.setdefault("generated_at", datetime.now(timezone.utc).isoformat())

    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        return _template_brief(summary, cluster_summaries)

    try:
        from google import genai

        client = genai.Client(api_key=key)
        prompt = _build_prompt(summary, cluster_summaries)
        response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        text = getattr(response, "text", None)
        if text and text.strip():
            return text.strip()
        return _template_brief(summary, cluster_summaries)
    except Exception:
        return _template_brief(summary, cluster_summaries)
