"""Evidence tab: incident table with Evidence Confidence Score, plus a
per-incident "why" breakdown. Never shows userId/userPhone (already stripped
in guardian_layer.py before this module ever sees the data).
"""

import streamlit as st

import review

DISPLAY_COLUMNS = [
    "incident_id",
    "riskLevel",
    "eventType",
    "locationSource",
    "accuracyM",
    "ecs",
    "cluster_id",
    "comms_degraded",
    "timestamp",
]


def render_evidence_tab(result):
    incidents = result["incidents"]

    st.caption(
        f"Loaded from: {result['incident_source']} · {len(incidents)} incidents with a "
        "valid position. Reports without a usable position are listed below, not discarded."
    )

    _render_unlocated(result)

    if incidents.empty:
        st.info("No incidents with a valid position in this run.")
        return

    display_cols = [c for c in DISPLAY_COLUMNS if c in incidents.columns]
    st.dataframe(
        incidents[display_cols].sort_values("ecs", ascending=False),
        width="stretch",
        hide_index=True,
    )

    _render_triage(result)

    st.subheader("Inspect one incident's Evidence Confidence Score")
    incident_id = st.selectbox("Incident", options=incidents["incident_id"].tolist(), key="inspect_incident")
    row = incidents[incidents["incident_id"] == incident_id].iloc[0]

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Evidence Confidence Score", f"{row['ecs']:.2f}")
        st.write(f"**Transcript:** {row.get('transcript') or '_(none)_'}")
        st.write(f"**Audio analysis:** {row.get('audioAnalysis') or '_(none)_'}")
    with col2:
        st.json(row["ecs_breakdown"])


def _render_unlocated(result):
    stats = result.get("unlocated_stats") or {"count": 0}
    st.metric(
        "Region comms-degraded reports (located + unlocated)",
        result.get("region_comms_degraded", 0),
        help="Reports that arrived via mesh relay or after a long delay.",
    )
    if not stats["count"]:
        return
    reasons = "; ".join(f"{n} × {r}" for r, n in stats["reasons"].items())
    st.warning(
        f"{stats['count']} unlocated report(s) ({stats['relayed_count']} relayed): {reasons}. "
        "They are scored as **partial** but not mapped, clustered or given a zone bonus."
    )
    cols = ["incident_id", "completeness", "unlocated_reason", "riskLevel", "eventType",
            "ecs", "comms_degraded", "timestamp"]
    part = result["unlocated"]
    st.dataframe(part[[c for c in cols if c in part.columns]], width="stretch", hide_index=True)


def _render_triage(result):
    queue = review.triage_queue(result["incidents"], result.get("review_state"))
    st.subheader("Triage queue (evidence confidence x severity)")
    st.caption(
        "Reviewer statuses are saved locally to review_state.json and are illustrative "
        "judgements on sample data. Dismissed clusters give no score bonus."
    )
    if queue.empty:
        st.info("No incident clusters in this run.")
        return
    st.dataframe(queue.drop(columns=["cluster_id"]), width="stretch", hide_index=True)
    key = st.selectbox("Cluster to review", queue["cluster_key"].tolist(), key="review_cluster")
    cur = queue[queue["cluster_key"] == key].iloc[0]
    status = st.selectbox("Status", review.STATUSES, index=review.STATUSES.index(cur["status"]),
                          key=f"review_status_{key}")
    note = st.text_input("Note (no names or phone numbers)", value=cur["note"], key=f"review_note_{key}")
    if st.button("Save review", key="review_save"):
        review.save_review(key, status, note)
        st.rerun()
