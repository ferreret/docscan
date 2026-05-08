"""add scan_show_dialog to applications

Revision ID: e6f9a013c245
Revises: d4e8f6a9b132
Create Date: 2026-05-08 17:30:00.000000

Sprint D — hito 13. Flag bool por aplicación que controla si al pulsar
🖨 en el workbench:

  - True (default): se muestra el diálogo del escáner antes de
    capturar. Windows con TWAIN/WIA → diálogo nativo del driver.
    Linux con SANE → ScannerOptionsDialog dinámico construido por el
    frontend a partir de get_device_options() (SANE no tiene UI propia).

  - False: se escanea directo con la última configuración del
    escáner (sin overrides desde el frontend). Útil para flujos
    repetitivos donde el operario ya fijó los parámetros una vez.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e6f9a013c245"
down_revision: Union[str, Sequence[str], None] = "d4e8f6a9b132"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("applications", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "scan_show_dialog",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("applications", schema=None) as batch_op:
        batch_op.drop_column("scan_show_dialog")
