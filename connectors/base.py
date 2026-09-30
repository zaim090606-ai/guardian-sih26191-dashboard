"""Shared fetch-with-cache-and-fallback helper for every Phase 6 connector.

Every connector call returns a FetchResult so the UI can show a
Live/Cached/Sample badge with a timestamp and source attribution, and so a
network failure never crashes the dashboard: it falls back to an on-disk
cache, then to bundled sample data. No connector call is allowed to raise —
`fetch_with_fallback` catches everything from `fetch_fn`.
"""

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
DEFAULT_TIMEOUT_S = 8
DEFAULT_CACHE_MAX_AGE_S = 20 * 60  # 20 minutes; matches the dashboard's auto-refresh interval


@dataclass
class FetchResult:
    status: str  # 'live' | 'cached' | 'sample'
    data: Any
    fetched_at: str  # ISO timestamp of when this data was actually obtained
    source: str  # attribution string, e.g. "Open-Meteo (CC BY 4.0)"
    error: Optional[str] = None

    @property
    def badge_label(self):
        return {"live": "Live", "cached": "Cached", "sample": "Sample"}.get(self.status, self.status)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _cache_path(cache_key):
    os.makedirs(CACHE_DIR, exist_ok=True)
    safe_key = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in cache_key)
    return os.path.join(CACHE_DIR, f"{safe_key}.json")


def read_cache(cache_key, max_age_s=DEFAULT_CACHE_MAX_AGE_S):
    """Returns the cached payload dict if present and fresh enough, else None.
    Never raises — a corrupt/missing cache file is treated as a cache miss."""
    path = _cache_path(cache_key)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
        age = time.time() - payload["_cached_at_epoch"]
        if age > max_age_s:
            return None
        return payload
    except Exception:
        return None


def write_cache(cache_key, data, fetched_at, source):
    """Best-effort cache write; a failure here must never break the caller."""
    path = _cache_path(cache_key)
    payload = {
        "_cached_at_epoch": time.time(),
        "fetched_at": fetched_at,
        "source": source,
        "data": data,
    }
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except Exception:
        pass


def fetch_with_fallback(
    cache_key,
    fetch_fn: Callable[[], Any],
    sample_fn: Callable[[], Any],
    source: str,
    cache_max_age_s: int = DEFAULT_CACHE_MAX_AGE_S,
) -> FetchResult:
    """Runs `fetch_fn()` (which should perform one live HTTP call — with its
    own timeout — and return parsed data, raising on any failure). On
    success, caches the result and returns status='live'. On any exception,
    falls back to a fresh-enough on-disk cache (status='cached'), and if
    there is none, to `sample_fn()` (status='sample', which must itself never
    raise). This function itself never raises.
    """
    fetched_at = now_iso()
    try:
        data = fetch_fn()
        write_cache(cache_key, data, fetched_at, source)
        return FetchResult(status="live", data=data, fetched_at=fetched_at, source=source)
    except Exception as e:
        cached = read_cache(cache_key, cache_max_age_s)
        if cached is not None:
            return FetchResult(
                status="cached",
                data=cached["data"],
                fetched_at=cached["fetched_at"],
                source=cached["source"],
                error=str(e),
            )
        try:
            sample_data = sample_fn()
        except Exception as sample_error:
            # sample_fn is required to never raise; if it somehow does, still
            # never crash the dashboard — surface an empty, clearly-labelled result.
            return FetchResult(
                status="sample",
                data=None,
                fetched_at=fetched_at,
                source=f"{source} (sample fallback failed: {sample_error})",
                error=str(e),
            )
        return FetchResult(
            status="sample",
            data=sample_data,
            fetched_at=fetched_at,
            source=f"{source} (sample fallback)",
            error=str(e),
        )
