"""add document separator to pages

Separador de documento como propiedad de la página (paridad con
FlexibarNET10): ``is_separator`` y ``separator_value``. Un documento es el
tramo que va de un separador al siguiente y no se almacena.

Se usa ``op.add_column`` y no ``batch_alter_table``: añadir una columna en
SQLite es un ALTER TABLE ADD COLUMN y no recrea la tabla (la recreación fue
la que vació datos en el bug de 2026-08-05).

Las páginas que ya tenían un barcode con ``role="separator"`` (puesto por
script) se marcan como separador con ese valor, para que los lotes
existentes se sigan viendo igual.

Revision ID: d3f8a1c6e2b7
Revises: b4e2a7c9d1f3
Create Date: 2026-10-27 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d3f8a1c6e2b7"
down_revision: Union[str, Sequence[str], None] = "b4e2a7c9d1f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns("pages")}


def upgrade() -> None:
    """Upgrade schema (idempotente: no falla si la columna ya existe)."""
    existing = _columns()
    if "is_separator" not in existing:
        op.add_column(
            "pages",
            sa.Column(
                "is_separator", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
        )
    if "separator_value" not in existing:
        op.add_column(
            "pages",
            sa.Column("separator_value", sa.Text(), nullable=False, server_default=""),
        )

    # Lotes antiguos: el rol del barcode pasa a ser la marca de la página.
    op.execute(
        """
        UPDATE pages
        SET is_separator = TRUE,
            separator_value = COALESCE((
                SELECT b.value FROM barcodes b
                WHERE b.page_id = pages.id AND b.role = 'separator'
                ORDER BY b.id LIMIT 1
            ), '')
        WHERE NOT is_separator AND EXISTS (
            SELECT 1 FROM barcodes b
            WHERE b.page_id = pages.id AND b.role = 'separator'
        )
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("pages", schema=None) as batch_op:
        batch_op.drop_column("separator_value")
        batch_op.drop_column("is_separator")
