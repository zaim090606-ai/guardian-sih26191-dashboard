import pandas as pd

import relocation


def test_site_capacity_reduced_by_slope_and_hazard():
    flat_safe_capacity, _ = relocation.site_capacity(area_ha=10, slope_deg=2, hazard=0.0)
    steep_hazardous_capacity, _ = relocation.site_capacity(area_ha=10, slope_deg=40, hazard=0.8)
    assert flat_safe_capacity > steep_hazardous_capacity
    assert steep_hazardous_capacity >= 0


def test_usable_area_fraction_bounds():
    assert 0.0 <= relocation.usable_area_fraction(0, 0) <= 1.0
    assert 0.0 <= relocation.usable_area_fraction(60, 1.0) <= 1.0
    # A very steep, very hazardous site still keeps a small nonzero floor
    # rather than being zeroed out entirely.
    assert relocation.usable_area_fraction(60, 1.0) > 0.0


def test_compute_site_capacities_adds_columns():
    sites = pd.DataFrame(
        {
            "site_id": ["S1", "S2"],
            "name": ["Site 1", "Site 2"],
            "area_ha": [5.0, 8.0],
            "slope_deg": [3.0, 20.0],
            "hazard": [0.1, 0.5],
        }
    )
    out = relocation.compute_site_capacities(sites)
    assert "capacity_people" in out.columns
    assert (out["capacity_people"] >= 0).all()
    assert out.loc[0, "capacity_people"] > out.loc[1, "capacity_people"]


def _make_habitations(n, population, priority_col="rpi"):
    return pd.DataFrame(
        {
            "habitation_id": [f"H{i}" for i in range(n)],
            "name": [f"Hab {i}" for i in range(n)],
            "lat": [30.5 + i * 0.001 for i in range(n)],
            "lon": [79.5 + i * 0.001 for i in range(n)],
            "population": population,
            priority_col: list(range(n, 0, -1)),
        }
    )


def test_greedy_allocate_respects_capacity_and_covers_every_habitation():
    habitations = _make_habitations(5, population=[100, 200, 150, 400, 50])
    sites = pd.DataFrame(
        {
            "site_id": ["S1", "S2"],
            "name": ["Site 1", "Site 2"],
            "lat": [30.501, 30.505],
            "lon": [79.501, 79.505],
            "capacity_people": [300, 200],
        }
    )

    allocation, sites_after, unallocated = relocation.greedy_allocate(habitations, sites, priority_col="rpi")

    assert len(allocation) + len(unallocated) == len(habitations)

    for _, site_row in sites_after.iterrows():
        allocated_pop = allocation.loc[allocation["site_id"] == site_row["site_id"], "population"].sum()
        original_capacity = sites.loc[sites["site_id"] == site_row["site_id"], "capacity_people"].iloc[0]
        assert allocated_pop <= original_capacity
        assert site_row["remaining_capacity"] == original_capacity - allocated_pop
        assert site_row["remaining_capacity"] >= 0


def test_greedy_allocate_empty_capacity_leaves_everyone_unallocated():
    habitations = _make_habitations(3, population=[10, 20, 30])
    sites = pd.DataFrame(
        {
            "site_id": ["S1"],
            "name": ["Site 1"],
            "lat": [30.501],
            "lon": [79.501],
            "capacity_people": [0],
        }
    )
    allocation, _, unallocated = relocation.greedy_allocate(habitations, sites, priority_col="rpi")
    assert allocation.empty
    assert len(unallocated) == len(habitations)


def test_export_allocation_csv(tmp_path):
    habitations = _make_habitations(2, population=[100, 200])
    sites = pd.DataFrame(
        {
            "site_id": ["S1"],
            "name": ["Site 1"],
            "lat": [30.501],
            "lon": [79.501],
            "capacity_people": [1000],
        }
    )
    allocation, _, unallocated = relocation.greedy_allocate(habitations, sites, priority_col="rpi")
    out_path = tmp_path / "alloc.csv"
    relocation.export_allocation_csv(allocation, unallocated, str(out_path))
    assert out_path.exists()
    content = out_path.read_text()
    assert "status" in content
