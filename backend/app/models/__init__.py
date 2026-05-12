import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, BigInteger, DateTime, ForeignKey, Enum, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_runs: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    runs: Mapped[list["Run"]] = relationship("Run", back_populates="project", cascade="all, delete-orphan")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_key: Mapped[str] = mapped_column(String(100), ForeignKey("projects.key", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("processing", "completed", "failed", name="run_status"), default="processing", nullable=False
    )
    branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commit_hash: Mapped[str | None] = mapped_column(String(40), nullable=True)
    total: Mapped[int] = mapped_column(Integer, default=0)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    broken: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    unknown: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    environment: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="runs")
    test_results: Mapped[list["TestResult"]] = relationship("TestResult", back_populates="run", cascade="all, delete-orphan")


class TestResult(Base):
    __tablename__ = "test_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    uuid: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    history_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    test_case_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    stage: Mapped[str | None] = mapped_column(String(20), nullable=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stop_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    labels: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    links: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    parameters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    run: Mapped["Run"] = relationship("Run", back_populates="test_results")
    steps: Mapped[list["TestStep"]] = relationship(
        "TestStep", back_populates="test_result", cascade="all, delete-orphan",
        foreign_keys="TestStep.test_result_id"
    )
    attachments: Mapped[list["TestAttachment"]] = relationship(
        "TestAttachment", back_populates="test_result", cascade="all, delete-orphan",
        foreign_keys="TestAttachment.test_result_id"
    )


class TestStep(Base):
    __tablename__ = "test_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("test_results.id", ondelete="CASCADE"), nullable=False)
    parent_step_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("test_steps.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    stage: Mapped[str | None] = mapped_column(String(20), nullable=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stop_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    test_result: Mapped["TestResult"] = relationship("TestResult", back_populates="steps", foreign_keys=[test_result_id])
    parent: Mapped["TestStep | None"] = relationship("TestStep", remote_side=[id], back_populates="children")
    children: Mapped[list["TestStep"]] = relationship(
        "TestStep", back_populates="parent", cascade="all, delete-orphan"
    )
    attachments: Mapped[list["TestAttachment"]] = relationship(
        "TestAttachment", back_populates="step", cascade="all, delete-orphan",
        foreign_keys="TestAttachment.step_id"
    )


class TestAttachment(Base):
    __tablename__ = "test_attachments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_result_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("test_results.id", ondelete="CASCADE"), nullable=True)
    step_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("test_steps.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str] = mapped_column(String(500), nullable=False)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    size: Mapped[int] = mapped_column(BigInteger, default=0)

    test_result: Mapped["TestResult | None"] = relationship("TestResult", back_populates="attachments", foreign_keys=[test_result_id])
    step: Mapped["TestStep | None"] = relationship("TestStep", back_populates="attachments", foreign_keys=[step_id])
