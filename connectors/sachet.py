"""NDMA SACHET (India CAP alert feed) connector.

UPDATE: the feed URL now comes from sachet_feed_url.txt (RSS index) and requests follow
NDMA's Integration Guide for Agencies (ETag / If-None-Match / 304 reuse) plus our own polite
limits (honest User-Agent, at most one poll per 10 minutes, no retries). The NEEDS-HUMAN
text below is historical.

**NEEDS-HUMAN — see BUILD_LOG.md, Phase 6 pre-work.** Despite reading the
official `Integration_Guide_For_Agencies.pdf`, inspecting the `/CapFeed`
page's source, and probing ~14 plausible URL patterns, no working public
"list current alerts" endpoint was found. The only endpoint NDMA documents
publicly fetches ONE alert already known by its CAP identifier:

    GET https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile?identifier=<id>

`LIST_ALERTS_URL` below is an **unverified placeholder** (reuses the same
base path, since that's the only confirmed-real path segment). A human with
the actual list/RSS endpoint — or NDMA integration access, see the PDF's
control-room contact — should replace it; nothing else in this file needs to
change. Until then, `fetch_active_alerts()` will fail against the
placeholder exactly like a real outage would, and correctly falls back to
sample data via the same `fetch_with_fallback` path every other connector
uses — this is the intended degraded behavior, not a bug to silently hide.

Gemini constraint (per spec): `summarize_alert_text()` may only summarise the
official alert text already present in a parsed record — it must never
invent facts, and falls back to the raw, unmodified text with no key or on
any error.
"""

import json
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

from . import region
from . import base as _base
from .base import DEFAULT_TIMEOUT_S, FetchResult, now_iso

SOURCE_ATTRIBUTION = "NDMA SACHET (India CAP feed)"

# UNVERIFIED PLACEHOLDER — see module docstring.
LIST_ALERTS_URL = "https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile"

# The one endpoint NDMA's own Integration Guide documents: fetches a single
# already-known alert by CAP identifier. Not used by fetch_active_alerts()
# (which needs to discover alerts, not fetch a known one), but kept here,
# confirmed-correct, for when a human wires up real alert discovery.
FETCH_SINGLE_ALERT_URL = "https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile"

# Optional operator-supplied feed URL: first non-empty line of
# dashboard/sachet_feed_url.txt. If present it replaces LIST_ALERTS_URL.
FEED_URL_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sachet_feed_url.txt")

# Polite-consumer rules. NDMA's "CAP XML Feed Integration Guide for Agencies"
# requires ETag caching: store the XML and its ETag, send If-None-Match on every
# later request, and on 304 use the stored copy and do not call again. The guide
# sets no polling interval or User-Agent; the values below are our own choices.
USER_AGENT = "GuardianSIH-Prototype/1.0 (student hackathon project)"
MIN_POLL_INTERVAL_S = 10 * 60  # never contact the feed more than once per 10 minutes
STORED_COPY_MAX_AGE_S = 24 * 60 * 60  # older stored copies are not shown as current
STATE_FILE = "sachet_feed_state.json"

CAP_NS = {"cap": "urn:oasis:names:tc:emergency:cap:1.2"}

GEMINI_MODEL_NAME = "gemini-1.5-flash"  # matches lib/services/ai_service.dart


def _sample_alerts():
    """ILLUSTRATIVE sample alerts, shaped like parsed CAP records."""
    now = datetime.now(timezone.utc).isoformat()
    return [
        {
            "identifier": "SAMPLE-0001",
            "sender": "ILLUSTRATIVE (sample data, not a real NDMA sender)",
            "sent": now,
            "event": "Flood Warning",
            "headline": "ILLUSTRATIVE sample flood warning for Chamoli district",
            "description": (
                "This is sample data, not a real NDMA alert — no working SACHET "
                "alert-list endpoint was available (see BUILD_LOG.md NEEDS-HUMAN)."
            ),
            "severity": "Moderate",
            "urgency": "Expected",
            "certainty": "Likely",
            "area_desc": "Chamoli, Uttarakhand (sample)",
            "effective": now,
            "expires": now,
            "web": "https://sachet.ndma.gov.in/",
        }
    ]


def _find(parent, tag):
    if parent is None:
        return None
    el = parent.find(f"cap:{tag}", CAP_NS)
    if el is None:
        el = parent.find(tag)
    return el


def _text(parent, tag):
    el = _find(parent, tag)
    if el is not None and el.text:
        return el.text.strip()
    return None


