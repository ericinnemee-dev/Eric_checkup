from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    team_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    site_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    skills_csv: Mapped[str] = mapped_column(Text, default="")
    cost_per_shift: Mapped[float] = mapped_column(default=1.0)
    available: Mapped[bool] = mapped_column(default=True)


class Shift(Base):
    __tablename__ = "shifts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    team_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    site_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    required_skill: Mapped[str] = mapped_column(String(64))
    route_distance_km: Mapped[float] = mapped_column(default=0.0)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OptimizerRun(Base):
    __tablename__ = "optimizer_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    team_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    site_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    total_shifts: Mapped[int] = mapped_column(Integer)
    unassigned_shifts: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    fill_rate: Mapped[float] = mapped_column(Float, default=0.0)
    fairness: Mapped[float] = mapped_column(Float, default=0.0)
    cost_score: Mapped[float] = mapped_column(Float, default=0.0)
    route_score: Mapped[float] = mapped_column(Float, default=0.0)
    penalty: Mapped[float] = mapped_column(Float, default=0.0)

    events: Mapped[list["AssignmentEvent"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class AssignmentEvent(Base):
    __tablename__ = "assignment_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("optimizer_runs.id"))
    shift_id: Mapped[str] = mapped_column(String(64))
    employee_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    decision: Mapped[str] = mapped_column(String(32), default="proposed")

    run: Mapped[OptimizerRun] = relationship(back_populates="events")
