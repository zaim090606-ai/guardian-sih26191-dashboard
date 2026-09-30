"""Pure computation pipeline (no Streamlit) that turns a set of sidebar-style
parameters into every DataFrame the dashboard needs: scored grid, scored
habitations, safe-site capacities, relocation allocation, and enriched
incidents. Kept separate from app.py so it can be unit-tested directly (see
tests/) without spinning up a Streamlit session.
"""

import numpy as np
import pandas as pd

import buffer
import data_gen
import guardian_layer as gl
import relocation
import review
import route_safety
import scoring
import vulnerability

DEFAULT_PARAMS = dict(
    hazard_scenario_multiplier=1.0,
    zone_weights=dict(scoring.DEFAULT_ZONE_WEIGHTS),
    history_cap=scoring.DEFAULT_HISTORY_CAP,
    red_threshold=scoring.DEFAULT_RED_THRESHOLD,
    amber_threshold=scoring.DEFAULT_AMBER_THRESHOLD,
    space_norm_m2=relocation.DEFAULT_NORMS["area_m2_per_person"],
    water_l_per_person=relocation.DEFAULT_NORMS["water_l_per_person"],
    people_per_toilet=relocation.DEFAULT_NORMS["people_per_toilet"],
    livestock_water_l=relocation.DEFAULT_NORMS["livestock_water_l"],
    livestock_area_m2=relocation.DEFAULT_NORMS["livestock_area_m2"],
    evidence_bonus_cap=scoring.MAX_GUARDIAN_EVIDENCE_BONUS,
    cluster_bonus_per_incident=gl.CLUSTER_BONUS_PER_INCIDENT,
    comms_bonus_cap=gl.COMMS_BONUS_CAP_DEFAULT,
    comms_bonus_per_incident=gl.COMMS_BONUS_PER_INCIDENT_DEFAULT,
    vi_weights=dict(vulnerability.DEFAULT_VI_WEIGHTS),
    buffer_high_m=buffer.DEFAULT_BUFFER_HIGH_M,
    buffer_low_m=buffer.DEFAULT_BUFFER_LOW_M,
    buffer_uplift=buffer.DEFAULT_BUFFER_UPLIFT,
    route_risk_threshold=route_safety.DEFAULT_ROUTE_THRESHOLD,
    mode="sample",
    include_guardian_evidence=True,
    seed=data_gen.SEED,
    review_state=None,  # None -> read dashboard/review_state.json
)


def build_routes(hab, sites, allocation, route_fn):
    """One straight-line route per habitation: to its allocated site, or to its
    nearest site if unallocated. Columns feed the map's route lines and each
    habitation's "why"."""
    assigned = dict(zip(allocation["habitation_id"], allocation["site_id"])) if not allocation.empty else {}
    rows = []
    for _, h in hab.iterrows():
        if h["habitation_id"] in assigned:
            site = sites[sites["site_id"] == assigned[h["habitation_id"]]].iloc[0]
        else:
            d = relocation._haversine_km(h["lat"], h["lon"], sites["lat"].values, sites["lon"].values)
            site = sites.iloc[int(d.argmin())]
        info = route_fn(h, site)
        rows.append({
            "habitation_id": h["habitation_id"], "site_id": site["site_id"],
            "allocated": h["habitation_id"] in assigned,
            "lat1": h["lat"], "lon1": h["lon"], "lat2": site["lat"], "lon2": site["lon"],
            **info,
        })
    return pd.DataFrame(rows)


