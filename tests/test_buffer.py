import pandas as pd

import buffer
import data_gen
import pipeline


def _grid():
    # one Red cell centred at (30.5, 79.5)
    return pd.DataFrame({"lat": [30.5], "lon": [79.5], "zone_tier": ["Red"]})


def test_distance_zero_inside_and_grows_outside():
    g = _grid()
    assert buffer.distance_to_red_m(30.5, 79.5, g) == 0.0
    edge = data_gen.CELL_SIZE_DEG / 2
    d = buffer.distance_to_red_m(30.5 + edge + 0.0004, 79.5, g)
    assert 40 < d < 50  # 0.0004 deg ~ 44.5 m
    assert buffer.distance_to_red_m(30.5, 79.5, g.assign(zone_tier="Green")) is None


def test_factor_fades_to_one_at_buffer_edge():
    assert buffer.buffer_factor(0, 50, 0.25) == 1.25
    assert abs(buffer.buffer_factor(25, 50, 0.25) - 1.125) < 1e-9
    assert buffer.buffer_factor(50, 50, 0.25) == 1.0
    assert buffer.buffer_factor(10, 0, 0.25) == 1.0
    assert buffer.buffer_factor(None, 50, 0.25) == 1.0


def test_buffer_lookup_by_tier():
    assert buffer.buffer_for_tier("Red", 50, 30) == 50
    assert buffer.buffer_for_tier("Amber", 50, 30) == 50
    assert buffer.buffer_for_tier("Green", 50, 30) == 30


def test_pipeline_shows_buffer_in_why_and_log_carries_rule_values():
    res = pipeline.run_pipeline(review_state={})
    hab = res["habitations"]
    assert all("buffer_rule" in bd for bd in hab["rpi_breakdown"])
    log = buffer.eligibility_log(hab, res["allocation"], res["unallocated"], res["params"])
    assert len(log) == len(hab)
    assert {"habitation_id", "tier", "reasons", "buffer_high_m", "buffer_low_m"} <= set(log.columns)
    assert (log["buffer_high_m"] == 50).all() and (log["buffer_low_m"] == 30).all()
    # a zero uplift switches the rule off
    off = pipeline.run_pipeline(review_state={}, buffer_uplift=0.0)["habitations"]
    assert (off["buffer_factor"] == 1.0).all()
