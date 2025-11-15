"""Tests for compliance score calculation."""

from __future__ import annotations

from backend.app.db.models import Flag
from backend.app.services.compliance_score import calculate_compliance_score, get_flag_summary


def test_compliance_score_perfect_compliance():
    """Test that all GREEN flags give perfect score."""
    flags = [
        Flag(flag_type="GREEN", severity_score=10),
        Flag(flag_type="GREEN", severity_score=20),
        Flag(flag_type="GREEN", severity_score=5),
    ]
    score = calculate_compliance_score(flags)
    assert score >= 100.0  # Should be 100 or higher with bonuses


def test_compliance_score_critical_non_compliance():
    """Test that RED flags heavily penalize score."""
    flags = [
        Flag(flag_type="RED", severity_score=90),
        Flag(flag_type="RED", severity_score=85),
    ]
    score = calculate_compliance_score(flags)
    assert score < 100.0
    assert score <= 80.0  # 2 RED flags = -20 points


def test_compliance_score_mixed_flags():
    """Test score calculation with mixed flag types."""
    flags = [
        Flag(flag_type="RED", severity_score=90),
        Flag(flag_type="YELLOW", severity_score=60),
        Flag(flag_type="GREEN", severity_score=10),
    ]
    score = calculate_compliance_score(flags)
    # 1 RED (-10) + 1 YELLOW (-3) + 1 GREEN (+1) = 100 - 10 - 3 + 1 = 88
    assert 85 <= score <= 90


def test_compliance_score_empty_flags():
    """Test that empty flags list gives perfect score."""
    score = calculate_compliance_score([])
    assert score == 100.0


def test_get_flag_summary():
    """Test flag summary generation."""
    flags = [
        Flag(flag_type="RED", severity_score=90),
        Flag(flag_type="YELLOW", severity_score=60),
        Flag(flag_type="GREEN", severity_score=10),
    ]
    summary = get_flag_summary(flags)
    assert summary["total_flags"] == 3
    assert summary["red_count"] == 1
    assert summary["yellow_count"] == 1
    assert summary["green_count"] == 1
    assert "compliance_score" in summary
    assert "avg_severity_score" in summary
    assert 0 <= summary["compliance_score"] <= 100


def test_compliance_score_clamped_to_100():
    """Test that score cannot exceed 100."""
    # Many GREEN flags should cap at 100
    flags = [Flag(flag_type="GREEN", severity_score=10) for _ in range(100)]
    score = calculate_compliance_score(flags)
    assert score <= 100.0


def test_compliance_score_clamped_to_0():
    """Test that score cannot go below 0."""
    # Many RED flags should cap at 0
    flags = [Flag(flag_type="RED", severity_score=90) for _ in range(20)]
    score = calculate_compliance_score(flags)
    assert score >= 0.0

