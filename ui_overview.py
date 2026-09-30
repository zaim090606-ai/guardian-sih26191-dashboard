"""Overview tab: title, tagline, headline metrics and a data-source badge.
All figures come from the already-computed pipeline result (illustrative data).
"""

import streamlit as st

TAGLINE = "Red Zones planned from above. Distress confirmed from the ground."

BADGES = {"live": "🟢 Live", "cached": "🟡 Cached", "sample": "⚪ Sample"}


CONNECTOR_NAMES = {
    "rainfall": "Open-Meteo", "discharge": "Open-Meteo", "elevation": "Open-Meteo",
    "alerts": "SACHET", "quakes": "USGS", "gdacs": "GDACS",
}


def data_status(signals):
    """Badge text reflecting the WEAKEST connector: all live -> "Live", all
    cached -> "Cached", all sample -> "Sample"; otherwise "Mixed: <sources on
    sample/cached>", e.g. "Mixed: SACHET (sample), GDACS (cached)"."""
    statuses = {r.status for r in signals.values()}
    if statuses == {"live"}:
        return BADGES["live"]
    if len(statuses) == 1:
        return BADGES[statuses.pop()]
    weak = []
    for key, r in signals.items():
        item = f"{CONNECTOR_NAMES.get(key, key)} ({r.status})"
        if r.status != "live" and item not in weak:
            weak.append(item)
    return "🟠 Mixed: " + ", ".join(weak)


def render_overview_tab(result, signals):
    st.title("Guardian x SIH26191: Relocation & Ground-Truth Prototype")
    st.markdown(f"**{TAGLINE}**")
    st.caption(
        "Places where the network fails are flagged too, because that is where response is "
        "hardest. All habitation, grid and incident data here is illustrative."
    )
    st.markdown(f"Data status: **{data_status(signals)}**")
    if result.get("sample_as_of") is not None:
        st.caption(f"Sample data as of {result['sample_as_of'].strftime('%d %b %Y')} (fixed; sample results do not change with today's date).")

    hab = result["habitations"]
    tiers = hab["rpi_tier"].value_counts()
    st.subheader("Habitations by relocation tier")
    c1, c2, c3 = st.columns(3)
    c1.metric("Immediate", int(tiers.get("immediate", 0)))
    c2.metric("Short-term", int(tiers.get("short-term", 0)))
    c3.metric("Medium-term", int(tiers.get("medium-term", 0)))

    st.subheader("Region status")
    d1, d2, d3 = st.columns(3)
    d1.metric("Red cells", int((result["grid"]["zone_tier"] == "Red").sum()))
    d2.metric("Incidents", int(len(result["incidents"]) + result["unlocated_stats"].get("count", 0)))
    d3.metric("Comms-degraded", int(result["region_comms_degraded"]))
