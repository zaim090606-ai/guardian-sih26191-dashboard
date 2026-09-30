"""Live Scenario tab (Phase 6): Live/Cached/Sample badges (with timestamp +
source attribution) for every connector, the derived hazard-scenario
multiplier with its "why" explanation, a manual Refresh button, and an
auto-refresh timer. `get_derived_scenario()` is also called from `app.py`'s
sidebar to seed the hazard-scenario slider's starting value — the slider
itself always remains a manual override (see
`connectors.scenario.effective_multiplier`).

Habitations and population used elsewhere in this dashboard remain entirely
illustrative — only the connectors this tab reports on fetch real data.
"""

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from connectors import sachet, scenario

AUTO_REFRESH_MINUTES = 20

STATUS_BADGE = {"live": "🟢 Live", "cached": "🟡 Cached", "sample": "⚪ Sample"}

CONNECTOR_LABELS = {
    "rainfall": "Open-Meteo: Rainfall",
    "discharge": "Open-Meteo: River discharge",
    "elevation": "Open-Meteo: Elevation/slope",
    "alerts": "NDMA SACHET: Alerts",
    "quakes": "USGS: Earthquakes",
    "gdacs": "GDACS: Multi-hazard",
}


@st.cache_data(ttl=AUTO_REFRESH_MINUTES * 60, show_spinner="Fetching live hazard data...")
def get_cached_signals():
    return scenario.gather_signals()


def get_derived_scenario():
    return scenario.derive_scenario(get_cached_signals())


def render_live_tab():
    st.caption(
        f"Live data feeding the hazard-scenario multiplier. Auto-refreshes every "
        f"{AUTO_REFRESH_MINUTES} minutes; use Refresh for an immediate update. "
        "Habitations and population elsewhere in this dashboard remain illustrative — "
        "only these feeds are real."
    )

    st_autorefresh(interval=AUTO_REFRESH_MINUTES * 60 * 1000, key="live_data_autorefresh")

    if st.button("Refresh now", key="live_refresh_button"):
        get_cached_signals.clear()
        st.rerun()

    signals = get_cached_signals()
    result = scenario.derive_scenario(signals)

    st.subheader("Data source status")
    badge_cols = st.columns(len(signals))
    for col, (key, fetch_result) in zip(badge_cols, signals.items()):
        with col:
            st.markdown(f"**{CONNECTOR_LABELS.get(key, key)}**")
            st.write(STATUS_BADGE.get(fetch_result.status, fetch_result.status))
            st.caption(fetch_result.source)
            st.caption(f"as of {fetch_result.fetched_at}")
            if fetch_result.error:
                st.caption(f"⚠️ {fetch_result.error}")

    st.subheader("Derived hazard-scenario multiplier")
    st.metric("Derived multiplier (sidebar slider overrides this)", f"{result['multiplier']:.2f}x")
    st.write("**Why this scenario:**")
    for reason in result["reasons"]:
        st.write(f"- {reason}")

    with st.expander("Raw signal values"):
        st.json(result["raw_signals"])

    _render_all_india_alerts(signals["alerts"])

    if signals["alerts"].data:
        st.subheader("Alerts for the region")
        for alert in signals["alerts"].data:
            title = f"{alert.get('event') or 'Alert'}: {alert.get('headline') or '(no headline)'}"
            with st.expander(title):
                st.write(alert.get("description") or "(no description)")
                st.caption(
                    f"Severity: {alert.get('severity')} · Effective: {alert.get('effective')} · "
                    f"Expires: {alert.get('expires')}"
                )


def _render_all_india_alerts(alerts_result):
    """Collapsed list of the latest 20 alerts anywhere in India, text as published,
    plus how many match the demo region (Chamoli, Uttarakhand)."""
    all_alerts = getattr(alerts_result, "all_alerts", None) or []
    latest = sachet.latest_alerts(all_alerts, 20)
    matches = len(alerts_result.data or [])
    with st.expander("All-India alerts (latest 20)", expanded=False):
        st.caption(
            f"{STATUS_BADGE.get(alerts_result.status, alerts_result.status)} · {alerts_result.source} · "
            f"as of {alerts_result.fetched_at}. Text is shown exactly as published; language is guessed from "
            "the writing script only."
        )
        if alerts_result.status == "sample":
            st.warning("Live feed unavailable: the list below is labelled sample data, not real alerts.")
        st.metric("Alerts matching the demo region", matches)
        if not matches:
            st.info("No active alert for this region")
        if not latest:
            st.write("No alerts available.")
        for a in latest:
            title = a.get("headline") or a.get("event") or "(no title)"
            st.markdown(f"**{title}**")
            st.caption(
                f"{a.get('sent') or a.get('effective') or 'time not given'} · "
                f"{sachet.detect_script_language(title + ' ' + (a.get('description') or ''))} · "
                + (f"[source]({a['web']})" if a.get("web") else "no source link")
            )
            if a.get("description"):
                st.text(a["description"])
