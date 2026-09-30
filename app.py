"""Guardian x SIH26191 prototype dashboard — thin Streamlit entry point.

Builds the sidebar parameters, runs the pipeline once, and dispatches to each
tab's render function. All real logic lives in pipeline.py / scoring.py /
relocation.py / guardian_layer.py / brief.py and the ui_*.py tab modules —
see BUILD_LOG.md for what each does and how it was verified.

ALL data in this dashboard is illustrative/synthetic (see data_gen.py and the
Method & Limits tab). This is a hackathon prototype, not a real-time national
hazard map, and makes no guaranteed-delivery claims.
"""

import streamlit as st

import pipeline
import scoring
import relocation
import route_safety
import ahp
import buffer
import vulnerability
import guardian_layer as gl
import ui_overview
import ui_map
import ui_map3d
import ui_evidence
import ui_relocation
import ui_impact
import ui_brief
import ui_scorecard
import ui_method
import ui_live

st.set_page_config(page_title="Guardian x SIH26191 Prototype", layout="wide")

FOOTER = (
    "**Illustrative data:** habitations, hazard grid, safe sites, livestock and sample incidents are "
    "synthetic, not a real survey or a validated hazard model. "
    "Data attribution: map tiles © OpenStreetMap contributors; rainfall, river discharge and elevation "
    "from Open-Meteo (CC BY 4.0); earthquakes from USGS; multi-hazard events from GDACS; alerts from "
    "NDMA SACHET (sample data until a public feed is configured). Capacity norms follow commonly cited "
    "Sphere Handbook defaults and should be verified."
)


