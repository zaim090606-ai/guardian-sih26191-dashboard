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
    allowed = {"rank", "label", "rpi", "tier", "tier_label", "color", "x", "y"}
    assert all(set(pt) == allowed for pt in p["points"])
    blob = json.dumps(p)
    assert "9999" not in blob and "Someone" not in blob and "population" not in blob


def test_html_has_caption_pinned_cdn_and_escapes_payload():
    df = _df().assign(name=["</script><b>", "B", "C", "D"])
    html = hero.build_hero_html(hero.build_hero_payload(df, 4))
    assert hero.CAPTION in html
    assert "cdnjs.cloudflare.com/ajax/libs/three.js/0.160.0/three.min.js" in html
    assert "</script><b>" not in html
    for banned in ("document.cookie", "localStorage", "sessionStorage", "window.parent", "window.top"):
        assert banned not in html
    assert "prefers-reduced-motion" in html and "IntersectionObserver" in html
