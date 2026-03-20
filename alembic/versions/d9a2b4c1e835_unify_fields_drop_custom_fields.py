"""unify page fields: merge custom_fields_json into index_fields_json

Revision ID: d9a2b4c1e835
Revises: c7e1f3a0b521
Create Date: 2026-03-20 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9a2b4c1e835'
down_revision: Union[str, Sequence[str], None] = 'c7e1f3a0b521'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge custom_fields_json into index_fields_json, then drop custom_fields_json."""
    import json

    conn = op.get_bind()

    # Merge non-empty custom_fields into index_fields
    rows = conn.execute(
        sa.text(
            "SELECT id, index_fields_json, custom_fields_json FROM pages "
            "WHERE custom_fields_json IS NOT NULL "
            "AND custom_fields_json NOT IN ('{}', '', 'null')"
        )
    ).fetchall()

    for row in rows:
        page_id, idx_json, cf_json = row
        try:
            idx = json.loads(idx_json) if idx_json else {}
            cf = json.loads(cf_json) if cf_json else {}
        except (json.JSONDecodeError, TypeError):
            continue
        if cf:
            merged = {**idx, **cf}
            conn.execute(
                sa.text("UPDATE pages SET index_fields_json = :val WHERE id = :id"),
                {"val": json.dumps(merged, ensure_ascii=False), "id": page_id},
            )

    # Drop custom_fields_json column
    with op.batch_alter_table('pages', schema=None) as batch_op:
        batch_op.drop_column('custom_fields_json')


def downgrade() -> None:
    """Re-add custom_fields_json column (data not split back)."""
    with op.batch_alter_table('pages', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('custom_fields_json', sa.Text(), nullable=False, server_default='{}'),
        )
