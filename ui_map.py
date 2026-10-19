"""Map tab: Folium map (zones, habitations, safe sites, incidents,
comms-degraded overlay) plus "select a cell/habitation to see its why
breakdown" controls. Imported by app.py; no top-level Streamlit calls run on
import.
"""

import html

import folium
import streamlit as st
from streamlit_folium import st_folium

import data_gen
import guardian_layer as gl
import palette
import route_safety
import ui_map3d
from ui import views

ZONE_COLORS = palette.TIER_COLORS
RISK_COLORS = {"CRITICAL": "#7f1d1d", "HIGH": palette.RED, "MEDIUM": palette.AMBER, "LOW": "#65a30d"}


def _cell_bounds(lat, lon):
    half = data_gen.CELL_SIZE_DEG / 2
    return [[lat - half, lon - half], [lat + half, lon + half]]


def build_folium_map(grid, habitations, sites, incidents, routes=None,
                     route_threshold=route_safety.DEFAULT_ROUTE_THRESHOLD):
    center_lat = float(grid["lat"].mean())
    center_lon = float(grid["lon"].mean())
    # OpenStreetMap tiles need no API key; a CSS filter mutes them to a light, classic
    # look. If tiles cannot load (offline) every vector layer below still draws on
    # the ivory background.
    fmap = folium.Map(location=[center_lat, center_lon], zoom_start=14, tiles=None)
    folium.TileLayer(
        tiles="https://tile.openstreetmap.org/{z}/{x}/{y}.png", name="Light basemap (OpenStreetMap, muted)",
        max_zoom=19, class_name="gd-muted-tiles",
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    ).add_to(fmap)
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap (standard colour)", show=False).add_to(fmap)
    fmap.get_root().header.add_child(folium.Element(_MAP_CSS))

    zones_layer = folium.FeatureGroup(name="Zone Risk (Red/Amber/Green)", show=True)
    for _, cell in grid.iterrows():
        folium.Rectangle(
            bounds=_cell_bounds(cell["lat"], cell["lon"]),
            color=ZONE_COLORS.get(cell["zone_tier"], "#999999"),
            weight=0.5,
            fill=True,
            fill_opacity=0.35,
            tooltip=(
                f"{cell['cell_id']} — {cell['zone_tier']} "
                f"(score {cell['zone_score']:.1f}, hazard {cell['hazard']:.2f})"
            ),
        ).add_to(zones_layer)
    zones_layer.add_to(fmap)

    hab_layer = folium.FeatureGroup(name="Habitations (colour = relocation tier)", show=True)
    for _, hab in habitations.iterrows():
        tier = hab["rpi_tier"]
        color = palette.RPI_TIER_COLORS.get(tier, "#14213D")
        radius = 5 + min(hab["population"] / 300, 9)
        tip = (f"{hab['name']} ({hab['habitation_id']}) — pop {hab['population']}, "
               f"RPI {hab['rpi']:.1f} ({tier})")
        # soft halo under the marker, so tiers read on any basemap
        folium.CircleMarker(location=[hab["lat"], hab["lon"]], radius=radius + 5, color=color, weight=0,
                            fill=True, fill_color=color, fill_opacity=0.18).add_to(hab_layer)
        folium.CircleMarker(
            location=[hab["lat"], hab["lon"]], radius=radius, color="#FFFDF8", weight=1.5,
            fill=True, fill_color=color, fill_opacity=0.95, tooltip=tip,
            popup=folium.Popup(_habitation_popup(hab), max_width=260),
        ).add_to(hab_layer)
    hab_layer.add_to(fmap)

    sites_layer = folium.FeatureGroup(name="Candidate safe sites", show=True)
    for _, site in sites.iterrows():
        folium.Marker(
            location=[site["lat"], site["lon"]],
            icon=folium.Icon(color="green", icon="ok-sign"),
            tooltip=(
                f"{site['name']} — capacity {int(site['capacity_people'])} people "
                f"({site['area_ha']:.1f} ha, slope {site['slope_deg']:.1f}°)"
            ),
        ).add_to(sites_layer)
    sites_layer.add_to(fmap)

    incidents_layer = folium.FeatureGroup(name="Guardian incidents", show=True)
    for _, inc in incidents.iterrows():
        color = RISK_COLORS.get(inc.get("riskLevel"), "#6b7280")
        radius_m = float(inc.get("accuracyM") or 30)
        folium.Circle(
            location=[inc["latitude"], inc["longitude"]],
            radius=radius_m,
            color=color,
            weight=1,
            fill=True,
            fill_color=color,
            fill_opacity=0.25,
            tooltip=(
                f"{inc['incident_id']} — {inc.get('riskLevel', '?')}, "
                f"ECS {inc.get('ecs', 0):.2f}, source {inc.get('locationSource', '?')}"
            ),
        ).add_to(incidents_layer)
    incidents_layer.add_to(fmap)

    comms_layer = folium.FeatureGroup(name=f"Comms-degraded ({gl.COMMS_DEGRADED_CAPTION})", show=True)
    degraded = incidents[incidents.get("comms_degraded", False) == True]  # noqa: E712
    for _, inc in degraded.iterrows():
        folium.CircleMarker(
            location=[inc["latitude"], inc["longitude"]],
            radius=9,
            color="#ea580c",
            weight=2,
            dash_array="4",
            fill=False,
            tooltip=f"{inc['incident_id']} — relay delay {inc.get('relay_delay_minutes', 0):.0f} min",
        ).add_to(comms_layer)
    comms_layer.add_to(fmap)

    if routes is not None and not routes.empty:
        routes_layer = folium.FeatureGroup(name="Evacuation routes (illustrative straight lines)", show=True)
        for _, r in routes.iterrows():
            folium.PolyLine(
                locations=[[r["lat1"], r["lon1"]], [r["lat2"], r["lon2"]]],
                color=route_safety.route_color(r["route_risk"], route_threshold),
                weight=3,
                opacity=0.8,
                dash_array=None if r["allocated"] else "6",
                tooltip=(
                    f"{r['habitation_id']} → {r['site_id']}: route risk {r['route_risk']:.0f} "
                    f"({r['route_flag']}); riskiest cell {r['riskiest_cell']} "
                    f"({r['riskiest_cell_score']:.0f})"
                ),
            ).add_to(routes_layer)
        routes_layer.add_to(fmap)
        fmap.get_root().html.add_child(folium.Element(_route_legend_html(route_threshold)))
    fmap.get_root().html.add_child(folium.Element(_tier_legend_html()))

    folium.LayerControl(collapsed=False).add_to(fmap)
    return fmap


