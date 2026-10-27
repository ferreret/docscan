"""add group to applications

Paridad con FlexibarNET10 (App.Group): el launcher agrupa las Apps bajo una
cabecera plegable con el nombre del grupo; "" = sin grupo (nivel raíz).

Solo ``op.add_column``: en SQLite no recrea la tabla (ver el bug de
2026-08-05 con ``batch_alter_table``).

Revision ID: f3a8c1d72b95
Revises: e2c7b9a4f160
Create Date: 2026-10-27 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f3a8c1d72b95"
down_revision: Union[str, Sequence[str], None] = "e2c7b9a4f160"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema (idempotente: no falla si la columna ya existe)."""
    existing = {
        c["name"] for c in sa.inspect(op.get_bind()).get_columns("applications")
    }
    if "group" not in existing:
        op.add_column(
            "applications",
            sa.Column("group", sa.String(200), nullable=False, server_default=""),
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("applications", schema=None) as batch_op:
        batch_op.drop_column("group")
