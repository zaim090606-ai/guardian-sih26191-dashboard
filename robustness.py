"""Decision robustness: how often does each habitation keep its relocation tier
when the scoring weights are jittered by +/-20%?

Each run multiplies every zone weight and every vulnerability-index weight by a
uniform factor in [1 - spread, 1 + spread] (renormalised) and reruns the
pipeline. A habitation is "Stable" if it keeps its baseline tier in at least
`stable_share` of the runs, otherwise "Sensitive". Seeded, so results repeat.
ILLUSTRATIVE: it tests weight sensitivity only, not data error or model validity.
"""

import numpy as np
import pandas as pd

import pipeline

DEFAULT_RUNS = 200
DEFAULT_SPREAD = 0.20
DEFAULT_STABLE_SHARE = 0.90
DEFAULT_SEED = 2026


def _jitter(weights, rng, spread):
    keys = list(weights)
    w = np.array([weights[k] for k in keys], dtype=float) * rng.uniform(1 - spread, 1 + spread, len(keys))
    w = w / w.sum() if w.sum() > 0 else w
    return dict(zip(keys, w.tolist()))


def run_robustness(runs=DEFAULT_RUNS, spread=DEFAULT_SPREAD, stable_share=DEFAULT_STABLE_SHARE,
                   seed=DEFAULT_SEED, **params):
    """Returns a DataFrame: habitation_id, name, baseline_tier, pct_runs_same_tier,
    label (Stable/Sensitive), runs. `params` are ordinary run_pipeline overrides."""
    base = pipeline.run_pipeline(**params)["habitations"]
    ids = base["habitation_id"].tolist()
    baseline = base.set_index("habitation_id")["rpi_tier"]
    zone_w = {**pipeline.DEFAULT_PARAMS["zone_weights"], **(params.get("zone_weights") or {})}
    vi_w = {**pipeline.DEFAULT_PARAMS["vi_weights"], **(params.get("vi_weights") or {})}
    same = pd.Series(0, index=ids, dtype=float)
    rng = np.random.default_rng(seed)
    for _ in range(runs):
        overrides = {**params, "zone_weights": _jitter(zone_w, rng, spread), "vi_weights": _jitter(vi_w, rng, spread)}
        tiers = pipeline.run_pipeline(**overrides)["habitations"].set_index("habitation_id")["rpi_tier"]
        same += (tiers.reindex(ids) == baseline.reindex(ids)).astype(float)
    pct = (100.0 * same / max(runs, 1)).round(1)
    out = pd.DataFrame({
        "habitation_id": ids,
        "name": base["name"].tolist(),
        "baseline_tier": baseline.reindex(ids).tolist(),
        "pct_runs_same_tier": pct.reindex(ids).tolist(),
    })
    out["label"] = np.where(out["pct_runs_same_tier"] >= 100.0 * stable_share, "Stable", "Sensitive")
    out["runs"] = runs
    return out
