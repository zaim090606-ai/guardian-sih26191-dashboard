"""Optional "Cinematic 3D mode" for the Map tab (pydeck): extruded zone
columns (height = zone score), incident markers with uncertainty rings
(radius = reported accuracy), and route arcs. Uses pydeck only if it is already
installed; any failure falls back to the flat Folium map (see ui_map.py).
Illustrative data only. Column heights are exaggerated for legibility.
"""

import pandas as pd
import streamlit as st

import palette
import route_safety

try:  # pydeck ships with Streamlit; never a hard requirement
    import pydeck as pdk
except Exception:  # pragma: no cover
    pdk = None

HEIGHT_SCALE_M = 6.0  # metres of column height per zone-score point (visual only)
TILT_PITCH = 55
FLAT_PITCH = 0


def available():
    return pdk is not None


def _rgb(hex_color, alpha=255):
    h = hex_color.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)] + [alpha]


def build_deck(result, pitch=TILT_PITCH):
    """pydeck.Deck for the current pipeline result (no Streamlit calls)."""
    if pdk is None:
        raise RuntimeError("pydeck is not installed")
    grid = result["grid"].copy()
    grid["color"] = [_rgb(palette.TIER_COLORS.get(t, "#999999"), 190) for t in grid["zone_tier"]]
    grid["height"] = grid["zone_score"].astype(float) * HEIGHT_SCALE_M
    grid["tip"] = [f"{c}: {t} ({s:.1f})" for c, t, s in zip(grid["cell_id"], grid["zone_tier"], grid["zone_score"])]

    layers = [pdk.Layer(
        "ColumnLayer", data=grid[["lon", "lat", "height", "color", "tip"]], get_position=["lon", "lat"],
        get_elevation="height", elevation_scale=1, radius=100, get_fill_color="color", pickable=True, extruded=True,
    )]

    inc = result["incidents"]
    if len(inc):
        d = pd.DataFrame({
            "lon": inc["longitude"], "lat": inc["latitude"],
            "acc": inc["accuracyM"].fillna(30).astype(float),
            "tip": [f"{i}: {r}, ECS {e:.2f}" for i, r, e in zip(inc["incident_id"], inc["riskLevel"], inc["ecs"])],
        })
        layers.append(pdk.Layer("ScatterplotLayer", data=d, get_position=["lon", "lat"], get_radius=8,
                                get_fill_color=[255, 255, 255, 255], pickable=True))
        layers.append(pdk.Layer("ScatterplotLayer", data=d, get_position=["lon", "lat"], get_radius="acc",
                                stroked=True, filled=False, get_line_color=[255, 255, 255, 200],
                                line_width_min_pixels=2, radius_units="meters"))

    routes = result.get("routes")
    if routes is not None and len(routes):
        thr = result["params"]["route_risk_threshold"]
        r = routes.copy()
        r["color"] = [_rgb(route_safety.route_color(x, thr), 220) for x in r["route_risk"]]
        layers.append(pdk.Layer(
            "ArcLayer", data=r[["lon1", "lat1", "lon2", "lat2", "color"]],
            get_source_position=["lon1", "lat1"], get_target_position=["lon2", "lat2"],
            get_source_color="color", get_target_color="color", get_width=2,
        ))

    view = pdk.ViewState(latitude=float(grid["lat"].mean()), longitude=float(grid["lon"].mean()),
                         zoom=13.3, pitch=pitch, bearing=20)
    return pdk.Deck(layers=layers, initial_view_state=view, map_provider="carto", map_style="dark",
                    tooltip={"text": "{tip}"})


def render_3d(result):
    """Draws the 3D map with a tilt button. Raises on any problem so the caller can fall back."""
    if "map3d_pitch" not in st.session_state:
        st.session_state["map3d_pitch"] = TILT_PITCH
    if st.button("Tilt / flatten view", key="map3d_tilt"):
        st.session_state["map3d_pitch"] = FLAT_PITCH if st.session_state["map3d_pitch"] else TILT_PITCH
    st.pydeck_chart(build_deck(result, st.session_state["map3d_pitch"]), height=520)
    st.caption("Cinematic 3D: column height = zone score (exaggerated), white rings = report accuracy, "
               "arcs = illustrative routes. Basemap tiles need internet; the flat map is the fallback.")
