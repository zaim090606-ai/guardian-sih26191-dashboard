from connectors import scenario
from connectors.base import FetchResult


def _result(status, data):
    return FetchResult(status=status, data=data, fetched_at="2026-01-01T00:00:00+00:00", source="test")


def _calm_signals():
    return {
        "rainfall": _result("live", {"hourly": {"precipitation": [0.0] * 24}}),
        "discharge": _result("live", {"daily": {"river_discharge": [1.0, 1.0, 1.0]}}),
        "elevation": _result("live", {"elevations": [1000.0] * 5, "offset_deg": 0.01}),
        "alerts": _result("live", []),
        "quakes": _result("live", {"features": []}),
        "gdacs": _result("live", {"features": []}),
    }


def test_derive_scenario_calm_signals_gives_baseline_multiplier():
    result = scenario.derive_scenario(_calm_signals())
    assert result["multiplier"] == scenario.DEFAULT_MULTIPLIER
    assert not any(result["triggers"].values())
    assert "No live signal crossed its threshold" in result["reasons"][0]


def test_derive_scenario_heavy_rain_raises_multiplier():
    signals = _calm_signals()
    signals["rainfall"] = _result("live", {"hourly": {"precipitation": [10.0] * 24}})
    result = scenario.derive_scenario(signals)
    assert result["triggers"]["heavy_rain"] is True
    assert result["multiplier"] > scenario.DEFAULT_MULTIPLIER
    assert any("Heavy rain" in r for r in result["reasons"])


def test_derive_scenario_active_alert_from_sachet_or_gdacs():
    signals = _calm_signals()
    signals["alerts"] = _result("sample", [{"headline": "x"}])
    result = scenario.derive_scenario(signals)
    assert result["triggers"]["active_alert"] is True


def test_derive_scenario_multiplier_is_capped():
    # Trip every signal at once; the sum of all weights exceeds
    # MAX_MULTIPLIER - DEFAULT_MULTIPLIER, so this must clip, not overshoot.
    signals = {
        "rainfall": _result("live", {"hourly": {"precipitation": [100.0] * 24}}),
        "discharge": _result("live", {"daily": {"river_discharge": [999.0]}}),
        "elevation": _result("live", {"elevations": [1000.0, 5000.0, 1000.0, 1000.0, 1000.0], "offset_deg": 0.01}),
        "alerts": _result("live", [{"headline": "x"}]),
        "quakes": _result("live", {"features": [{"properties": {"mag": 7.0}}]}),
        "gdacs": _result("live", {"features": [{"properties": {}}]}),
    }
    result = scenario.derive_scenario(signals)
    assert result["multiplier"] == scenario.MAX_MULTIPLIER
    assert all(result["triggers"].values())


def test_derive_scenario_never_raises_on_missing_data():
    empty_result = _result("sample", None)
    signals = {k: empty_result for k in ["rainfall", "discharge", "elevation", "alerts", "quakes", "gdacs"]}
    result = scenario.derive_scenario(signals)
    assert result["multiplier"] == scenario.DEFAULT_MULTIPLIER


def test_derive_scenario_reports_data_sources_status():
    signals = _calm_signals()
    signals["alerts"] = _result("cached", [])
    result = scenario.derive_scenario(signals)
    assert result["data_sources"]["alerts"] == "cached"
    assert result["data_sources"]["rainfall"] == "live"


def test_effective_multiplier_no_override_uses_derived():
    assert scenario.effective_multiplier(1.3, override=None) == 1.3


def test_effective_multiplier_override_always_wins():
    assert scenario.effective_multiplier(1.3, override=0.7) == 0.7
    assert scenario.effective_multiplier(1.3, override=2.0) == 2.0
