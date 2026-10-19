"""Interactive Altair charts in the app's classic palette. Tier colours come
from palette.py so every chart, table, map and the hero agree. Pure builders:
DataFrame in, alt.Chart out (tested via .to_dict()).
"""

import altair as alt

import palette
from ui import theme, views

TIER_ORDER = ["immediate", "short-term", "medium-term"]
TIER_DOMAIN = [views.tier_label(t) for t in TIER_ORDER]
TIER_RANGE = [palette.RPI_TIER_COLORS[t] for t in TIER_ORDER]
RISK_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
RISK_RANGE = ["#7f1d1d", palette.RED, palette.AMBER, "#4d7c0f"]


def style(chart, height=None):
    """Apply the shared classic styling: serif title, light grid, ivory-free background."""
    c = chart.configure(background="transparent").configure_view(stroke=None)
    c = c.configure_axis(labelFont="Inter", titleFont="Inter", labelColor=theme.MUTED, titleColor=theme.MUTED,
                         labelFontSize=12, titleFontSize=12, gridColor=theme.RULE, domainColor=theme.RULE,
                         tickColor=theme.RULE, titleFontWeight=500)
    c = c.configure_legend(labelFont="Inter", titleFont="Inter", labelColor=theme.INK, titleColor=theme.MUTED,
                           labelFontSize=12, symbolType="square")
    c = c.configure_title(font="Cormorant Garamond", fontSize=20, color=theme.INK, anchor="start", fontWeight=700)
    return c.properties(height=height) if height else c


def rpi_bar_chart(habitations, n=12):
    """Highest-priority habitations: horizontal bars by Relocation Priority Index, coloured by tier."""
    top = habitations.sort_values("rpi", ascending=False).head(n).copy()
    top["Tier"] = top["rpi_tier"].map(views.tier_label)
    top["Village"] = top["name"]
    top["Index"] = top["rpi"].astype(float).round(1)
    top["Residents"] = top["population"].astype(int)
    top["Zone score"] = top["zone_score"].astype(float).round(1)
    base = alt.Chart(top[["Village", "Tier", "Index", "Residents", "Zone score"]]).mark_bar(
        cornerRadiusTopRight=3, cornerRadiusBottomRight=3, height={"band": 0.62})
    chart = base.encode(
        y=alt.Y("Village:N", sort="-x", title=None, axis=alt.Axis(labelLimit=180, ticks=False)),
        x=alt.X("Index:Q", title="Relocation Priority Index", scale=alt.Scale(domain=[0, 100])),
        color=alt.Color("Tier:N", scale=alt.Scale(domain=TIER_DOMAIN, range=TIER_RANGE), legend=alt.Legend(title="Tier", orient="bottom")),
        tooltip=["Village", "Tier", "Index", "Residents", "Zone score"],
    )
    return style(chart, height=max(120, 26 * len(top) + 40))


def capacity_chart(sites):
    """Per safe site: people allocated vs remaining capacity (stacked bars)."""
    rows = []
    for _, s in sites.iterrows():
        alloc = float(s["allocated_people"])
        rows.append({"Site": s["name"], "Part": "Allocated", "People": alloc})
        rows.append({"Site": s["name"], "Part": "Remaining", "People": max(float(s["capacity_people"]) - alloc, 0.0)})
    data = alt.Data(values=rows)
    chart = alt.Chart(data).mark_bar(cornerRadiusTopRight=3, cornerRadiusBottomRight=3, height={"band": 0.62}).encode(
        y=alt.Y("Site:N", title=None, axis=alt.Axis(labelLimit=180, ticks=False)),
        x=alt.X("People:Q", title="People", stack="zero"),
        color=alt.Color("Part:N", scale=alt.Scale(domain=["Allocated", "Remaining"], range=[theme.INK, "#C9BC9C"]),
                        legend=alt.Legend(title=None, orient="bottom")),
        tooltip=["Site:N", "Part:N", alt.Tooltip("People:Q", format=",.0f")],
    )
    return style(chart, height=max(120, 34 * len(sites) + 50))


def ecs_chart(incidents):
    """Evidence Confidence Score per incident, coloured by reported risk level."""
    cols = [c for c in ("incident_id", "riskLevel", "eventType", "ecs") if c in incidents.columns]
    d = incidents[cols].copy()
    if "riskLevel" not in d.columns:
        d["riskLevel"] = "UNKNOWN"
    if "eventType" not in d.columns:
        d["eventType"] = ""
    d["ecs"] = d["ecs"].astype(float).round(2)
    d = d.sort_values("ecs", ascending=False)
    chart = alt.Chart(d).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("incident_id:N", sort=None, title="Incident", axis=alt.Axis(labelAngle=-60, labelLimit=90)),
        y=alt.Y("ecs:Q", title="Evidence Confidence Score", scale=alt.Scale(domain=[0, 1])),
        color=alt.Color("riskLevel:N", title="Risk level", scale=alt.Scale(domain=RISK_ORDER, range=RISK_RANGE)),
        tooltip=[alt.Tooltip("incident_id:N", title="Incident"), alt.Tooltip("riskLevel:N", title="Risk level"),
                 alt.Tooltip("eventType:N", title="Event"), alt.Tooltip("ecs:Q", title="Confidence", format=".2f")],
    )
    return style(chart, height=260)


def show(st, chart):
    """Render with the app's own styling instead of Streamlit's chart theme."""
    st.altair_chart(chart, theme=None, width="stretch")
