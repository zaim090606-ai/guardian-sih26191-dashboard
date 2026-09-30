import os
import sys

# dashboard/*.py modules use plain imports (import data_gen, etc.), so the
# dashboard/ directory (parent of tests/) must be on sys.path for pytest,
# which by default only adds the test file's own directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402


@pytest.fixture
def isolated_connector_cache(tmp_path, monkeypatch):
    """Points connectors.base.CACHE_DIR at a fresh temp directory, so one
    test's 'live' write can never leak into another test's 'should fall
    back to sample' assertion. Opt in explicitly in connector test modules
    (not autouse — irrelevant to non-connector tests)."""
    from connectors import base as connectors_base

    monkeypatch.setattr(connectors_base, "CACHE_DIR", str(tmp_path))
