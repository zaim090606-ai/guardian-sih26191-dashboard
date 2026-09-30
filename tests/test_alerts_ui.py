import os

import requests
from streamlit.testing.v1 import AppTest

import ui_live
from connectors import base, sachet

APP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


def _rss(n, chamoli=False):
    items = "".join(
        f"<item><title>Alert {i}{' Chamoli' if chamoli and i == 1 else ''}</title><description>text {i}</description>"
        f"<link>https://sachet.ndma.gov.in/x/{i}</link><guid>G{i}</guid>"
        f"<pubDate>Tue, {i:02d} Sep 2026 09:00:00 GMT</pubDate></item>" for i in range(1, n + 1))
    return f"<rss version='2.0'><channel>{items}</channel></rss>"


class _R:
    status_code = 200
    headers = {"ETag": '"x"'}

    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


def _run(monkeypatch, tmp_path, text):
    ui_live.get_cached_signals.clear()  # st.cache_data would otherwise reuse the previous test's feed
    monkeypatch.setattr(base, "CACHE_DIR", str(tmp_path))
    f = tmp_path / "u.txt"
    f.write_text("https://example.invalid/rss.xml", encoding="utf-8")
    monkeypatch.setattr(sachet, "FEED_URL_FILE", str(f))
    real_get = requests.get
    monkeypatch.setattr(requests, "get",
                        lambda url, **k: _R(text) if "example.invalid" in url else (_ for _ in ()).throw(requests.ConnectionError("off")))
    at = AppTest.from_file(APP_PATH, default_timeout=90).run()
    monkeypatch.setattr(requests, "get", real_get)
    return at


def test_all_india_list_collapsed_shows_20_and_no_region_message(monkeypatch, tmp_path):
    at = _run(monkeypatch, tmp_path, _rss(25))
    assert not at.exception
    exp = [e for e in at.expander if e.label == "All-India alerts (latest 20)"]
    assert exp and not exp[0].proto.expanded
    assert any("No active alert for this region" in i.value for i in at.info)
    body = " ".join(m.value for m in exp[0].markdown)
    assert "Alert 25" in body and "Alert 6" in body and "Alert 5**" not in body


def test_region_match_count_shown(monkeypatch, tmp_path):
    at = _run(monkeypatch, tmp_path, _rss(3, chamoli=True))
    assert not at.exception
    assert not any("No active alert for this region" in i.value for i in at.info)
    assert any(m.label == "Alerts matching the demo region" and m.value == "1" for m in at.metric)
