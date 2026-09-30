"""Method & Limits tab: static disclaimers about what this prototype is and
isn't, kept as one place so every other tab can stay brief."""

import pandas as pd
import streamlit as st

METHOD_TEXT = """
### What this is

A hackathon prototype for SIH26191, built to demonstrate one idea end-to-end:
**Red Zones are planned from above** (hazard/vulnerability/history), **distress is
confirmed from the ground** (the Guardian app's emergency reports), and **places where
the network itself fails are flagged**, because that is where response is hardest.

### What the data is

Every hazard cell, habitation, safe site, and sample incident on this dashboard is
**synthetic and seeded** (see `data_gen.py`) — not a real place, not a real survey, not
a real emergency. Only the *shape* of Guardian's real incident data (fields like
`locationSource`, `accuracyM`, `audioEvents`) is real; the values are invented so the
dashboard has something reproducible to run against without needing live phones in the
field.

### What the scores mean (and don't)

- **Zone Risk Score**, **Evidence Confidence Score**, and **Relocation Priority Index**
  are illustrative formulas with adjustable weights/thresholds/caps (see the sidebar),
  not a validated hazard or vulnerability model. Every score returns a "why" breakdown —
  use the Map tab's cell/habitation selectors or the Evidence tab's incident selector to
  see exactly which inputs produced a number.
- **Carrying capacity** is the minimum of three limits: usable area (3.5 m²/person), water
  (15 L/person/day) and sanitation (20 people/toilet), with livestock drawing on water
  (20 L/head/day) and area (3 m²/head). Defaults are illustrative, adjustable, and should be
  verified against the Sphere Handbook; livestock figures are assumptions, not Sphere values.
- **PDR (dead-reckoning) positions and their accuracy estimates are approximations**
  with real uncertainty — a PDR fix drifts the longer a phone has walked since its last
  GPS anchor. `accuracyIsEstimate=true` marks exactly this case.
- **Gemini's briefing is assistive text, not a source of numbers.** It is prompted with
  only the already-computed summary figures (see the Brief tab) — it never invents a
  score, and every number in this dashboard is computed by code, not by the model.

### What this system does NOT claim

- Not a real-time national hazard map, and not a substitute for an official geological
  or hydrological survey.
- Not a guaranteed-delivery communication system — the "comms-degraded" layer exists
  precisely because mesh relay and delayed delivery are real failure modes, not
  edge cases to be hidden.
- Never shows or transmits `userPhone`/`userId` — incidents are identified only by a
  short id (`INC-####` in sample data, or the raw Firestore document id in live mode).

### Known limits of this prototype specifically

- The mesh relay payload (`relay_service.dart` / `mesh_receiver_service.dart`) was not
  extended with `riskLevel`/`eventType`/`locationSource` — that needs two real phones to
  test and is logged as a future item in `BUILD_LOG.md`.
- Live Firestore mode reads via the REST API with the prototype's open rules; it has no
  retry/pagination beyond one page and falls back to sample data on any error, by
  design, so the demo never breaks for lack of network access.
- The Scorecard tab's Implemented/Partial/Not marks are computed when the tests in
  `tests/` were last run, not live inside this app.
- **Relay payloads are unauthenticated:** a relayed emergency message is not signed, so a
  receiver cannot prove who sent it or that it was not altered or forged.
- **Relay reaches only nearby participating Guardian devices**, not the public internet
  or emergency services on its own; delivery depends on such devices being in range.
- **PDR is an estimate:** dead-reckoned positions drift with distance walked and are not
  survey-grade.
- **All data is illustrative:** grid, habitations, sites, livestock and sample incidents
  are synthetic.
- **No validation against real events:** none of the scores or rankings has been tested
  against a real disaster, so they show how the method works, not that it is correct.
- The NDMA SACHET connector (Live Scenario tab) currently runs on sample data: no
  public "list current alerts" endpoint could be found despite reading NDMA's own
  integration guide and probing the feed page — only fetching one already-known alert
  by ID is documented. See `BUILD_LOG.md`'s NEEDS-HUMAN list. Rainfall, river
  discharge, elevation/slope, earthquakes, and GDACS multi-hazard events are all real
  live data for this region.
"""


