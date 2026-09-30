import scoring


def test_zone_risk_score_thresholds():
    red_score, _ = scoring.zone_risk_score(hazard=1.0, vulnerability=1.0, past_incidents=10)
    amber_score, _ = scoring.zone_risk_score(hazard=0.4, vulnerability=0.4, past_incidents=2)
    green_score, _ = scoring.zone_risk_score(hazard=0.0, vulnerability=0.0, past_incidents=0)

    assert scoring.zone_tier(red_score) == "Red"
    assert scoring.zone_tier(amber_score) == "Amber"
    assert scoring.zone_tier(green_score) == "Green"
    assert 0 <= red_score <= 100
    assert 0 <= amber_score <= 100
    assert 0 <= green_score <= 100


def test_zone_risk_score_uses_all_three_inputs():
    baseline, _ = scoring.zone_risk_score(hazard=0.0, vulnerability=0.0, past_incidents=0)

    hazard_only, _ = scoring.zone_risk_score(hazard=1.0, vulnerability=0.0, past_incidents=0)
    vulnerability_only, _ = scoring.zone_risk_score(hazard=0.0, vulnerability=1.0, past_incidents=0)
    history_only, _ = scoring.zone_risk_score(hazard=0.0, vulnerability=0.0, past_incidents=scoring.DEFAULT_HISTORY_CAP)

    assert hazard_only > baseline
    assert vulnerability_only > baseline
    assert history_only > baseline
    # Each input has its own nonzero weight, so none of them alone can reach
    # the full weighted total.
    assert hazard_only < 100
    assert vulnerability_only < 100
    assert history_only < 100


def test_hazard_scenario_multiplier_scales_hazard_component_only():
    low, _ = scoring.zone_risk_score(hazard=0.5, vulnerability=0.5, past_incidents=2, hazard_scenario_multiplier=1.0)
    high, _ = scoring.zone_risk_score(hazard=0.5, vulnerability=0.5, past_incidents=2, hazard_scenario_multiplier=2.0)
    assert high > low


def test_guardian_evidence_bonus_is_capped():
    score_uncapped_request, breakdown = scoring.zone_risk_score(
        hazard=0.1, vulnerability=0.1, past_incidents=0, guardian_evidence_bonus=999
    )
    assert breakdown["guardian_evidence_bonus_applied"] == scoring.MAX_GUARDIAN_EVIDENCE_BONUS
    assert score_uncapped_request <= 100


def test_evidence_confidence_score_range_and_none_source_floor():
    score_none, _ = scoring.evidence_confidence_score("none", None)
    assert score_none == 0.0

    score_gps, _ = scoring.evidence_confidence_score(
        "gps", 10.0, sensor_trigger=True, yamnet_distress_label=True, whisper_keyword_hit=True, gemini_emergency_flag=True
    )
    assert 0.0 <= score_gps <= 1.0
    assert score_gps > score_none


def test_evidence_confidence_score_freshness_decay():
    fresh, _ = scoring.evidence_confidence_score("gps", 10.0, sensor_trigger=True, age_hours=0)
    stale, _ = scoring.evidence_confidence_score("gps", 10.0, sensor_trigger=True, age_hours=1000)
    assert fresh > stale
    assert stale >= 0.0


def test_relocation_priority_index_normalizes_to_100():
    raw = [10, 20, 50, 100]
    rpi = scoring.relocation_priority_index(raw)
    assert rpi[-1] == 100.0
    assert all(0 <= v <= 100 for v in rpi)


def test_relocation_priority_index_all_zero_raw():
    rpi = scoring.relocation_priority_index([0, 0, 0])
    assert all(v == 0 for v in rpi)


def test_rpi_tier_thresholds():
    assert scoring.rpi_tier(70) == "immediate"
    assert scoring.rpi_tier(scoring.RPI_IMMEDIATE_THRESHOLD) == "immediate"
    assert scoring.rpi_tier(40) == "short-term"
    assert scoring.rpi_tier(scoring.RPI_SHORT_TERM_THRESHOLD) == "short-term"
    assert scoring.rpi_tier(10) == "medium-term"
