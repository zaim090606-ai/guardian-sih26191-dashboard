"""Presentation helpers for tables: tier labels (glyph + word + colour, so tier
never relies on colour alone), HTML tier pills, and st.dataframe configuration.
No scoring logic; inputs are the already-computed DataFrames.
"""

import html

import palette

# (glyph, label) per tier vocabulary used in the app.
_TIERS = {
    "immediate": ("▲", "Immediate"), "short-term": ("◆", "Short-term"), "medium-term": ("●", "Medium-term"),
    "red": ("▲", "Red"), "amber": ("◆", "Amber"), "green": ("●", "Green"),
}
_TIER_COLOR = {
    "immediate": palette.RED, "short-term": palette.AMBER, "medium-term": palette.GREEN,
    "red": palette.RED, "amber": palette.AMBER, "green": palette.GREEN,
}
# The tier vocabularies that appear as table columns.
TIER_COLUMNS = ("rpi_tier", "zone_tier", "tier", "tier_without_evidence", "tier_with_evidence")


def tier_label(tier):
    """'immediate' -> '▲ Immediate'; unknown values come back as text unchanged."""
    key = str(tier).strip().lower()
    if key in _TIERS:
        glyph, label = _TIERS[key]
        return f"{glyph} {label}"
    return str(tier)


def tier_color(tier):
    return _TIER_COLOR.get(str(tier).strip().lower())


def tier_pill_html(tier):
    """A small outlined pill: glyph + word, coloured by tier."""
    key = str(tier).strip().lower()
    cls = {"red": "immediate", "amber": "short-term", "green": "medium-term"}.get(key, key)
    if key not in _TIERS:
        return f'<span class="gd-pill">{html.escape(str(tier))}</span>'
    return f'<span class="gd-pill gd-pill-{cls}">{html.escape(tier_label(tier))}</span>'


# Friendly headers and bar-style columns for the columns the app shows.
LABELS = {
    "habitation_id": "ID", "name": "Name", "population": "Residents", "vulnerability": "Vulnerability",
    "zone_score": "Zone score", "rpi": "Priority index", "rpi_tier": "Tier", "zone_tier": "Zone",
    "red_distance_m": "Distance to Red (m)", "buffer_m": "Buffer (m)", "buffer_factor": "Buffer factor",
    "route_risk": "Route risk", "route_flag": "Route flag", "riskiest_cell": "Riskiest cell",
    "riskiest_cell_score": "Riskiest cell score", "site_id": "Site", "capacity_people": "Capacity",
    "allocated_people": "Allocated", "remaining_capacity": "Remaining", "area_limit": "Area limit",
    "water_limit": "Water limit", "sanitation_limit": "Sanitation limit", "limiting_resource": "Limiting resource",
    "incident_id": "Incident", "riskLevel": "Risk level", "eventType": "Event", "locationSource": "Location source",
    "accuracyM": "Accuracy (m)", "ecs": "Evidence confidence", "cluster_id": "Cluster", "comms_degraded": "Comms degraded",
    "timestamp": "Time", "pct_runs_same_tier": "Same tier (%)",
}
# column -> (min, max, format)
BARS = {
    "rpi": (0, 100, "%.1f"), "zone_score": (0, 100, "%.1f"), "route_risk": (0, 100, "%.0f"),
    "riskiest_cell_score": (0, 100, "%.0f"), "vulnerability": (0, 1, "%.2f"), "ecs": (0, 1, "%.2f"),
    "pct_runs_same_tier": (0, 100, "%.0f"),
}


def prepare_table(df):
    """Return (display_df, column_config_spec) for st.dataframe.

    Tier columns are replaced by their glyph + word labels. column_config_spec
    maps column -> dict(label=..., bar=(min, max, fmt) or None) so the caller
    (or a test) can inspect it without Streamlit.
    """
    out = df.copy()
    spec = {}
    for col in out.columns:
        if col in TIER_COLUMNS:
            out[col] = out[col].map(tier_label)
        spec[col] = {"label": LABELS.get(col), "bar": BARS.get(col)}
    return out, spec


def _color_tier_cell(val):
    c = tier_color(str(val).split(" ", 1)[-1])
    return f"color:{c};font-weight:600" if c else ""


def show_table(st, df, **kwargs):
    """st.dataframe with tier labels, progress bars and friendly headers."""
    shown, spec = prepare_table(df)
    cfg = {}
    for col, s in spec.items():
        label = s["label"]
        if s["bar"] is not None:
            lo, hi, fmt = s["bar"]
            cfg[col] = st.column_config.ProgressColumn(label or col, min_value=lo, max_value=hi, format=fmt)
        elif str(shown[col].dtype).startswith("float"):
            cfg[col] = st.column_config.NumberColumn(label or col, format="%.0f" if col.endswith("_m") else "%.2f")
        elif label:
            cfg[col] = st.column_config.Column(label)
    target = shown
    tier_cols = [c for c in shown.columns if c in TIER_COLUMNS]
    if tier_cols:
        try:
            target = shown.style.map(_color_tier_cell, subset=tier_cols)
        except Exception:  # Styler unavailable: labels alone still carry the tier
            target = shown
    kwargs.setdefault("hide_index", True)
    kwargs.setdefault("width", "stretch")
    return st.dataframe(target, column_config=cfg, **kwargs)
