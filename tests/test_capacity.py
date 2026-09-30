import pandas as pd

import relocation


def _site(usable_ha=1.0, water=1_000_000, toilets=10_000):
    # slope 0 / hazard 0 => usable fraction 1.0, so usable area == area_ha * 10_000
    return pd.DataFrame([{"site_id": "S1", "name": "S1", "lat": 30.0, "lon": 79.0, "area_ha": usable_ha,
                          "slope_deg": 0.0, "hazard": 0.0, "water_l_per_day": water, "toilets": toilets}])


def test_area_is_binding_limit():
    out = relocation.compute_multi_resource_capacities(_site(usable_ha=0.35))  # 3500 m2 / 3.5 = 1000
    assert out.loc[0, "limiting_resource"] == "area" and out.loc[0, "capacity_people"] == 1000


def test_water_is_binding_limit():
    out = relocation.compute_multi_resource_capacities(_site(water=3000))  # 3000 / 15 = 200
    assert out.loc[0, "limiting_resource"] == "water" and out.loc[0, "capacity_people"] == 200


def test_sanitation_is_binding_limit():
    out = relocation.compute_multi_resource_capacities(_site(toilets=5))  # 5 x 20 = 100
    assert out.loc[0, "limiting_resource"] == "sanitation" and out.loc[0, "capacity_people"] == 100


def test_livestock_reduces_water_limit():
    base = relocation.compute_multi_resource_capacities(_site(water=3000))
    with_lv = relocation.compute_multi_resource_capacities(_site(water=3000), livestock_water_l=[20 * 50])
    assert base.loc[0, "water_limit"] == 200
    assert with_lv.loc[0, "water_limit"] == 133  # (3000 - 1000) / 15, floored


def test_norms_are_adjustable():
    site = _site(water=3000)
    assert relocation.compute_multi_resource_capacities(site, {"water_l_per_person": 30}).loc[0, "water_limit"] == 100
    assert relocation.compute_multi_resource_capacities(_site(toilets=5), {"people_per_toilet": 50}).loc[0, "sanitation_limit"] == 250


def test_allocation_charges_livestock_and_reports_reason():
    sites = relocation.compute_multi_resource_capacities(_site(water=3000))  # 200 people by water
    hab = pd.DataFrame([
        {"habitation_id": "A", "name": "A", "lat": 30.0, "lon": 79.0, "population": 150, "livestock": 0, "rpi": 90},
        {"habitation_id": "B", "name": "B", "lat": 30.0, "lon": 79.0, "population": 40, "livestock": 20, "rpi": 50},
    ])
    alloc, after, unalloc = relocation.allocate_multi_resource(hab, sites)
    assert list(alloc["habitation_id"]) == ["A"]  # B: 600 L + 400 L livestock > 750 L left
    assert unalloc.iloc[0]["habitation_id"] == "B" and "water" in unalloc.iloc[0]["reason"]
    assert after.loc[0, "remaining_capacity"] >= 0
