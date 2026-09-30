import os

import pytest
import requests

from connectors import sachet

pytestmark = pytest.mark.usefixtures("isolated_connector_cache")

CHAMOLI_CAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>IN-NDMA-2026-000123</identifier>
  <sender>ndma@nic.in</sender>
  <sent>2026-09-30T06:00:00+05:30</sent>
  <info>
    <event>Flood Warning</event>
    <headline>Flood warning for Chamoli district, Uttarakhand</headline>
    <description>Heavy rainfall expected to raise river levels.</description>
    <severity>Severe</severity>
    <urgency>Expected</urgency>
    <certainty>Likely</certainty>
    <effective>2026-09-30T06:00:00+05:30</effective>
    <expires>2026-10-01T06:00:00+05:30</expires>
    <web>https://sachet.ndma.gov.in/</web>
    <area>
      <areaDesc>Chamoli district, Uttarakhand</areaDesc>
    </area>
  </info>
</alert>"""

CHENNAI_CAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>IN-NDMA-2026-000456</identifier>
  <sender>ndma@nic.in</sender>
  <sent>2026-09-30T06:00:00+05:30</sent>
  <info>
    <event>Heavy Rain Warning</event>
    <headline>Heavy rain warning for Chennai, Tamil Nadu</headline>
    <description>Monsoon rainfall expected to cause urban waterlogging.</description>
    <severity>Moderate</severity>
    <urgency>Expected</urgency>
    <certainty>Likely</certainty>
    <effective>2026-09-30T06:00:00+05:30</effective>
    <expires>2026-10-01T06:00:00+05:30</expires>
    <web>https://sachet.ndma.gov.in/</web>
    <area>
      <areaDesc>Chennai district, Tamil Nadu</areaDesc>
    </area>
  </info>
</alert>"""


class _FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


def test_parse_cap_xml_extracts_all_fields():
    records = sachet.parse_cap_xml(CHAMOLI_CAP_XML)
    assert len(records) == 1
    r = records[0]
    assert r["identifier"] == "IN-NDMA-2026-000123"
    assert r["event"] == "Flood Warning"
    assert r["headline"] == "Flood warning for Chamoli district, Uttarakhand"
    assert r["severity"] == "Severe"
    assert r["area_desc"] == "Chamoli district, Uttarakhand"


def test_parse_cap_xml_handles_garbage_without_raising():
    assert sachet.parse_cap_xml("not xml at all <<<") == []
    assert sachet.parse_cap_xml("") == []
    assert sachet.parse_cap_xml(None) == []


def test_filter_alerts_to_region_keeps_matching_drops_others():
    chamoli_records = sachet.parse_cap_xml(CHAMOLI_CAP_XML)
    chennai_records = sachet.parse_cap_xml(CHENNAI_CAP_XML)

    kept = sachet.filter_alerts_to_region(chamoli_records)
    dropped = sachet.filter_alerts_to_region(chennai_records)

    assert len(kept) == 1
    assert len(dropped) == 0


def test_fetch_active_alerts_live_success(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **kw: _FakeResponse(CHAMOLI_CAP_XML))
    result = sachet.fetch_active_alerts()
    assert result.status == "live"
    assert len(result.data) == 1


def test_fetch_active_alerts_falls_back_on_network_error(monkeypatch):
    def _raise(*a, **kw):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(requests, "get", _raise)
    result = sachet.fetch_active_alerts()
    assert result.status == "sample"
    assert len(result.data) == 1
    assert "ILLUSTRATIVE" in result.data[0]["headline"]


def test_fetch_active_alerts_falls_back_when_response_has_no_parseable_alerts(monkeypatch):
    # A 200 OK with unparseable/empty content must still fall back safely,
    # not return an empty live result silently.
    monkeypatch.setattr(requests, "get", lambda *a, **kw: _FakeResponse("<html>not CAP</html>"))
    result = sachet.fetch_active_alerts()
    assert result.status == "sample"


def test_fetch_alerts_for_region_filters_sample_fallback_too(monkeypatch):
    def _raise(*a, **kw):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(requests, "get", _raise)
    result = sachet.fetch_alerts_for_region()
    assert result.status == "sample"
    # sample data is itself always region-labelled, so filtering must not drop it
    assert len(result.data) == 1
    assert "chamoli" in result.data[0]["area_desc"].lower()


def test_summarize_alert_text_no_key_returns_raw_text():
    alert = {"headline": "Flood warning", "description": "Rivers rising."}
    summary = sachet.summarize_alert_text(alert, api_key=None)
    assert summary == "Flood warning Rivers rising."


def test_summarize_alert_text_empty_alert_returns_placeholder():
    assert sachet.summarize_alert_text({}, api_key=None) == "(no alert text)"


def test_summarize_alert_text_never_raises_on_bad_key():
    alert = {"headline": "Flood warning", "description": "Rivers rising."}
    # An invalid key must fall back to the raw text, not raise.
    summary = sachet.summarize_alert_text(alert, api_key="not-a-real-key")
    assert "Flood warning" in summary


with open(os.path.join(os.path.dirname(__file__), "data", "sachet_rss_sample.xml"), encoding="utf-8") as _f:
    RSS_SAMPLE = _f.read()


def test_configured_feed_url_reads_first_line_and_rejects_non_http(tmp_path):
    f = tmp_path / "u.txt"
    f.write_text("\nhttps://example.invalid/feed.xml\n", encoding="utf-8")
    assert sachet.configured_feed_url(str(f)) == "https://example.invalid/feed.xml"
    f.write_text("javascript:alert(1)", encoding="utf-8")
    assert sachet.configured_feed_url(str(f)) is None
    assert sachet.configured_feed_url(str(tmp_path / "missing.txt")) is None


