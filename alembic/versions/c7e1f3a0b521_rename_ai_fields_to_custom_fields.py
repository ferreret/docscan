"""rename ai_fields_json to custom_fields_json and remove ai steps

Revision ID: c7e1f3a0b521
Revises: a324c82d5742
Create Date: 2026-03-20 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7e1f3a0b521'
down_revision: Union[str, Sequence[str], None] = 'a324c82d5742'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename ai_fields_json -> custom_fields_json y limpiar pasos AI del pipeline."""
    # 1. Renombrar columna en tabla pages
    with op.batch_alter_table('pages', schema=None) as batch_op:
        batch_op.alter_column(
            'ai_fields_json',
            new_column_name='custom_fields_json',
        )

    # 2. Limpiar pasos "ai" del pipeline_json de applications
    import json
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, pipeline_json FROM applications "
            "WHERE pipeline_json IS NOT NULL "
            "AND pipeline_json LIKE '%\"type\": \"ai\"%'"
        )
    ).fetchall()
    for row in rows:
        try:
            steps = json.loads(row[1])
        except (json.JSONDecodeError, TypeError):
            continue
        filtered = [s for s in steps if s.get("type") != "ai"]
        if len(filtered) != len(steps):
            conn.execute(
                sa.text("UPDATE applications SET pipeline_json = :pj WHERE id = :id"),
                {"pj": json.dumps(filtered, ensure_ascii=False), "id": row[0]},
            )


def downgrade() -> None:
    """Revert: custom_fields_json -> ai_fields_json.

    NOTA: Los pasos 'ai' eliminados del pipeline_json NO se restauran;
    no es posible recuperarlos sin una copia de seguridad previa.
    """
    with op.batch_alter_table('pages', schema=None) as batch_op:
        batch_op.alter_column(
            'custom_fields_json',
            new_column_name='ai_fields_json',
        )
