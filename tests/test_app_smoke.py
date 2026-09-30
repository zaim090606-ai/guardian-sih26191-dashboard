import os

from streamlit.testing.v1 import AppTest

APP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


def test_app_loads_without_exceptions():
    at = AppTest.from_file(APP_PATH)
    # Generous timeout: the sidebar now calls ui_live.get_derived_scenario()
    # on every load, which fetches all Phase 6 connectors live (GDACS alone
    # measured ~13-20s in BUILD_LOG.md's Phase 6 notes).
    at.run(timeout=90)
    assert not at.exception
    assert len(at.tabs) == 9


def test_overview_tab_renders_first():
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=90)
    assert not at.exception
    overview = at.tabs[0]
    assert overview.label == "Overview"
    assert any("Red Zones planned from above. Distress confirmed from the ground." in m.value
               for m in overview.markdown)
    assert len(overview.metric) == 6  # 3 tiers + Red cells, incidents, comms-degraded
    assert any(m.value.startswith("Data status:") for m in overview.markdown)


def test_app_generate_brief_button_works():
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=90)
    buttons = [b for b in at.button if b.key == "generate_brief_button"]
    assert buttons
    buttons[0].click().run(timeout=90)
    assert not at.exception
    assert len(at.text) >= 1


def test_app_live_refresh_button_works():
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=90)
    buttons = [b for b in at.button if b.key == "live_refresh_button"]
    assert buttons
    buttons[0].click().run(timeout=90)
    assert not at.exception