COMPARISON_INTRO = (
    "Every gap below is worded **as far as we found** from public descriptions of each tool; "
    "we may have missed features, and the tools evolve. This is an illustrative comparison, not a review."
)

COMPARISON_ROWS = [
    {
        "Approach": "Ushahidi-style crisis maps",
        "What it does": "Collects crowdsourced reports (web, SMS, apps) and shows them on a map.",
        "Gap (as far as we found)": "Reports are mostly unstructured text and need connectivity; we found no built-in on-device "
                                    "evidence scoring, offline relay, or link to relocation priority.",
        "What Guardian adds": "Structured on-device reports with an Evidence Confidence Score, mesh relay, a comms-degraded flag.",
    },
    {
        "Approach": "InaSAFE",
        "What it does": "Makes impact maps, summaries, minimum-needs estimates and checklists for a hazard scenario.",
        "Gap (as far as we found)": "Needs external hazard and exposure data supplied by the user; we found no ground-evidence "
                                    "feed from phones in the field.",
        "What Guardian adds": "Ground reports that corroborate or challenge a zone, plus per-habitation relocation ordering.",
    },
    {
        "Approach": "Sahana Eden",
        "What it does": "Disaster-management platform: organisation and resource registries, shelters, requests and needs, people tracking.",
        "Gap (as far as we found)": "Coordination-focused; we found no automatic distress evidence from phones or hazard-zone "
                                    "scoring feeding its priorities.",
        "What Guardian adds": "Distress evidence and Red Zone scoring that could feed a coordination tool's priorities.",
    },
    {
        "Approach": "SACHET (NDMA)",
        "What it does": "Aggregates and disseminates official CAP alerts to the public.",
        "Gap (as far as we found)": "Top-down warnings by area; we found no channel for ground reports back, and no "
                                    "habitation-level relocation ranking.",
        "What Guardian adds": "A bottom-up ground signal and habitation-level ranking beside official alerts.",
    },
    {
        "Approach": "GSI landslide susceptibility maps",
        "What it does": "Geological Survey of India susceptibility maps showing where slopes are prone to landslides.",
        "Gap (as far as we found)": "Static susceptibility layers; we found no live update from ground reports and no "
                                    "capacity or relocation step.",
        "What Guardian adds": "Treats such a layer as one input, adds live ground evidence, carrying capacity and allocation.",
    },
    {
        "Approach": "Bridgefy / Serval mesh apps",
        "What it does": "Peer-to-peer messaging without cellular or internet coverage.",
        "Gap (as far as we found)": "General-purpose messaging; we found no scoring of distress evidence or mapping of "
                                    "messages to hazard zones.",
        "What Guardian adds": "A relayed structured emergency payload that is scored, mapped and used in prioritisation.",
    },
]


def render_ahp_section(ahp_result):
    st.subheader("AHP weights for the Zone Risk Score")
    st.caption("Pairwise judgements (Saaty 1-9) are illustrative demo choices, not elicited from experts. "
               "Weights = principal eigenvector; they are the default zone weights unless overridden in the sidebar.")
    names = list(ahp_result["criteria"])
    st.dataframe(pd.DataFrame(ahp_result["matrix"], index=names, columns=names).round(3), width="stretch")
    st.write("Weights: " + ", ".join(f"{c} {w:.3f}" for c, w in ahp_result["weights"].items()))
    st.write(f"lambda_max {ahp_result['lambda_max']:.3f}, CI {ahp_result['ci']:.3f}, "
             f"**consistency ratio {ahp_result['cr']:.3f}** (warn above 0.1)")
    if not ahp_result["consistent"]:
        st.warning("Consistency ratio above 0.1: the pairwise judgements are inconsistent.")


def render_method_tab(ahp_result=None):
    st.markdown(METHOD_TEXT)
    if ahp_result is not None:
        render_ahp_section(ahp_result)
    st.subheader("Compared with existing approaches")
    st.caption(COMPARISON_INTRO)
    st.dataframe(COMPARISON_ROWS, width="stretch", hide_index=True)
