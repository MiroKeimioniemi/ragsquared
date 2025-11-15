"""API endpoints for compliance score history."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..db.session import get_session
from ..services.score_tracker import ScoreTracker

scores_blueprint = Blueprint("scores", __name__, url_prefix="/scores")


@scores_blueprint.route("/", methods=["GET"])
def list_scores():
    """Get compliance score history, optionally filtered by organization."""
    organization = request.args.get("organization")
    limit = request.args.get("limit", type=int, default=50)
    
    if limit and limit > 100:
        limit = 100  # Cap at 100
    
    session = get_session()
    tracker = ScoreTracker(session)
    score_history = tracker.get_score_history(organization=organization, limit=limit)
    
    return jsonify({
        "organization": organization,
        "count": len(score_history),
        "scores": [
            {
                "audit_id": score.audit_id,
                "overall_score": score.overall_score,
                "red_count": score.red_count,
                "yellow_count": score.yellow_count,
                "green_count": score.green_count,
                "total_flags": score.total_flags,
                "created_at": score.created_at.isoformat() if score.created_at else None,
            }
            for score in score_history
        ],
    })


@scores_blueprint.route("/organizations/<organization>", methods=["GET"])
def get_organization_scores(organization: str):
    """Get compliance score history for a specific organization."""
    limit = request.args.get("limit", type=int, default=50)
    
    if limit and limit > 100:
        limit = 100  # Cap at 100
    
    session = get_session()
    tracker = ScoreTracker(session)
    score_history = tracker.get_score_history(organization=organization, limit=limit)
    
    return jsonify({
        "organization": organization,
        "count": len(score_history),
        "scores": [
            {
                "audit_id": score.audit_id,
                "overall_score": score.overall_score,
                "red_count": score.red_count,
                "yellow_count": score.yellow_count,
                "green_count": score.green_count,
                "total_flags": score.total_flags,
                "created_at": score.created_at.isoformat() if score.created_at else None,
            }
            for score in score_history
        ],
    })

