import numpy as np

import ahp
import pipeline


def test_weights_sum_to_one_and_default_is_consistent():
    r = ahp.compute()
    assert abs(sum(r["weights"].values()) - 1) < 1e-9
    assert r["weights"]["hazard"] > r["weights"]["vulnerability"] > r["weights"]["history"]
    assert r["cr"] < 0.1 and r["consistent"]
    assert np.allclose(r["matrix"] * r["matrix"].T, 1.0)  # reciprocal


def test_perfectly_consistent_matrix_has_zero_cr_and_known_weights():
    j = {("hazard", "vulnerability"): 2.0, ("hazard", "history"): 4.0, ("vulnerability", "history"): 2.0}
    r = ahp.compute(j)
    assert r["cr"] < 1e-9
    assert np.allclose([r["weights"][c] for c in ahp.CRITERIA], [4 / 7, 2 / 7, 1 / 7])


def test_inconsistent_judgements_warn():
    j = {("hazard", "vulnerability"): 9.0, ("vulnerability", "history"): 9.0, ("hazard", "history"): 1 / 9}
    r = ahp.compute(j)
    assert r["cr"] > ahp.CR_WARN_THRESHOLD and not r["consistent"]


def test_saaty_step_roundtrip_and_range_check():
    for step in range(-8, 9):
        assert ahp.step_from_saaty(ahp.saaty_from_step(step)) == step
    try:
        ahp.build_matrix({("hazard", "history"): 10.0})
        assert False
    except ValueError:
        pass


def test_ahp_weights_flow_into_pipeline_and_keep_demo_tier_flip():
    w = ahp.compute()["weights"]
    with_r, _, changes = pipeline.compare_with_without_guardian_evidence(zone_weights=w, review_state={})
    assert abs(sum(with_r["params"]["zone_weights"].values()) - 1) < 1e-9
    assert not changes.empty
