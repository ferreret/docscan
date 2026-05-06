"""Tests del cliente HTTP que el agente usa para hablar con el SaaS.

Mockeamos las respuestas HTTP con ``httpx.MockTransport`` (incluido en
httpx — sin nuevas dependencias) para no necesitar un servidor real.
"""

from __future__ import annotations

import json

import httpx
import pytest

from docscan_local_agent.saas_client import (
    PairClaimError,
    SaasClient,
    SaasUnavailable,
    WhoamiError,
)


def _mock_client(handler) -> httpx.Client:
    """Crea un httpx.Client que usa el handler en lugar de red real."""
    return httpx.Client(transport=httpx.MockTransport(handler))


# ---------------------------------------------------------------------------
# pair_claim
# ---------------------------------------------------------------------------


def test_pair_claim_success_returns_token_and_device_id() -> None:
    """En el happy path el SaaS devuelve {agent_token, device_id}."""

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "POST"
        assert req.url.path == "/api/agent/pair-claim"
        assert json.loads(req.content) == {"code": "ABCD2345"}
        return httpx.Response(
            200,
            json={"agent_token": "7.deadbeef", "device_id": 7},
        )

    with _mock_client(handler) as http:
        client = SaasClient("https://saas.example.com", http_client=http)
        result = client.pair_claim("ABCD2345")

    assert result.agent_token == "7.deadbeef"
    assert result.device_id == 7


def test_pair_claim_normalises_code_uppercase_and_strip() -> None:
    """El SaaS espera el código en upper y sin espacios. El cliente lo normaliza."""
    captured: dict[str, object] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(req.content)
        return httpx.Response(200, json={"agent_token": "1.x", "device_id": 1})

    with _mock_client(handler) as http:
        SaasClient("https://saas.example.com", http_client=http).pair_claim(
            "  abcd2345  "
        )

    assert captured["body"] == {"code": "ABCD2345"}


def test_pair_claim_404_raises_invalid_code() -> None:
    """SaaS responde 404 (código inexistente o consumido)."""

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "Código de pairing no válido"})

    with _mock_client(handler) as http:
        client = SaasClient("https://saas.example.com", http_client=http)
        with pytest.raises(PairClaimError) as exc:
            client.pair_claim("WRONGCD2")

    assert exc.value.status_code == 404
    assert "no válido" in exc.value.detail.lower()


def test_pair_claim_410_raises_expired() -> None:
    """SaaS responde 410 cuando el código ha expirado."""

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(410, json={"detail": "Código de pairing expirado"})

    with _mock_client(handler) as http:
        client = SaasClient("https://saas.example.com", http_client=http)
        with pytest.raises(PairClaimError) as exc:
            client.pair_claim("ABCD2345")

    assert exc.value.status_code == 410
    assert "expirado" in exc.value.detail.lower()


def test_pair_claim_network_error_raises_saas_unavailable() -> None:
    """Si el SaaS no responde, levantamos SaasUnavailable (no httpx.*)."""

    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with _mock_client(handler) as http:
        client = SaasClient("https://saas.example.com", http_client=http)
        with pytest.raises(SaasUnavailable):
            client.pair_claim("ABCD2345")


def test_pair_claim_strips_trailing_slash_in_base_url() -> None:
    """``base_url`` con o sin slash final produce la misma URL."""
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["url"] = str(req.url)
        return httpx.Response(200, json={"agent_token": "1.x", "device_id": 1})

    with _mock_client(handler) as http:
        SaasClient("https://saas.example.com/", http_client=http).pair_claim("ABCD2345")

    assert captured["url"] == "https://saas.example.com/api/agent/pair-claim"


# ---------------------------------------------------------------------------
# whoami
# ---------------------------------------------------------------------------


def _whoami_payload() -> dict:
    return {
        "device_id": 7,
        "name": "Portátil Ana",
        "user": {
            "id": 3,
            "email": "ana@example.com",
            "display_name": "Ana García",
            "role": "operator",
        },
        "tenant": {"id": 2, "name": "TecnoMedia", "slug": "tecnomedia"},
        "paired_at": "2026-05-06T12:00:00",
        "last_seen": None,
    }


def test_whoami_success_parses_full_payload() -> None:
    """whoami sends Bearer y devuelve el AgentInfo completo."""
    captured: dict[str, object] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "GET"
        assert req.url.path == "/api/agent/whoami"
        captured["auth"] = req.headers.get("authorization")
        return httpx.Response(200, json=_whoami_payload())

    with _mock_client(handler) as http:
        client = SaasClient("https://saas.example.com", http_client=http)
        info = client.whoami("7.deadbeef")

    assert captured["auth"] == "Bearer 7.deadbeef"
    assert info.device_id == 7
    assert info.name == "Portátil Ana"
    assert info.user.email == "ana@example.com"
    assert info.tenant.name == "TecnoMedia"


def test_whoami_401_raises_whoami_error() -> None:
    """Token inválido → 401 → WhoamiError."""

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "Token inválido"})

    with _mock_client(handler) as http:
        client = SaasClient("https://saas.example.com", http_client=http)
        with pytest.raises(WhoamiError) as exc:
            client.whoami("bad-token")

    assert exc.value.status_code == 401
