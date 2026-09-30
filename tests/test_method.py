import ui_method


def test_comparison_covers_all_tools_and_hedges_every_gap():
    names = " ".join(r["Approach"] for r in ui_method.COMPARISON_ROWS)
    for tool in ("Ushahidi", "InaSAFE", "Sahana", "SACHET", "GSI", "Bridgefy"):
        assert tool in names
    assert all("as far as we found" in r["Gap (as far as we found)"] or "we found no" in r["Gap (as far as we found)"]
               for r in ui_method.COMPARISON_ROWS)
    inasafe = next(r for r in ui_method.COMPARISON_ROWS if r["Approach"] == "InaSAFE")
    assert "external hazard and exposure data" in inasafe["Gap (as far as we found)"]


def test_limits_listed():
    t = ui_method.METHOD_TEXT.lower()
    for phrase in ("unauthenticated", "nearby participating guardian devices", "pdr is an estimate",
                   "all data is illustrative", "no validation against real events"):
        assert phrase in t
