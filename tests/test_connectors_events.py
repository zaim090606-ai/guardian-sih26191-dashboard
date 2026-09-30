import pytest
import requests

from connectors import events

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


def test_fetch_earthquakes_live_success(monkeypatch):
    fake_data = {"type": "FeatureCollection", "features": []}
    monkeypatch.setattr(requests, "get", lambda *a, **kw: _FakeResponse(fake_data))
    result = events.fetch_earthquakes()
    assert result.status == "live"
    assert result.source == events.USGS_SOURCE


def test_fetch_earthquakes_falls_back_on_network_error(monkeypatch):
    def _raise(*a, **kw):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(requests, "get", _raise)
    result = events.fetch_earthquakes()
    assert result.status == "sample"
    assert result.data.get("illustrative") is True


def test_fetch_gdacs_events_filters_out_of_region_features(monkeypatch):
    # One feature inside the Chamoli bbox, one clearly outside (Mexico).
    fake_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [79.5, 30.4]},
                "properties": {"eventtype": "FL", "name": "In-region flood"},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-108.0, 30.5]},
                "properties": {"eventtype": "TC", "name": "Out-of-region cyclone"},
            },
        ],
    }
    monkeypatch.setattr(requests, "get", lambda *a, **kw: _FakeResponse(fake_data))
    result = events.fetch_gdacs_events()
    assert result.status == "live"
    names = [f["properties"]["name"] for f in result.data["features"]]
    assert names == ["In-region flood"]


def test_fetch_gdacs_events_falls_back_on_timeout(monkeypatch):
    def _raise(*a, **kw):
        raise requests.Timeout("too slow")

    monkeypatch.setattr(requests, "get", _raise)
    result = events.fetch_gdacs_events()
    assert result.status == "sample"


def test_events_in_region_merges_both_sources():
    usgs_data = {
        "features": [
            {
                "properties": {"mag": 4.1, "place": "near Joshimath", "time": 123, "url": "http://x"},
                "geometry": {"type": "Point", "coordinates": [79.5, 30.4, 5.0]},
            }
        ]
    }
    gdacs_data = {
        "features": [
            {
                "properties": {"eventtype": "FL", "name": "Flood", "alertlevel": "Orange"},
                "geometry": {"type": "Point", "coordinates": [79.6, 30.5]},
            }
        ]
    }
    merged = events.events_in_region(usgs_data, gdacs_data)
    assert len(merged) == 2
    assert {"USGS", "GDACS"} == {e["source"] for e in merged}


def test_events_in_region_handles_none_inputs():
    assert events.events_in_region(None, None) == []


def test_max_earthquake_magnitude():
    data = {"features": [{"properties": {"mag": 2.0}}, {"properties": {"mag": 5.5}}]}
    assert events.max_earthquake_magnitude(data) == 5.5


def test_max_earthquake_magnitude_no_features():
    assert events.max_earthquake_magnitude({"features": []}) == 0.0


def test_feature_in_region_uses_bbox_when_no_point_geometry():
    feature_inside = {"geometry": {}, "bbox": [79.4, 30.2, 79.6, 30.4]}
    feature_outside = {"geometry": {}, "bbox": [-109.0, 30.0, -107.0, 31.0]}
    assert events._feature_in_region(feature_inside) is True
    assert events._feature_in_region(feature_outside) is False
