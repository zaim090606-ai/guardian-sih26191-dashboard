"""QA: every tab renders without exceptions in Sample mode and when every
network call fails (including Live Firestore mode falling back to samples)."""
import os

import pytest
import requests
from streamlit.testing.v1 import AppTest

import ui_live
from connectors import base

APP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")
TABS = ["Overview", "Map", "Evidence", "Relocation", "Impact of Ground Evidence", "Live Scenario",
        "Brief", "Scorecard", "Method & Limits"]


def _fail(*a, **k):
    raise requests.ConnectionError("mocked live failure")


def _check(at):
    assert not at.exception, [e.message for e in at.exception]
    assert [t.label for t in at.tabs] == TABS
    assert not at.error


@pytest.fixture
def clean(monkeypatch, tmp_path):
    ui_live.get_cached_signals.clear()
    monkeypatch.setattr(base, "CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


def test_all_tabs_render_in_sample_mode(clean):
    at = AppTest.from_file(APP_PATH, default_timeout=120).run()
    _check(at)
    assert at.sidebar.radio[0].value == "Sample data"


def test_all_tabs_render_when_live_calls_fail(clean, monkeypatch):
    monkeypatch.setattr(requests, "get", _fail)
    monkeypatch.setattr(requests.Session, "request", _fail)
    at = AppTest.from_file(APP_PATH, default_timeout=120).run()
    _check(at)  # connectors fall back to labelled samples
    at.sidebar.radio[0].set_value("Live Firestore").run()
    _check(at)
    assert any("Live Firestore read failed" in w.value for w in at.sidebar.warning)


def test_all_tabs_render_with_3d_on_and_live_failure(clean, monkeypatch):
    monkeypatch.setattr(requests, "get", _fail)
    monkeypatch.setattr(requests.Session, "request", _fail)
    at = AppTest.from_file(APP_PATH, default_timeout=120).run()
    at.sidebar.toggle[0].set_value(True).run()
    _check(at)
