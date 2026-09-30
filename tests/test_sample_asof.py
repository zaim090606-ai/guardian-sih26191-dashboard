import numpy as np
import pandas as pd
import pytest

import guardian_layer as gl
import pipeline


class _FakePd:
    """Proxy for guardian_layer's `pd` whose clock reads a fixed instant."""

    def __init__(self, instant):
        class _TS(pd.Timestamp):
            @classmethod
            def now(cls, tz=None):
                return pd.Timestamp(instant).tz_convert(tz) if tz else pd.Timestamp(instant).tz_localize(None)

        self.Timestamp = _TS

    def __getattr__(self, name):
        return getattr(pd, name)


def _snapshot(res):
    inc = res["incidents"].sort_values("incident_id")
    hab = res["habitations"].sort_values("habitation_id")
    return (inc["ecs"].round(9).tolist(), res["unlocated"]["ecs"].round(9).tolist(),
            res["grid"]["zone_score"].round(9).tolist(), hab["rpi"].round(9).tolist(), hab["rpi_tier"].tolist())


def _run_on(monkeypatch, instant, **kw):
    monkeypatch.setattr(gl, "pd", _FakePd(pd.Timestamp(instant, tz="UTC")))
    return pipeline.run_pipeline(review_state={}, **kw)


def test_sample_mode_identical_on_two_different_dates(monkeypatch):
    a = _run_on(monkeypatch, "2026-09-30 08:00")
    b = _run_on(monkeypatch, "2027-03-15 20:30")
    assert _snapshot(a) == _snapshot(b)
    assert a["sample_as_of"] == pd.Timestamp("2026-09-28T12:00:00Z")


def test_live_fallback_to_sample_is_also_deterministic(monkeypatch):
    monkeypatch.setattr(gl, "get_firebase_project_id", lambda: None)
    a = _run_on(monkeypatch, "2026-09-30 08:00", mode="live")
    b = _run_on(monkeypatch, "2027-03-15 20:30", mode="live")
    assert a["incident_source"] == "sample_fallback" and _snapshot(a) == _snapshot(b)


def test_real_data_still_uses_the_real_clock(monkeypatch):
    df = gl.load_sample_incidents().head(6)
    early = pd.Timestamp("2026-09-28 12:00", tz="UTC")
    late = pd.Timestamp("2026-09-30 12:00", tz="UTC")
    e = gl.compute_incident_ecs(df, now=early)["ecs"].to_numpy()
    l = gl.compute_incident_ecs(df, now=late)["ecs"].to_numpy()
    assert (l <= e).all() and not np.allclose(e, l)  # decay follows whatever clock is passed
    monkeypatch.setattr(gl, "pd", _FakePd(early))
    assert np.allclose(gl.compute_incident_ecs(df)["ecs"].to_numpy(), e)  # default = clock
