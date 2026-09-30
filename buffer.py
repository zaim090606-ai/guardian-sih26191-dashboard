"""Buffer rule: how close a habitation sits to a Red zone, folded into its
relocation priority.

ILLUSTRATIVE RULE inspired by buffer distances mentioned in public reports; it
is NOT an official standard. Defaults: 50 m for habitations in a high-risk
(Red/Amber) cell, 30 m for lower-risk (Green) cells. A habitation inside the
buffer (or inside a Red cell) gets a priority uplift that fades linearly to
zero at the buffer edge.

Grid cell-size assumption: cells are CELL_SIZE_DEG = 0.0025 deg, i.e. about
278 m north-south and about 240 m east-west at this latitude. Distance is
measured from the habitation point to the nearest edge of the nearest Red
cell. Because the grid is far coarser than a 30-50 m buffer, the distance is
only indicative (roughly one cell of resolution).
"""

import numpy as np
import pandas as pd

import data_gen

DEFAULT_BUFFER_HIGH_M = 50.0
DEFAULT_BUFFER_LOW_M = 30.0
DEFAULT_BUFFER_UPLIFT = 0.25  # max +25% on raw priority, at distance 0
HIGH_RISK_TIERS = ("Red", "Amber")
M_PER_DEG = 111_320.0
RULE_LABEL = "Illustrative buffer rule inspired by public reports; not an official standard."


def distance_to_red_m(lat, lon, grid):
    """Metres from a point to the nearest Red cell's rectangle (0 inside one);
    None if the grid has no Red cell."""
    red = grid[grid["zone_tier"] == "Red"]
    if red.empty:
        return None
    half = data_gen.CELL_SIZE_DEG / 2.0
    lat_gap = np.maximum(np.abs(red["lat"].values - lat) - half, 0.0) * M_PER_DEG
    lon_gap = np.maximum(np.abs(red["lon"].values - lon) - half, 0.0) * M_PER_DEG * np.cos(np.radians(lat))
    return float(np.sqrt(lat_gap**2 + lon_gap**2).min())


def buffer_for_tier(zone_tier, high_m=DEFAULT_BUFFER_HIGH_M, low_m=DEFAULT_BUFFER_LOW_M):
    return high_m if zone_tier in HIGH_RISK_TIERS else low_m


def buffer_factor(distance_m, buffer_m, uplift=DEFAULT_BUFFER_UPLIFT):
    """1.0 outside the buffer; 1 + uplift at distance 0, linear in between."""
    if distance_m is None or buffer_m <= 0 or distance_m >= buffer_m:
        return 1.0
    return 1.0 + uplift * (1.0 - distance_m / buffer_m)


def apply_buffer_rule(hab, grid, high_m, low_m, uplift):
    """Adds red_distance_m, buffer_m, buffer_factor, buffer_applied columns
    (`hab` needs lat, lon, zone_tier). Returns a copy."""
    out = hab.copy()
    dist = [distance_to_red_m(la, lo, grid) for la, lo in zip(out["lat"], out["lon"])]
    bufs = [buffer_for_tier(t, high_m, low_m) for t in out["zone_tier"]]
    out["red_distance_m"] = dist
    out["buffer_m"] = bufs
    out["buffer_factor"] = [buffer_factor(d, b, uplift) for d, b in zip(dist, bufs)]
    out["buffer_applied"] = out["buffer_factor"] > 1.0
    return out


def buffer_why(row, uplift):
    d = row["red_distance_m"]
    return {
        "rule": RULE_LABEL,
        "distance_to_red_m": None if d is None or pd.isna(d) else round(float(d), 1),
        "buffer_m": row["buffer_m"],
        "max_uplift": uplift,
        "buffer_factor": round(float(row["buffer_factor"]), 3),
        "applied": bool(row["buffer_applied"]),
        "cell_size_assumption": "cells ~278 m x ~240 m; distance is indicative only",
    }


def eligibility_log(hab, allocation, unallocated, params):
    """One row per habitation: tier, plain-language reasons and the rule values
    used. Anonymised (habitation ids/names only)."""
    alloc = dict(zip(allocation["habitation_id"], allocation["site_id"])) if len(allocation) else {}
    unalloc = dict(zip(unallocated["habitation_id"], unallocated["reason"])) if len(unallocated) else {}
    rows = []
    for _, h in hab.sort_values("rpi", ascending=False).iterrows():
        reasons = [f"zone {h['zone_tier']} (score {h['zone_score']:.1f})",
                   f"vulnerability {h['vulnerability']:.2f}", f"population {int(h['population'])}"]
        d = h["red_distance_m"]
        if h["buffer_applied"]:
            reasons.append(f"{d:.0f} m from Red zone, inside {h['buffer_m']:.0f} m buffer "
                           f"(priority x{h['buffer_factor']:.2f})")
        else:
            reasons.append("outside Red-zone buffer" if d is not None else "no Red zone in grid")
        if h["route_flag"]:
            reasons.append(f"route: {h['route_flag']}")
        if h["habitation_id"] in alloc:
            reasons.append(f"allocated to {alloc[h['habitation_id']]}")
        elif h["habitation_id"] in unalloc:
            reasons.append(f"unallocated: {unalloc[h['habitation_id']]}")
        rows.append({
            "habitation_id": h["habitation_id"], "name": h["name"], "tier": h["rpi_tier"],
            "reasons": "; ".join(reasons),
            "buffer_high_m": params["buffer_high_m"], "buffer_low_m": params["buffer_low_m"],
            "buffer_max_uplift": params["buffer_uplift"],
            "cell_size_deg": data_gen.CELL_SIZE_DEG, "rule_note": RULE_LABEL,
        })
    return pd.DataFrame(rows)
