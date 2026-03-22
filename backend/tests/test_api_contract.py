import os
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - local env without deps
    TestClient = None

TEST_DB = Path("test_hms.db")
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///./test_hms.db"

if TestClient is not None:
    from app.main import app  # noqa: E402
else:  # pragma: no cover - local env without deps
    app = None


class TestApiContract(unittest.TestCase):
    def setUp(self):
        if TestClient is None:
            self.skipTest("fastapi is not installed in this environment")
        self.client = TestClient(app)
        self.planner_headers = self._token_headers("planner", "planner123")
        self.viewer_headers = self._token_headers("viewer", "viewer123")

    def _token_headers(self, username: str, password: str) -> dict[str, str]:
        resp = self.client.post("/auth/token", json={"username": username, "password": password})
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertIn("version", response.json())
        self.assertIn("env", response.json())
        self.assertIn("server_time_utc", response.json())

    def test_frontend_shell(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("HMS Planner", response.text)

    def test_auth_required(self):
        response = self.client.get("/kpis")
        self.assertEqual(response.status_code, 401)

    def test_auth_me(self):
        me = self.client.get("/auth/me", headers=self.viewer_headers)
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["username"], "viewer")
        self.assertEqual(me.json()["role"], "viewer")

    def test_capacity_heatmap_hourly_overlap(self):
        employee_available = self.client.post(
            "/employees",
            json={
                "id": "cap_e1",
                "team_id": "t1",
                "site_id": "s1",
                "skills": ["operator"],
                "available": True,
            },
            headers=self.planner_headers,
        )
        self.assertEqual(employee_available.status_code, 200)
        employee_absent = self.client.post(
            "/employees",
            json={
                "id": "cap_e2",
                "team_id": "t1",
                "site_id": "s1",
                "skills": ["operator"],
                "available": False,
            },
            headers=self.planner_headers,
        )
        self.assertEqual(employee_absent.status_code, 200)

        base = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        for i in range(2):
            create_shift = self.client.post(
                "/shifts",
                json={
                    "id": f"cap_s{i + 1}",
                    "team_id": "t1",
                    "site_id": "s1",
                    "required_skill": "operator",
                    "start": base.isoformat(),
                    "end": (base + timedelta(hours=1)).isoformat(),
                },
                headers=self.planner_headers,
            )
            self.assertEqual(create_shift.status_code, 200)

        heatmap = self.client.get(
            "/capacity/heatmap",
            params={
                "start": base.isoformat(),
                "end": (base + timedelta(hours=2)).isoformat(),
                "team_id": "t1",
                "site_id": "s1",
                "bucket_minutes": 60,
            },
            headers=self.viewer_headers,
        )
        self.assertEqual(heatmap.status_code, 200)
        body = heatmap.json()
        self.assertEqual(body["bucket_minutes"], 60)
        self.assertEqual(len(body["buckets"]), 2)
        self.assertEqual(body["buckets"][0]["required_count"], 2)
        self.assertEqual(body["buckets"][0]["available_count"], 1)
        self.assertEqual(body["buckets"][0]["absence_count"], 1)
        self.assertEqual(body["buckets"][0]["gap"], 1)
        self.assertTrue(body["buckets"][0]["overlap_absence_understaffed"])
        self.assertEqual(body["buckets"][0]["risk_level"], "high")

    def test_employee_and_shift_crud(self):
        emp = self.client.post(
            "/employees",
            json={"id": "e1", "skills": ["operator"], "available": True},
            headers=self.planner_headers,
        )
        self.assertEqual(emp.status_code, 200)

        list_emp = self.client.get("/employees", headers=self.viewer_headers)
        self.assertEqual(list_emp.status_code, 200)
        self.assertGreaterEqual(len(list_emp.json()), 1)

        shift_now = datetime.now(timezone.utc)
        create_shift = self.client.post(
            "/shifts",
            json={
                "id": "s1",
                "required_skill": "operator",
                "start": shift_now.isoformat(),
                "end": (shift_now + timedelta(hours=8)).isoformat(),
            },
            headers=self.planner_headers,
        )
        self.assertEqual(create_shift.status_code, 200)

        delete_shift = self.client.delete("/shifts/s1", headers=self.planner_headers)
        self.assertEqual(delete_shift.status_code, 204)

        delete_employee = self.client.delete("/employees/e1", headers=self.planner_headers)
        self.assertEqual(delete_employee.status_code, 204)

    def test_optimize_kpis_feedback_flow(self):
        now = datetime.now(timezone.utc)
        payload = {
            "shifts": [
                {
                    "id": "s_opt",
                    "required_skill": "operator",
                    "start": now.isoformat(),
                    "end": (now + timedelta(hours=8)).isoformat(),
                }
            ],
            "employees": [{"id": "e_opt", "skills": ["operator"], "available": True}],
            "constraints": [],
        }
        optimize = self.client.post("/optimize", json=payload, headers=self.planner_headers)
        self.assertEqual(optimize.status_code, 200)
        body = optimize.json()
        self.assertIn("run_id", body)
        self.assertGreater(body["run_id"], 0)
        self.assertGreater(body["assignments"][0]["event_id"], 0)

        feedback = self.client.post(
            "/feedback",
            json={
                "assignment_id": body["assignments"][0]["event_id"],
                "decision": "accepted",
                "reason": "planner approved",
            },
            headers=self.planner_headers,
        )
        self.assertEqual(feedback.status_code, 200)
        self.assertEqual(feedback.json()["status"], "captured")

        kpis = self.client.get("/kpis", headers=self.viewer_headers)
        self.assertEqual(kpis.status_code, 200)
        kpi_body = kpis.json()
        self.assertGreaterEqual(kpi_body["unassigned_shifts"], 0)
        self.assertGreaterEqual(kpi_body["fill_rate"], 0.0)

        runs = self.client.get("/runs?limit=5", headers=self.viewer_headers)
        self.assertEqual(runs.status_code, 200)
        self.assertGreaterEqual(len(runs.json()), 1)
        self.assertIn("fill_rate", runs.json()[0])

        delete_run = self.client.delete(
            f"/runs/{runs.json()[0]['id']}", headers=self.planner_headers
        )
        self.assertEqual(delete_run.status_code, 204)

        runs_invalid = self.client.get("/runs?offset=-1", headers=self.viewer_headers)
        self.assertEqual(runs_invalid.status_code, 400)

    def test_list_filters_and_pagination(self):
        self.client.post(
            "/employees",
            json={
                "id": "e_team",
                "team_id": "team-z",
                "site_id": "site-z",
                "skills": ["operator"],
                "available": True,
            },
            headers=self.planner_headers,
        )
        self.client.post(
            "/employees",
            json={"id": "e_other", "skills": ["operator"], "available": True},
            headers=self.planner_headers,
        )

        filtered = self.client.get(
            "/employees?team_id=team-z&limit=1&offset=0", headers=self.viewer_headers
        )
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(len(filtered.json()), 1)
        self.assertEqual(filtered.json()[0]["id"], "e_team")

        sorted_desc = self.client.get(
            "/employees?sort_by=id&sort_dir=desc", headers=self.viewer_headers
        )
        self.assertEqual(sorted_desc.status_code, 200)
        self.assertGreaterEqual(len(sorted_desc.json()), 2)

        invalid = self.client.get("/employees?limit=0", headers=self.viewer_headers)
        self.assertEqual(invalid.status_code, 400)

        invalid_sort = self.client.get("/employees?sort_by=unknown", headers=self.viewer_headers)
        self.assertEqual(invalid_sort.status_code, 400)

    def test_optimize_from_db_flow(self):
        shift_now = datetime.now(timezone.utc)
        self.client.post(
            "/employees",
            json={
                "id": "e_db",
                "team_id": "team-a",
                "site_id": "site-1",
                "skills": ["operator"],
                "available": True,
            },
            headers=self.planner_headers,
        )
        self.client.post(
            "/shifts",
            json={
                "id": "s_db",
                "team_id": "team-a",
                "site_id": "site-1",
                "required_skill": "operator",
                "start": shift_now.isoformat(),
                "end": (shift_now + timedelta(hours=8)).isoformat(),
            },
            headers=self.planner_headers,
        )

        run = self.client.post(
            "/optimize/run",
            json={
                "shift_ids": ["s_db"],
                "employee_ids": ["e_db"],
                "team_id": "team-a",
                "site_id": "site-1",
                "constraints": [],
            },
            headers=self.planner_headers,
        )
        self.assertEqual(run.status_code, 200)
        self.assertGreater(run.json()["run_id"], 0)

        scoped_kpi = self.client.get(
            "/kpis?team_id=team-a&site_id=site-1", headers=self.viewer_headers
        )
        self.assertEqual(scoped_kpi.status_code, 200)
        self.assertGreaterEqual(scoped_kpi.json()["fill_rate"], 0.0)

    def test_negative_cost_is_rejected(self):
        response = self.client.post(
            "/employees",
            json={"id": "e_bad", "skills": ["operator"], "cost_per_shift": -2},
            headers=self.planner_headers,
        )
        self.assertEqual(response.status_code, 422)

    def test_negative_route_distance_is_rejected(self):
        now = datetime.now(timezone.utc)
        response = self.client.post(
            "/shifts",
            json={
                "id": "s_bad",
                "required_skill": "operator",
                "route_distance_km": -1,
                "start": now.isoformat(),
                "end": (now + timedelta(hours=8)).isoformat(),
            },
            headers=self.planner_headers,
        )
        self.assertEqual(response.status_code, 422)

    def test_feedback_missing_event_returns_404(self):
        feedback = self.client.post(
            "/feedback",
            json={"assignment_id": 999999, "decision": "accepted", "reason": "missing"},
            headers=self.planner_headers,
        )
        self.assertEqual(feedback.status_code, 404)


if __name__ == "__main__":
    unittest.main()
