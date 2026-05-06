"""Tests del CLI de bootstrap inicial de la plataforma SaaS (Hito 1).

Cubre la función pública ``bootstrap_superadmin`` y el parser de
argumentos del módulo ``web.api.bootstrap``.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
import web.api._register_models  # noqa: F401  registra todas las tablas

from web.api.auth.security import verify_password
from web.api.bootstrap import (
    BootstrapError,
    bootstrap_superadmin,
    parse_args,
)
from web.api.models import (
    ROLE_COMPANY_ADMIN,
    ROLE_SUPERADMIN,
    Tenant,
    User,
)


@pytest.fixture
def db_session():
    """Sesión SQLAlchemy aislada en SQLite memoria."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


class TestBootstrapSuperadmin:
    def test_crea_tenant_tecnomedia_y_primer_superadmin(self, db_session):
        user = bootstrap_superadmin(
            db_session,
            email="admin@tecnomedia.es",
            password="secreto1234",
            display_name="Admin TecnoMedia",
        )
        assert user.id > 0
        assert user.email == "admin@tecnomedia.es"
        assert user.role == ROLE_SUPERADMIN
        assert user.display_name == "Admin TecnoMedia"
        assert user.active is True
        assert verify_password("secreto1234", user.hashed_password)

        tenant = db_session.execute(
            select(Tenant).where(Tenant.slug == "tecnomedia")
        ).scalar_one()
        assert tenant.name == "TecnoMedia"
        assert tenant.plan == "enterprise"
        assert tenant.active is True
        assert user.tenant_id == tenant.id

    def test_password_no_se_guarda_en_claro(self, db_session):
        user = bootstrap_superadmin(
            db_session,
            email="admin@tecnomedia.es",
            password="secreto1234",
            display_name="X",
        )
        assert "secreto1234" not in user.hashed_password
        assert verify_password("secreto1234", user.hashed_password)

    def test_idempotente_email_existente_devuelve_mismo_usuario(self, db_session):
        first = bootstrap_superadmin(
            db_session,
            email="admin@tecnomedia.es",
            password="secreto1234",
            display_name="Original",
        )

        again = bootstrap_superadmin(
            db_session,
            email="admin@tecnomedia.es",
            password="otropassword",
            display_name="Cambiado",
        )

        assert again.id == first.id
        assert again.display_name == "Original"
        assert verify_password("secreto1234", again.hashed_password)
        tenants = db_session.execute(select(Tenant)).scalars().all()
        assert len(tenants) == 1

    def test_segundo_superadmin_se_anade_al_tenant_tecnomedia(self, db_session):
        primero = bootstrap_superadmin(
            db_session,
            email="primero@tecnomedia.es",
            password="x12345678",
            display_name="P",
        )
        segundo = bootstrap_superadmin(
            db_session,
            email="segundo@tecnomedia.es",
            password="y12345678",
            display_name="S",
        )
        assert primero.tenant_id == segundo.tenant_id
        assert segundo.role == ROLE_SUPERADMIN
        tenants = db_session.execute(select(Tenant)).scalars().all()
        assert len(tenants) == 1

    def test_email_existente_en_otro_tenant_lanza_error(self, db_session):
        otro = Tenant(name="Otro", slug="otro", plan="free")
        db_session.add(otro)
        db_session.flush()
        db_session.add(
            User(
                tenant_id=otro.id,
                email="duplicado@test.com",
                hashed_password="dummy",
                display_name="Existente",
                role=ROLE_COMPANY_ADMIN,
            )
        )
        db_session.commit()

        with pytest.raises(BootstrapError, match="email"):
            bootstrap_superadmin(
                db_session,
                email="duplicado@test.com",
                password="x12345678",
                display_name="X",
            )

    def test_email_existente_en_tecnomedia_pero_no_superadmin_lanza_error(
        self, db_session
    ):
        tecno = Tenant(name="TecnoMedia", slug="tecnomedia", plan="enterprise")
        db_session.add(tecno)
        db_session.flush()
        db_session.add(
            User(
                tenant_id=tecno.id,
                email="rebajado@tecnomedia.es",
                hashed_password="dummy",
                display_name="Rebajado",
                role=ROLE_COMPANY_ADMIN,
            )
        )
        db_session.commit()

        with pytest.raises(BootstrapError, match="email"):
            bootstrap_superadmin(
                db_session,
                email="rebajado@tecnomedia.es",
                password="x12345678",
                display_name="X",
            )


class TestBootstrapValidation:
    def test_password_corta_lanza_error(self, db_session):
        with pytest.raises(BootstrapError, match="contraseña"):
            bootstrap_superadmin(
                db_session,
                email="admin@tecnomedia.es",
                password="corto",
                display_name="X",
            )

    def test_email_invalido_lanza_error(self, db_session):
        with pytest.raises(BootstrapError, match="email"):
            bootstrap_superadmin(
                db_session,
                email="no-es-email",
                password="x12345678",
                display_name="X",
            )


class TestParseArgs:
    def test_argumentos_validos(self):
        ns = parse_args(
            [
                "superadmin",
                "--email",
                "admin@tecnomedia.es",
                "--password",
                "secreto1234",
                "--display",
                "Admin",
            ]
        )
        assert ns.command == "superadmin"
        assert ns.email == "admin@tecnomedia.es"
        assert ns.password == "secreto1234"
        assert ns.display == "Admin"

    def test_falta_password_lanza_systemexit(self):
        with pytest.raises(SystemExit):
            parse_args(
                [
                    "superadmin",
                    "--email",
                    "admin@tecnomedia.es",
                    "--display",
                    "Admin",
                ]
            )

    def test_sin_subcomando_lanza_systemexit(self):
        with pytest.raises(SystemExit):
            parse_args([])
