"""Decision report: a one-page HTML / Markdown export per habitation and per
safe site, built only from the current pipeline result (anonymised fields; no
user ids, phone numbers or free-text transcripts).

A report is {"title", "subtitle", "sections": [(heading, [(label, value), ...])]}.
Everything shown is illustrative sample-scale output, not an official decision.
"""

import html
from datetime import datetime, timezone

import buffer
import guardian_layer

LIMITS = [
    "All data (grid, habitations, sites, livestock, sample incidents) is illustrative; nothing here is a real survey.",
    "Scores and tiers are adjustable formulas that have not been validated against real events.",
    "PDR positions are estimates; relayed payloads are unauthenticated and reach only nearby participating Guardian devices.",
    "The buffer rule is an illustrative rule inspired by public reports, not an official standard.",
    "This report supports a human field review; it is not an evacuation order.",
]

MODE_LABELS = {
    "sample": "Sample data",
    "live": "Live Firestore",
    "sample_fallback": "Sample data (live Firestore read failed)",
}


def _fmt(v):
    if isinstance(v, float):
        return f"{v:.2f}"
    if isinstance(v, dict):
        return ", ".join(f"{k}: {_fmt(x)}" for k, x in v.items())
    return "—" if v is None else str(v)


def _assumptions(params):
    return [
        ("Hazard-scenario multiplier", params["hazard_scenario_multiplier"]),
        ("Zone weights", params["zone_weights"]),
        ("Red / Amber thresholds", f"{params['red_threshold']} / {params['amber_threshold']}"),
        ("Area / water / people per toilet norms",
         f"{params['space_norm_m2']} m2 / {params['water_l_per_person']} L / {params['people_per_toilet']}"),
        ("Route-risk threshold", params["route_risk_threshold"]),
        ("Buffer rule (high / lower risk, max uplift)",
         f"{params['buffer_high_m']:.0f} m / {params['buffer_low_m']:.0f} m / {params['buffer_uplift']}"),
        ("Guardian evidence included", params["include_guardian_evidence"]),
    ]