def parse_cap_xml(xml_text):
    """Parses one or more CAP <alert> elements from raw XML text into plain
    dicts. Tolerant of a bare <alert> root or a wrapper containing several
    <alert> children. Never raises — returns [] on anything unparseable."""
    if not xml_text:
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    if root.tag.endswith("alert"):
        alert_elements = [root]
    else:
        alert_elements = root.findall(".//cap:alert", CAP_NS)
        if not alert_elements:
            alert_elements = root.findall(".//alert")

    records = []
    for alert_el in alert_elements:
        info_el = _find(alert_el, "info")
        area_el = _find(info_el, "area") if info_el is not None else None
        records.append(
            {
                "identifier": _text(alert_el, "identifier"),
                "sender": _text(alert_el, "sender"),
                "sent": _text(alert_el, "sent"),
                "event": _text(info_el, "event"),
                "headline": _text(info_el, "headline"),
                "description": _text(info_el, "description"),
                "severity": _text(info_el, "severity"),
                "urgency": _text(info_el, "urgency"),
                "certainty": _text(info_el, "certainty"),
                "area_desc": _text(area_el, "areaDesc"),
                "effective": _text(info_el, "effective"),
                "expires": _text(info_el, "expires"),
                "web": _text(info_el, "web"),
            }
        )
    return records


