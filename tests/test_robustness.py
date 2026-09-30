import robustness


def test_seeded_repeatable_and_well_formed():
    a = robustness.run_robustness(runs=6, review_state={})
    b = robustness.run_robustness(runs=6, review_state={})
    assert a.equals(b)
    assert len(a) == 40 and set(a["label"]) <= {"Stable", "Sensitive"}
    assert a["pct_runs_same_tier"].between(0, 100).all()
    stable = a[a["label"] == "Stable"]
    assert (stable["pct_runs_same_tier"] >= 90).all()


def test_zero_spread_is_fully_stable_and_big_spread_is_not_more_stable():
    zero = robustness.run_robustness(runs=4, spread=0.0, review_state={})
    assert (zero["pct_runs_same_tier"] == 100).all() and (zero["label"] == "Stable").all()
    wide = robustness.run_robustness(runs=6, spread=0.9, review_state={})
    assert wide["pct_runs_same_tier"].mean() <= 100.0