def run_pipeline(**overrides):
    """Runs the full illustrative scoring pipeline and returns a dict of
    DataFrames/params. `include_guardian_evidence=False` skips the Phase 3
    fusion entirely (used by Phase 4b's with/without comparison)."""
    params = {**DEFAULT_PARAMS, **overrides}
    seed = params["seed"]

    grid = data_gen.generate_region_grid(seed)
    habitations = data_gen.generate_habitations(seed, grid)
    habitations = vulnerability.apply_index(
        vulnerability.add_components(habitations, seed), params["vi_weights"]
    )
    safe_sites = data_gen.generate_safe_sites(seed, grid)

    incidents_raw, source = gl.load_incidents(mode=params["mode"])
    # Sample data (including the live->sample fallback) ages from a fixed as-of
    # time so results are reproducible; real Firestore data uses the real clock.
    as_of = gl.sample_as_of() if source in ("sample", "sample_fallback") else None

    review_state = params["review_state"]
    if review_state is None:
        review_state = review.load_review_state()

    if params["include_guardian_evidence"]:
        grid_evidence, incidents_enriched = gl.build_guardian_overlay(
            grid,
            incidents_raw,
            cluster_bonus_per_incident=params["cluster_bonus_per_incident"],
            cluster_bonus_cap=params["evidence_bonus_cap"],
            comms_bonus_per_incident=params["comms_bonus_per_incident"],
            comms_bonus_cap=params["comms_bonus_cap"],
            now=as_of,
            dismissed_keys=review.dismissed_keys(review_state),
        )
    else:
        grid_evidence = grid.copy()
        grid_evidence["guardian_evidence_bonus"] = 0.0
        grid_evidence["comms_degraded_bonus"] = 0.0
        clean = gl.drop_invalid_fixes(incidents_raw)
        incidents_enriched = gl.compute_incident_ecs(clean, now=as_of)
        incidents_enriched["cluster_id"] = -1
        incidents_enriched["cluster_key"] = ""
        incidents_enriched["comms_degraded"] = False
        incidents_enriched["relay_delay_minutes"] = 0.0

    zone_scores = []
    zone_breakdowns = []
    for _, row in grid_evidence.iterrows():
        score, breakdown = scoring.zone_risk_score(
            row["hazard"],
            row["vulnerability"],
            row["past_incidents"],
            hazard_scenario_multiplier=params["hazard_scenario_multiplier"],
            weights=params["zone_weights"],
            history_cap=params["history_cap"],
            guardian_evidence_bonus=row["guardian_evidence_bonus"],
        )
        zone_scores.append(score)
        zone_breakdowns.append(breakdown)
    grid_evidence["zone_score"] = zone_scores
    grid_evidence["zone_breakdown"] = zone_breakdowns
    grid_evidence["zone_tier"] = grid_evidence["zone_score"].apply(
        lambda s: scoring.zone_tier(s, params["red_threshold"], params["amber_threshold"])
    )

    cell_lookup = grid_evidence.set_index(["row", "col"])
    hab = habitations.copy()
    hab["zone_score_pre_comms"] = [
        cell_lookup.loc[(r, c), "zone_score"] for r, c in zip(hab["row"], hab["col"])
    ]
    hab["comms_degraded_bonus"] = [
        cell_lookup.loc[(r, c), "comms_degraded_bonus"] for r, c in zip(hab["row"], hab["col"])
    ]
    # The comms-degraded bump raises a habitation's effective priority too
    # (not just the map overlay) — it's about how hard response would be,
    # which belongs in relocation priority.
    hab["zone_score"] = np.clip(hab["zone_score_pre_comms"] + hab["comms_degraded_bonus"], 0, 100)

    hab["zone_tier"] = hab["zone_score"].apply(
        lambda s: scoring.zone_tier(s, params["red_threshold"], params["amber_threshold"])
    )
    hab = buffer.apply_buffer_rule(
        hab, grid_evidence, params["buffer_high_m"], params["buffer_low_m"], params["buffer_uplift"]
    )
    raw_rpi = [
        scoring.relocation_priority_raw(z, v, p) * f
        for z, v, p, f in zip(hab["zone_score"], hab["vulnerability"], hab["population"], hab["buffer_factor"])
    ]
    hab["rpi"] = scoring.relocation_priority_index(raw_rpi)
    hab["rpi_tier"] = hab["rpi"].apply(scoring.rpi_tier)
    hab["rpi_breakdown"] = [
        scoring.relocation_priority_breakdown(z, v, p, rpi, tier)
        for z, v, p, rpi, tier in zip(
            hab["zone_score"], hab["vulnerability"], hab["population"], hab["rpi"], hab["rpi_tier"]
        )
    ]

    norms = dict(
        area_m2_per_person=params["space_norm_m2"],
        water_l_per_person=params["water_l_per_person"],
        people_per_toilet=params["people_per_toilet"],
        livestock_water_l=params["livestock_water_l"],
        livestock_area_m2=params["livestock_area_m2"],
    )
    sites_capacity = relocation.compute_multi_resource_capacities(safe_sites, norms)
    route_threshold = params["route_risk_threshold"]
    route_fn = route_safety.make_route_fn(grid_evidence, params["hazard_scenario_multiplier"], route_threshold)
    allocation, sites_after, unallocated = relocation.allocate_multi_resource(
        hab, sites_capacity, norms, priority_col="rpi", route_fn=route_fn, route_threshold=route_threshold
    )
    routes = build_routes(hab, sites_capacity, allocation, route_fn)
    route_cols = routes.set_index("habitation_id")
    for col in ("route_risk", "route_flag", "riskiest_cell", "riskiest_cell_score"):
        hab[col] = hab["habitation_id"].map(route_cols[col])
    # A habitation whose only capacity-feasible sites had unsafe routes is not "safe" on any route.
    if not unallocated.empty:
        blocked = set(unallocated.loc[unallocated["reason"] == "no safe route: field review", "habitation_id"])
        hab.loc[hab["habitation_id"].isin(blocked), "route_flag"] = route_safety.NO_SAFE_ROUTE_FLAG
    # Route facts go into each habitation's "why" (copy: don't mutate shared dicts).
    hab["rpi_breakdown"] = [
        {**bd, "vulnerability_index": vi, "buffer_rule": buffer.buffer_why(h, params["buffer_uplift"]), "route_risk": round(float(rr), 1), "route_flag": rf,
         "riskiest_cell": rc, "riskiest_cell_score": round(float(rs), 1)}
        for bd, vi, h, rr, rf, rc, rs in zip(
            hab["rpi_breakdown"], hab["vi_breakdown"], (r for _, r in hab.iterrows()), hab["route_risk"], hab["route_flag"],
            hab["riskiest_cell"], hab["riskiest_cell_score"]
        )
    ]

    unlocated = gl.score_unlocated(incidents_raw, now=as_of)
    unlocated_stats = gl.unlocated_summary(unlocated)
    located_degraded = int(incidents_enriched["comms_degraded"].sum()) if "comms_degraded" in incidents_enriched else 0

    return dict(
        params=params,
        unlocated=unlocated,
        unlocated_stats=unlocated_stats,
        region_comms_degraded=located_degraded + unlocated_stats["relayed_count"],
        grid=grid_evidence,
        habitations=hab,
        routes=routes,
        safe_sites=sites_capacity,
        sites_after=sites_after,
        allocation=allocation,
        unallocated=unallocated,
        incidents=incidents_enriched,
        review_state=review_state,
        incident_source=source,
        sample_as_of=as_of,
    )


