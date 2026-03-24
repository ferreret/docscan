"""Tests del módulo de internacionalización (i18n)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QTranslator
from PySide6.QtWidgets import QApplication

from app.i18n import (
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    _TRANSLATIONS_DIR,
    _active_translators,
    _uninstall_translators,
    available_languages,
    get_language_preference,
    load_language,
    save_language_preference,
)


class TestAvailableLanguages:
    """Tests para available_languages()."""

    def test_returns_dict(self):
        result = available_languages()
        assert isinstance(result, dict)

    def test_contains_es_en_ca(self):
        result = available_languages()
        assert "es" in result
        assert "en" in result
        assert "ca" in result

    def test_language_labels(self):
        result = available_languages()
        assert result["es"] == "ES"
        assert result["en"] == "EN"
        assert result["ca"] == "CAT"

    def test_returns_copy(self):
        """Verificar que devuelve una copia, no la referencia."""
        result = available_languages()
        result["xx"] = "Test"
        assert "xx" not in SUPPORTED_LANGUAGES


class TestDefaultLanguage:
    """Tests para el idioma por defecto."""

    def test_default_is_spanish(self):
        assert DEFAULT_LANGUAGE == "es"


class TestTranslationsDir:
    """Tests para el directorio de traducciones."""

    def test_translations_dir_exists(self):
        assert _TRANSLATIONS_DIR.exists()

    def test_en_qm_exists(self):
        assert (_TRANSLATIONS_DIR / "docscan_en.qm").exists()

    def test_ca_qm_exists(self):
        assert (_TRANSLATIONS_DIR / "docscan_ca.qm").exists()


class TestLoadLanguage:
    """Tests para load_language()."""

    def test_load_spanish_returns_true(self, qapp):
        """Español es el idioma base, siempre devuelve True."""
        result = load_language("es", qapp)
        assert result is True

    def test_load_spanish_no_translators(self, qapp):
        """Español no necesita traductores instalados."""
        load_language("es", qapp)
        assert len(_active_translators) == 0

    def test_load_english_returns_true(self, qapp):
        result = load_language("en", qapp)
        assert result is True

    def test_load_english_installs_translator(self, qapp):
        load_language("en", qapp)
        assert len(_active_translators) >= 1

    def test_load_catalan_returns_true(self, qapp):
        result = load_language("ca", qapp)
        assert result is True

    def test_load_catalan_installs_translator(self, qapp):
        load_language("ca", qapp)
        assert len(_active_translators) >= 1

    def test_load_unsupported_returns_false(self, qapp):
        result = load_language("xx", qapp)
        assert result is False

    def test_switching_language_uninstalls_previous(self, qapp):
        """Al cambiar de idioma, se desinstalan los traductores anteriores."""
        load_language("en", qapp)
        en_count = len(_active_translators)
        assert en_count >= 1

        load_language("ca", qapp)
        # Los traductores EN se desinstalaron, ahora hay traductores CA
        assert len(_active_translators) >= 1

    def test_switch_back_to_spanish(self, qapp):
        """Volver a español desinstala traductores."""
        load_language("en", qapp)
        load_language("es", qapp)
        assert len(_active_translators) == 0

    def test_load_with_explicit_none_and_no_instance(self, monkeypatch):
        """Sin QApplication activa, devuelve False."""
        monkeypatch.setattr(QApplication, "instance", staticmethod(lambda: None))
        result = load_language("en", None)
        assert result is False


class TestLanguagePreference:
    """Tests para guardar/leer preferencia de idioma."""

    def test_save_and_read(self, qapp):
        save_language_preference("en")
        assert get_language_preference() == "en"

        # Restaurar
        save_language_preference("es")

    def test_default_preference(self, qapp):
        """El valor por defecto es español."""
        save_language_preference("es")
        assert get_language_preference() == "es"
