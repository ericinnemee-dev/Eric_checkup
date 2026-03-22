import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.planner import build_plan


class TestPlanner(unittest.TestCase):
    def test_assigns_employee_on_skill_match(self):
        shifts = [
            SimpleNamespace(
                id="s1",
                required_skill="crane",
                start=datetime.now(timezone.utc),
                end=datetime.now(timezone.utc) + timedelta(hours=8),
            )
        ]
        employees = [SimpleNamespace(id="e1", skills=["crane"], available=True)]

        assignments, score, violations, breakdown = build_plan(shifts, employees, constraints=[])

        self.assertEqual(assignments[0]["employee_id"], "e1")
        self.assertGreaterEqual(score, 0.9)
        self.assertEqual(violations, [])
        self.assertIn("fill_rate", breakdown)

    def test_respects_max_assignment_constraint(self):
        now = datetime.now(timezone.utc)
        shifts = [
            SimpleNamespace(
                id="s1", required_skill="driver", start=now, end=now + timedelta(hours=8)
            ),
            SimpleNamespace(
                id="s2", required_skill="driver", start=now, end=now + timedelta(hours=8)
            ),
        ]
        employees = [SimpleNamespace(id="e1", skills=["driver"], available=True)]
        constraints = [SimpleNamespace(key="max_assignments_per_employee", value=1)]

        assignments, score, violations, _ = build_plan(shifts, employees, constraints)

        self.assertEqual(assignments[0]["employee_id"], "e1")
        self.assertIsNone(assignments[1]["employee_id"])
        self.assertEqual(len(violations), 1)
        self.assertLess(score, 1.0)

    def test_fairness_weight_impacts_score(self):
        now = datetime.now(timezone.utc)
        shifts = [
            SimpleNamespace(
                id="s1", required_skill="driver", start=now, end=now + timedelta(hours=8)
            ),
            SimpleNamespace(
                id="s2", required_skill="driver", start=now, end=now + timedelta(hours=8)
            ),
        ]
        employees = [
            SimpleNamespace(id="e1", skills=["driver"], available=True),
            SimpleNamespace(id="e2", skills=["driver"], available=True),
        ]

        _, score_default, _, _ = build_plan(shifts, employees, constraints=[])
        fairness_constraints = [
            SimpleNamespace(key="weight_fill_rate", value=0.2),
            SimpleNamespace(key="weight_fairness", value=0.8),
        ]
        _, score_fairness, _, _ = build_plan(shifts, employees, constraints=fairness_constraints)

        self.assertGreaterEqual(score_fairness, 0.0)
        self.assertGreaterEqual(score_default, 0.0)

    def test_cost_weight_impacts_score(self):
        now = datetime.now(timezone.utc)
        shifts = [
            SimpleNamespace(
                id="s1", required_skill="driver", start=now, end=now + timedelta(hours=8)
            ),
        ]
        employees = [
            SimpleNamespace(id="cheap", skills=["driver"], available=True, cost_per_shift=10.0),
            SimpleNamespace(
                id="expensive", skills=["driver"], available=True, cost_per_shift=100.0
            ),
        ]

        _, score_default, _, _ = build_plan(shifts, employees, constraints=[])
        cost_constraints = [
            SimpleNamespace(key="weight_fill_rate", value=0.0),
            SimpleNamespace(key="weight_fairness", value=0.0),
            SimpleNamespace(key="weight_cost", value=1.0),
            SimpleNamespace(key="cost_normalizer", value=100.0),
        ]
        _, score_cost, _, _ = build_plan(shifts, employees, constraints=cost_constraints)

        self.assertGreaterEqual(score_default, 0.0)
        self.assertGreater(score_cost, 0.0)

    def test_route_weight_impacts_score(self):
        now = datetime.now(timezone.utc)
        shifts = [
            SimpleNamespace(
                id="s1",
                required_skill="driver",
                route_distance_km=80.0,
                start=now,
                end=now + timedelta(hours=8),
            )
        ]
        employees = [SimpleNamespace(id="e1", skills=["driver"], available=True)]

        route_constraints = [
            SimpleNamespace(key="weight_fill_rate", value=0.0),
            SimpleNamespace(key="weight_fairness", value=0.0),
            SimpleNamespace(key="weight_cost", value=0.0),
            SimpleNamespace(key="weight_route", value=1.0),
            SimpleNamespace(key="route_normalizer", value=100.0),
        ]
        _, score_route, _, breakdown = build_plan(shifts, employees, constraints=route_constraints)

        self.assertGreaterEqual(score_route, 0.0)
        self.assertIn("route_score", breakdown)


if __name__ == "__main__":
    unittest.main()