def _meta(result, now):
    mode = MODE_LABELS.get(result["incident_source"], str(result["incident_source"]))
    return [("Data mode", f"{mode} — hazard grid and habitations are synthetic"),
            ("Generated (UTC)", (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M:%S"))]


def habitation_report(result, habitation_id, now=None):
    hab = result["habitations"]
    h = hab[hab["habitation_id"] == habitation_id].iloc[0]
    grid = result["grid"]
    cell_id = f"C{int(h['row']):02d}-{int(h['col']):02d}"
    cell = grid[grid["cell_id"] == cell_id].iloc[0]
    zb = cell["zone_breakdown"]

    inc = result["incidents"]
    in_cell = inc[[guardian_layer.nearest_cell_id(la, lo) == cell_id for la, lo in zip(inc["latitude"], inc["longitude"])]] if len(inc) else inc
    review_state = result.get("review_state") or {}
    cell_keys = sorted({k for k in (in_cell["cluster_key"] if len(in_cell) else []) if k})
    reviews = [f"{k}: {review_state.get(k, {}).get('status', 'Pending')}" for k in cell_keys]

    alloc = result["allocation"]
    unalloc = result["unallocated"]
    sites = result["sites_after"]
    a = alloc[alloc["habitation_id"] == habitation_id] if len(alloc) else alloc
    if len(a):
        site = sites[sites["site_id"] == a.iloc[0]["site_id"]].iloc[0]
        capacity = [("Allocated site", f"{site['site_id']} ({a.iloc[0]['distance_km']} km)"),
                    ("Capacity limiter at that site", site["limiting_resource"]),
                    ("Site limits (area / water / sanitation)",
                     f"{site['area_limit']} / {site['water_limit']} / {site['sanitation_limit']}"),
                    ("Site remaining capacity", int(site["remaining_capacity"]))]
    else:
        u = unalloc[unalloc["habitation_id"] == habitation_id] if len(unalloc) else unalloc
        capacity = [("Allocation", "unallocated"),
                    ("Reason (capacity limiter)", u.iloc[0]["reason"] if len(u) else "—")]

    bd = h["rpi_breakdown"]
    sections = [
        ("Decision", [("Priority tier", h["rpi_tier"]), ("Relocation Priority Index", round(float(h["rpi"]), 1)),
                      ("Population", int(h["population"])), ("Livestock", int(h["livestock"])),
                      ("Vulnerability", round(float(h["vulnerability"]), 2))]),
        (f"Zone score breakdown (cell {cell_id})", [
            ("Zone tier / score", f"{cell['zone_tier']} / {cell['zone_score']:.1f}"),
            ("Hazard (weighted points)", round(zb["hazard_weighted_points"], 1)),
            ("Vulnerability (weighted points)", round(zb["vulnerability_weighted_points"], 1)),
            ("History (weighted points)", round(zb["history_weighted_points"], 1)),
            ("Guardian evidence bonus applied", round(zb["guardian_evidence_bonus_applied"], 1)),
            ("Comms-degraded bump (added to habitation)", round(float(h["comms_degraded_bonus"]), 1)),
            ("Weights", zb["weights"])]),
        ("Guardian evidence", [
            ("Valid-position reports in this cell", int(len(in_cell))),
            ("Highest evidence confidence", round(float(in_cell["ecs"].max()), 2) if len(in_cell) else "none"),
            ("Cluster review status", "; ".join(reviews) or "no cluster in this cell")]),
        ("Vulnerability index", [(k, v) for k, v in {**bd["vulnerability_index"]["components"]}.items()]
         + [("Weights", bd["vulnerability_index"]["weights"]),
            ("Vulnerability index", bd["vulnerability_index"]["vulnerability_index"]),
            ("Data note", bd["vulnerability_index"]["note"])]),
        ("Route risk", [("Route risk (0-100)", bd["route_risk"]), ("Route flag", bd["route_flag"]),
                        ("Riskiest cell on route", f"{bd['riskiest_cell']} ({bd['riskiest_cell_score']})")]),
        ("Capacity limiter", capacity),
        ("Buffer rule", [(k, v) for k, v in bd["buffer_rule"].items()]),
        ("Assumptions", _assumptions(result["params"])),
        ("Data and time", _meta(result, now)),
        ("Limits", [(f"{i + 1}", t) for i, t in enumerate(LIMITS)]),
    ]
    return {"title": f"Decision report: {h['name']} ({habitation_id})",
            "subtitle": "Illustrative decision support, not an official order", "sections": sections}


def site_report(result, site_id, now=None):
    sites = result["sites_after"]
    s = sites[sites["site_id"] == site_id].iloc[0]
    alloc = result["allocation"]
    a = alloc[alloc["site_id"] == site_id] if len(alloc) else alloc
    hab = result["habitations"].set_index("habitation_id")
    tiers = [f"{r['habitation_id']} ({hab.loc[r['habitation_id'], 'rpi_tier']}, {int(r['population'])} people)"
             for _, r in a.iterrows()]
    routes = result["routes"]
    rr = routes[(routes["site_id"] == site_id) & routes["allocated"]]
    sections = [
        ("Decision", [("Site", f"{s['name']} ({site_id})"), ("Capacity (people)", int(s["capacity_people"])),
                      ("Allocated people", int(s["allocated_people"])),
                      ("Remaining capacity", int(s["remaining_capacity"])),
                      ("Habitations allocated", "; ".join(tiers) or "none")]),
        ("Capacity limiter", [("Limiting resource", s["limiting_resource"]),
                              ("Area limit", int(s["area_limit"])), ("Water limit", int(s["water_limit"])),
                              ("Sanitation limit", int(s["sanitation_limit"])),
                              ("Usable area (m2)", round(float(s["usable_area_m2"]))),
                              ("Site water (L/day) / toilets", f"{s['water_l_per_day']:.0f} / {int(s['toilets'])}")]),
        ("Site conditions", [("Hazard (0-1)", round(float(s["hazard"]), 2)),
                             ("Slope (deg)", round(float(s["slope_deg"]), 1)), ("Area (ha)", round(float(s["area_ha"]), 2))]),
        ("Route risk (allocated routes)", [
            ("Routes into this site", int(len(rr))),
            ("Highest route risk", round(float(rr["route_risk"].max()), 1) if len(rr) else "n/a"),
            ("Unsafe route flags", int((rr["route_flag"] != "safe").sum()) if len(rr) else 0)]),
        ("Buffer rule", [("Rule", buffer.RULE_LABEL),
                         ("Applies to", "habitation priority, not to site selection")]),
        ("Assumptions", _assumptions(result["params"])),
        ("Data and time", _meta(result, now)),
        ("Limits", [(f"{i + 1}", t) for i, t in enumerate(LIMITS)]),
    ]
    return {"title": f"Decision report: {s['name']} ({site_id})",
            "subtitle": "Illustrative decision support, not an official order", "sections": sections}


def to_markdown(report):
    out = [f"# {report['title']}", f"_{report['subtitle']}_", ""]
    for heading, rows in report["sections"]:
        out += [f"## {heading}", ""]
        out += [f"- **{label}:** {_fmt(value)}" for label, value in rows]
        out.append("")
    return "\n".join(out)


def to_html(report):
    e = html.escape
    parts = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        f"<title>{e(report['title'])}</title>",
        "<style>body{font-family:system-ui,sans-serif;max-width:46rem;margin:2rem auto;padding:0 1rem;color:#1a1a1a}"
        "h1{font-size:1.4rem}h2{font-size:1.05rem;margin-top:1.4rem;border-bottom:1px solid #ccc}"
        "td{padding:.2rem .6rem .2rem 0;vertical-align:top}td:first-child{font-weight:600;white-space:nowrap}"
        ".note{color:#555;font-style:italic}</style></head><body>",
        f"<h1>{e(report['title'])}</h1><p class='note'>{e(report['subtitle'])}</p>",
    ]
    for heading, rows in report["sections"]:
        parts.append(f"<h2>{e(heading)}</h2><table>")
        parts += [f"<tr><td>{e(str(label))}</td><td>{e(_fmt(value))}</td></tr>" for label, value in rows]
        parts.append("</table>")
    parts.append("</body></html>")
    return "".join(parts)
