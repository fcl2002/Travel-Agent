"""Rename users.update_at to updated_at.

Revision ID: 0004_rename_users_updated_at
Revises: 0003_create_auth_sessions
"""

from alembic import op

revision = "0004_rename_users_updated_at"
down_revision = "0003_create_auth_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "update_at", new_column_name="updated_at")


def downgrade() -> None:
    op.alter_column("users", "updated_at", new_column_name="update_at")
