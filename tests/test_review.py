import pandas as pd

import guardian_layer as gl
import pipeline
import review


def test_save_load_roundtrip_and_bad_file(tmp_path):
    p = str(tmp_path / "r.json")
    assert review.load_review_state(p) == {}
    review.save_review("K1", "Confirmed", "seen on site", p)
    assert review.load_review_state(p)["K1"] == {"status": "Confirmed", "note": "seen on site"}
    open(p, "w").write("{not json")
    assert review.load_review_state(p) == {}


def test_dismissed_cluster_gives_no_bonus():
    base = pipeline.run_pipeline(review_state={})
    inc = base["incidents"]
    keys = [k for k in inc["cluster_key"].unique() if k]
    assert keys
    dismissed = {k: {"status": "Dismissed", "note": ""} for k in keys}
    res = pipeline.run_pipeline(review_state=dismissed)
    assert base["grid"]["guardian_evidence_bonus"].sum() > 0
    assert res["grid"]["guardian_evidence_bonus"].sum() == 0
    confirmed = pipeline.run_pipeline(review_state={k: {"status": "Confirmed"} for k in keys})
    assert confirmed["grid"]["guardian_evidence_bonus"].sum() == base["grid"]["guardian_evidence_bonus"].sum()


def test_triage_queue_sorted_by_confidence_times_severity():
    inc = pd.DataFrame({
        "cluster_id": [0, 0, 1, 1, -1], "cluster_key": ["A", "A", "B", "B", ""],
        "ecs": [0.2, 0.2, 0.5, 0.5, 0.9], "riskLevel": ["LOW", "MEDIUM", "CRITICAL", "HIGH", "LOW"],
    })
    q = review.triage_queue(inc, {"B": {"status": "Confirmed", "note": "x"}})
    assert list(q["cluster_key"]) == ["B", "A"]
    assert q.iloc[0]["triage_score"] == 2.0 and q.iloc[0]["status"] == "Confirmed"
    assert q.iloc[1]["status"] == "Pending"
