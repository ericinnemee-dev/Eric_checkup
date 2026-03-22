from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class TokenRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class AuthContext(BaseModel):
    username: str
    role: str


class AuthMeResponse(BaseModel):
    username: str
    role: str


class Shift(BaseModel):
    id: str
    team_id: str | None = None
    site_id: str | None = None
    required_skill: str
    route_distance_km: float = Field(default=0.0, ge=0)
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def validate_time_window(self):
        if self.end <= self.start:
            raise ValueError("Shift end must be after shift start")
        return self


class Employee(BaseModel):
    id: str
    team_id: str | None = None
    site_id: str | None = None
    skills: list[str]
    cost_per_shift: float = Field(default=1.0, ge=0)
    available: bool = True


class Constraint(BaseModel):
    key: str
    value: str | int | float


class OptimizeRequest(BaseModel):
    shifts: list[Shift]
    employees: list[Employee]
    constraints: list[Constraint] = Field(default_factory=list)


class OptimizeRunRequest(BaseModel):
    shift_ids: list[str] | None = None
    employee_ids: list[str] | None = None
    team_id: str | None = None
    site_id: str | None = None
    start_from: datetime | None = None
    end_to: datetime | None = None
    constraints: list[Constraint] = Field(default_factory=list)


class Assignment(BaseModel):
    event_id: int | None = None
    shift_id: str
    employee_id: str | None = None
    reason: str


class ScoreBreakdownResponse(BaseModel):
    fill_rate: float
    fairness: float
    cost_score: float
    route_score: float
    penalty: float


class OptimizeResponse(BaseModel):
    run_id: int
    assignments: list[Assignment]
    score: float
    score_breakdown: ScoreBreakdownResponse
    violations: list[str]


class FeedbackRequest(BaseModel):
    assignment_id: int
    decision: Literal["accepted", "rejected"]
    reason: str


class FeedbackResponse(BaseModel):
    status: str
    updated_at: datetime


class RunSummaryResponse(BaseModel):
    id: int
    created_at: datetime
    team_id: str | None = None
    site_id: str | None = None
    score: float
    total_shifts: int
    unassigned_shifts: int
    fill_rate: float | None = None
    fairness: float | None = None
    cost_score: float | None = None
    route_score: float | None = None
    penalty: float | None = None


class KpiResponse(BaseModel):
    fill_rate: float
    unassigned_shifts: int
    overtime_risk: float


class CapacityBucketResponse(BaseModel):
    bucket_start: datetime
    bucket_end: datetime
    required_count: int
    available_count: int
    absence_count: int
    gap: int
    overlap_absence_understaffed: bool
    risk_level: Literal["low", "medium", "high"]


class CapacityHeatmapResponse(BaseModel):
    team_id: str | None = None
    site_id: str | None = None
    start: datetime
    end: datetime
    bucket_minutes: int
    buckets: list[CapacityBucketResponse]


class EmployeeCreateRequest(BaseModel):
    id: str
    team_id: str | None = None
    site_id: str | None = None
    skills: list[str]
    cost_per_shift: float = Field(default=1.0, ge=0)
    available: bool = True


class EmployeePatchRequest(BaseModel):
    team_id: str | None = None
    site_id: str | None = None
    skills: list[str] | None = None
    cost_per_shift: float | None = Field(default=None, ge=0)
    available: bool | None = None


class EmployeeResponse(BaseModel):
    id: str
    team_id: str | None = None
    site_id: str | None = None
    skills: list[str]
    cost_per_shift: float
    available: bool


class ShiftCreateRequest(BaseModel):
    id: str
    team_id: str | None = None
    site_id: str | None = None
    required_skill: str
    route_distance_km: float = Field(default=0.0, ge=0)
    start: datetime
    end: datetime


class ShiftPatchRequest(BaseModel):
    team_id: str | None = None
    site_id: str | None = None
    required_skill: str | None = None
    route_distance_km: float | None = Field(default=None, ge=0)
    start: datetime | None = None
    end: datetime | None = None


class ShiftResponse(BaseModel):
    id: str
    team_id: str | None = None
    site_id: str | None = None
    required_skill: str
    route_distance_km: float
    start: datetime
    end: datetime