_MAP_CSS = """<style>
.gd-muted-tiles{filter:grayscale(.9) sepia(.22) brightness(1.07) contrast(.92)}
.leaflet-container{background:#F2ECDD;font-family:Inter,'Segoe UI',system-ui,sans-serif}
.gd-pop{font-size:13px;line-height:1.45;color:#14213D;min-width:190px}
.gd-pop .nm{font-family:'Cormorant Garamond',Georgia,serif;font-size:19px;font-weight:700;line-height:1.15}
.gd-pop .t{font-weight:600}
.gd-pop .w{color:#4A5568;margin-top:4px}
.leaflet-popup-content-wrapper{border-radius:4px;border-top:3px solid #A8782A;box-shadow:0 6px 18px rgba(20,33,61,.25)}
.gd-leg{position:fixed;bottom:24px;right:12px;z-index:9999;background:rgba(255,253,248,.96);color:#14213D;padding:7px 10px;
 border:1px solid #E1D8C3;border-radius:4px;font-size:12px;line-height:1.5;box-shadow:0 2px 8px rgba(20,33,61,.15)}
.gd-leg b{font-variant:small-caps;letter-spacing:.06em}
</style>"""


def _habitation_popup(hab):
    tier = hab["rpi_tier"]
    why = (f"Zone score {hab['zone_score']:.0f}/100, vulnerability {hab['vulnerability']:.2f}, "
           f"{int(hab['population']):,} residents.")
    color = palette.RPI_TIER_COLORS.get(tier, "#14213D")
    return (f'<div class="gd-pop"><div class="nm">{html.escape(str(hab["name"]))}</div>'
            f'<div class="t" style="color:{color}">{html.escape(views.tier_label(tier))}</div>'
            f'<div>Relocation Priority Index <b>{hab["rpi"]:.1f}</b></div>'
            f'<div class="w">{html.escape(why)}</div></div>')


def _tier_legend_html():
    rows = "".join(
        f'<div><span style="color:{palette.RPI_TIER_COLORS[t]}">&#9679;</span> {html.escape(views.tier_label(t))}</div>'
        for t in ("immediate", "short-term", "medium-term")
    )
    return f'<div class="gd-leg"><b>Habitation tier</b>{rows}</div>'


def _route_legend_html(threshold):
    amber = threshold * route_safety.AMBER_FRACTION
    return (
        '<div style="position:fixed;bottom:24px;left:24px;z-index:9999;background:white;color:#111;'
        'padding:8px 10px;border:1px solid #888;border-radius:4px;font-size:12px;">'
        "<b>Route risk</b> (dashed = unallocated)<br>"
        f'<span style="color:{palette.GREEN}">&#9632;</span> green &lt; {amber:.0f}<br>'
        f'<span style="color:{palette.AMBER}">&#9632;</span> amber {amber:.0f}&ndash;{threshold:.0f}<br>'
        f'<span style="color:{palette.RED}">&#9632;</span> red &ge; {threshold:.0f} (unsafe)</div>'
    )


def render_map_tab(result, three_d=False):
    grid = result["grid"]
    habitations = result["habitations"]
    sites = result["sites_after"]
    incidents = result["incidents"]

    st.caption(
        "Zones are planned from hazard/vulnerability/history above; incident circles are "
        "ground reports; the dashed orange layer is " + gl.COMMS_DEGRADED_CAPTION.lower()
    )

    shown_3d = False
    if three_d:
        try:
            ui_map3d.render_3d(result)
            shown_3d = True
        except Exception as exc:  # fall back to the flat map on any error
            st.warning(f"3D mode unavailable ({type(exc).__name__}); showing the flat map instead.")
    if not shown_3d:
        fmap = build_folium_map(
            grid, habitations, sites, incidents,
            routes=result.get("routes"), route_threshold=result["params"]["route_risk_threshold"],
        )
        st_folium(fmap, height=520, use_container_width=True, key="main_map", returned_objects=[])

    st.subheader("Inspect a score \"why\" breakdown")
    col1, col2 = st.columns(2)

    with col1:
        cell_id = st.selectbox("Grid cell", options=grid["cell_id"].tolist(), key="inspect_cell")
        cell_row = grid[grid["cell_id"] == cell_id].iloc[0]
        st.write(f"**Zone tier:** {cell_row['zone_tier']} — score {cell_row['zone_score']:.1f}/100")
        st.json(cell_row["zone_breakdown"])

    with col2:
        hab_id = st.selectbox(
            "Habitation",
            options=habitations["habitation_id"].tolist(),
            format_func=lambda hid: f"{hid} — {habitations.set_index('habitation_id').loc[hid, 'name']}",
            key="inspect_hab",
        )
        hab_row = habitations[habitations["habitation_id"] == hab_id].iloc[0]
        st.write(f"**RPI tier:** {hab_row['rpi_tier']} — RPI {hab_row['rpi']:.1f}/100")
        st.json(hab_row["rpi_breakdown"])
