"""add agent_devices table

Revision ID: c5d8e1f64b27
Revises: a3b8d4e2f7c9
Create Date: 2026-05-06 10:30:00.000000

Crea la tabla ``agent_devices`` para el sprint del cliente local web.
Cada fila representa una vinculación (pairing) entre un usuario y un
agente local instalado en su PC. Ver docstring del modelo
``AgentDevice`` en ``web/api/models.py`` para el flujo completo.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c5d8e1f64b27"
down_revision: Union[str, Sequence[str], None] = "a3b8d4e2f7c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("pairing_code", sa.String(16), nullable=True),
        sa.Column("code_expires_at", sa.DateTime(), nullable=True),
        sa.Column("token_hash", sa.String(255), nullable=True),
        sa.Column("paired_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen", sa.DateTime(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_agent_devices_user_id", "agent_devices", ["user_id"])
    op.create_index("ix_agent_devices_tenant_id", "agent_devices", ["tenant_id"])
    op.create_index(
        "ix_agent_devices_pairing_code",
        "agent_devices",
        ["pairing_code"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_devices_pairing_code", table_name="agent_devices")
    op.drop_index("ix_agent_devices_tenant_id", table_name="agent_devices")
    op.drop_index("ix_agent_devices_user_id", table_name="agent_devices")
    op.drop_table("agent_devices")
