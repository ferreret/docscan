"""Módulo de internacionalización (i18n) de DocScan Studio.

Gestiona la carga de traducciones Qt (.qm) según el idioma configurado.
Idiomas soportados: es (español, por defecto), en (inglés), ca (catalán).
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QLocale, QTranslator
from PySide6.QtWidgets import QApplication

log = logging.getLogger(__name__)

# Idiomas soportados: código -> nombre nativo
SUPPORTED_LANGUAGES: dict[str, str] = {
    "es": "ES",
    "en": "EN",
    "ca": "CAT",
}

DEFAULT_LANGUAGE = "es"

# Directorio donde residen los ficheros .qm compilados
_TRANSLATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "resources" / "translations"

# Traductores activos (para poder desinstalarlos al cambiar idioma)
_active_translators: list[QTranslator] = []


def available_languages() -> dict[str, str]:
    """Devuelve los idiomas disponibles (código -> nombre nativo)."""
    return dict(SUPPORTED_LANGUAGES)


def load_language(language: str, app: QApplication | None = None) -> bool:
    """Carga las traducciones para el idioma indicado.

    Args:
        language: Código de idioma ('es', 'en', 'ca').
        app: Instancia de QApplication. Si es None, usa QApplication.instance().

    Returns:
        True si se cargaron traducciones (o es español, idioma base).
    """
    if app is None:
        app = QApplication.instance()
    if app is None:
        log.warning("No hay QApplication activa para instalar traducciones")
        return False

    # Desinstalar traductores anteriores
    _uninstall_translators(app)

    # Español es el idioma base de los strings en código — no necesita .qm
    if language == DEFAULT_LANGUAGE:
        log.info("Idioma: %s (base, sin traductor)", language)
        return True

    if language not in SUPPORTED_LANGUAGES:
        log.warning("Idioma '%s' no soportado, usando '%s'", language, DEFAULT_LANGUAGE)
        return False

    # Cargar traducción de la app
    qm_path = _TRANSLATIONS_DIR / f"docscan_{language}.qm"
    translator = QTranslator(app)
    if not translator.load(str(qm_path)):
        log.warning("No se pudo cargar traducción: %s", qm_path)
        return False

    app.installTranslator(translator)
    _active_translators.append(translator)
    log.info("Idioma cargado: %s (%s)", language, qm_path.name)

    # Cargar traducción de Qt (botones estándar: OK, Cancel, etc.)
    qt_translator = QTranslator(app)
    qt_qm = _TRANSLATIONS_DIR / f"qt_{language}.qm"
    if qt_translator.load(str(qt_qm)):
        app.installTranslator(qt_translator)
        _active_translators.append(qt_translator)

    return True


def _uninstall_translators(app: QApplication) -> None:
    """Desinstala todos los traductores activos."""
    for translator in _active_translators:
        app.removeTranslator(translator)
        translator.deleteLater()
    _active_translators.clear()


def get_language_preference() -> str:
    """Lee el idioma guardado en preferencias (QSettings)."""
    from PySide6.QtCore import QSettings
    settings = QSettings("DocScanStudio", "DocScanStudio")
    return settings.value("i18n/language", DEFAULT_LANGUAGE)


def save_language_preference(language: str) -> None:
    """Guarda el idioma en preferencias (QSettings)."""
    from PySide6.QtCore import QSettings
    settings = QSettings("DocScanStudio", "DocScanStudio")
    settings.setValue("i18n/language", language)
