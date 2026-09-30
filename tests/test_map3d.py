import os

import pytest
from streamlit.testing.v1 import AppTest

import pipeline
import ui_map3d

pytestmark = pytest.mark.skipif(not ui_map3d.available(), reason="pydeck not installed")
APP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


def test_deck_has_columns_rings_and_arcs():
    res = pipeline.run_pipeline(review_state={})
    deck = ui_map3d.build_deck(res, pitch=40)
    kinds = [layer.type for layer in deck.layers]
    assert kinds.count("ColumnLayer") == 1 and kinds.count("ArcLayer") == 1 and kinds.count("ScatterplotLayer") == 2
    assert deck.initial_view_state.pitch == 40
    assert len(deck.layers[0].data) == len(res["grid"])


def test_3d_toggle_renders_and_falls_back_on_error(monkeypatch):
    at = AppTest.from_file(APP_PATH, default_timeout=90).run()
    assert not at.exception
    at.sidebar.toggle[0].set_value(True).run()
    assert not at.exception  # 3D path renders
    monkeypatch.setattr(ui_map3d, "build_deck", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    at2 = AppTest.from_file(APP_PATH, default_timeout=90).run()
    at2.sidebar.toggle[0].set_value(True).run()
    assert not at2.exception
    assert any("3D mode unavailable" in w.value for w in at2.warning)
