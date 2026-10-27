"""add show_scanner_ui and icon_accent to applications

Paridad con FlexibarNET10 (ShowScannerUi e IconAccent): las Apps del Hospital
Arnau de Vilanova muestran el diálogo del escáner y llevan el icono en azul.

Solo ``op.add_column``: en SQLite no recrea la tabla (ver el bug de
2026-08-05 con ``batch_alter_table``).

Revision ID: e2c7b9a4f160
Revises: d3f8a1c6e2b7
Create Date: 2026-10-27 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e2c7b9a4f160"
down_revision: Union[str, Sequence[str], None] = "d3f8a1c6e2b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns("applications")}


def upgrade() -> None:
    """Upgrade schema (idempotente: no falla si la columna ya existe)."""
    existing = _columns()
    if "show_scanner_ui" not in existing:
        op.add_column(
            "applications",
            sa.Column(
                "show_scanner_ui",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
    if "icon_accent" not in existing:
        op.add_column(
            "applications",
            sa.Column("icon_accent", sa.String(20), nullable=False, server_default=""),
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("applications", schema=None) as batch_op:
        batch_op.drop_column("icon_accent")
        batch_op.drop_column("show_scanner_ui")
