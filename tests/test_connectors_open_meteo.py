import pytest
import requests

from connectors import open_meteo as om

pytestmark = pytest.mark.usefixtures("isolated_connector_cache")


class _FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")

    def json(self):
        return self._json_data


def test_fetch_rainfall_forecast_live_success(monkeypatch):
    fake_data = {"hourly": {"time": ["t0", "t1"], "precipitation": [1.0, 2.0]}}
    monkeypatch.setattr(requests, "get", lambda *a, **kw: _FakeResponse(fake_data))

    result = om.fetch_rainfall_forecast(30.5, 79.5)
    assert result.status == "live"
    assert result.source == om.SOURCE_ATTRIBUTION
    assert result.data == fake_data


def test_fetch_rainfall_forecast_falls_back_to_sample_on_network_error(monkeypatch):
    def _raise(*a, **kw):
        raise requests.ConnectionError("no network")

    monkeypatch.setattr(requests, "get", _raise)
    result = om.fetch_rainfall_forecast(30.5, 79.5)
    assert result.status == "sample"
    assert result.data.get("illustrative") is True
    assert result.error is not None


def test_fetch_rainfall_forecast_falls_back_on_http_error(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **kw: _FakeResponse({}, status_code=500))
    result = om.fetch_rainfall_forecast(30.5, 79.5)
    assert result.status == "sample"


def test_fetch_river_discharge_live_success(monkeypatch):
    fake_data = {"daily": {"time": ["d0"], "river_discharge": [5.0]}}
    monkeypatch.setattr(requests, "get", lambda *a, **kw: _FakeResponse(fake_data))
    result = om.fetch_river_discharge(30.5, 79.5)
    assert result.status == "live"
    assert om.peak_river_discharge(result.data, 1) == 5.0


def test_fetch_elevation_slope_live_success(monkeypatch):
    fake_data = {"elevation": [1800.0, 1900.0, 1700.0, 1800.0, 1800.0]}
    monkeypatch.setattr(requests, "get", lambda *a, **kw: _FakeResponse(fake_data))
    result = om.fetch_elevation_slope(30.5, 79.5)
    assert result.status == "live"
    slope = om.max_slope_degrees(result.data)
    assert slope > 0


def test_total_precipitation_mm_sums_window():
    data = {"hourly": {"precipitation": [1.0, 2.0, 3.0, 100.0]}}
    assert om.total_precipitation_mm(data, hours=3) == 6.0


def test_total_precipitation_mm_handles_missing_data():
    assert om.total_precipitation_mm({}, hours=24) == 0.0
    assert om.total_precipitation_mm(None, hours=24) == 0.0


def test_peak_river_discharge_handles_missing_data():
    assert om.peak_river_discharge({}, days=3) == 0.0


def test_max_slope_degrees_flat_terrain_is_zero():
    data = {"elevations": [1000.0, 1000.0, 1000.0, 1000.0, 1000.0], "offset_deg": 0.01}
    assert om.max_slope_degrees(data) == 0.0


def test_max_slope_degrees_handles_missing_data():
    assert om.max_slope_degrees({}) == 0.0
