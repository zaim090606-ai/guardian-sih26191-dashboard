import json

import pandas as pd

import palette
from ui import hero


def _df():
    return pd.DataFrame({
        "habitation_id": ["H1", "H2", "H3", "H4"],
        "name": ["Alpha", "Beta", "Gamma", "Delta"],
        "population": [100, 200, 300, 400],
        "rpi": [10.0, 95.0, 60.0, 30.0],
        "rpi_tier": ["medium-term", "immediate", "short-term", "medium-term"],
        "lat": [30.0, 30.2, 30.4, 30.6],
        "lon": [78.0, 78.1, 78.2, 78.3],
    })


def test_top_n_sorted_by_rpi():
    p = hero.build_hero_payload(_df(), 2)
    assert [pt["label"] for pt in p["points"]] == ["Beta", "Gamma"]
    assert [pt["rank"] for pt in p["points"]] == [1, 2]


def test_tier_colors_match_palette():
    p = hero.build_hero_payload(_df(), 4)
    by = {pt["label"]: pt for pt in p["points"]}
    assert by["Beta"]["color"] == palette.RED
    assert by["Gamma"]["color"] == palette.AMBER
    assert by["Delta"]["color"] == palette.GREEN
    assert {l["color"] for l in p["legend"]} == {palette.RED, palette.AMBER, palette.GREEN}


def test_positions_normalised_and_tier_derived_when_missing():
    df = _df().drop(columns=["rpi_tier"])
    p = hero.build_hero_payload(df, 4)
    assert all(0 <= pt["x"] <= 1 and 0 <= pt["y"] <= 1 for pt in p["points"])
    assert {pt["label"]: pt["tier"] for pt in p["points"]}["Beta"] == "immediate"


def test_empty_and_missing_columns():
    assert hero.build_hero_payload(pd.DataFrame(), 5)["points"] == []
    assert hero.build_hero_payload(None)["points"] == []
    assert hero.build_hero_payload(pd.DataFrame({"name": ["x"]}), 5)["points"] == []
    assert hero.build_hero_payload(_df(), 0)["points"] == []
    sparse = pd.DataFrame({"rpi": [5.0, float("nan"), 80.0]})
    pts = hero.build_hero_payload(sparse, 5)["points"]
    assert [pt["rpi"] for pt in pts] == [80.0, 5.0]
    assert all(0 <= pt["x"] <= 1 for pt in pts)


def test_no_personal_or_extra_fields():
    df = _df().assign(phone="9999", contact_name="Someone")
    p = hero.build_hero_payload(df, 4)
    allowed = {"rank", "label", "rpi", "tier", "tier_label", "color", "x", "y", "id", "glyph", "why"}
    assert all(set(pt) == allowed for pt in p["points"])
    blob = json.dumps(p)
    assert "9999" not in blob and "Someone" not in blob


def test_point_has_id_glyph_and_why_from_real_row():
    df = _df().assign(zone_score=[10.0, 72.4, 50.0, 20.0], vulnerability=[0.2, 0.47, 0.3, 0.1],
                      buffer_applied=[False, True, False, False])
    top = hero.build_hero_payload(df, 1)["points"][0]
    assert top["id"] == "H2" and top["glyph"] == hero.TIER_GLYPHS["immediate"]
    assert "Zone score 72/100" in top["why"] and "vulnerability 0.47" in top["why"]
    assert "200 residents" in top["why"] and "buffer uplift" in top["why"]


def test_why_line_degrades_gracefully():
    assert hero.why_line({}).startswith("Ranked by Relocation Priority Index")
    assert hero.why_line({"zone_score": float("nan"), "population": None}).startswith("Ranked")


def test_apply_selection_once_per_click_and_only_valid_ids():
    state = {}
    ids = ["H1", "H2"]
    assert hero.apply_selection(state, {"id": "H2", "n": "a"}, ids) is True
    assert state["selected_hab"] == "H2" and state["dr_hab"] == "H2" and state["inspect_hab"] == "H2"
    assert state["dr_kind"] == "Habitation"
    assert hero.apply_selection(state, {"id": "H1", "n": "a"}, ids) is False  # same click replayed
    assert state["selected_hab"] == "H2"
    assert hero.apply_selection(state, {"id": "nope", "n": "b"}, ids) is False
    assert hero.apply_selection(state, None, ids) is False
    assert hero.apply_selection(state, {"id": "H1", "n": "c"}, ids) is True and state["selected_hab"] == "H1"


def test_html_has_caption_pinned_cdn_and_escapes_payload():
    df = _df().assign(name=["</script><b>", "B", "C", "D"])
    html = hero.build_hero_html(hero.build_hero_payload(df, 4))
    assert hero.CAPTION in html
    assert "cdnjs.cloudflare.com/ajax/libs/three.js/0.160.0/three.min.js" in html
    assert "</script><b>" not in html
    for banned in ("document.cookie", "localStorage", "sessionStorage", "window.parent", "window.top", "eval("):
        assert banned not in html
    assert "prefers-reduced-motion" in html and "IntersectionObserver" in html


def test_component_file_pins_same_three_url_and_sri_and_has_interaction_features():
    html = hero._template()
    assert hero.THREE_URL in html and hero.THREE_SRI in html
    assert "window.__HERO__=null;" in html  # placeholder the fallback embed replaces
    for needle in ("streamlit:componentReady", "streamlit:setComponentValue", "streamlit:render",
                   "Reset view", "pointerdown", "wheel", "devicePixelRatio", "visibilitychange"):
        assert needle in html
    # the only call toward the parent page is the Streamlit postMessage channel
    assert html.count("parent.") == 1 and "parent.postMessage" in html


def test_fallback_html_embeds_payload_and_no_placeholder_left():
    html = hero.build_hero_html({"points": [], "legend": [], "caption": "x"})
    assert "window.__HERO__={" in html and "window.__HERO__=null;" not in html


def _script_count(html):
    return html.lower().count("<script"), html.lower().count("</script")


def test_embedded_payload_cannot_break_out_of_script_tag():
    base = hero.build_hero_html(hero.build_hero_payload(_df(), 4))
    evil = "</script><script>alert(1)</script>"
    html = hero.build_hero_html(hero.build_hero_payload(_df().assign(name=[evil, "B", "C", "D"]), 4))
    assert _script_count(html) == _script_count(base)
    assert "alert(1)</script>" not in html and "</script><script>alert" not in html
    start = html.index("window.__HERO__={")
    payload_line = html[start:html.index("</script>", start)]
    assert "<" not in payload_line and ">" not in payload_line
    assert "\\u003c/script\\u003e" in payload_line


def test_payload_escapes_quotes_ampersands_unicode_and_line_separators():
    tricky = 'Ra"m & <Sons> \u2028\u2029 \u0928\u093e\u092e \'x\''
    payload = hero.build_hero_payload(_df().assign(name=[tricky, "B", "C", "D"]), 4)
    text = hero.safe_json(payload)
    for raw in ("<", ">", "&", "\u2028", "\u2029"):
        assert raw not in text
    back = json.loads(text)  # escaping is lossless
    labels = [p["label"] for p in back["points"]]
    assert [l for l in labels if l.startswith("Ra")] == [tricky.strip()[:40]]
    html = hero.build_hero_html(payload)
    assert "\u2028" not in html and "\u2029" not in html


def test_component_js_never_writes_data_with_innerhtml():
    import re
    js = hero._template()
    for m in re.finditer(r"innerHTML\s*=\s*([^;]*);", js):
        assert m.group(1).strip() == "''"
