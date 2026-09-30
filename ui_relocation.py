"""Relocation tab: ranked habitations by Relocation Priority Index, the
greedy site allocation, unallocated habitations, and a CSV export."""

import io

import streamlit as st

import buffer
import relocation
import report
import robustness


def render_relocation_tab(result):
    habitations = result["habitations"]
    allocation = result["allocation"]
    unallocated = result["unallocated"]
    sites = result["sites_after"]

    st.subheader("Candidate safe sites: carrying capacity")
    st.dataframe(
        sites[["site_id", "name", "area_limit", "water_limit", "sanitation_limit", "limiting_resource",
               "capacity_people", "allocated_people", "remaining_capacity"]],
        width="stretch",
        hide_index=True,
    )
    st.caption(
        "Limits are people supported by usable area (after slope/hazard reduction), water and "
        "toilets, net of livestock placed at the site. Norms are illustrative defaults; verify "
        "against the Sphere Handbook. Site water/toilet supply is illustrative data."
    )

    st.subheader("Habitations ranked by Relocation Priority Index")
    ranked = habitations.sort_values("rpi", ascending=False)[
        ["habitation_id", "name", "population", "vulnerability", "zone_score", "rpi", "rpi_tier",
         "red_distance_m", "buffer_m", "buffer_factor", "route_risk", "route_flag", "riskiest_cell", "riskiest_cell_score"]
    ]
    st.dataframe(ranked, width="stretch", hide_index=True)

    tier_counts = habitations["rpi_tier"].value_counts()
    c1, c2, c3 = st.columns(3)
    c1.metric("Immediate", int(tier_counts.get("immediate", 0)))
    c2.metric("Short-term", int(tier_counts.get("short-term", 0)))
    c3.metric("Medium-term", int(tier_counts.get("medium-term", 0)))

    st.subheader("Greedy allocation to nearest site with capacity")
    if allocation.empty:
        st.info("No habitation could be allocated to any candidate site at this capacity/space norm.")
    else:
        st.dataframe(allocation, width="stretch", hide_index=True)

    st.subheader("Unallocated (no site had enough remaining capacity)")
    if unallocated.empty:
        st.success("Every habitation was allocated to a site.")
    else:
        st.dataframe(unallocated, width="stretch", hide_index=True)  # includes "reason"
        st.caption(f"Total unallocated population: {int(unallocated['population'].sum())}")

    csv_buf = io.StringIO()
    relocation.export_allocation_csv(allocation, unallocated, csv_buf)
    st.download_button(
        "Download allocation CSV",
        data=csv_buf.getvalue(),
        file_name="relocation_allocation.csv",
        mime="text/csv",
    )

    st.caption(buffer.RULE_LABEL + " Distance to the nearest Red cell and the buffer used appear in each habitation's why.")
    log = buffer.eligibility_log(habitations, allocation, unallocated, result["params"])
    st.download_button(
        "Download eligibility log CSV",
        data=log.to_csv(index=False),
        file_name="eligibility_log.csv",
        mime="text/csv",
    )

    st.subheader("Decision report")
    st.caption("One-page export per habitation or site (illustrative, anonymised).")
    kind = st.radio("Report for", ["Habitation", "Safe site"], horizontal=True, key="dr_kind")
    if kind == "Habitation":
        hid = st.selectbox("Habitation", habitations["habitation_id"].tolist(), key="dr_hab")
        rep = report.habitation_report(result, hid)
        stem = f"decision_report_{hid}"
    else:
        sid = st.selectbox("Safe site", sites["site_id"].tolist(), key="dr_site")
        rep = report.site_report(result, sid)
        stem = f"decision_report_{sid}"
    d1, d2 = st.columns(2)
    d1.download_button("Download report (HTML)", report.to_html(rep), f"{stem}.html", "text/html", key="dr_html")
    d2.download_button("Download report (Markdown)", report.to_markdown(rep), f"{stem}.md", "text/markdown", key="dr_md")

    st.subheader("Decision robustness")
    st.caption(
        f"Reruns the scoring {robustness.DEFAULT_RUNS} times with the zone and vulnerability weights "
        f"jittered by +/-{int(robustness.DEFAULT_SPREAD * 100)}% (seeded). Stable = tier unchanged in at least "
        f"{int(robustness.DEFAULT_STABLE_SHARE * 100)}% of runs. Tests weight sensitivity only, not data quality. Takes about a minute."
    )
    if st.button("Run robustness check", key="rob_run"):
        with st.spinner("Running scenarios..."):
            st.session_state["robustness"] = robustness.run_robustness(**result["params"])
    rob = st.session_state.get("robustness")
    if rob is not None:
        n_sens = int((rob["label"] == "Sensitive").sum())
        st.write(f"{n_sens} of {len(rob)} habitations are **Sensitive** (based on the last run; rerun after changing sidebar settings).")
        st.dataframe(rob.sort_values("pct_runs_same_tier"), width="stretch", hide_index=True)
