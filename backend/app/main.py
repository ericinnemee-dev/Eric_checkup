from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from passlib.context import CryptContext
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine, get_db
from .models import Employee as EmployeeModel
from .models import OptimizerRun as OptimizerRunModel
from .models import Shift as ShiftModel
from .models import User
from .persistence import latest_run, save_feedback, save_optimizer_run
from .planner import build_plan
from .schemas import (
    Assignment,
    AuthContext,
    AuthMeResponse,
    CapacityBucketResponse,
    CapacityHeatmapResponse,
    Employee,
    EmployeeCreateRequest,
    EmployeePatchRequest,
    EmployeeResponse,
    FeedbackRequest,
    FeedbackResponse,
    KpiResponse,
    OptimizeRequest,
    OptimizeResponse,
    OptimizeRunRequest,
    RunSummaryResponse,
    ScoreBreakdownResponse,
    Shift,
    ShiftCreateRequest,
    ShiftPatchRequest,
    ShiftResponse,
    TokenRequest,
    TokenResponse,
)
from .settings import settings

app = FastAPI(title="HMS Planning API", version="0.9.0")
security = HTTPBearer(auto_error=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


def _create_token(username: str, role: str) -> str:
    payload = {
        "sub": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_ttl_min),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)


def _parse_skills(skills_csv: str) -> list[str]:
    if not skills_csv:
        return []
    return [s for s in skills_csv.split(",") if s]


def _serialize_employee(employee: EmployeeModel) -> EmployeeResponse:
    return EmployeeResponse(
        id=employee.id,
        team_id=employee.team_id,
        site_id=employee.site_id,
        skills=_parse_skills(employee.skills_csv),
        cost_per_shift=employee.cost_per_shift,
        available=employee.available,
    )


def _serialize_shift(shift: ShiftModel) -> ShiftResponse:
    return ShiftResponse(
        id=shift.id,
        team_id=shift.team_id,
        site_id=shift.site_id,
        required_skill=shift.required_skill,
        route_distance_km=shift.route_distance_km,
        start=shift.start_at,
        end=shift.end_at,
    )


def _db_employee_to_planner_input(employee: EmployeeModel) -> Employee:
    return Employee(
        id=employee.id,
        team_id=employee.team_id,
        site_id=employee.site_id,
        skills=_parse_skills(employee.skills_csv),
        cost_per_shift=employee.cost_per_shift,
        available=employee.available,
    )


def _serialize_run(run: OptimizerRunModel) -> RunSummaryResponse:
    return RunSummaryResponse(
        id=run.id,
        created_at=run.created_at,
        team_id=run.team_id,
        site_id=run.site_id,
        score=run.score,
        total_shifts=run.total_shifts,
        unassigned_shifts=run.unassigned_shifts,
        fill_rate=run.fill_rate,
        fairness=run.fairness,
        cost_score=run.cost_score,
        route_score=run.route_score,
        penalty=run.penalty,
    )


def _db_shift_to_planner_input(shift: ShiftModel) -> Shift:
    return Shift(
        id=shift.id,
        team_id=shift.team_id,
        site_id=shift.site_id,
        required_skill=shift.required_skill,
        route_distance_km=shift.route_distance_km,
        start=shift.start_at,
        end=shift.end_at,
    )


