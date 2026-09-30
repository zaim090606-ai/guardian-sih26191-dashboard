from connectors import scenario
from connectors.base import FetchResult
import ui_overview


def _r(status, data=None):
    return FetchResult(status=status, data=data, fetched_at="2026-01-01T00:00:00+00:00", source="test")


def _signals(**overrides):
    base = {
        "rainfall": _r("live", {"hourly": {"precipitation": [0.0] * 24}}),
        "discharge": _r("live", {"daily": {"river_discharge": [1.0] * 3}}),
        "elevation": _r("live", {"elevation": [1000.0] * 5}),
        "alerts": _r("live", []),
        "quakes": _r("live", {"features": []}),
        "gdacs": _r("live", {"features": []}),
    }
    base.update(overrides)
    return base


def test_badge_all_live_is_live():
    assert ui_overview.data_status(_signals()) == ui_overview.BADGES["live"]


def test_badge_reflects_weakest_source_when_sachet_is_sample():
    text = ui_overview.data_status(_signals(alerts=_r("sample", [{"headline": "x"}])))
    assert "Mixed: SACHET (sample)" in text
    assert "Live" not in text


def test_badge_lists_cached_and_sample_sources_once_each():
    text = ui_overview.data_status(_signals(rainfall=_r("cached"), discharge=_r("cached"), alerts=_r("sample")))
    assert text.count("Open-Meteo (cached)") == 1 and "SACHET (sample)" in text


def test_badge_all_sample_is_sample():
    s = {k: _r("sample") for k in _signals()}
    assert ui_overview.data_status(s) == ui_overview.BADGES["sample"]


def test_scenario_reason_says_sample_sachet_alert():
    s = _signals(alerts=_r("sample", [{"headline": "x"}]))
    assert "sample SACHET alert" in scenario.derive_scenario(s)["reasons"][0]
    s = _signals(alerts=_r("live", [{"headline": "x"}]))
    assert "official SACHET alert" in scenario.derive_scenario(s)["reasons"][0]
