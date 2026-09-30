import pandas as pd

import guardian_layer as gl
import scoring


def test_drop_invalid_fixes_removes_null_and_zero_zero():
    df = pd.DataFrame(
        {
            "incident_id": ["A", "B", "C", "D"],
            "latitude": [30.5, None, 0.0, 30.6],
            "longitude": [79.5, None, 0.0, 79.6],
        }
    )
    out = gl.drop_invalid_fixes(df)
    assert set(out["incident_id"]) == {"A", "D"}


def test_load_sample_incidents_strips_sensitive_fields(tmp_path):
    path = tmp_path / "sample.json"
    path.write_text(
        '[{"incident_id": "X", "userId": "abc", "userPhone": "+911234567890", '
        '"latitude": 30.5, "longitude": 79.5}]',
        encoding="utf-8",
    )
    df = gl.load_sample_incidents(str(path))
    assert "userId" not in df.columns
    assert "userPhone" not in df.columns


def test_load_incidents_live_mode_falls_back_without_project_id(monkeypatch):
    monkeypatch.setattr(gl, "get_firebase_project_id", lambda: None)
    df, source = gl.load_incidents(mode="live")
    assert source == "sample_fallback"
    assert not df.empty


def _make_incident_batch(coords, ecs_values):
    return pd.DataFrame(
        {
            "incident_id": [f"I{i}" for i in range(len(coords))],
            "latitude": [c[0] for c in coords],
            "longitude": [c[1] for c in coords],
            "ecs": ecs_values,
        }
    )


def test_cluster_zone_bonus_is_capped():
    # Many tightly-clustered, high-confidence incidents should still clip at
    # the cap, not scale unboundedly with cluster size.
    coords = [(30.550000 + i * 0.00001, 79.560000) for i in range(10)]
    df = _make_incident_batch(coords, ecs_values=[1.0] * 10)
    clustered = gl.cluster_incidents(df, eps_km=0.05, min_samples=2)
    assert (clustered["cluster_id"] != -1).all()

    bonuses = gl.cluster_zone_bonuses(clustered, bonus_per_incident=10.0, bonus_cap=15.0)
    assert bonuses
    assert all(v <= 15.0 for v in bonuses.values())


def test_cluster_zone_bonus_requires_at_least_two_distinct_incidents():
    df = _make_incident_batch([(30.55, 79.56)], ecs_values=[1.0])
    clustered = gl.cluster_incidents(df, eps_km=0.05, min_samples=1)
    bonuses = gl.cluster_zone_bonuses(clustered)
    assert bonuses == {}


def test_flag_comms_degraded_by_relay_flag_and_by_delay():
    df = pd.DataFrame(
        {
            "incident_id": ["A", "B", "C"],
            "latitude": [30.55, 30.56, 30.57],
            "longitude": [79.56, 79.57, 79.58],
            "relayedByMesh": [True, False, False],
            "originTimestamp": [
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            ],
            "relayedAt": [
                "2026-01-01T00:05:00+00:00",
                None,
                "2026-01-01T00:20:00+00:00",
            ],
        }
    )
    out = gl.flag_comms_degraded(df, delay_threshold_minutes=10.0)
    assert out.set_index("incident_id").loc["A", "comms_degraded"] == True  # relayed at all
    assert out.set_index("incident_id").loc["B", "comms_degraded"] == False  # no relay, no delay
    assert out.set_index("incident_id").loc["C", "comms_degraded"] == True  # delay exceeds threshold


def test_comms_degraded_bonus_is_capped():
    flagged = pd.DataFrame(
        {
            "incident_id": [f"I{i}" for i in range(20)],
            "latitude": [30.55] * 20,
            "longitude": [79.56] * 20,
            "comms_degraded": [True] * 20,
        }
    )
    bonuses = gl.comms_degraded_cell_bonuses(flagged, bonus_per_incident=2.0, bonus_cap=5.0)
    assert all(v <= 5.0 for v in bonuses.values())


def test_compute_incident_ecs_modality_flags_increase_score():
    # Use a "last_known" fix with mediocre accuracy so the location
    # component alone is well under 1.0 and has headroom for a modality
    # bonus to actually show up (a fresh GPS fix already clips at 1.0).
    df = pd.DataFrame(
        {
            "incident_id": ["A", "B"],
            "eventType": ["sensor_trigger", "voice_trigger"],
            "audioEvents": [[{"label": "Screaming", "score": 0.9}], []],
            "transcript": ["", "bachao madad karo"],
            "audioAnalysis": ["", ""],
            "locationSource": ["last_known", "last_known"],
            "accuracyM": [60.0, 60.0],
            "timestamp": ["2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"],
        }
    )
    out = gl.compute_incident_ecs(df, now=pd.Timestamp("2026-01-01T00:00:00", tz="UTC"))
    baseline, _ = scoring.evidence_confidence_score("last_known", 60.0, age_hours=0)
    assert out.set_index("incident_id").loc["A", "ecs"] > baseline
    assert out.set_index("incident_id").loc["B", "ecs"] > baseline


def test_unlocated_reports_are_kept_scored_and_labelled_partial():
    df = gl.load_sample_incidents()
    part = gl.score_unlocated(df, now="2026-09-26T00:00:00+00:00")
    assert len(part) >= 3
    assert set(part["completeness"]) == {"partial"}
    assert part["ecs"].between(0, 1).all()
    assert set(part["unlocated_reason"]) <= {gl.UNLOCATED_REASON_NULL, gl.UNLOCATED_REASON_ZERO}
    stats = gl.unlocated_summary(part)
    assert stats["count"] == len(part) and stats["relayed_count"] >= 1
    assert not {"userId", "userPhone"} & set(part.columns)


def test_pipeline_exposes_unlocated_and_region_comms_stat():
    import pipeline
    r = pipeline.run_pipeline()
    assert r["unlocated_stats"]["count"] >= 3
    assert r["region_comms_degraded"] >= r["unlocated_stats"]["relayed_count"]
    assert (r["incidents"]["latitude"] != 0).all()
