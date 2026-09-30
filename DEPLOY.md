# Deploying the dashboard

All data is illustrative/synthetic; Phase 6 connectors fetch public data and fall
back to labelled sample data offline.

## Run locally

```
python -m venv .venv && . .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

No `.env`, API key or network is needed to start (tests/test_offline.py); connectors fall back to labelled sample data. Default mode is **Sample data**; the Brief tab uses a plain
template. Live Firestore mode needs a `.firebaserc` in a parent folder and falls
back to sample data if absent.

## Optional configuration

| Variable | Effect |
|---|---|
| `GEMINI_API_KEY` | Enables Gemini wording in the Brief tab and SACHET summaries. Unset = template/raw text. |

Set it as an environment variable or a host secret (Streamlit Community Cloud →
App settings → Secrets). Do not commit it; `.env`, `secrets.toml` and
`review_state.json` are gitignored. See `.env.example`.

## Streamlit Community Cloud

1. Push this folder as its own repo.
2. New app → select repo, main file `app.py`, **Python 3.12** (Advanced settings). All pins in `requirements.txt` have published Python 3.12 wheels (checked with `pip download --python-version 3.12 --only-binary=:all:`).
3. Optionally add `GEMINI_API_KEY` under Secrets.

## Checks before publishing

- `python -m pytest tests/` (needs `pip install pytest`; no network required).
- Secret/PII scan done: no keys, phone numbers or user IDs in the tree
  (`sample_incidents.json` has `userId`/`userPhone` stripped at load; tests use fake values).
- `connectors/.cache/` is gitignored; first load may take ~20 s (GDACS) with no cache.
