import pandas as pd

import data_gen
import pipeline
import relocation
import route_safety


def _ll(r, c):
    return (data_gen.ORIGIN_LAT + (r + 0.5) * data_gen.CELL_SIZE_DEG,
            data_gen.ORIGIN_LON + (c + 0.5) * data_gen.CELL_SIZE_DEG)


def _grid(hot_cells=(), hot=95.0, base=10.0):
    rows = [(r, c) for r in range(data_gen.GRID_SIZE) for c in range(data_gen.GRID_SIZE)]
    return pd.DataFrame({
        "row": [r for r, _ in rows], "col": [c for _, c in rows],
        "cell_id": [f"C{r:02d}-{c:02d}" for r, c in rows],
        "zone_score": [hot if (r, c) in hot_cells else base for r, c in rows],
    })


def _scene(hot_cells=()):
    """Habitation at (2,2); site S1 near it at (2,8); site S2 far at (17,2)."""
    lat, lon = _ll(2, 2)
    hab = pd.DataFrame([{"habitation_id": "H1", "name": "H1", "lat": lat, "lon": lon,
                         "population": 100, "rpi": 50.0}])
    s1, s2 = _ll(2, 8), _ll(17, 2)
    sites = pd.DataFrame([
        {"site_id": "S1", "name": "S1", "lat": s1[0], "lon": s1[1], "capacity_people": 500},
        {"site_id": "S2", "name": "S2", "lat": s2[0], "lon": s2[1], "capacity_people": 500},
    ])
    fn = route_safety.make_route_fn(_grid(hot_cells), 1.0, 60.0)
    return hab, sites, fn


def test_route_risk_formula_and_multiplier_cap():
    lookup = route_safety.zone_score_lookup(_grid({(2, 5)}, hot=100.0, base=0.0))
    a, b = _ll(2, 2), _ll(2, 8)
    r = route_safety.route_risk(*a, *b, lookup)
    assert r["riskiest_cell"] == "C02-05" and r["riskiest_cell_score"] == 100.0
    assert 60.0 < r["route_risk"] < 100.0  # 0.6*100 + 0.4*mean(>0)
    assert route_safety.route_risk(*a, *b, lookup, scenario_multiplier=2.0)["route_risk"] == 100.0


def test_safe_route_is_kept():
    hab, sites, fn = _scene()
    alloc, _, unalloc = relocation.greedy_allocate(hab, sites, route_fn=fn, route_threshold=60.0)
    assert alloc.iloc[0]["site_id"] == "S1" and unalloc.empty


def test_risky_route_is_reallocated_to_next_best_site():
    hab, sites, fn = _scene(hot_cells={(2, 5)})  # blocks the short route to S1 only
    alloc, _, unalloc = relocation.greedy_allocate(hab, sites, route_fn=fn, route_threshold=60.0)
    assert alloc.iloc[0]["site_id"] == "S2" and unalloc.empty


def test_no_alternative_is_flagged_for_field_review():
    hot = {(2, 5), (9, 2)}  # one hot cell on each route
    hab, sites, fn = _scene(hot_cells=hot)
    alloc, _, unalloc = relocation.greedy_allocate(hab, sites, route_fn=fn, route_threshold=60.0)
    assert alloc.empty
    assert unalloc.iloc[0]["reason"] == route_safety.NO_SAFE_ROUTE_FLAG


def test_threshold_changes_outcomes_in_pipeline():
    lax = pipeline.run_pipeline(route_risk_threshold=101)
    strict = pipeline.run_pipeline(route_risk_threshold=0)
    assert len(lax["allocation"]) > len(strict["allocation"]) == 0
    assert (strict["unallocated"]["reason"] == route_safety.NO_SAFE_ROUTE_FLAG).any()
    hab = lax["habitations"]
    for col in ("route_risk", "route_flag", "riskiest_cell", "riskiest_cell_score"):
        assert col in hab and hab[col].notna().all()
    assert "route_risk" in hab.iloc[0]["rpi_breakdown"]
