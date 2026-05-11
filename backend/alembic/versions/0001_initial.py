"""initial

Revision ID: 0001
Revises:
Create Date: 2025-05-11
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("max_runs", sa.Integer, server_default="20", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("key"),
    )

    op.create_table(
        "runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_key", sa.String(100), nullable=False),
        sa.Column("status", sa.Enum("processing", "completed", "failed", name="run_status"), nullable=False, server_default="processing"),
        sa.Column("branch", sa.String(255), nullable=True),
        sa.Column("commit_hash", sa.String(40), nullable=True),
        sa.Column("total", sa.Integer, server_default="0", nullable=False),
        sa.Column("passed", sa.Integer, server_default="0", nullable=False),
        sa.Column("failed", sa.Integer, server_default="0", nullable=False),
        sa.Column("broken", sa.Integer, server_default="0", nullable=False),
        sa.Column("skipped", sa.Integer, server_default="0", nullable=False),
        sa.Column("unknown", sa.Integer, server_default="0", nullable=False),
        sa.Column("duration_ms", sa.BigInteger, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_key"], ["projects.key"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "test_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uuid", sa.String(36), nullable=False),
        sa.Column("history_id", sa.String(64), nullable=True),
        sa.Column("test_case_id", sa.String(64), nullable=True),
        sa.Column("full_name", sa.Text, nullable=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("stage", sa.String(20), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stop_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.BigInteger, nullable=True),
        sa.Column("labels", postgresql.JSONB, nullable=True),
        sa.Column("links", postgresql.JSONB, nullable=True),
        sa.Column("parameters", postgresql.JSONB, nullable=True),
        sa.Column("status_details", postgresql.JSONB, nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_test_results_uuid", "test_results", ["uuid"])
    op.create_index("ix_test_results_history_id", "test_results", ["history_id"])

    op.create_table(
        "test_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("test_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_step_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("stage", sa.String(20), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stop_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.BigInteger, nullable=True),
        sa.Column("status_details", postgresql.JSONB, nullable=True),
        sa.ForeignKeyConstraint(["test_result_id"], ["test_results.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_step_id"], ["test_steps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "test_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("test_result_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("step_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("source", sa.String(500), nullable=False),
        sa.Column("type", sa.String(100), nullable=False),
        sa.Column("file_path", sa.Text, nullable=True),
        sa.Column("size", sa.BigInteger, server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["test_result_id"], ["test_results.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["step_id"], ["test_steps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("test_attachments")
    op.drop_table("test_steps")
    op.drop_index("ix_test_results_history_id", "test_results")
    op.drop_index("ix_test_results_uuid", "test_results")
    op.drop_table("test_results")
    op.drop_table("runs")
    op.execute("DROP TYPE IF EXISTS run_status")
    op.drop_table("projects")
