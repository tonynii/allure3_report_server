from __future__ import annotations
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


# ── Project ────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    max_runs: int = Field(default=20, ge=1, le=200)


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    max_runs: int | None = Field(None, ge=1, le=200)


class ProjectResponse(BaseModel):
    key: str
    name: str
    description: str | None
    max_runs: int
    runs_count: int = 0
    latest_run_status: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    key: str
    name: str
    description: str | None
    runs_count: int = 0
    latest_run_status: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Run ────────────────────────────────────────────────────────────────

class RunCreateRequest(BaseModel):
    branch: str | None = None
    commit_hash: str | None = None


class RunResponse(BaseModel):
    id: UUID
    project_key: str
    status: str
    branch: str | None
    commit_hash: str | None
    total: int
    passed: int
    failed: int
    broken: int
    skipped: int
    unknown: int
    duration_ms: int | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class RunDetailResponse(RunResponse):
    test_results: list["TestResultSummary"] = []


class RunListItem(BaseModel):
    id: UUID
    status: str
    branch: str | None
    commit_hash: str | None
    total: int
    passed: int
    failed: int
    broken: int
    skipped: int
    duration_ms: int | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


# ── Test Result ────────────────────────────────────────────────────────

class TestResultSummary(BaseModel):
    id: UUID
    uuid: str
    history_id: str | None
    full_name: str | None
    name: str
    status: str
    duration_ms: int | None
    labels: list | None

    model_config = {"from_attributes": True}


class TestResultDetail(TestResultSummary):
    test_case_id: str | None
    description: str | None
    stage: str | None
    start_time: datetime | None
    stop_time: datetime | None
    links: list | None
    parameters: list | None
    status_details: dict | None
    steps: list["TestStepSummary"] = []
    attachments: list["TestAttachmentSummary"] = []

    model_config = {"from_attributes": True}


# ── Test Step ──────────────────────────────────────────────────────────

class TestStepSummary(BaseModel):
    id: UUID
    name: str
    status: str
    duration_ms: int | None
    children: list["TestStepSummary"] = []

    model_config = {"from_attributes": True}


class TestStepDetail(TestStepSummary):
    stage: str | None
    start_time: datetime | None
    stop_time: datetime | None
    status_details: dict | None
    attachments: list["TestAttachmentSummary"] = []

    model_config = {"from_attributes": True}


# ── Test Attachment ────────────────────────────────────────────────────

class TestAttachmentSummary(BaseModel):
    id: UUID
    name: str
    source: str
    type: str
    size: int

    model_config = {"from_attributes": True}
