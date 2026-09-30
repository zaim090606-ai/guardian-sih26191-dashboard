"""Route safety for the SIH26191 prototype. Illustrative: a route is a straight
line from a habitation to a candidate site, sampled at N points that are mapped
to grid cells; it is NOT a real road/path network. Zone scores come from the
illustrative grid, so route risk is illustrative too.
"""

import numpy as np

import data_gen
import palette

N_ROUTE_SAMPLES = 20
DEFAULT_ROUTE_THRESHOLD = 60.0
MAX_WEIGHT = 0.6
MEAN_WEIGHT = 0.4
AMBER_FRACTION = 0.75  # route is amber from this fraction of the threshold up
UNSAFE_FLAG = "unsafe: delay or use alternate"
SAFE_FLAG = "safe"
NO_SAFE_ROUTE_FLAG = "no safe route: field review"


def _cell_rc(lat, lon):
    row = int(np.clip((lat - data_gen.ORIGIN_LAT) / data_gen.CELL_SIZE_DEG, 0, data_gen.GRID_SIZE - 1))
    col = int(np.clip((lon - data_gen.ORIGIN_LON) / data_gen.CELL_SIZE_DEG, 0, data_gen.GRID_SIZE - 1))
    return row, col


def sample_route_cells(lat1, lon1, lat2, lon2, n=N_ROUTE_SAMPLES):
    """(row, col) of the grid cell under each of n evenly spaced points on the
    straight line from (lat1, lon1) to (lat2, lon2), endpoints included."""
    lats = np.linspace(lat1, lat2, n)
    lons = np.linspace(lon1, lon2, n)
    return [_cell_rc(a, b) for a, b in zip(lats, lons)]


def zone_score_lookup(grid):
    """{(row, col): (cell_id, zone_score)} from the scored grid."""
    return {
        (int(r), int(c)): (cid, float(s))
        for r, c, cid, s in zip(grid["row"], grid["col"], grid["cell_id"], grid["zone_score"])
    }


def route_risk(lat1, lon1, lat2, lon2, lookup, scenario_multiplier=1.0,
               threshold=DEFAULT_ROUTE_THRESHOLD, n=N_ROUTE_SAMPLES):
    """Route Risk (0-100) = 0.6 x max zone score + 0.4 x mean zone score along
    the route, scaled by the scenario multiplier and capped at 100."""
    cells = [lookup[rc] for rc in sample_route_cells(lat1, lon1, lat2, lon2, n)]
    scores = [s for _, s in cells]
    riskiest_cell, riskiest_score = max(cells, key=lambda x: x[1])
    raw = MAX_WEIGHT * max(scores) + MEAN_WEIGHT * float(np.mean(scores))
    risk = min(100.0, raw * scenario_multiplier)
    return {
        "route_risk": risk,
        "route_flag": UNSAFE_FLAG if risk >= threshold else SAFE_FLAG,
        "riskiest_cell": riskiest_cell,
        "riskiest_cell_score": riskiest_score,
    }


def route_color(risk, threshold):
    if risk >= threshold:
        return palette.RED
    if risk >= threshold * AMBER_FRACTION:
        return palette.AMBER
    return palette.GREEN


def make_route_fn(grid, scenario_multiplier=1.0, threshold=DEFAULT_ROUTE_THRESHOLD):
    """Callable (hab_row, site_row) -> route_risk dict, for greedy_allocate."""
    lookup = zone_score_lookup(grid)

    def fn(hab, site):
        return route_risk(hab["lat"], hab["lon"], site["lat"], site["lon"], lookup,
                          scenario_multiplier, threshold)

    return fn
