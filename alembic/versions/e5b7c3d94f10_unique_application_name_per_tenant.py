"""unique application name per tenant

Revision ID: e5b7c3d94f10
Revises: d9a2b4c1e835
Create Date: 2026-04-13 11:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect


revision: str = "e5b7c3d94f10"
down_revision: Union[str, Sequence[str], None] = "bf8a2c4d1e9a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _application_uniques() -> set[str]:
    """Nombres de constraints UNIQUE presentes en la tabla applications."""
    insp = inspect(op.get_bind())
    return {uc["name"] for uc in insp.get_unique_constraints("applications")}


def upgrade() -> None:
    """Reemplaza UNIQUE global de applications.name por (tenant_id, name).

    Idempotente: en BD web el constraint ``applications_name_key`` existe y se
    reemplaza; en BD desktop creada por ``create_all`` (que nace con
    ``uq_applications_tenant_name`` y sin el nombre viejo) los guards evitan que
    ``upgrade head`` reviente con "No such constraint".
    """
    uniques = _application_uniques()
    with op.batch_alter_table("applications", schema=None) as batch_op:
        if "applications_name_key" in uniques:
            batch_op.drop_constraint("applications_name_key", type_="unique")
        if "uq_applications_tenant_name" not in uniques:
            batch_op.create_unique_constraint(
                "uq_applications_tenant_name", ["tenant_id", "name"]
            )


def downgrade() -> None:
    uniques = _application_uniques()
    with op.batch_alter_table("applications", schema=None) as batch_op:
        if "uq_applications_tenant_name" in uniques:
            batch_op.drop_constraint("uq_applications_tenant_name", type_="unique")
        if "applications_name_key" not in uniques:
            batch_op.create_unique_constraint("applications_name_key", ["name"])
