"""Carrying capacity and greedy relocation allocation for the SIH26191
prototype. Illustrative: the space-per-person norm and usable-area formula
below are simplifying assumptions for a demo, not an official standard.
"""

import numpy as np
import pandas as pd

# Illustrative default: not an official standard (e.g. Sphere Handbook uses
# ~3.5 m^2/person for emergency shelter; we default a bit higher to also cover
# access paths/services in a resettlement site). Adjustable in the UI.
DEFAULT_SPACE_NORM_M2_PER_PERSON = 45.0

# Usable-area reduction: steeper slope and higher hazard cut into how much of
# a site's raw area can actually be built on. Both illustrative curves.
SLOPE_USABLE_CUTOFF_DEG = 25.0  # above this slope, usability drops sharply


def usable_area_fraction(slope_deg, hazard):
    """Fraction (0-1) of a site's raw area assumed buildable, from slope and
    hazard. Illustrative: linear slope penalty capped at the cutoff, times a
    hazard penalty.
    """
    slope_fraction = max(0.0, 1.0 - min(slope_deg, SLOPE_USABLE_CUTOFF_DEG) / SLOPE_USABLE_CUTOFF_DEG)
    slope_fraction = 0.2 + 0.8 * slope_fraction  # floor at 0.2 so a steep site isn't zeroed out
    hazard_fraction = 1.0 - 0.6 * max(0.0, min(hazard, 1.0))
    return max(0.0, min(1.0, slope_fraction * hazard_fraction))