def _iter_hourly_buckets(start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    buckets: list[tuple[datetime, datetime]] = []
    cursor = start
    while cursor < end:
        bucket_end = min(cursor + timedelta(hours=1), end)
        buckets.append((cursor, bucket_end))
        cursor = bucket_end
    return buckets


def _run_optimizer(
    payload: OptimizeRequest,
    db: Session,
    team_id: str | None = None,
    site_id: str | None = None,
) -> OptimizeResponse:
    if not payload.shifts:
        raise HTTPException(status_code=400, detail="At least one shift is required")
    if not payload.employees:
        raise HTTPException(status_code=400, detail="At least one employee is required")

    assignments, score, violations, score_breakdown = build_plan(
        shifts=payload.shifts,
        employees=payload.employees,
        constraints=payload.constraints,
    )
    run_id, persisted_assignments = save_optimizer_run(
        db,
        assignments,
        score,
        violations,
        score_breakdown=score_breakdown,
        team_id=team_id,
        site_id=site_id,
    )

    return OptimizeResponse(
        run_id=run_id,
        assignments=[Assignment(**item) for item in persisted_assignments],
        score=score,
        score_breakdown=ScoreBreakdownResponse(**score_breakdown),
        violations=violations,
    )


def _ensure_dev_users() -> None:
    db = SessionLocal()
    try:
        defaults = [
            (settings.planner_seed_username, settings.planner_seed_password, "planner"),
            (settings.viewer_seed_username, settings.viewer_seed_password, "viewer"),
        ]
        for username, password, role in defaults:
            existing = db.scalar(select(User).where(User.username == username))
            if existing:
                continue
            db.add(
                User(
                    username=username,
                    password_hash=pwd_context.hash(password),
                    role=role,
                    is_active=True,
                )
            )
        db.commit()
    finally:
        db.close()


@app.on_event("startup")
def on_startup() -> None:
    if (
        settings.app_env.lower() in {"prod", "production"}
        and settings.jwt_secret == "dev-secret-change-me"
    ):
        raise RuntimeError("JWT_SECRET must be set in production")

    if settings.app_env.lower() in {"dev", "test"}:
        Base.metadata.create_all(bind=engine)

    if settings.seed_dev_users:
        _ensure_dev_users()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> AuthContext:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

    try:
        payload = jwt.decode(
            credentials.credentials, settings.jwt_secret, algorithms=[settings.jwt_alg]
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from exc

    username = payload.get("sub")
    role = payload.get("role")
    if not username or role not in {"planner", "viewer"}:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload"
        )
    return AuthContext(username=username, role=role)


def require_role(*allowed_roles: str):
    def dependency(user: AuthContext = Depends(get_current_user)) -> AuthContext:
        if user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user

    return dependency


@app.get("/", include_in_schema=False)
def frontend_home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.post("/auth/token", response_model=TokenResponse)
def login(payload: TokenRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.username == payload.username))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not pwd_context.verify(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = _create_token(payload.username, user.role)
    return TokenResponse(access_token=token, role=user.role)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "version": app.version,
        "env": settings.app_env,
        "server_time_utc": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/auth/me", response_model=AuthMeResponse)
def auth_me(user: AuthContext = Depends(get_current_user)) -> AuthMeResponse:
    return AuthMeResponse(username=user.username, role=user.role)


@app.post("/optimize", response_model=OptimizeResponse)
def optimize(
    payload: OptimizeRequest,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_role("planner")),
) -> OptimizeResponse:
    scopes = {(shift.team_id, shift.site_id) for shift in payload.shifts}
    team_id, site_id = (None, None)
    if len(scopes) == 1:
        team_id, site_id = next(iter(scopes))
    return _run_optimizer(payload, db, team_id=team_id, site_id=site_id)


@app.post("/optimize/run", response_model=OptimizeResponse)
def optimize_from_db(
    payload: OptimizeRunRequest,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_role("planner")),
) -> OptimizeResponse:
    shift_query = select(ShiftModel)
    if payload.shift_ids:
        shift_query = shift_query.where(ShiftModel.id.in_(payload.shift_ids))
    if payload.team_id:
        shift_query = shift_query.where(ShiftModel.team_id == payload.team_id)
    if payload.site_id:
        shift_query = shift_query.where(ShiftModel.site_id == payload.site_id)
    if payload.start_from:
        shift_query = shift_query.where(ShiftModel.start_at >= payload.start_from)
    if payload.end_to:
        shift_query = shift_query.where(ShiftModel.end_at <= payload.end_to)

    employee_query = select(EmployeeModel)
    if payload.employee_ids:
        employee_query = employee_query.where(EmployeeModel.id.in_(payload.employee_ids))
    if payload.team_id:
        employee_query = employee_query.where(EmployeeModel.team_id == payload.team_id)
    if payload.site_id:
        employee_query = employee_query.where(EmployeeModel.site_id == payload.site_id)

    shifts = [_db_shift_to_planner_input(s) for s in db.scalars(shift_query).all()]
    employees = [_db_employee_to_planner_input(e) for e in db.scalars(employee_query).all()]

    return _run_optimizer(
        OptimizeRequest(shifts=shifts, employees=employees, constraints=payload.constraints),
        db,
        team_id=payload.team_id,
        site_id=payload.site_id,
    )


@app.post("/feedback", response_model=FeedbackResponse)
def feedback(
    payload: FeedbackRequest,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_role("planner")),
) -> FeedbackResponse:
    updated = save_feedback(db, payload.assignment_id, payload.decision, payload.reason)
    if not updated:
        raise HTTPException(status_code=404, detail="Assignment event not found")
    return FeedbackResponse(status="captured", updated_at=datetime.now(timezone.utc))


