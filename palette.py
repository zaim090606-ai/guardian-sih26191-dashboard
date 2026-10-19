"""Single Red/Amber/Green palette shared by the map, route lines and overview."""

RED = "#b91c1c"
AMBER = "#a35a06"
GREEN = "#15803d"
TIER_COLORS = {"Red": RED, "Amber": AMBER, "Green": GREEN}
# Relocation Priority Index tiers share the same three colours (>= 4.5:1 on the
# ivory page), so map, tables, legend and hero agree.
RPI_TIER_COLORS = {"immediate": RED, "short-term": AMBER, "medium-term": GREEN}
