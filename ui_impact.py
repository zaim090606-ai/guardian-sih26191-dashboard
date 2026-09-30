"""Phase 4b: "Impact of ground evidence" tab. Runs the pipeline twice (same
weights/thresholds, Guardian evidence off vs on) and shows the zone map,
relocation tier counts, and which habitations changed tier and why. This
isolates what the ground-evidence layer alone changes, independent of the
main sidebar's own "include Guardian evidence" toggle.
"""

import streamlit as st
from streamlit_folium import st_folium

import pipeline
import ui_map


def render_impact_tab(sidebar_params):
    st.caption(
        "Same weights, thresholds, and incident data, run twice: once ignoring all "
        "Guardian ground reports, once including them. This isolates what the ground "
        "evidence layer alone changes — independent of the sidebar's own toggle."
    )

    overrides = {k: v for k, v in sidebar_params.items() if k != "include_guardian_evidence"}
    with_result, without_result, changes = pipeline.compare_with_without_guardian_evidence(**overrides)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Without Guardian evidence")
        _render_tier_summary(without_result)
        fmap = ui_map.build_folium_map(
            without_result["grid"], without_result["habitations"], without_result["sites_after"], without_result["incidents"]
        )
        st_folium(fmap, height=360, use_container_width=True, key="impact_map_without", returned_objects=[])

    with col2:
        st.subheader("With Guardian evidence")
        _render_tier_summary(with_result)
        fmap = ui_map.build_folium_map(
            with_result["grid"], with_result["habitations"], with_result["sites_after"], with_result["incidents"]
        )
        st_folium(fmap, height=360, use_container_width=True, key="impact_map_with", returned_objects=[])

    st.subheader("Habitations that changed relocation tier")
    if changes.empty:
        st.info(
            "No habitation crossed a tier boundary on this run. Guardian evidence still "
            "nudges zone scores (see the Map tab's cell breakdown for "
            "guardian_evidence_bonus / comms_degraded_bonus) — try raising the evidence "
            "bonus cap in the sidebar to see a bigger effect."
        )
        return

    for _, row in changes.iterrows():
        with st.expander(
            f"{row['name']} ({row['habitation_id']}): "
            f"{row['tier_without_evidence']} -> {row['tier_with_evidence']}"
        ):
            c1, c2 = st.columns(2)
            with c1:
                st.metric("Zone score (without)", f"{row['zone_score_without_evidence']:.1f}")
                st.metric("RPI (without)", f"{row['rpi_without_evidence']:.1f}")
            with c2:
                st.metric("Zone score (with)", f"{row['zone_score_with_evidence']:.1f}")
                st.metric("RPI (with)", f"{row['rpi_with_evidence']:.1f}")
            st.write("**Why (with-evidence RPI breakdown):**")
            st.json(row["why"])


def _render_tier_summary(result):
    tiers = result["habitations"]["rpi_tier"].value_counts()
    zone_tiers = result["grid"]["zone_tier"].value_counts()
    m1, m2, m3 = st.columns(3)
    m1.metric("Immediate", int(tiers.get("immediate", 0)))
    m2.metric("Short-term", int(tiers.get("short-term", 0)))
    m3.metric("Medium-term", int(tiers.get("medium-term", 0)))
    st.caption(
        f"Zones: {int(zone_tiers.get('Red', 0))} Red, "
        f"{int(zone_tiers.get('Amber', 0))} Amber, {int(zone_tiers.get('Green', 0))} Green"
    )
