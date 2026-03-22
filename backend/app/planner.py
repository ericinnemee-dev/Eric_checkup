from collections import Counter
from collections.abc import Sequence
from typing import TypedDict


class PlannerAssignment(TypedDict):
    shift_id: str
    employee_id: str | None
    reason: str


class ScoreBreakdown(TypedDict):
    fill_rate: float
    fairness: float
    cost_score: float
    route_score: float
    penalty: float


def _read_int_constraint(constraints: Sequence, key: str) -> int | None:
    raw = next((c.value for c in constraints if c.key == key), None)
    if raw is None:
        return None
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _read_float_constraint(constraints: Sequence, key: str, default: float) -> float:
    raw = next((c.value for c in constraints if c.key == key), None)
    if raw is None:
        return default
    try:
        parsed = float(raw)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _fairness_score(assigned_counter: Counter[str]) -> float:
    if not assigned_counter:
        return 1.0
    values = list(assigned_counter.values())
    peak = max(values)
    valley = min(values)
    if peak == 0:
        return 1.0
    return round(1 - ((peak - valley) / peak), 4)


def build_plan(shifts: Sequence, employees: Sequence, constraints: Sequence):
    """Simple deterministic planner v4 with score breakdown."""
    assignments: list[PlannerAssignment] = []
    violations: list[str] = []
    assigned_counter: Counter[str] = Counter()

    max_assignments = _read_int_constraint(constraints, "max_assignments_per_employee")
    weight_fill_rate = _read_float_constraint(constraints, "weight_fill_rate", 0.7)
    weight_fairness = _read_float_constraint(constraints, "weight_fairness", 0.2)
    weight_cost = _read_float_constraint(constraints, "weight_cost", 0.1)
    weight_route = _read_float_constraint(constraints, "weight_route", 0.0)

    for shift in shifts:
        match = None
        for employee in employees:
            if not employee.available:
                continue
            if shift.required_skill not in employee.skills:
                continue
            if max_assignments is not None and assigned_counter[employee.id] >= max_assignments:
                continue
            match = employee
            break

        if match is None:
            assignments.append(
                {
                    "shift_id": shift.id,
                    "employee_id": None,
                    "reason": "No employee available with required skill within constraints.",
                }
            )
            violations.append(f"Unassigned shift: {shift.id}")
            continue

        assigned_counter[match.id] += 1
        assignments.append(
            {
                "shift_id": shift.id,
                "employee_id": match.id,
                "reason": "Assigned by availability + skill-match rules.",
            }
        )

    fill_rate = 0.0 if not shifts else sum(1 for a in assignments if a["employee_id"]) / len(shifts)
    fairness = _fairness_score(assigned_counter)

    avg_assignment_cost = 0.0
    assigned_count = sum(1 for a in assignments if a["employee_id"])
    if assigned_count:
        employee_lookup = {e.id: getattr(e, "cost_per_shift", 1.0) for e in employees}
        total_cost = sum(
            employee_lookup.get(a["employee_id"], 1.0) for a in assignments if a["employee_id"]
        )
        avg_assignment_cost = total_cost / assigned_count

    cost_normalizer = _read_float_constraint(constraints, "cost_normalizer", 100.0)
    if cost_normalizer <= 0:
        cost_normalizer = 100.0
    cost_score = (
        max(0.0, round(1 - (avg_assignment_cost / cost_normalizer), 4)) if assigned_count else 1.0
    )

    avg_route_distance = 0.0
    if shifts:
        avg_route_distance = sum(
            getattr(shift, "route_distance_km", 0.0) for shift in shifts
        ) / len(shifts)
    route_normalizer = _read_float_constraint(constraints, "route_normalizer", 100.0)
    if route_normalizer <= 0:
        route_normalizer = 100.0
    route_score = max(0.0, round(1 - (avg_route_distance / route_normalizer), 4))

    weight_total = weight_fill_rate + weight_fairness + weight_cost + weight_route
    if weight_total == 0:
        base_score = fill_rate
    else:
        base_score = (
            (fill_rate * weight_fill_rate)
            + (fairness * weight_fairness)
            + (cost_score * weight_cost)
            + (route_score * weight_route)
        ) / weight_total

    penalty = len(violations) * 0.1
    score = max(0.0, round(base_score - penalty, 4))
    breakdown: ScoreBreakdown = {
        "fill_rate": round(fill_rate, 4),
        "fairness": round(fairness, 4),
        "cost_score": round(cost_score, 4),
        "route_score": round(route_score, 4),
        "penalty": round(penalty, 4),
    }

    return assignments, score, violations, breakdown
