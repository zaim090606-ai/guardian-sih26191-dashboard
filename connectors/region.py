"""Phase 6 region of interest: Chamoli district, Uttarakhand, India.

Chosen to match the illustrative hillside theme already used in
`data_gen.py` (landslide/hazard-prone Himalayan terrain, near the real town
of Joshimath). The bounding box below is a hand-drawn APPROXIMATION of
Chamoli district for filtering public hazard feeds (USGS, GDACS, SACHET) —
it is not an official administrative boundary. Habitations and population
used elsewhere in this dashboard remain entirely illustrative/synthetic;
only the live feeds in `connectors/` query real coordinates.
"""

REGION_NAME = "Chamoli, Uttarakhand, India"

# Representative point for point-based queries (Open-Meteo forecast/flood/
# elevation): Joshimath town, a real settlement in Chamoli district.
REGION_LAT = 30.5563
REGION_LON = 79.5642

# Approximate bounding box (min_lon, min_lat, max_lon, max_lat) covering
# Chamoli district, used to filter USGS/GDACS event feeds and to text-match
# SACHET alert area descriptions. Deliberately generous rather than tight.
REGION_BBOX = {
    "min_lon": 79.0,
    "min_lat": 29.9,
    "max_lon": 80.3,
    "max_lat": 31.1,
}

REGION_NAME_MATCH_TERMS = ["chamoli", "uttarakhand", "joshimath", "badrinath", "gopeshwar"]


def point_in_region(lat, lon):
    return (
        REGION_BBOX["min_lat"] <= lat <= REGION_BBOX["max_lat"]
        and REGION_BBOX["min_lon"] <= lon <= REGION_BBOX["max_lon"]
    )


def bbox_intersects_region(min_lon, min_lat, max_lon, max_lat):
    return not (
        max_lon < REGION_BBOX["min_lon"]
        or min_lon > REGION_BBOX["max_lon"]
        or max_lat < REGION_BBOX["min_lat"]
        or min_lat > REGION_BBOX["max_lat"]
    )


def text_mentions_region(text):
    if not text:
        return False
    lowered = text.lower()
    return any(term in lowered for term in REGION_NAME_MATCH_TERMS)
