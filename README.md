# SIH26191 Prototype Dashboard

A Streamlit/Folium dashboard built on top of the Guardian emergency app, for
Smart India Hackathon problem statement **SIH26191** (hazard Red Zones,
relocation carrying capacity, ranked relocation).

**Everything here is illustrative.** The hazard grid, habitations, safe
sites, and sample incidents are seeded synthetic data (`data_gen.py`), not a
real survey. See the app's **Method & Limits** tab for the full disclaimer.

Core idea: Red Zones are planned from above (hazard/vulnerability/history),
distress is confirmed from the ground (Guardian's emergency reports), and
places where the network itself fails are flagged — because that is where
response is hardest.

## Setup

```bash
cd dashboard
pip install -r requirements.txt
python data_gen.py          # regenerates sample_incidents.json (optional — already committed)
streamlit run app.py
```

Optional: set `GEMINI_API_KEY` in the environment for the Brief tab to call
Gemini instead of falling back to a plain template brief.

## Running the tests

```bash
cd dashboard
pip install pytest
python -m pytest tests/
```

68 tests across `test_scoring.py`, `test_relocation.py`, `test_guardian_layer.py`,
`test_pipeline_impact.py`, `test_app_smoke.py`, and `test_connectors_*.py` (Phase 6
live-data connectors, all with mocked HTTP responses — no network needed to run the
suite). See `BUILD_LOG.md` (repo root) for what each one checks and why.

## Live data (Phase 6)

`connectors/` fetches real public data for **Chamoli, Uttarakhand** (Open-Meteo
rainfall/river-discharge/elevation, USGS earthquakes, GDACS multi-hazard events) to
derive a default hazard-scenario intensity — see the **Live Scenario** tab for each
source's Live/Cached/Sample status and the "why this scenario" explanation. The sidebar
slider always overrides the derived value. The NDMA SACHET connector currently runs on
sample data only — see `BUILD_LOG.md`'s NEEDS-HUMAN list.

## 2-minute demo flow

1. **Map tab** — point out the Red/Amber/Green zone grid, the habitation and
   safe-site markers, and the incident circles. Toggle the "Comms-degraded"
   layer to show the dashed-orange overlay — "where the network fails,
   response is hardest." Pick a Red cell and a habitation from the two
   dropdowns below the map to show the score "why" breakdown.
2. **Evidence tab** — show the incident table sorted by Evidence Confidence
   Score, then open one incident to show its ECS breakdown next to its
   transcript/audio analysis text.
3. **Relocation tab** — show the ranked-by-RPI habitation table, the greedy
   allocation to the 3 candidate safe sites, and the unallocated list.
   Download the CSV.
4. **Impact of Ground Evidence tab** — this is the punch line. With the
   default sidebar settings, at least one habitation visibly flips
   relocation tier purely because of a corroborated cluster of ground
   reports. Open its expander to show the before/after zone score and RPI.
5. **Brief tab** — click "Generate briefing" and show the state-authority
   briefing text, generated only from the computed summary numbers shown
   right above it (no raw transcript ever reaches the prompt).
6. **Live Scenario tab** — real live data (rainfall, river discharge, terrain slope,
   earthquakes, GDACS events) for Chamoli, with Live/Cached/Sample badges and the
   "why this scenario" reasons behind the sidebar's derived multiplier default.
7. **Scorecard tab** — the SIH26191 requirement coverage table, each row
   backed by a real, currently-passing test.

Along the way, open the sidebar and move the hazard-scenario slider or the
evidence-bonus-cap slider to show every tab react live.