@app.get("/runs", response_model=list[RunSummaryResponse])
def list_runs(
    team_id: str | None = None,
    site_id: str | None = None,
    limit: int = 20,
    offset: int = 0,
    sort_dir: str = "desc",
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_role("planner", "viewer")),
) -> list[RunSummaryResponse]:
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be >= 0")
    if sort_dir not in {"asc", "desc"}:
        raise HTTPException(status_code=400, detail="sort_dir must be asc or desc")

    query = select(OptimizerRunModel)
    if team_id:
        query = query.where(OptimizerRunModel.team_id == team_id)
    if site_id:
        query = query.where(OptimizerRunModel.site_id == site_id)

    order_expr = (
        OptimizerRunModel.created_at.asc()
        if sort_dir == "asc"
        else OptimizerRunModel.created_at.desc()
    )
    rows = db.scalars(query.order_by(order_expr).offset(offset).limit(limit)).all()
    return [_serialize_run(row) for row in rows]


@app.delete("/runs/{run_id}", status_code=204)
def delete_run(
    run_id: int,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_role("planner")),
) -> None:
    run = db.get(OptimizerRunModel, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    db.delete(run)
    db.commit()


@app.get("/kpis", response_model=KpiResponse)
def kpis(
    team_id: str | None = None,
    site_id: str | None = None,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_role("planner", "viewer")),
) -> KpiResponse:
    run = latest_run(db, team_id=team_id, site_id=site_id)
    if run is None or run.total_shifts == 0:
        return KpiResponse(fill_rate=0.0, unassigned_shifts=0, overtime_risk=0.0)

    fill_rate = round((run.total_shifts - run.unassigned_shifts) / run.total_shifts, 4)
    return KpiResponse(
        fill_rate=fill_rate,
        unassigned_shifts=run.unassigned_shifts,
        overtime_risk=round(max(0.0, 1 - run.score), 4),
    )


@app.get("/capacity/heatmap", response_model=CapacityHeatmapResponse)
def capacity_heatmap(
    start: datetime,
    end: datetime,
    team_id: str | None = None,
    site_id: str | None = None,
    bucket_minutes: int = 60,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_role("planner", "viewer")),
) -> CapacityHeatmapResponse:
    if end <= start:
        raise HTTPException(status_code=400, detail="end must be after start")
    if bucket_minutes != 60:
        raise HTTPException(status_code=400, detail="Only hourly buckets (60 min) are supported")

    shift_query = select(ShiftModel).where(ShiftModel.start_at < end, ShiftModel.end_at > start)
    employee_query = select(EmployeeModel)
    if team_id:
        shift_query = shift_query.where(ShiftModel.team_id == team_id)
        employee_query = employee_query.where(EmployeeModel.team_id == team_id)
    if site_id:
        shift_query = shift_query.where(ShiftModel.site_id == site_id)
        employee_query = employee_query.where(EmployeeModel.site_id == site_id)

    shifts = db.scalars(shift_query).all()
    employees = db.scalars(employee_query).all()
    available_count = sum(1 for emp in employees if emp.available)
    absence_count = sum(1 for emp in employees if not emp.available)

    buckets: list[CapacityBucketResponse] = []
    for bucket_start, bucket_end in _iter_hourly_buckets(start, end):
        required_count = sum(
            1 for shift in shifts if shift.start_at < bucket_end and shift.end_at > bucket_start
        )
        gap = max(0, required_count - available_count)
        overlap = gap > 0 and absence_count > 0
        risk_level = "high" if overlap else ("medium" if gap > 0 else "low")
        buckets.append(
            CapacityBucketResponse(
                bucket_start=bucket_start,
                bucket_end=bucket_end,
                required_count=required_count,
                available_count=available_count,
                absence_count=absence_count,
                gap=gap,
                overlap_absence_understaffed=overlap,
                risk_level=risk_level,
            )
        )

    return CapacityHeatmapResponse(
        team_id=team_id,
        site_id=site_id,
        start=start,
        end=end,
        bucket_minutes=bucket_minutes,
        buckets=buckets,
    )


@app.post("/employees", response_model=EmployeeResponse)
def create_employee(
    payload: EmployeeCreateRequest,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_role("planner")),
) -> EmployeeResponse:
    existing = db.get(EmployeeModel, payload.id)
    if existing:
        raise HTTPException(status_code=409, detail="Employee already exists")

    employee = EmployeeModel(
        id=payload.id,
        team_id=payload.team_id,
        site_id=payload.site_id,
        skills_csv=",".join(payload.skills),
        cost_per_shift=payload.cost_per_shift,
        available=payload.available,
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return _serialize_employee(employee)


@app.get("/employees", response_model=list[EmployeeResponse])
def list_employees(
    team_id: str | None = None,
    site_id: str | None = None,
    sort_by: str = "id",
    sort_dir: str = "asc",
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_role("planner", "viewer")),
) -> list[EmployeeResponse]:
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be >= 0")

    query = select(EmployeeModel)
    if team_id:
        query = query.where(EmployeeModel.team_id == team_id)
    if site_id:
        query = query.where(EmployeeModel.site_id == site_id)

    sort_fields = {
        "id": EmployeeModel.id,
        "team_id": EmployeeModel.team_id,
        "site_id": EmployeeModel.site_id,
        "cost_per_shift": EmployeeModel.cost_per_shift,
    }
    if sort_by not in sort_fields:
        raise HTTPException(status_code=400, detail="invalid sort_by")
    if sort_dir not in {"asc", "desc"}:
        raise HTTPException(status_code=400, detail="sort_dir must be asc or desc")

    sort_col = sort_fields[sort_by]
    order_expr = desc(sort_col) if sort_dir == "desc" else sort_col.asc()

    rows = db.scalars(query.order_by(order_expr).offset(offset).limit(limit)).all()
    return [_serialize_employee(row) for row in rows]


