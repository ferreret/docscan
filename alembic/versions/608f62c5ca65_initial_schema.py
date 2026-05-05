"""initial schema

Revision ID: 608f62c5ca65
Revises:
Create Date: 2026-03-13 14:18:00.315098

Crea el esquema base del proyecto (pre-web): applications, batches, pages,
barcodes, templates, operation_history. Las tablas multi-tenant (tenants,
users, invitations) se añaden en migraciones posteriores.

Reemplaza el primer intento retrofiteado que solo añadía image_config_json
sobre un esquema ya creado por ``Base.metadata.create_all``. Ahora las
migraciones son la fuente de verdad: ``alembic upgrade head`` sobre una
BD vacía produce el esquema completo.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "608f62c5ca65"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea el esquema inicial del desktop (pre-web)."""
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("pipeline_json", sa.Text(), nullable=False),
        sa.Column("events_json", sa.Text(), nullable=False),
        sa.Column("transfer_json", sa.Text(), nullable=False),
        sa.Column("batch_fields_json", sa.Text(), nullable=False),
        sa.Column("index_fields_json", sa.Text(), nullable=False),
        sa.Column("auto_transfer", sa.Boolean(), nullable=False),
        sa.Column("close_after_transfer", sa.Boolean(), nullable=False),
        sa.Column("background_color", sa.String(7), nullable=False),
        sa.Column("output_format", sa.String(20), nullable=False),
        sa.Column("default_tab", sa.String(20), nullable=False),
        sa.Column("scanner_backend", sa.String(10), nullable=False),
        sa.Column(
            "image_config_json",
            sa.Text(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("ai_config_json", sa.Text(), nullable=False),
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
        sa.UniqueConstraint("name", name="applications_name_key"),
    )

    op.create_table(
        "batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("folder_path", sa.Text(), nullable=False),
        sa.Column("hostname", sa.String(100), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("fields_json", sa.Text(), nullable=False),
        sa.Column("stats_json", sa.Text(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], ondelete="CASCADE"
        ),
    )

    op.create_table(
        "pages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("page_index", sa.Integer(), nullable=False),
        sa.Column("image_path", sa.Text(), nullable=False),
        sa.Column("ocr_text", sa.Text(), nullable=False),
        sa.Column("index_fields_json", sa.Text(), nullable=False),
        sa.Column("ai_fields_json", sa.Text(), nullable=False),
        sa.Column("needs_review", sa.Boolean(), nullable=False),
        sa.Column("review_reason", sa.Text(), nullable=False),
        sa.Column("is_blank", sa.Boolean(), nullable=False),
        sa.Column("is_excluded", sa.Boolean(), nullable=False),
        sa.Column("processing_errors_json", sa.Text(), nullable=False),
        sa.Column("script_errors_json", sa.Text(), nullable=False),
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
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "barcodes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("page_id", sa.Integer(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("symbology", sa.String(50), nullable=False),
        sa.Column("engine", sa.String(10), nullable=False),
        sa.Column("step_id", sa.String(50), nullable=False),
        sa.Column("quality", sa.Float(), nullable=False),
        sa.Column("pos_x", sa.Integer(), nullable=False),
        sa.Column("pos_y", sa.Integer(), nullable=False),
        sa.Column("pos_w", sa.Integer(), nullable=False),
        sa.Column("pos_h", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.ForeignKeyConstraint(["page_id"], ["pages.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("fields_json", sa.Text(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], ondelete="CASCADE"
        ),
    )

    op.create_table(
        "operation_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("operation", sa.String(50), nullable=False),
        sa.Column("old_state", sa.String(20), nullable=False),
        sa.Column("new_state", sa.String(20), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    """Elimina el esquema inicial."""
    op.drop_table("operation_history")
    op.drop_table("templates")
    op.drop_table("barcodes")
    op.drop_table("pages")
    op.drop_table("batches")
    op.drop_table("applications")