def build_brief_summary(result):
    """Structured-numbers-only summary dict for brief.py."""
    grid = result["grid"]
    hab = result["habitations"]
    sites = result["sites_after"]
    incidents = result["incidents"]
    unallocated = result["unallocated"]

    return {
        "n_red_zones": int((grid["zone_tier"] == "Red").sum()),
        "n_amber_zones": int((grid["zone_tier"] == "Amber").sum()),
        "n_green_zones": int((grid["zone_tier"] == "Green").sum()),
        "hazard_scenario_multiplier": result["params"]["hazard_scenario_multiplier"],
        "n_habitations": int(len(hab)),
        "total_population": int(hab["population"].sum()),
        "immediate_tier_count": int((hab["rpi_tier"] == "immediate").sum()),
        "short_term_tier_count": int((hab["rpi_tier"] == "short-term").sum()),
        "medium_term_tier_count": int((hab["rpi_tier"] == "medium-term").sum()),
        "total_safe_site_capacity": int(sites["capacity_people"].sum()),
        "unallocated_population": int(unallocated["population"].sum()) if not unallocated.empty else 0,
        "n_incidents_considered": int(len(incidents)),
        "n_comms_degraded_incidents": int(incidents["comms_degraded"].sum())
        if "comms_degraded" in incidents
        else 0,
        "incident_source": result["incident_source"],
    }


def compare_with_without_guardian_evidence(**overrides):
    """Phase 4b: runs the pipeline twice — with and without Guardian evidence,
    all other parameters identical — and returns
    (with_result, without_result, tier_changes_df).

    tier_changes_df lists every habitation whose rpi_tier differs between the
    two runs, with both RPI/zone-score values and the "why" breakdown from the
    with-evidence run, so the UI can show exactly what changed and why.
    """
    overrides = dict(overrides)
    overrides.pop("include_guardian_evidence", None)

    with_result = run_pipeline(include_guardian_evidence=True, **overrides)
    without_result = run_pipeline(include_guardian_evidence=False, **overrides)

    hab_with = with_result["habitations"].set_index("habitation_id")
    hab_without = without_result["habitations"].set_index("habitation_id")

    changes = []
    for hid in hab_with.index:
        tier_with = hab_with.loc[hid, "rpi_tier"]
        tier_without = hab_without.loc[hid, "rpi_tier"]
        if tier_with != tier_without:
            changes.append(
                {
                    "habitation_id": hid,
                    "name": hab_with.loc[hid, "name"],
                    "tier_without_evidence": tier_without,
                    "tier_with_evidence": tier_with,
                    "rpi_without_evidence": round(float(hab_without.loc[hid, "rpi"]), 1),
                    "rpi_with_evidence": round(float(hab_with.loc[hid, "rpi"]), 1),
                    "zone_score_without_evidence": round(float(hab_without.loc[hid, "zone_score"]), 1),
                    "zone_score_with_evidence": round(float(hab_with.loc[hid, "zone_score"]), 1),
                    "why": hab_with.loc[hid, "rpi_breakdown"],
                }
            )

    changes_df = pd.DataFrame(changes)
    return with_result, without_result, changes_df
