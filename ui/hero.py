"""Engraved-plate hero: an original Three.js scene of schematic terrain with
glowing points for the highest-priority villages of the current run.

build_hero_payload() is pure (DataFrame in, JSON-able dict out) and unit
tested; render_hero() wraps the HTML in a components iframe. Presentation only:
nothing here changes scoring or allocation.
"""

import json
import math
import os

import palette
import scoring

THREE_URL = "https://cdnjs.cloudflare.com/ajax/libs/three.js/0.160.0/three.min.js"
THREE_SRI = "sha512-vnmn/Qqn6aG0POAc9mIGzjq0IybrvxJXYDafNvp9JSnDGxeF3pbkSqLvf+YGd5ku63pT7sa/jxHn7/d0mU8+tA=="
HERO_HEIGHT = 360
DEFAULT_TOP_N = 12

CAPTION = ("Schematic terrain, not to scale. Points show the highest-priority villages from the "
           "current run; demo data is illustrative.")

TIER_LABELS = {"immediate": "Immediate", "short-term": "Short-term", "medium-term": "Medium-term"}
# Shape + label next to the colour, so tiers do not rely on colour alone.
TIER_GLYPHS = {"immediate": "▲", "short-term": "◆", "medium-term": "●"}


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def build_hero_payload(df, n=DEFAULT_TOP_N):
    """Top-n habitations by Relocation Priority Index as a small JSON-able dict.

    Only whitelisted, non-personal fields are emitted (a village label, RPI,
    tier, colour and a 0-1 map position). Missing/empty input gives an empty
    point list rather than an error.
    """
    legend = [{"tier": t, "label": TIER_LABELS[t], "glyph": TIER_GLYPHS[t], "color": c}
              for t, c in palette.RPI_TIER_COLORS.items()]
    payload = {"points": [], "legend": legend, "caption": CAPTION}
    try:
        n = max(0, int(n))
    except (TypeError, ValueError):
        n = DEFAULT_TOP_N
    if df is None or len(df) == 0 or "rpi" not in df.columns or n == 0:
        return payload

    rows = []
    for _, row in df.iterrows():
        rpi = _num(row.get("rpi"))
        if rpi is not None:
            rows.append((rpi, row))
    rows.sort(key=lambda t: -t[0])
    rows = rows[:n]

    has_geo = "lat" in df.columns and "lon" in df.columns
    lats = [v for v in (_num(x) for x in df["lat"]) if v is not None] if has_geo else []
    lons = [v for v in (_num(x) for x in df["lon"]) if v is not None] if has_geo else []
    lat0, lat1 = (min(lats), max(lats)) if lats else (0.0, 1.0)
    lon0, lon1 = (min(lons), max(lons)) if lons else (0.0, 1.0)

    for rank, (rpi, row) in enumerate(rows):
        tier = row.get("rpi_tier") if "rpi_tier" in df.columns else None
        if tier not in palette.RPI_TIER_COLORS:
            tier = scoring.rpi_tier(rpi)
        lat, lon = _num(row.get("lat")), _num(row.get("lon"))
        if lat is not None and lon is not None:
            x = (lon - lon0) / ((lon1 - lon0) or 1.0)
            y = (lat - lat0) / ((lat1 - lat0) or 1.0)
        else:  # no coordinates: deterministic golden-angle spread
            a = rank * 2.399963
            r = 0.15 + 0.3 * ((rank + 1) / (len(rows) + 1))
            x, y = 0.5 + r * math.cos(a), 0.5 + r * math.sin(a)
        label = row.get("name") if "name" in df.columns else None
        if not isinstance(label, str) or not label.strip():
            hid = row.get("habitation_id") if "habitation_id" in df.columns else None
            label = str(hid) if hid is not None else f"Village {rank + 1}"
        payload["points"].append({
            "rank": rank + 1, "label": label.strip()[:40], "rpi": round(rpi, 1), "tier": tier,
            "tier_label": TIER_LABELS[tier], "color": palette.RPI_TIER_COLORS[tier],
            "x": round(min(max(x, 0.0), 1.0), 4), "y": round(min(max(y, 0.0), 1.0), 4),
            "id": str(row.get("habitation_id")) if "habitation_id" in df.columns else "",
            "glyph": TIER_GLYPHS[tier], "why": why_line(row),
        })
    return payload


_COMPONENT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hero_component")
_PLACEHOLDER = "window.__HERO__=null;"


def why_line(row):
    """One plain-language line from the already-computed row (no personal data)."""
    parts = []
    z, v, pop = _num(row.get("zone_score")), _num(row.get("vulnerability")), _num(row.get("population"))
    if z is not None:
        parts.append(f"Zone score {z:.0f}/100")
    if v is not None:
        parts.append(f"vulnerability {v:.2f}")
    if pop is not None:
        parts.append(f"{int(pop):,} residents")
    text = ", ".join(parts) if parts else "Ranked by Relocation Priority Index"
    if row.get("buffer_applied") is True:
        text += "; near a Red zone, so a buffer uplift applies"
    return text + "."


def _template():
    with open(os.path.join(_COMPONENT_DIR, "index.html"), encoding="utf-8") as fh:
        return fh.read()


_JS_ESCAPES = {"<": "\\u003c", ">": "\\u003e", "&": "\\u0026", chr(0x2028): "\\u2028", chr(0x2029): "\\u2029"}


def safe_json(payload):
    """json.dumps output that is safe inside an inline <script>: the characters that
    could close the tag, open a comment or break a JS string are \\u-escaped."""
    text = json.dumps(payload, ensure_ascii=False)
    for ch, esc in _JS_ESCAPES.items():
        text = text.replace(ch, esc)
    return text


def build_hero_html(payload):
    """Self-contained HTML (data embedded, script-safe) for the non-component fallback."""
    data = safe_json(payload)
    return _template().replace(_PLACEHOLDER, f"window.__HERO__={data};", 1)


_component = None


def _get_component():
    global _component
    if _component is None:
        try:
            import streamlit.components.v1 as components
            _component = components.declare_component("guardian_hero", path=_COMPONENT_DIR)
        except Exception:
            _component = False
    return _component or None


def render_hero(habitations_df, n=DEFAULT_TOP_N, height=HERO_HEIGHT):
    """Draw the hero. Returns {"id", "n"} when a pin was clicked (bidirectional
    component), else None. Falls back to the embedded, display-only iframe."""
    import streamlit as st
    payload = build_hero_payload(habitations_df, n)
    comp = _get_component()
    if comp is not None:
        try:
            return comp(payload=payload, key="guardian_hero", default=None)
        except Exception:
            pass
    from ui.embed import embed_html
    embed_html(st, build_hero_html(payload), height)
    return None


def apply_selection(state, selection, valid_ids):
    """Record a pin click (once per click) and preselect that village in the
    Relocation and Map tab widgets. `state` is st.session_state (any dict).
    Returns True when a new, valid selection was applied."""
    if not isinstance(selection, dict):
        return False
    hid, nonce = selection.get("id"), selection.get("n")
    if hid not in set(valid_ids) or nonce == state.get("_hero_last_click"):
        return False
    state["_hero_last_click"] = nonce
    state["selected_hab"] = hid
    state["dr_kind"] = "Habitation"
    state["dr_hab"] = hid
    state["inspect_hab"] = hid
    return True
