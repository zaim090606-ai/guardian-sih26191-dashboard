import pipeline
import report

REQUIRED = ["Zone score breakdown", "Guardian evidence", "Route risk", "Capacity limiter", "Buffer rule",
            "Decision", "Assumptions", "Data and time", "Limits"]


def _res():
    return pipeline.run_pipeline(review_state={})


def test_habitation_report_has_every_section_in_both_formats():
    res = _res()
    for hid in (res["habitations"]["habitation_id"].iloc[0], res["unallocated"]["habitation_id"].iloc[0]):
        rep = report.habitation_report(res, hid)
        md, html_ = report.to_markdown(rep), report.to_html(rep)
        heads = [h for h, _ in rep["sections"]]
        for want in REQUIRED:
            assert any(want in h for h in heads), want
        assert "Sample data" in md and "Generated (UTC)" in md and "tier" in md.lower()
        assert html_.startswith("<!doctype html>") and "</html>" in html_


def test_site_report_and_no_personal_fields():
    res = _res()
    sid = res["sites_after"]["site_id"].iloc[0]
    rep = report.site_report(res, sid)
    md = report.to_markdown(rep)
    for want in ("Capacity limiter", "Limiting resource", "Route risk", "Buffer rule"):
        assert want in md
    assert "userPhone" not in md and "userId" not in md and "transcript" not in md.lower()


def test_html_escapes_content():
    rep = {"title": "<b>x</b>", "subtitle": "s", "sections": [("h", [("a", "<script>")])]}
    out = report.to_html(rep)
    assert "<script>" not in out and "&lt;script&gt;" in out
