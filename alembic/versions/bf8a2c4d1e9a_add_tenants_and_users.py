"""add tenants and users

Revision ID: bf8a2c4d1e9a
Revises: bd2be614cf0f
Create Date: 2026-04-14 10:00:00.000000

Las tablas ``tenants`` y ``users`` se crearon originalmente solo via
``Base.metadata.create_all`` en el bootstrap del contenedor. Esta migración
cierra el agujero del chain para que ``alembic upgrade head`` desde una BD
vacía produzca el esquema completo sin necesidad de ``create_all``.

Es idempotente: si las tablas ya existen (despliegues previos que las
crearon con ``create_all`` antes de esta migración), no hace nada.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "bf8a2c4d1e9a"
down_revision: Union[str, Sequence[str], None] = "bd2be614cf0f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing = set(inspect(op.get_bind()).get_table_names())

    if "tenants" not in existing:
        op.create_table(
            "tenants",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("slug", sa.String(100), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False),
            sa.Column("plan", sa.String(50), nullable=False),
            sa.Column("settings_json", sa.Text(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.UniqueConstraint("name"),
            sa.UniqueConstraint("slug"),
        )

    if "users" not in existing:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("hashed_password", sa.String(255), nullable=False),
            sa.Column("display_name", sa.String(200), nullable=False),
            sa.Column("role", sa.String(50), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.UniqueConstraint("email"),
        )


def downgrade() -> None:
    op.drop_table("users")
    op.drop_table("tenants")
