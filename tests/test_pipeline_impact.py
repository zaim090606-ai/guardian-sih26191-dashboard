import pipeline


def test_run_pipeline_returns_consistent_shapes():
    result = pipeline.run_pipeline()
    assert len(result["grid"]) == 400  # 20x20
    assert len(result["habitations"]) == 40
    assert len(result["allocation"]) + len(result["unallocated"]) == len(result["habitations"])
    assert set(result["grid"]["zone_tier"].unique()) <= {"Red", "Amber", "Green"}
    assert set(result["habitations"]["rpi_tier"].unique()) <= {"immediate", "short-term", "medium-term"}


def test_run_pipeline_without_guardian_evidence_has_zero_bonuses():
    result = pipeline.run_pipeline(include_guardian_evidence=False)
    assert (result["grid"]["guardian_evidence_bonus"] == 0).all()
    assert (result["grid"]["comms_degraded_bonus"] == 0).all()
    assert (result["incidents"]["cluster_id"] == -1).all()


def test_build_brief_summary_has_expected_keys():
    result = pipeline.run_pipeline()
    summary = pipeline.build_brief_summary(result)
    for key in [
        "n_red_zones",
        "n_amber_zones",
        "n_green_zones",
        "immediate_tier_count",
        "short_term_tier_count",
        "medium_term_tier_count",
        "total_safe_site_capacity",
        "unallocated_population",
        "n_incidents_considered",
        "n_comms_degraded_incidents",
    ]:
        assert key in summary


def test_compare_with_without_guardian_evidence_flags_a_tier_change():
    """Phase 4b: the with/without comparison must, on the seeded sample
    data's default parameters, find at least one habitation whose relocation
    tier actually changes because of Guardian ground evidence — not just run
    without error. See BUILD_LOG.md Step 4.2 for why the sample data
    deliberately places a corroborated incident cluster near a habitation
    sitting just below a tier boundary.
    """
    with_result, without_result, changes = pipeline.compare_with_without_guardian_evidence()

    assert len(with_result["habitations"]) == len(without_result["habitations"])
    assert not changes.empty, "expected at least one habitation to change tier on the default seed"

    for _, row in changes.iterrows():
        assert row["tier_with_evidence"] != row["tier_without_evidence"]
        assert row["zone_score_with_evidence"] >= row["zone_score_without_evidence"]
        assert isinstance(row["why"], dict)


def test_compare_with_without_guardian_evidence_same_habitation_set():
    with_result, without_result, _ = pipeline.compare_with_without_guardian_evidence()
    with_ids = set(with_result["habitations"]["habitation_id"])
    without_ids = set(without_result["habitations"]["habitation_id"])
    assert with_ids == without_ids
