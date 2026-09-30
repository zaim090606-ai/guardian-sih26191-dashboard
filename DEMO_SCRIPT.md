# Guardian x SIH26191: 3-minute demo script

All data on screen is illustrative (synthetic hillside grid, 40 habitations, 3 candidate sites, 30 sample
Guardian reports). Only the Live Scenario feeds are real.

## Before you start (30 seconds, off stage)

1. `cd dashboard && streamlit run app.py`
2. Nothing to refresh: in Sample mode, report freshness is measured from a fixed "sample as-of" time
   (28 Sep 2026, stored in `sample_incidents.json`), so the numbers below do not change with today's date.
3. Sidebar > **Hazard scenario**: set the slider to **1.00**. It starts at a live-derived value, so this makes
   the numbers below repeatable. Leave **Incident data source** on **Sample data**.

All expected numbers assume the defaults plus that 1.00 setting. Default zone weights come from the AHP
inputs: hazard 0.54, vulnerability 0.30, history 0.16.

## Click path

| Time | Click | Say | Judge should see |
|---|---|---|---|
| 0:00 | Open **Overview** | "Red Zones are planned from above, distress is confirmed from the ground, and we flag where the network fails, because response is hardest there." | Tier counts **9 immediate / 8 short-term / 23 medium-term**. **29 Red cells**. **30 incidents**, **7 comms-degraded**. A data-status badge and "Sample data as of 28 Sep 2026". |
| 0:25 | **Map** tab. Toggle layers in the map's layer box. | "Colour is the Zone Risk Score. Circles are Guardian reports, coloured by risk level and sized by GPS accuracy. Orange dashed rings arrived late or through mesh relay." | 400 coloured cells, habitation dots, 3 site markers, route lines coloured by route risk. |
| 0:50 | In **Map**, under "Inspect a score why breakdown" choose Habitation **H12** | "Every number explains itself." | RPI **100.0, immediate**. The why shows vulnerability index parts, the buffer rule (0 m to a Red cell, factor 1.25) and route risk. |
| 1:10 | **Evidence** tab. Show the triage queue. Pick the top cluster, set status **Confirmed**, note "seen on site", **Save review** | "A reviewer confirms or dismisses each cluster. Dismissed clusters give no score bonus." | Top cluster `C16-15|INC-0004`: 4 reports, triage score about 1.2. Warning about **6 unlocated reports** (3 null fix, 3 placeholder 0,0), kept as partial evidence. |
| 1:35 | **Impact of Ground Evidence** tab | "Same scoring twice: without and with Guardian evidence. One habitation changes tier purely from corroborated ground reports." | H22 goes **medium-term to short-term** (RPI 31.6 to 35.1). Tier totals 9/7/24 without vs 9/8/23 with. |
| 2:00 | **Relocation** tab. Scroll: capacity table, allocation, then **Download eligibility log CSV** and **Decision report** (choose H12, **Download report (HTML)**) | "Capacity is the minimum of area, water and sanitation. Each decision exports as a one-page report with its assumptions and limits." | S1 limited by sanitation (7,062 of 7,140 used), S2 by water, S3 by area. **27 allocated, 13 unallocated (12,554 people)**, with reasons. One habitation flagged "no safe route: field review". |
| 2:25 | Sidebar > **Zone risk scoring**: nudge one AHP slider, e.g. "Hazard vs vulnerability", then reset it. Then **Method & Limits** | "Weights come from pairwise comparison with a consistency check. Tell us your priorities and the ranking moves." | AHP matrix, weights and **consistency ratio 0.008** (warns above 0.1). "Compared with existing approaches" table. |
| 2:45 | **Live Scenario** tab. Open **All-India alerts (latest 20)** | "This is real public data, fetched politely: ETag caching, at most one call every 10 minutes, honest User-Agent." | Live/Cached/Sample badges. Alert list as published. Region count, or "No active alert for this region". |
| 2:55 | **Scorecard** tab | "Every Implemented mark is backed by a passing test." | Requirement table with test names. |

