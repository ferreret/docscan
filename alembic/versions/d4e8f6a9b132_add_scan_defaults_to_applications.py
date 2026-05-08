"""add scan_defaults_json to applications

Revision ID: d4e8f6a9b132
Revises: c5d8e1f64b27
Create Date: 2026-05-08 16:50:00.000000

Sprint D — hito 13. Añade ``scan_defaults_json`` a ``applications``
para persistir las opciones de escaneo elegidas por el operario en el
``ScannerOptionsDialog`` del frontend (modo color, resolución,
fuente, brillo, ...). El frontend lee el dict al abrir el dialog para
preseleccionar valores; el agente NO consulta este campo (recibe los
overrides directamente del frontend en cada llamada a /scan-*).

NOT NULL DEFAULT '{}' por consistencia con los otros campos JSON
(pipeline_json, transfer_json, ...).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e8f6a9b132"
down_revision: Union[str, Sequence[str], None] = "c5d8e1f64b27"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("applications", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "scan_defaults_json",
                sa.Text(),
                nullable=False,
                server_default="{}",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("applications", schema=None) as batch_op:
        batch_op.drop_column("scan_defaults_json")