def build_sidebar_params():
    st.sidebar.title("Scenario controls")
    st.sidebar.caption("All data is illustrative/synthetic. See the Method & Limits tab.")

    with st.sidebar.expander("Hazard scenario", expanded=True):
        derived = ui_live.get_derived_scenario()
        st.caption(
            f"Live-derived default: {derived['multiplier']:.2f}x — {derived['reasons'][0]} "
            "See the Live Scenario tab for the full why. Moving the slider below always overrides this."
        )
        hazard_scenario_multiplier = st.slider(
            "Hazard-scenario intensity multiplier", 0.5, 2.0, round(derived["multiplier"], 2), 0.05,
            help="Starts at the live-derived value (Live Scenario tab); multiplies the hazard component only.",
        )

    with st.sidebar.expander("Zone risk scoring"):
        st.markdown("**AHP pairwise comparison** (Saaty 1-9; + favours the first, - the second)")
        d = ahp.DEFAULT_JUDGEMENTS
        judgements = {
            ("hazard", "vulnerability"): ahp.saaty_from_step(st.slider(
                "Hazard vs vulnerability", -8, 8, ahp.step_from_saaty(d[("hazard", "vulnerability")]), key="ahp_hv")),
            ("hazard", "history"): ahp.saaty_from_step(st.slider(
                "Hazard vs history", -8, 8, ahp.step_from_saaty(d[("hazard", "history")]), key="ahp_hh")),
            ("vulnerability", "history"): ahp.saaty_from_step(st.slider(
                "Vulnerability vs history", -8, 8, ahp.step_from_saaty(d[("vulnerability", "history")]), key="ahp_vh")),
        }
        ahp_result = ahp.compute(judgements)
        if not ahp_result["consistent"]:
            st.warning(f"AHP consistency ratio {ahp_result['cr']:.2f} is above {ahp.CR_WARN_THRESHOLD}: "
                       "these judgements contradict each other. Revisit them or use the manual override.")
        manual = st.checkbox("Manual weight override", value=False,
                             help="Off: the AHP weights are used. On: the sliders below set the weights.")
        aw = ahp_result["weights"]
        w_hazard = st.slider("Hazard weight", 0.0, 1.0, round(aw["hazard"], 2), disabled=not manual,
                             help="Relative weight of terrain/slope hazard in the Zone Risk Score.")
        w_vuln = st.slider("Vulnerability weight", 0.0, 1.0, round(aw["vulnerability"], 2), disabled=not manual,
                           help="Relative weight of social/structural vulnerability.")
        w_hist = st.slider("History weight", 0.0, 1.0, round(aw["history"], 2), disabled=not manual,
                           help="Relative weight of past incidents in the cell.")
        if manual:
            total_w = max(w_hazard + w_vuln + w_hist, 1e-9)
            zone_weights = {"hazard": w_hazard / total_w, "vulnerability": w_vuln / total_w, "history": w_hist / total_w}
        else:
            zone_weights = dict(aw)
        st.caption(
            f"Normalized: hazard {zone_weights['hazard']:.2f}, vulnerability "
            f"{zone_weights['vulnerability']:.2f}, history {zone_weights['history']:.2f}"
        )
        red_threshold = st.slider("Red threshold", 0, 100, scoring.DEFAULT_RED_THRESHOLD,
                                  help="Zone score at or above this is a Red Zone.")
        amber_threshold = st.slider("Amber threshold", 0, 100, scoring.DEFAULT_AMBER_THRESHOLD,
                                    help="Zone score at or above this (and below Red) is Amber.")

    with st.sidebar.expander("Capacity norms"):
        norms = relocation.DEFAULT_NORMS
        space_norm_m2 = st.slider(
            "Area norm (m² / person)", 1.0, 100.0, norms["area_m2_per_person"], 0.5,
            help="Default 3.5 m² follows the commonly cited Sphere minimum; illustrative.",
        )
        water_l_per_person = st.slider(
            "Water norm (L / person / day)", 5.0, 50.0, norms["water_l_per_person"], 0.5,
            help="Default 15 L follows the commonly cited Sphere minimum; illustrative.",
        )
        people_per_toilet = st.slider(
            "People per toilet", 5, 100, int(norms["people_per_toilet"]),
            help="Default 20 follows the commonly cited Sphere guideline; illustrative.",
        )
        livestock_water_l = st.slider(
            "Livestock water (L / head / day)", 5.0, 100.0, norms["livestock_water_l"], 1.0,
            help="Illustrative assumption, not from Sphere.",
        )
        livestock_area_m2 = st.slider(
            "Livestock area (m² / head)", 1.0, 10.0, norms["livestock_area_m2"], 0.5,
            help="Illustrative assumption, not from Sphere.",
        )
        st.caption(
            "Norm defaults are illustrative; verify against the current Sphere Handbook "
            "(spherestandards.org) before real use."
        )

    with st.sidebar.expander("Route safety"):
        route_risk_threshold = st.slider(
            "Route-risk threshold", 0, 100, int(route_safety.DEFAULT_ROUTE_THRESHOLD),
            help="Routes at or above this risk are flagged unsafe and reallocated (illustrative straight-line routes).",
        )

    with st.sidebar.expander("Vulnerability index weights"):
        vi_raw = {
            c: st.slider(c.replace("_", " ").capitalize(), 0.0, 1.0, vulnerability.DEFAULT_VI_WEIGHTS[c],
                         key=f"vi_{c}", help="Relative weight of this component in the vulnerability index.")
            for c in vulnerability.COMPONENTS
        }
        vi_weights = vulnerability.normalize_weights(vi_raw)
        st.caption("Normalized: " + ", ".join(f"{c.split('_')[0]} {w:.2f}" for c, w in vi_weights.items())
                   + ". Component data is illustrative and aggregated.")

    with st.sidebar.expander("Buffer rule (illustrative)"):
        buffer_high_m = st.slider("Buffer, high-risk cell (m)", 0, 200, int(buffer.DEFAULT_BUFFER_HIGH_M),
                                  help="Red/Amber-cell habitations within this distance of a Red zone get a priority uplift.")
        buffer_low_m = st.slider("Buffer, lower-risk cell (m)", 0, 200, int(buffer.DEFAULT_BUFFER_LOW_M),
                                 help="Same for Green-cell habitations.")
        buffer_uplift = st.slider("Max priority uplift", 0.0, 1.0, buffer.DEFAULT_BUFFER_UPLIFT, 0.05,
                                  help="Uplift at distance 0, fading to none at the buffer edge.")
        st.caption(buffer.RULE_LABEL + " Grid cells are ~278 x ~240 m, so distances are indicative only.")

    with st.sidebar.expander("Guardian ground evidence"):
        include_guardian_evidence = st.checkbox(
            "Include Guardian ground evidence", value=True,
            help="Turn off to score zones from planning data only.",
        )
        evidence_bonus_cap = st.slider(
            "Evidence-corroboration bonus cap (points)", 0, 30, scoring.MAX_GUARDIAN_EVIDENCE_BONUS,
            help="Maximum zone-score points ground reports can add to one cell.",
        )
        cluster_bonus_per_incident = st.slider(
            "Cluster bonus per corroborating incident", 0.0, 10.0, gl.CLUSTER_BONUS_PER_INCIDENT,
            help="Points per confidence-weighted report in a cluster of nearby reports.",
        )
        comms_bonus_cap = st.slider(
            "Comms-degraded bonus cap (points)", 0.0, 15.0, gl.COMMS_BONUS_CAP_DEFAULT,
            help="Maximum points added to a cell where reports arrived late or via mesh relay.",
        )
        comms_bonus_per_incident = st.slider(
            "Comms-degraded bonus per incident", 0.0, 5.0, gl.COMMS_BONUS_PER_INCIDENT_DEFAULT,
            help="Points per comms-degraded report in a cell.",
        )

    with st.sidebar.expander("Incident data source"):
        mode_label = st.radio(
            "Mode", ["Sample data", "Live Firestore"],
            help="Live Firestore falls back to sample data if it cannot be read.",
        )
        mode = "live" if mode_label == "Live Firestore" else "sample"

    return ahp_result, dict(
        hazard_scenario_multiplier=hazard_scenario_multiplier,
        zone_weights=zone_weights,
        red_threshold=red_threshold,
        amber_threshold=amber_threshold,
        space_norm_m2=space_norm_m2,
        water_l_per_person=water_l_per_person,
        people_per_toilet=people_per_toilet,
        livestock_water_l=livestock_water_l,
        livestock_area_m2=livestock_area_m2,
        route_risk_threshold=route_risk_threshold,
        vi_weights=vi_weights,
        buffer_high_m=float(buffer_high_m),
        buffer_low_m=float(buffer_low_m),
        buffer_uplift=buffer_uplift,
        include_guardian_evidence=include_guardian_evidence,
        evidence_bonus_cap=evidence_bonus_cap,
        cluster_bonus_per_incident=cluster_bonus_per_incident,
        comms_bonus_cap=comms_bonus_cap,
        comms_bonus_per_incident=comms_bonus_per_incident,
        mode=mode,
    )


