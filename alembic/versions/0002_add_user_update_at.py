"""Record the latest user update time.

Revision ID: 0002_add_user_update_at
Revises: 0001_create_users
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_add_user_update_at"
down_revision = "0001_create_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("update_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "update_at")
