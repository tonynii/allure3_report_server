"""add environment column

Revision ID: 0002
Revises: 0001
Create Date: 2025-05-12
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("environment", postgresql.JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("runs", "environment")
