"""Tests de la aplicación acotada en tiempo de regex de usuario (C3)."""

from __future__ import annotations

import time

import pytest

from app.utils import safe_regex

# Patrón con backtracking catastrófico que ni el módulo `regex` puede
# resolver por optimización: solo lo salva el timeout.
PATOLOGICO = r"^(a|a)*$"
CEBO = "a" * 40 + "b"

necesita_timeout = pytest.mark.skipif(
    not safe_regex.HAS_TIMEOUT_SUPPORT,
    reason="el módulo 'regex' no está instalado",
)


class TestSearch:
    def test_encuentra_coincidencia(self):
        assert safe_regex.search(r"^FAC-\d+$", "FAC-1234") is True

    def test_sin_coincidencia(self):
        assert safe_regex.search(r"^FAC-\d+$", "ALB-1234") is False

    def test_busca_en_cualquier_posicion(self):
        assert safe_regex.search(r"\d{3}", "abc123def") is True

    def test_regex_invalido_es_fail_open(self):
        assert safe_regex.search("(sin cerrar", "loquesea") is True

    @necesita_timeout
    def test_patron_patologico_no_cuelga(self):
        """El caso que motivó C3: corta a tiempo en vez de congelarse."""
        inicio = time.monotonic()
        resultado = safe_regex.search(PATOLOGICO, CEBO, timeout=0.3)
        transcurrido = time.monotonic() - inicio

        assert transcurrido < 3.0, f"tardó {transcurrido:.1f}s: no hubo timeout"
        # Fail-open: ante la duda, el valor pasa el filtro.
        assert resultado is True

    @necesita_timeout
    def test_fail_open_configurable(self):
        assert safe_regex.search(PATOLOGICO, CEBO, timeout=0.3, default=False) is False

    @necesita_timeout
    def test_el_timeout_no_afecta_a_la_llamada_siguiente(self):
        """Un patrón colgado no deja el motor inservible."""
        safe_regex.search(PATOLOGICO, CEBO, timeout=0.3)

        inicio = time.monotonic()
        assert safe_regex.search(r"^ok$", "ok") is True
        assert time.monotonic() - inicio < 0.5


class TestFullmatch:
    def test_valida_valor_completo(self):
        assert safe_regex.fullmatch(r"[A-Z]\d{8}", "A12345678") is True

    def test_rechaza_valor_parcial(self):
        assert safe_regex.fullmatch(r"[A-Z]\d{8}", "A12345678X") is False

    def test_regex_invalido_es_fail_open(self):
        assert safe_regex.fullmatch("[sin cerrar", "loquesea") is True

    @necesita_timeout
    def test_patron_patologico_no_cuelga(self):
        inicio = time.monotonic()
        resultado = safe_regex.fullmatch(PATOLOGICO, CEBO, timeout=0.3)

        assert time.monotonic() - inicio < 3.0
        # Fail-open: se acepta el valor antes que bloquear al operador.
        assert resultado is True


class TestCompilePattern:
    def test_devuelve_none_si_es_invalido(self):
        assert safe_regex.compile_pattern("(sin cerrar") is None

    def test_compila_patron_valido(self):
        assert safe_regex.compile_pattern(r"\d+") is not None

    def test_cachea_por_texto(self):
        a = safe_regex.compile_pattern(r"cacheado-\d+")
        b = safe_regex.compile_pattern(r"cacheado-\d+")
        assert a is b
