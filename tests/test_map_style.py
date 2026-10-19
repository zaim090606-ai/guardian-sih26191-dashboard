import pandas as pd

import ui_map


def test_habitation_popup_has_name_tier_rpi_why_and_escapes():
    row = pd.Series({"name": "<b>X</b>", "rpi_tier": "immediate", "rpi": 88.0, "zone_score": 70.0,
                     "vulnerability": 0.4, "population": 1234})
    html = ui_map._habitation_popup(row)
    assert "&lt;b&gt;X" in html and "Immediate" in html and "88.0" in html and "1,234 residents" in html


def test_tier_legend_lists_all_three_tiers_by_label():
    html = ui_map._tier_legend_html()
    assert all(w in html for w in ("Immediate", "Short-term", "Medium-term"))
