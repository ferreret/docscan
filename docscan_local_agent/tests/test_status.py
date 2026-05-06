"""Tests del endpoint GET /status del agente local."""

from __future__ import annotations

from fastapi.testclient import TestClient

from docscan_local_agent import __version__


def test_status_returns_200(client: TestClient) -> None:
    """El endpoint /status responde 200 OK."""
    resp = client.get("/status")
    assert resp.status_code == 200


def test_status_returns_expected_payload(client: TestClient) -> None:
    """El payload incluye name, version y paired."""
    resp = client.get("/status")
    body = resp.json()
    assert body["name"] == "docscan-local-agent"
    assert body["version"] == __version__
    assert body["paired"] is False


def test_status_content_type_json(client: TestClient) -> None:
    """El content-type es JSON."""
    resp = client.get("/status")
    assert resp.headers["content-type"].startswith("application/json")