@app.patch("/employees/{employee_id}", response_model=EmployeeResponse)
def patch_employee(
    employee_id: str,
    payload: EmployeePatchRequest,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_role("planner")),
) -> EmployeeResponse:
    employee = db.get(EmployeeModel, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    if payload.team_id is not None:
        employee.team_id = payload.team_id
    if payload.site_id is not None:
        employee.site_id = payload.site_id
    if payload.skills is not None:
        employee.skills_csv = ",".join(payload.skills)
    if payload.cost_per_shift is not None:
        employee.cost_per_shift = payload.cost_per_shift
    if payload.available is not None:
        employee.available = payload.available

    db.commit()
    db.refresh(employee)
    return _serialize_employee(employee)


@app.delete("/employees/{employee_id}", status_code=204)
def delete_employee(
    employee_id: str,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_role("planner")),
) -> None:
    employee = db.get(EmployeeModel, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    db.delete(employee)
    db.commit()


@app.post("/shifts", response_model=ShiftResponse)
def create_shift(
    payload: ShiftCreateRequest,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_role("planner")),
) -> ShiftResponse:
    if payload.end <= payload.start:
        raise HTTPException(status_code=400, detail="Shift end must be after shift start")

    existing = db.get(ShiftModel, payload.id)
    if existing:
        raise HTTPException(status_code=409, detail="Shift already exists")

    shift = ShiftModel(
        id=payload.id,
        team_id=payload.team_id,
        site_id=payload.site_id,
        required_skill=payload.required_skill,
        route_distance_km=payload.route_distance_km,
        start_at=payload.start,
        end_at=payload.end,
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return _serialize_shift(shift)


@app.get("/shifts", response_model=list[ShiftResponse])
def list_shifts(
    team_id: str | None = None,
    site_id: str | None = None,
    required_skill: str | None = None,
    sort_by: str = "start_at",
    sort_dir: str = "asc",
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_role("planner", "viewer")),
) -> list[ShiftResponse]:
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be >= 0")

    query = select(ShiftModel)
    if team_id:
        query = query.where(ShiftModel.team_id == team_id)
    if site_id:
        query = query.where(ShiftModel.site_id == site_id)
    if required_skill:
        query = query.where(ShiftModel.required_skill == required_skill)

    sort_fields = {
        "start_at": ShiftModel.start_at,
        "id": ShiftModel.id,
        "required_skill": ShiftModel.required_skill,
    }
    if sort_by not in sort_fields:
        raise HTTPException(status_code=400, detail="invalid sort_by")
    if sort_dir not in {"asc", "desc"}:
        raise HTTPException(status_code=400, detail="sort_dir must be asc or desc")

    sort_col = sort_fields[sort_by]
    order_expr = desc(sort_col) if sort_dir == "desc" else sort_col.asc()

    rows = db.scalars(query.order_by(order_expr).offset(offset).limit(limit)).all()
    return [_serialize_shift(row) for row in rows]


@app.patch("/shifts/{shift_id}", response_model=ShiftResponse)
def patch_shift(
    shift_id: str,
    payload: ShiftPatchRequest,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_role("planner")),
) -> ShiftResponse:
    shift = db.get(ShiftModel, shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    if payload.team_id is not None:
        shift.team_id = payload.team_id
    if payload.site_id is not None:
        shift.site_id = payload.site_id
    if payload.required_skill is not None:
        shift.required_skill = payload.required_skill
    if payload.route_distance_km is not None:
        shift.route_distance_km = payload.route_distance_km
    if payload.start is not None:
        shift.start_at = payload.start
    if payload.end is not None:
        shift.end_at = payload.end
    if shift.end_at <= shift.start_at:
        raise HTTPException(status_code=400, detail="Shift end must be after shift start")

    db.commit()
    db.refresh(shift)
    return _serialize_shift(shift)


@app.delete("/shifts/{shift_id}", status_code=204)
def delete_shift(
    shift_id: str,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_role("planner")),
) -> None:
    shift = db.get(ShiftModel, shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    db.delete(shift)
    db.commit()
