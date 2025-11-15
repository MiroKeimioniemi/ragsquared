"""Compliance score calculation utilities."""

from __future__ import annotations

from collections import Counter
from typing import Any

from ..db.models import Flag


def calculate_compliance_score(flags: list[Flag]) -> float:
    """
    Calculate compliance score from flags using exponential decay for consecutive flags.
    Score ranges from 0-100, where:
    - 100 = perfect compliance (mixed flags with no critical issues)
    - 0 = unbalanced compliance (100% RED or 100% GREEN) or severe penalties
    
    Formula:
    - Base score: 100
    - RED flags: -20 points each (with exponential decay for consecutive)
    - YELLOW flags: -10 points each (with exponential decay for consecutive)
    - Consecutive flags of same type: exponential decay (0.9^(consecutive_count-1))
      * First flag: full penalty (20 for RED, 10 for YELLOW)
      * Second consecutive: 0.9x penalty
      * Third consecutive: 0.81x penalty, etc.
    - If 100% red or 100% green: score = 0 (unbalanced compliance)
    """
    if not flags:
        return 100.0  # No flags = fully compliant

    # Count flags by type
    severity_counts = Counter(flag.flag_type for flag in flags)
    red_count = severity_counts.get("RED", 0)
    yellow_count = severity_counts.get("YELLOW", 0)
    green_count = severity_counts.get("GREEN", 0)
    total_flags = len(flags)

    # If all flags are one type, return 0 (unbalanced)
    if total_flags > 0:
        if red_count == total_flags or green_count == total_flags:
            return 0.0

    # Sort flags by creation time to ensure consistent consecutive detection
    # Use created_at if available, otherwise fall back to id
    sorted_flags = sorted(
        flags, 
        key=lambda f: (f.created_at.timestamp() if f.created_at else float('inf'), f.id)
    )
    
    # Calculate penalties with exponential decay for consecutive flags
    # Process flags in order to detect consecutive sequences
    red_penalty = 0.0
    yellow_penalty = 0.0
    
    # Track consecutive counts
    consecutive_red = 0
    consecutive_yellow = 0
    consecutive_green = 0
    
    # Decay factor for consecutive flags
    decay_factor = 0.9
    
    for flag in sorted_flags:
        if flag.flag_type == "RED":
            consecutive_red += 1
            consecutive_yellow = 0
            consecutive_green = 0
            # Apply exponential decay: first flag = full penalty, second = 0.9x, third = 0.81x, etc.
            penalty_multiplier = decay_factor ** (consecutive_red - 1)
            red_penalty += 20 * penalty_multiplier
        elif flag.flag_type == "YELLOW":
            consecutive_yellow += 1
            consecutive_red = 0
            consecutive_green = 0
            # Apply exponential decay
            penalty_multiplier = decay_factor ** (consecutive_yellow - 1)
            yellow_penalty += 10 * penalty_multiplier
        else:  # GREEN
            consecutive_green += 1
            consecutive_red = 0
            consecutive_yellow = 0
            # Green flags don't add penalty, but reset consecutive counts for others

    # Base score starts at 100
    base_score = 100.0

    # Apply penalties
    score = base_score - red_penalty - yellow_penalty

    # Clamp to 0-100 range
    return max(0.0, min(100.0, score))


def get_flag_summary(flags: list[Flag]) -> dict[str, Any]:
    """Get summary statistics for a list of flags."""
    from collections import Counter

    severity_counts = Counter(flag.flag_type for flag in flags)
    total_score = sum(flag.severity_score for flag in flags)
    avg_severity = total_score / len(flags) if flags else 0

    return {
        "total_flags": len(flags),
        "red_count": severity_counts.get("RED", 0),
        "yellow_count": severity_counts.get("YELLOW", 0),
        "green_count": severity_counts.get("GREEN", 0),
        "avg_severity_score": round(avg_severity, 2),
        "compliance_score": round(calculate_compliance_score(flags), 2),
    }

