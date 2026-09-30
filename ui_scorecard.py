"""Scorecard tab: SIH26191 requirement coverage, each marked Implemented /
Partial / Not. "Implemented" is only used once the referenced test in
tests/ has actually been run and passes — see BUILD_LOG.md Phase 5.1. This
table is static (computed when the tests were last run), not re-executed
live inside the app: running pytest on every Streamlit rerun would be slow,
and pytest is not a runtime dependency of the deployed app.
"""

import streamlit as st

REQUIREMENTS = [
    {
        "requirement": "Red Zones mapped and updated",
        "status": "Implemented",
        "notes": (
            "scoring.zone_risk_score() + zone_tier() (Red/Amber/Green). Re-scored live "
            "from the sidebar (hazard-scenario multiplier, weights, thresholds) and "
            "from Guardian evidence bonuses — \"updated\" means re-scored on every "
            "parameter change or incident-source switch, not a one-off static map."
        ),
        "test": "tests/test_scoring.py::test_zone_risk_score_thresholds",
    },
    {
        "requirement": "Carrying capacity",
        "status": "Implemented",
        "notes": "relocation.site_capacity() — slope/hazard-adjusted usable area divided by an adjustable space norm.",
        "test": "tests/test_relocation.py::test_site_capacity_reduced_by_slope_and_hazard",
    },
    {
        "requirement": "Relocation prioritisation (immediate / short-term / medium-term)",
        "status": "Implemented",
        "notes": (
            "scoring.relocation_priority_index() + rpi_tier(); "
            "relocation.greedy_allocate() ranks by RPI, allocates to the nearest site "
            "with capacity, and surfaces unallocated habitations separately."
        ),
        "test": "tests/test_relocation.py::test_greedy_allocate_respects_capacity_and_covers_every_habitation",
    },
    {
        "requirement": "Inputs: hazard / vulnerability / history",
        "status": "Implemented",
        "notes": (
            "All three are independent per-cell inputs from data_gen.py (hazard from "
            "invented hazard centers, vulnerability from a beta distribution plus a "
            "hazard-linked term, history from Poisson(hazard)) and are separately "
            "weighted in zone_risk_score()."
        ),
        "test": "tests/test_scoring.py::test_zone_risk_score_uses_all_three_inputs",
    },
    {
        "requirement": "Insights for the State Disaster Management Authority",
        "status": "Implemented",
        "notes": (
            "brief.py's Gemini/template briefing, generated only from computed "
            "numbers; the Impact tab's with/without-Guardian-evidence comparison is "
            "itself an insight — where ground truth changes the plan, and why."
        ),
        "test": "tests/test_pipeline_impact.py::test_compare_with_without_guardian_evidence_flags_a_tier_change",
    },
]

STATUS_ICON = {"Implemented": "🟢", "Partial": "🟡", "Not": "🔴"}


def render_scorecard_tab():
    st.caption(
        "Status is 'Implemented' only where the referenced automated test currently "
        "passes (see BUILD_LOG.md, Phase 5). Computed when the tests were last run, "
        "not re-executed live inside this app."
    )
    for req in REQUIREMENTS:
        icon = STATUS_ICON.get(req["status"], "⚪")
        st.markdown(f"**{icon} {req['requirement']}** — _{req['status']}_")
        st.caption(req["notes"])
        st.code(req["test"], language="text")
        st.divider()