def site_capacity(area_ha, slope_deg, hazard, space_norm_m2=DEFAULT_SPACE_NORM_M2_PER_PERSON):
    """How many people a candidate safe site can hold."""
    usable_fraction = usable_area_fraction(slope_deg, hazard)
    usable_area_m2 = area_ha * 10_000 * usable_fraction
    capacity = int(usable_area_m2 // space_norm_m2)
    return capacity, {
        "area_ha": area_ha,
        "slope_deg": slope_deg,
        "hazard": hazard,
        "usable_area_fraction": usable_fraction,
        "usable_area_m2": usable_area_m2,
        "space_norm_m2_per_person": space_norm_m2,
        "capacity_people": capacity,
    }


def compute_site_capacities(safe_sites_df, space_norm_m2=DEFAULT_SPACE_NORM_M2_PER_PERSON):
    """Adds capacity_people / usable_area_m2 columns to a safe_sites DataFrame."""
    df = safe_sites_df.copy()
    capacities = []
    usable_areas = []
    for _, row in df.iterrows():
        capacity, breakdown = site_capacity(row["area_ha"], row["slope_deg"], row["hazard"], space_norm_m2)
        capacities.append(capacity)
        usable_areas.append(breakdown["usable_area_m2"])
    df["capacity_people"] = capacities
    df["usable_area_m2"] = usable_areas
    df["remaining_capacity"] = df["capacity_people"]
    return df


# Multi-resource capacity (area, water, sanitation). Defaults follow commonly
# cited Sphere Handbook minimums (~3.5 m2 covered living space, 15 L/person/day
# water, 1 toilet per 20 people) but are ILLUSTRATIVE here: verify against the
# current Sphere Handbook (spherestandards.org) before any real use.
# Livestock figures are illustrative assumptions, not from Sphere.
DEFAULT_NORMS = dict(
    area_m2_per_person=3.5,
    water_l_per_person=15.0,
    people_per_toilet=20,
    livestock_water_l=20.0,
    livestock_area_m2=3.0,
)
RESOURCES = ("area", "water", "sanitation")


def compute_multi_resource_capacities(safe_sites_df, norms=None, livestock_area_m2=None, livestock_water_l=None):
    """Per site: people supported by each resource and the binding one.

    area_limit = (usable area after slope/hazard reduction - livestock area) / area norm
    water_limit = (water_l_per_day - livestock water) / water norm
    sanitation_limit = toilets x people-per-toilet
    capacity_people = min of the three; limiting_resource names the minimum
    (ties resolve area, water, sanitation). livestock_* are optional per-site
    Series/lists of the load already placed at each site.
    """
    norms = {**DEFAULT_NORMS, **(norms or {})}
    df = safe_sites_df.copy()
    n = len(df)
    lv_area = np.zeros(n) if livestock_area_m2 is None else np.asarray(livestock_area_m2, dtype=float)
    lv_water = np.zeros(n) if livestock_water_l is None else np.asarray(livestock_water_l, dtype=float)

    usable = np.array([
        r["area_ha"] * 10_000 * usable_area_fraction(r["slope_deg"], r["hazard"]) for _, r in df.iterrows()
    ])
    area_limit = np.floor(np.maximum(0.0, usable - lv_area) / norms["area_m2_per_person"])
    water_limit = np.floor(np.maximum(0.0, df["water_l_per_day"].to_numpy(dtype=float) - lv_water)
                           / norms["water_l_per_person"])
    sanit_limit = np.floor(df["toilets"].to_numpy(dtype=float) * norms["people_per_toilet"])

    limits = np.vstack([area_limit, water_limit, sanit_limit])
    df["usable_area_m2"] = usable
    df["area_limit"] = area_limit.astype(int)
    df["water_limit"] = water_limit.astype(int)
    df["sanitation_limit"] = sanit_limit.astype(int)
    df["capacity_people"] = limits.min(axis=0).astype(int)
    df["limiting_resource"] = [RESOURCES[i] for i in limits.argmin(axis=0)]
    df["remaining_capacity"] = df["capacity_people"]
    return df


def allocate_multi_resource(habitations_df, sites_df, norms=None, priority_col="rpi",
                            route_fn=None, route_threshold=60.0):
    """Greedy allocation (most urgent first, nearest site first) that tracks
    area, water and sanitation separately; livestock draws on water and area.
    Habitations that fit nowhere are unallocated with the reason (which
    resource fails at the nearest site, or the route-safety block).

    sites_df must come from compute_multi_resource_capacities. Returns
    (allocation_df, sites_after_df, unallocated_df); sites_after shows the
    three limits net of the livestock placed at each site.
    """
    norms = {**DEFAULT_NORMS, **(norms or {})}
    sites = sites_df.reset_index(drop=True)
    rem = {
        "area": sites["usable_area_m2"].to_numpy(dtype=float).copy(),
        "water": sites["water_l_per_day"].to_numpy(dtype=float).copy(),
        "sanitation": (sites["toilets"].to_numpy(dtype=float) * norms["people_per_toilet"]).copy(),
    }
    lv_area = np.zeros(len(sites))
    lv_water = np.zeros(len(sites))
    placed_pop = np.zeros(len(sites))

    allocations, unallocated_rows = [], []
    for _, hab in habitations_df.sort_values(priority_col, ascending=False).iterrows():
        pop = float(hab["population"])
        lv = float(hab.get("livestock", 0) or 0)
        need = {
            "area": pop * norms["area_m2_per_person"] + lv * norms["livestock_area_m2"],
            "water": pop * norms["water_l_per_person"] + lv * norms["livestock_water_l"],
            "sanitation": pop,
        }
        distances = _haversine_km(hab["lat"], hab["lon"], sites["lat"].values, sites["lon"].values)
        order = distances.argsort()

        placed = False
        blocked_by_route = False
        for idx in order:
            if any(need[r] > rem[r][idx] for r in RESOURCES):
                continue
            if route_fn is not None and route_fn(hab, sites.iloc[idx])["route_risk"] >= route_threshold:
                blocked_by_route = True
                continue
            for r in RESOURCES:
                rem[r][idx] -= need[r]
            lv_area[idx] += lv * norms["livestock_area_m2"]
            lv_water[idx] += lv * norms["livestock_water_l"]
            placed_pop[idx] += pop
            allocations.append({
                "habitation_id": hab["habitation_id"],
                "habitation_name": hab["name"],
                "population": hab["population"],
                "livestock": int(lv),
                priority_col: hab[priority_col],
                "site_id": sites.iloc[idx]["site_id"],
                "site_name": sites.iloc[idx]["name"],
                "distance_km": round(float(distances[idx]), 2),
            })
            placed = True
            break

        if not placed:
            nearest = order[0]
            failing = [r for r in RESOURCES if need[r] > rem[r][nearest]]
            if blocked_by_route:
                reason = "no safe route: field review"
            else:
                reason = f"insufficient {'/'.join(failing)} at nearest site {sites.iloc[nearest]['site_id']}"
            unallocated_rows.append({
                "habitation_id": hab["habitation_id"],
                "habitation_name": hab["name"],
                "population": hab["population"],
                "livestock": int(lv),
                priority_col: hab[priority_col],
                "nearest_site_id": sites.iloc[nearest]["site_id"],
                "reason": reason,
            })

    sites_after = compute_multi_resource_capacities(
        sites.drop(columns=["usable_area_m2", "area_limit", "water_limit", "sanitation_limit",
                            "capacity_people", "limiting_resource", "remaining_capacity"], errors="ignore"),
        norms, lv_area, lv_water,
    )
    sites_after["allocated_people"] = placed_pop.astype(int)
    sites_after["remaining_capacity"] = (sites_after["capacity_people"] - sites_after["allocated_people"]).clip(lower=0)
    return pd.DataFrame(allocations), sites_after, pd.DataFrame(unallocated_rows)


def _haversine_km(lat1, lon1, lat2, lon2):
    import numpy as np

    r = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def greedy_allocate(habitations_df, safe_sites_with_capacity_df, priority_col="rpi",
                    route_fn=None, route_threshold=60.0):
    """Greedy allocation: process habitations most-urgent-first, each placed
    at its nearest safe site that still has remaining capacity. Habitations
    that don't fit anywhere are listed as unallocated.

    If route_fn(hab, site) is given (see route_safety.make_route_fn), a site whose
    route risk is at/above route_threshold is skipped in favour of the next-best
    site with capacity and a safe route; if every site with capacity has an
    unsafe route the habitation is unallocated as "no safe route: field review".

    Returns (allocation_df, sites_df_with_remaining, unallocated_df).
    """
    sites = safe_sites_with_capacity_df.copy()
    sites["remaining_capacity"] = sites["capacity_people"]

    habitations = habitations_df.sort_values(priority_col, ascending=False).copy()

    allocations = []
    unallocated_rows = []

    for _, hab in habitations.iterrows():
        distances = _haversine_km(hab["lat"], hab["lon"], sites["lat"].values, sites["lon"].values)
        order = distances.argsort()

        placed = False
        blocked_by_route = False
        for idx in order:
            site = sites.iloc[idx]
            if site["remaining_capacity"] >= hab["population"]:
                if route_fn is not None and route_fn(hab, site)["route_risk"] >= route_threshold:
                    blocked_by_route = True
                    continue
                allocations.append(
                    {
                        "habitation_id": hab["habitation_id"],
                        "habitation_name": hab["name"],
                        "population": hab["population"],
                        priority_col: hab[priority_col],
                        "site_id": site["site_id"],
                        "site_name": site["name"],
                        "distance_km": round(float(distances[idx]), 2),
                    }
                )
                sites.loc[sites["site_id"] == site["site_id"], "remaining_capacity"] -= hab["population"]
                placed = True
                break

        if not placed:
            nearest_idx = order[0]
            unallocated_rows.append(
                {
                    "habitation_id": hab["habitation_id"],
                    "habitation_name": hab["name"],
                    "population": hab["population"],
                    priority_col: hab[priority_col],
                    "nearest_site_id": sites.iloc[nearest_idx]["site_id"],
                    "nearest_site_shortfall": max(
                        0, int(hab["population"] - sites.iloc[nearest_idx]["remaining_capacity"])
                    ),
                    "reason": "no safe route: field review" if blocked_by_route
                    else "no site with enough remaining capacity",
                }
            )

    allocation_df = pd.DataFrame(allocations)
    unallocated_df = pd.DataFrame(unallocated_rows)
    return allocation_df, sites, unallocated_df


def export_allocation_csv(allocation_df, unallocated_df, path):
    """Writes a single CSV: allocated rows plus unallocated rows (status column
    distinguishes them), for the Relocation tab's export button."""
    alloc = allocation_df.copy()
    alloc["status"] = "allocated"
    unalloc = unallocated_df.copy()
    unalloc["status"] = "unallocated"
    combined = pd.concat([alloc, unalloc], ignore_index=True, sort=False)
    combined.to_csv(path, index=False)
    return path