Optional extras if time allows (not counted in the 3 minutes): sidebar **Cinematic 3D mode** toggle then the tilt
button on the Map tab; **Run robustness check** in the Relocation tab (about a minute, so start it early).

## Numbers cheat sheet (defaults, slider 1.00, Sample data)

- Zones: 248 Green, 123 Amber, 29 Red (without Guardian evidence: 249 / 122 / 29).
- Habitations: 9 immediate, 8 short-term, 23 medium-term. Top three by RPI: H12 (100.0), H32 (98.7), H13 (91.1).
- Buffer rule applied to 3 habitations: H07 and H12 inside a Red cell (x1.25), H18 at about 37 m (x1.07).
- Incidents: 24 with a position + 6 unlocated = 30. Comms-degraded 7 across both groups.
- Allocation: 27 allocated, 13 unallocated. Reasons: 8 sanitation at S1, 2 area at S3, 2 water at S2, 1 no safe route.
- Site limits: S1 sanitation 7,140, S2 water 6,624, S3 area 19,001.
- AHP: weights 0.540 / 0.297 / 0.163, CR 0.008.

If a number differs, the usual cause is the hazard slider not being at 1.00. Live and Cached data (Firestore,
SACHET, weather) use the real clock and are not part of these numbers. The tier flip (H22) is the one to
check before presenting.

---

# Known limits and what is illustrative

**Illustrative (synthetic, seeded, not a real place):**
- The 20x20 hazard grid, slopes, past-incident counts, the 40 habitations, populations, livestock, and the
  3 candidate safe sites with their water and toilet supply.
- All four vulnerability components (elderly share, disabled share, housing fragility, livestock dependence);
  they are aggregated shares, not records of real people.
- The 30 sample Guardian reports, including their transcripts, audio labels, relay delays and reviewer status.
- Every weight, threshold, cap and norm: AHP judgements, Red/Amber cut-offs, evidence bonuses, the buffer rule
  (50 m / 30 m, up to +25%, inspired by public reports and not an official standard), route-risk threshold,
  capacity norms (Sphere-style defaults, to be verified) and the livestock figures.
- The cell size: about 278 m by 240 m, so 30-50 m buffers are indicative only.

**Real (Live Scenario tab only):** Open-Meteo rainfall, river discharge and elevation; USGS earthquakes; GDACS
events; the NDMA SACHET RSS alert index. They only nudge the default hazard-scenario multiplier, which the
sidebar slider overrides.

**Not claimed:**
- No validation against any real event. Scores show how the method works, not that it is correct.
- Not a real-time national hazard map, not an official order, and not a substitute for a geological survey.
  The decision reports support a human field review.
- The GSI landslide susceptibility layer is not loaded (no file provided); the grid is synthetic.
- Comparisons with other tools are worded "as far as we found" and may miss features.

**Guardian app and relay:**
- Relay payloads are unauthenticated, so a receiver cannot verify the sender.
- Relay reaches only nearby participating Guardian devices; delivery is not guaranteed.
- PDR positions are estimates that drift with distance walked.
- The relay payload does not yet carry risk level, event type or location source (needs two phones to test).

**Data handling and services:**
- User IDs and phone numbers are stripped as soon as reports are loaded and are never shown or sent to Gemini.
- Gemini only receives computed summary numbers (Brief) or official alert text (summaries); with no key the app
  uses a template or the raw text.
- Live Firestore mode reads one page with no retry and falls back to sample data on any error.
- SACHET: one poll per 10 minutes at most, ETag reuse on 304. On 403 or errors the app shows a stored copy under a day
  old, otherwise labelled sample alerts. The current all-India feed rarely mentions the demo region, so
  "No active alert for this region" is a normal result.
- GDACS is slow (up to about 20 s); the first Live Scenario load may take a while.
- A hardcoded Gemini key exists in the Flutter app (`lib/services/ai_service.dart`); rotate it before real deployment.
