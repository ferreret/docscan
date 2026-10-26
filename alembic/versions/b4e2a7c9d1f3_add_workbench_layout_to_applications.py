"""add workbench layout and hide_add_barcode_button to applications

Panel derecho del Workbench configurable por aplicación (paridad con
FlexibarNET10): orden/visibilidad de paneles y pestañas y la opción de ocultar
el botón «+ Añadir» barcode.

Se usa ``op.add_column`` directamente y no ``batch_alter_table``: en SQLite
añadir una columna es un ALTER TABLE ADD COLUMN y no hace falta recrear la
tabla (la recreación fue la que vació datos en el bug de 2026-08-05).

Revision ID: b4e2a7c9d1f3
Revises: c1d5e9f34b28
Create Date: 2026-10-26 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b4e2a7c9d1f3"
down_revision: Union[str, Sequence[str], None] = "c1d5e9f34b28"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns("applications")}


def upgrade() -> None:
    """Upgrade schema (idempotente: no falla si la columna ya existe)."""
    existing = _columns()
    if "workbench_layout_json" not in existing:
        op.add_column(
            "applications",
            sa.Column(
                "workbench_layout_json", sa.Text(), nullable=False, server_default=""
            ),
        )
    if "hide_add_barcode_button" not in existing:
        op.add_column(
            "applications",
            sa.Column(
                "hide_add_barcode_button",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("applications", schema=None) as batch_op:
        batch_op.drop_column("hide_add_barcode_button")
        batch_op.drop_column("workbench_layout_json")
