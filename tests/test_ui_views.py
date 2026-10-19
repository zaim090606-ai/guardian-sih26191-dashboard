import pandas as pd

import palette
from ui import charts, kpi, views


def _hab():
    return pd.DataFrame({
        "habitation_id": ["H1", "H2", "H3"], "name": ["A", "B", "C"], "population": [100, 200, 300],
        "rpi": [90.0, 50.0, 10.0], "rpi_tier": ["immediate", "short-term", "medium-term"],
        "zone_score": [70.0, 40.0, 10.0], "vulnerability": [0.5, 0.4, 0.3],
    })


def test_tier_label_has_glyph_and_word():
    assert views.tier_label("immediate") == "▲ Immediate"
    assert views.tier_label("Amber") == "◆ Amber"
    assert views.tier_label("something else") == "something else"


def test_tier_pill_escapes_and_classes():
    assert "gd-pill-immediate" in views.tier_pill_html("immediate")
    assert "Immediate" in views.tier_pill_html("immediate")
    assert "gd-pill-short-term" in views.tier_pill_html("Amber")
    assert "&lt;b&gt;" in views.tier_pill_html("<b>")


def test_tier_colors_match_palette():
    assert views.tier_color("immediate") == palette.RED and views.tier_color("Green") == palette.GREEN
    assert views.tier_color("nope") is None


def test_prepare_table_labels_tiers_and_flags_bars_without_mutating_input():
    df = _hab()
    shown, spec = views.prepare_table(df)
    assert shown["rpi_tier"].tolist() == ["▲ Immediate", "◆ Short-term", "● Medium-term"]
    assert df["rpi_tier"].tolist()[0] == "immediate"
    assert spec["rpi"]["bar"] == (0, 100, "%.1f") and spec["rpi"]["label"] == "Priority index"
    assert spec["name"]["bar"] is None


def _result():
    grid = pd.DataFrame({"zone_tier": ["Red", "Amber", "Amber", "Green"]})
    return {"habitations": _hab(), "grid": grid, "incidents": pd.DataFrame({"a": [1, 2]}),
            "unlocated_stats": {"count": 3}, "region_comms_degraded": 2}


def test_build_kpis_numbers_come_from_data():
    k = kpi.build_kpis(_result())
    assert [c["value"] for c in k] == [3, 100, 1, 5]
    assert [b["value"] for b in k[0]["bars"]] == [1, 1, 1]
    assert [b["value"] for b in k[2]["bars"]] == [1, 2, 1]
    assert k[3]["note"].startswith("2 arrived")


def test_kpi_html_prerenders_final_numbers_and_respects_reduced_motion():
    html = kpi.build_kpi_html(kpi.build_kpis(_result()))
    assert 'data-final="100">100<' in html  # static fallback shows the final number
    assert "prefers-reduced-motion" in html and "<svg" in html


def test_charts_build_with_tier_colors_and_tooltips():
    spec = charts.rpi_bar_chart(_hab()).to_dict()
    assert "tooltip" in str(spec) and palette.RED in str(spec)
    cap = pd.DataFrame({"name": ["S1"], "capacity_people": [100], "allocated_people": [40]})
    assert "Remaining" in str(charts.capacity_chart(cap).to_dict())
    inc = pd.DataFrame({"incident_id": ["I1"], "riskLevel": ["HIGH"], "eventType": ["x"], "ecs": [0.5]})
    assert charts.ecs_chart(inc).to_dict()
