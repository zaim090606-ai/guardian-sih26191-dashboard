"""The dashboard must start with no .env, no API key and no network."""
import os

import requests
from streamlit.testing.v1 import AppTest

APP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


def test_app_runs_offline_without_env(monkeypatch, isolated_connector_cache):
    def _no_network(*a, **k):
        raise requests.ConnectionError("network disabled for test")

    monkeypatch.setattr(requests, "get", _no_network)
    monkeypatch.setattr(requests.Session, "request", _no_network)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    at = AppTest.from_file(APP_PATH, default_timeout=90).run()
    assert not at.exception
    assert len(at.tabs) >= 8
    assert at.sidebar.radio[0].value == "Sample data"  # Sample mode by default
