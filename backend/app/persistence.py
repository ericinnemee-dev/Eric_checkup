from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AssignmentEvent, OptimizerRun


def save_optimizer_run(
    db: Session,
    assignments: list[dict],
    score: float,
    violations: list[str],
    score_breakdown: dict[str, float],
    team_id: str | None = None,
    site_id: str | None = None,
) -> tuple[int, list[dict]]:
    run = OptimizerRun(
        team_id=team_id,
        site_id=site_id,
        total_shifts=len(assignments),
        unassigned_shifts=len(violations),
        score=score,
        fill_rate=score_breakdown.get("fill_rate", 0.0),
        fairness=score_breakdown.get("fairness", 0.0),
        cost_score=score_breakdown.get("cost_score", 0.0),
        route_score=score_breakdown.get("route_score", 0.0),
        penalty=score_breakdown.get("penalty", 0.0),
    )
    db.add(run)
    db.flush()

    persisted_assignments: list[dict] = []
    for assignment in assignments:
        event = AssignmentEvent(
            run_id=run.id,
            shift_id=assignment["shift_id"],
            employee_id=assignment["employee_id"],
            reason=assignment["reason"],
        )
        db.add(event)
        db.flush()
        persisted_assignments.append(
            {
                "event_id": event.id,
                "shift_id": event.shift_id,
                "employee_id": event.employee_id,
                "reason": event.reason,
            }
        )

    db.commit()
    return run.id, persisted_assignments


def latest_run(
    db: Session, team_id: str | None = None, site_id: str | None = None
) -> OptimizerRun | None:
    query = select(OptimizerRun)
    if team_id:
        query = query.where(OptimizerRun.team_id == team_id)
    if site_id:
        query = query.where(OptimizerRun.site_id == site_id)
    query = query.order_by(OptimizerRun.id.desc()).limit(1)
    return db.scalar(query)


def save_feedback(db: Session, assignment_id: int, decision: str, reason: str) -> bool:
    event = db.get(AssignmentEvent, assignment_id)
    if not event:
        return False
    event.decision = decision
    event.reason = f"{event.reason} | feedback: {reason}"
    db.commit()
    return True
