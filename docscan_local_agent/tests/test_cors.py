"""Tests del middleware CORS del agente local.

Hito 9 sprint cliente local web. El frontend del SaaS (origin
``https://docscan.example.com`` o ``http://localhost:5173`` en dev)
necesita poder hacer ``fetch`` a ``http://127.0.0.1:47816/...``. Sin
CORS configurado el navegador bloquea las peticiones, así que el agente
expone ``Access-Control-Allow-Origin: *`` con ``allow_credentials=False``.

Decisión deliberada de no usar credentials: el agente NO usa cookies
(la auth interna es por presencia de ``agent.json`` en disco). Mantener
``credentials=False`` impide que un sitio malicioso pueda atacar el
agente con la sesión del operario en su navegador.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from docscan_local_agent.main import create_app


def test_status_includes_cors_origin_header() -> None:
    """GET /status devuelve Access-Control-Allow-Origin para origen externo."""
    client = TestClient(create_app())

    resp = client.get("/status", headers={"Origin": "https://docscan.example.com"})

    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "*"


def test_preflight_pair_allows_post(tmp_path) -> None:
    """OPTIONS /pair (preflight) responde con allow-methods POST."""
    client = TestClient(create_app())

    resp = client.options(
        "/pair",
        headers={
            "Origin": "https://docscan.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )

    assert resp.status_code == 200
    allow_methods = resp.headers.get("access-control-allow-methods", "")
    assert "POST" in allow_methods
    assert resp.headers.get("access-control-allow-origin") == "*"


def test_preflight_allows_authorization_header() -> None:
    """El preflight permite el header Authorization (lo usan /scanners y co.)."""
    client = TestClient(create_app())

    resp = client.options(
        "/scanners",
        headers={
            "Origin": "https://docscan.example.com",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert resp.status_code == 200
    allow_headers = resp.headers.get("access-control-allow-headers", "").lower()
    assert "authorization" in allow_headers


def test_no_credentials_for_security() -> None:
    """No exponemos Access-Control-Allow-Credentials=true (cierra ataques CSRF
    contra el agente desde un sitio malicioso autenticado en el SaaS)."""
    client = TestClient(create_app())

    resp = client.get("/status", headers={"Origin": "https://evil.example"})

    # CORSMiddleware sólo emite el header cuando allow_credentials=True.
    # Verificamos la ausencia.
    assert resp.headers.get("access-control-allow-credentials") is None
