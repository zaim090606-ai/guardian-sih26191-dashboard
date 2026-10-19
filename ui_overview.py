"""Overview tab: title, tagline, headline metrics and a data-source badge.
All figures come from the already-computed pipeline result (illustrative data).
"""

import streamlit as st

from ui import charts, kpi
from ui.embed import embed_html

TAGLINE = "Red Zones planned from above. Distress confirmed from the ground."

BADGES = {"live": "Live", "cached": "Cached", "sample": "Sample"}


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
    return "Mixed: " + ", ".join(weak)


_ICONS = {
    "evidence": '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M7 4h14l5 5v19H7z"/><path d="M21 4v5h5"/><path d="M11 15h10M11 19h10M11 23h6"/></svg>',
    "score": '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 5v20M8 25h16M16 8l-8 3 3 8a5 5 0 0 1-6 0l3-8M16 8l8 3-3 8a5 5 0 0 0 6 0l-3-8"/></svg>',
    "allocate": '<svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="8" cy="9" r="3"/><circle cx="24" cy="23" r="3"/><path d="M11 9h8a4 4 0 0 1 0 8h-6a4 4 0 0 0 0 8h8"/></svg>',
}

STEPS = [
    ("evidence", "Step 1", "Evidence",
     "Hazard, vulnerability and incident history are combined for every grid cell. Ground reports from phones "
     "can add a capped, explained bonus."),
    ("score", "Step 2", "Score",
     "Each cell receives a Zone Risk Score and each habitation a Relocation Priority Index, "
     "with the contributing factors shown."),
    ("allocate", "Step 3", "Allocate",
     "Habitations are matched in priority order to the nearest safe site with capacity left. "
     "Any that cannot be placed are listed with the reason."),
]


def steps_html():
    cards = "".join(
        f'<div class="gd-step">{_ICONS[key]}<div class="gd-num">{num}</div><div class="gd-h">{title}</div><p>{text}</p></div>'
        for key, num, title, text in STEPS
    )
    return f'<div class="gd-steps">{cards}</div>'


def render_overview_tab(result, signals):
    st.markdown(f'<div class="gd-lede">{TAGLINE}</div>', unsafe_allow_html=True)
    st.markdown(f"Data status: **{data_status(signals)}**")

    st.subheader("At a glance")
    with st.container(key="gd-kpi"):
        embed_html(st, kpi.build_kpi_html(kpi.build_kpis(result)), 255)

    st.subheader("How it works")
    st.markdown(steps_html(), unsafe_allow_html=True)

    hab = result["habitations"]
    st.subheader("Highest-priority habitations")
    charts.show(st, charts.rpi_bar_chart(hab))
    st.caption("Bars show the Relocation Priority Index (0 to 100); hover a bar for residents and zone score.")

    with st.expander("About this prototype, data status and detailed counts"):
        st.caption(
            "Places where the network fails are flagged too, because that is where response is "
            "hardest. All habitation, grid and incident data here is illustrative."
        )
        if result.get("sample_as_of") is not None:
            st.caption(f"Sample data as of {result['sample_as_of'].strftime('%d %b %Y')} (fixed; sample results do not change with today's date).")
        tiers = hab["rpi_tier"].value_counts()
        st.markdown("**Habitations by relocation tier**")
        c1, c2, c3 = st.columns(3)
        c1.metric("Immediate", int(tiers.get("immediate", 0)))
        c2.metric("Short-term", int(tiers.get("short-term", 0)))
        c3.metric("Medium-term", int(tiers.get("medium-term", 0)))

        st.markdown("**Region status**")
        d1, d2, d3 = st.columns(3)
        d1.metric("Red cells", int((result["grid"]["zone_tier"] == "Red").sum()))
        d2.metric("Incidents", int(len(result["incidents"]) + result["unlocated_stats"].get("count", 0)))
        d3.metric("Comms-degraded", int(result["region_comms_degraded"]))
