"""unique application name per tenant

Revision ID: e5b7c3d94f10
Revises: d9a2b4c1e835
Create Date: 2026-04-13 11:30:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "e5b7c3d94f10"
down_revision: Union[str, Sequence[str], None] = "bd2be614cf0f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Reemplaza UNIQUE global de applications.name por (tenant_id, name)."""
    with op.batch_alter_table("applications", schema=None) as batch_op:
        batch_op.drop_constraint("applications_name_key", type_="unique")
        batch_op.create_unique_constraint(
            "uq_applications_tenant_name", ["tenant_id", "name"]
        )


def downgrade() -> None:
    with op.batch_alter_table("applications", schema=None) as batch_op:
        batch_op.drop_constraint("uq_applications_tenant_name", type_="unique")
        batch_op.create_unique_constraint("applications_name_key", ["name"])