def configured_feed_url(path=None):
    """The URL in sachet_feed_url.txt, or None if the file is missing/empty or
    the line is not an http(s) URL."""
    try:
        with open(path or FEED_URL_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    return line if line.lower().startswith(("http://", "https://")) else None
    except OSError:
        pass
    return None


def parse_rss_items(xml_text):
    """Parses an RSS 2.0 alert index (as SACHET's rss_india.xml) into the same
    record shape as parse_cap_xml. RSS items carry only a title, optional
    description, category, link and pubDate, so severity/area fields are None
    and region matching uses title/description text. Never raises."""
    if not xml_text:
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    records = []
    for item in root.iter("item"):
        def t(tag):
            el = item.find(tag)
            return el.text.strip() if el is not None and el.text and el.text.strip() else None

        records.append({
            "identifier": t("guid"), "sender": t("author"), "sent": t("pubDate"),
            "event": t("category"), "headline": t("title"), "description": t("description"),
            "severity": None, "urgency": None, "certainty": None, "area_desc": None,
            "effective": t("pubDate"), "expires": None, "web": t("link"),
        })
    return records


def filter_alerts_to_region(alerts):
    """Keeps only alerts whose area description, headline, or description
    text mentions the region (see region.py's REGION_NAME_MATCH_TERMS).
    Text-based, since CAP <area><polygon>/<circle> geometry parsing would add
    real complexity for a feed we can't currently even reach live."""
    return [
        a
        for a in alerts
        if region.text_mentions_region(a.get("area_desc"))
        or region.text_mentions_region(a.get("headline"))
        or region.text_mentions_region(a.get("description"))
    ]


def _state_path():
    os.makedirs(_base.CACHE_DIR, exist_ok=True)
    return os.path.join(_base.CACHE_DIR, STATE_FILE)


def _load_state(url):
    try:
        with open(_state_path(), encoding="utf-8") as f:
            state = json.load(f)
        return state if state.get("url") == url else {}
    except Exception:
        return {}


def _save_state(state):
    try:
        with open(_state_path(), "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass


def _parse_feed(text):
    return parse_cap_xml(text) or parse_rss_items(text)


def _from_stored(state, error):
    """Stored copy as a 'cached' result, or None if absent/too old."""
    body = state.get("body")
    if not body or time.time() - state.get("fetched_epoch", 0) > STORED_COPY_MAX_AGE_S:
        return None
    records = _parse_feed(body)
    if not records:
        return None
    return FetchResult(status="cached", data=records, fetched_at=state["fetched_at"],
                       source=f"{SOURCE_ATTRIBUTION} (stored copy)", error=error)


def _sample_result(error):
    return FetchResult(status="sample", data=_sample_alerts(), fetched_at=now_iso(),
                       source=f"{SOURCE_ATTRIBUTION} (sample fallback)", error=error)


def fetch_active_alerts(timeout_s=DEFAULT_TIMEOUT_S):
    """Unfiltered fetch (all parsed alerts, not yet region-filtered).

    One request at most every MIN_POLL_INTERVAL_S (failures count, so there is
    no retry loop); honest User-Agent; If-None-Match with the stored ETag; 304
    reuses the stored copy. On 403 or any error: stored copy (labelled cached
    with its own timestamp), else labelled sample data. Never raises."""
    url = configured_feed_url() or LIST_ALERTS_URL
    state = _load_state(url)
    now = time.time()

    if state and now - state.get("last_attempt_epoch", 0) < MIN_POLL_INTERVAL_S:
        wait = "polled within the last 10 minutes; not contacting the feed again yet"
        return _from_stored(state, wait) or _sample_result(state.get("last_error") or wait)

    state = {**state, "url": url, "last_attempt_epoch": now}
    headers = {"User-Agent": USER_AGENT}
    if state.get("etag") and state.get("body"):
        headers["If-None-Match"] = state["etag"]
    try:
        resp = requests.get(url, headers=headers, timeout=timeout_s)
        code = getattr(resp, "status_code", 200)
        if code == 304 and state.get("body"):
            state.update(fetched_at=now_iso(), fetched_epoch=now, last_error=None)
            _save_state(state)
            records = _parse_feed(state["body"])
            if records:
                return FetchResult(status="live", data=records, fetched_at=state["fetched_at"],
                                   source=f"{SOURCE_ATTRIBUTION} (unchanged, HTTP 304)")
            raise ValueError("stored copy unreadable after 304")
        if code == 403:
            raise PermissionError("HTTP 403 from the feed; backing off, not retrying")
        resp.raise_for_status()
        records = _parse_feed(resp.text)
        if not records:
            raise ValueError("No alert records could be parsed from the response")
        etag = (getattr(resp, "headers", None) or {}).get("ETag")
        state.update(body=resp.text, etag=etag, fetched_at=now_iso(), fetched_epoch=now, last_error=None)
        _save_state(state)
        return FetchResult(status="live", data=records, fetched_at=state["fetched_at"], source=SOURCE_ATTRIBUTION)
    except Exception as e:  # noqa: BLE001 - any failure degrades to stored copy or sample
        state["last_error"] = str(e)
        _save_state(state)
        return _from_stored(state, str(e)) or _sample_result(str(e))


def detect_script_language(text):
    """Language guess from the writing script only (RSS items carry no language
    field): Latin script is reported as English/Latin since it may also be a
    romanised regional language."""
    ranges = [("Hindi/Devanagari", 0x0900, 0x097F), ("Bengali", 0x0980, 0x09FF), ("Gurmukhi (Punjabi)", 0x0A00, 0x0A7F),
              ("Gujarati", 0x0A80, 0x0AFF), ("Odia", 0x0B00, 0x0B7F), ("Tamil", 0x0B80, 0x0BFF),
              ("Telugu", 0x0C00, 0x0C7F), ("Kannada", 0x0C80, 0x0CFF), ("Malayalam", 0x0D00, 0x0D7F),
              ("Urdu/Arabic", 0x0600, 0x06FF)]
    counts = {}
    for ch in text or "":
        cp = ord(ch)
        for name, lo, hi in ranges:
            if lo <= cp <= hi:
                counts[name] = counts.get(name, 0) + 1
    return max(counts, key=counts.get) if counts else "English/Latin script"


def _sent_datetime(alert):
    raw = alert.get("sent") or alert.get("effective")
    if not raw:
        return None
    for parse in (parsedate_to_datetime, datetime.fromisoformat):
        try:
            dt = parse(raw)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None


def latest_alerts(alerts, n=20):
    """Newest-first list of at most n alerts, unfiltered, text as published."""
    floor = datetime.min.replace(tzinfo=timezone.utc)
    ordered = sorted(alerts or [], key=lambda a: _sent_datetime(a) or floor, reverse=True)
    return ordered[:n]


def fetch_alerts_for_region(timeout_s=DEFAULT_TIMEOUT_S):
    """Same as fetch_active_alerts(), with the result's `data` narrowed to
    alerts that mention the configured region — including for the sample
    fallback, so the 'no live feed available' case still only shows relevant
    sample content."""
    result = fetch_active_alerts(timeout_s)
    result.all_alerts = list(result.data or [])  # unfiltered, for the All-India list
    if result.data:
        result.data = filter_alerts_to_region(result.data)
    return result


def summarize_alert_text(alert, api_key=None):
    """Gemini may ONLY summarise this alert's own official text (headline +
    description) — never invent facts. No key, empty text, or any API error
    all fall back to the raw text unmodified."""
    raw_text = " ".join(t for t in [alert.get("headline"), alert.get("description")] if t)
    if not raw_text:
        return "(no alert text)"

    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        return raw_text

    try:
        from google import genai

        client = genai.Client(api_key=key)
        prompt = (
            "Summarize the following OFFICIAL disaster alert text in one factual "
            "sentence. Do not add any fact, number, or claim that is not already "
            "present in the text below.\n\n" + raw_text
        )
        response = client.models.generate_content(model=GEMINI_MODEL_NAME, contents=prompt)
        text = getattr(response, "text", None)
        return text.strip() if text and text.strip() else raw_text
    except Exception:
        return raw_text