def main():
    ahp_result, params = build_sidebar_params()
    three_d = False
    if ui_map3d.available():
        three_d = st.sidebar.toggle("Cinematic 3D mode", value=False,
                                    help="Map tab: extruded zones, uncertainty rings, route arcs (pydeck).")
    result = pipeline.run_pipeline(**params)

    if result["incident_source"] == "sample_fallback":
        st.sidebar.warning("Live Firestore read failed — showing sample data instead.")

    tabs = st.tabs(
        ["Overview", "Map", "Evidence", "Relocation", "Impact of Ground Evidence", "Live Scenario",
         "Brief", "Scorecard", "Method & Limits"]
    )

    with tabs[0]:
        ui_overview.render_overview_tab(result, ui_live.get_cached_signals())
    with tabs[1]:
        ui_map.render_map_tab(result, three_d=three_d)
    with tabs[2]:
        ui_evidence.render_evidence_tab(result)
    with tabs[3]:
        ui_relocation.render_relocation_tab(result)
    with tabs[4]:
        ui_impact.render_impact_tab(params)
    with tabs[5]:
        ui_live.render_live_tab()
    with tabs[6]:
        ui_brief.render_brief_tab(result)
    with tabs[7]:
        ui_scorecard.render_scorecard_tab()
    with tabs[8]:
        ui_method.render_method_tab(ahp_result)

    st.divider()
    st.caption(FOOTER)


main()
