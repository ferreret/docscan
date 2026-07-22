"""add notifications_json to applications

Revision ID: c1d5e9f34b28
Revises: a3b8d4e2f7c9
Create Date: 2026-07-22 11:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c1d5e9f34b28"
down_revision: Union[str, Sequence[str], None] = "a3b8d4e2f7c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("applications", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "notifications_json", sa.Text(), nullable=False, server_default="{}"
            )
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("applications", schema=None) as batch_op:
        batch_op.drop_column("notifications_json")