def test_parse_rss_sample_and_region_filter():
    items = sachet.parse_rss_items(RSS_SAMPLE)
    assert len(items) == 2 and items[0]["identifier"] == "SAMPLE-1"
    kept = sachet.filter_alerts_to_region(items)
    assert [a["identifier"] for a in kept] == ["SAMPLE-1"]


class _Resp:
    def __init__(self, status=200, text=RSS_SAMPLE, etag='"v1"'):
        self.status_code, self.text = status, text
        self.headers = {"ETag": etag} if etag else {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


@pytest.fixture
def feed(monkeypatch, tmp_path):
    """Configured feed URL, a controllable clock and a request recorder."""
    f = tmp_path / "u.txt"
    f.write_text("https://example.invalid/rss.xml", encoding="utf-8")
    monkeypatch.setattr(sachet, "FEED_URL_FILE", str(f))
    clock = {"t": 1_000_000.0}
    monkeypatch.setattr(sachet.time, "time", lambda: clock["t"])
    calls, queue = [], []

    def fake_get(url, headers=None, timeout=None):
        calls.append({"url": url, "headers": dict(headers or {})})
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(sachet.requests, "get", fake_get)
    return type("F", (), {"clock": clock, "calls": calls, "queue": queue})


def test_first_request_uses_honest_user_agent_and_no_etag(feed):
    feed.queue.append(_Resp())
    res = sachet.fetch_alerts_for_region()
    assert res.status == "live" and [a["identifier"] for a in res.data] == ["SAMPLE-1"]
    h = feed.calls[0]["headers"]
    assert h["User-Agent"] == "GuardianSIH-Prototype/1.0 (student hackathon project)"
    assert "If-None-Match" not in h and set(h) == {"User-Agent"}  # no browser spoofing


def test_second_poll_sends_stored_etag_and_304_reuses_copy(feed):
    feed.queue.append(_Resp())
    sachet.fetch_active_alerts()
    feed.clock["t"] += sachet.MIN_POLL_INTERVAL_S + 1
    feed.queue.append(_Resp(304, text="", etag=None))
    res = sachet.fetch_active_alerts()
    assert feed.calls[1]["headers"]["If-None-Match"] == '"v1"'
    assert res.status == "live" and len(res.data) == 2 and "304" in res.source


def test_200_replaces_stored_copy_and_etag(feed):
    feed.queue.append(_Resp())
    sachet.fetch_active_alerts()
    feed.clock["t"] += sachet.MIN_POLL_INTERVAL_S + 1
    new = RSS_SAMPLE.replace("SAMPLE-2", "SAMPLE-3")
    feed.queue.append(_Resp(200, text=new, etag='"v2"'))
    sachet.fetch_active_alerts()
    feed.clock["t"] += sachet.MIN_POLL_INTERVAL_S + 1
    feed.queue.append(_Resp(304, text="", etag=None))
    res = sachet.fetch_active_alerts()
    assert feed.calls[2]["headers"]["If-None-Match"] == '"v2"'
    assert {a["identifier"] for a in res.data} == {"SAMPLE-1", "SAMPLE-3"}


def test_never_polls_more_than_every_10_minutes(feed):
    feed.queue.append(_Resp())
    sachet.fetch_active_alerts()
    feed.clock["t"] += 599
    res = sachet.fetch_active_alerts()
    assert len(feed.calls) == 1 and res.status == "cached" and len(res.data) == 2


def test_403_falls_back_to_stored_copy_without_retrying(feed):
    feed.queue.append(_Resp())
    sachet.fetch_active_alerts()
    feed.clock["t"] += sachet.MIN_POLL_INTERVAL_S + 1
    feed.queue.append(_Resp(403, text="", etag=None))
    res = sachet.fetch_active_alerts()
    assert res.status == "cached" and "403" in res.error and len(res.data) == 2
    feed.clock["t"] += 5  # an immediate second attempt must not hit the network
    sachet.fetch_active_alerts()
    assert len(feed.calls) == 2


def test_error_without_stored_copy_is_labelled_sample_and_not_retried(feed):
    feed.queue.append(requests.ConnectionError("down"))
    res = sachet.fetch_active_alerts()
    assert res.status == "sample" and "sample" in res.source and res.error
    feed.clock["t"] += 30
    assert sachet.fetch_active_alerts().status == "sample"
    assert len(feed.calls) == 1


def test_stored_copy_older_than_a_day_is_not_shown_as_current(feed):
    feed.queue.append(_Resp())
    sachet.fetch_active_alerts()
    feed.clock["t"] += sachet.STORED_COPY_MAX_AGE_S + 60
    feed.queue.append(requests.ConnectionError("down"))
    assert sachet.fetch_active_alerts().status == "sample"


def test_latest_alerts_sorted_newest_first_capped_and_script_language():
    alerts = [{"identifier": str(i), "sent": f"Tue, {i:02d} Sep 2026 09:00:00 GMT"} for i in range(1, 26)]
    top = sachet.latest_alerts(alerts, 20)
    assert len(top) == 20 and top[0]["identifier"] == "25" and top[-1]["identifier"] == "6"
    assert sachet.detect_script_language("మీ ప్రాంతంలో పిడుగులు") == "Telugu"
    assert sachet.detect_script_language("Heavy rain warning") == "English/Latin script"
