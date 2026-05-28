"""Add failure_patterns and remediation_rules tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-27
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "failure_patterns",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_key",
            sa.String(100),
            sa.ForeignKey("projects.key", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("signature_hash", sa.String(64), nullable=False),
        sa.Column("error_type", sa.String(50), nullable=False),
        sa.Column("error_location", JSONB, nullable=True),
        sa.Column("error_exemplar", sa.Text, nullable=True),
        sa.Column("failure_modality", sa.String(30), nullable=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("occurrence_count", sa.Integer, default=1),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(20), default="active"),
        sa.Column("confidence", sa.Float, default=0.0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_fp_signature", "failure_patterns", ["project_key", "signature_hash"])
    op.create_index("ix_fp_error_type", "failure_patterns", ["project_key", "error_type"])

    op.create_table(
        "remediation_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_key",
            sa.String(100),
            sa.ForeignKey("projects.key", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("error_type", sa.String(50), nullable=False),
        sa.Column("location_pattern", sa.String(255), nullable=True),
        sa.Column("suggestion", sa.Text, nullable=False),
        sa.Column("code_locations", JSONB, nullable=True),
        sa.Column("confidence", sa.Float, default=0.7),
        sa.Column("hit_count", sa.Integer, default=0),
        sa.Column("created_by", sa.String(50), default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("remediation_rules")
    op.drop_table("failure_patterns")
