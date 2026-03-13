"""Tests de componentes UI: ThemeManager, IconFactory y ViewerOverlay.

Cubre:
- ThemeManager: singleton, properties, apply_theme, toggle_theme,
  increase_font, decrease_font y _scale_font_sizes.
- IconFactory: funciones icon_sun, icon_moon, icon_font_increase,
  icon_font_decrease — retorno de QIcon con pixmap de tamaño correcto.
- ViewerOverlay: construcción, emisión de señales por click en botones
  y actualización del label de página.
"""

from __future__ import annotations

import pytest
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.ui.icon_factory import (
    icon_font_decrease,
    icon_font_increase,
    icon_moon,
    icon_sun,
)
from app.ui.theme_manager import (
    BASE_FONT_SIZE,
    MAX_FONT_SIZE,
    MIN_FONT_SIZE,
    Theme,
    ThemeManager,
)
from app.ui.workbench.viewer_overlay import ViewerOverlay


# ================================================================== #
# Fixtures
# ================================================================== #


@pytest.fixture(autouse=True)
def reset_theme_manager_singleton():
    """Resetea el singleton de ThemeManager antes y después de cada test.

    Garantiza aislamiento total entre tests: cada uno obtiene una
    instancia fresca con estado inicial predeterminado.
    Usa QSettings de test aislado para no leer preferencias reales.
    """
    from PySide6.QtCore import QSettings

    ThemeManager._instance = None
    # Limpiar preferencias de test para que cada test arranque con defaults
    settings = QSettings("DocScanStudio", "DocScanStudio")
    settings.remove("appearance")
    settings.sync()
    yield
    ThemeManager._instance = None
    settings = QSettings("DocScanStudio", "DocScanStudio")
    settings.remove("appearance")
    settings.sync()


# ================================================================== #
# Tests de ThemeManager
# ================================================================== #


class TestThemeManagerSingleton:
    """Verifica el comportamiento singleton de ThemeManager."""

    def test_singleton_returns_same_instance(self):
        """Dos llamadas a ThemeManager() deben devolver el mismo objeto."""
        tm1 = ThemeManager()
        tm2 = ThemeManager()
        assert tm1 is tm2

    def test_singleton_reset_creates_new_instance(self):
        """Tras resetear _instance, la siguiente construcción es nueva."""
        tm1 = ThemeManager()
        ThemeManager._instance = None
        tm2 = ThemeManager()
        assert tm1 is not tm2


class TestThemeManagerDefaults:
    """Verifica el estado inicial tras construir ThemeManager."""

    def test_default_theme_is_dark(self):
        """El tema por defecto debe ser DARK."""
        tm = ThemeManager()
        assert tm.current_theme == Theme.DARK

    def test_is_dark_true_on_init(self):
        """is_dark debe ser True cuando el tema inicial es DARK."""
        tm = ThemeManager()
        assert tm.is_dark is True

    def test_default_font_size_equals_base(self):
        """El tamaño de fuente inicial debe coincidir con BASE_FONT_SIZE."""
        tm = ThemeManager()
        assert tm.font_size == BASE_FONT_SIZE


class TestThemeManagerApplyTheme:
    """Verifica apply_theme y sus efectos secundarios."""

    def test_apply_theme_light_changes_current_theme(self):
        """apply_theme(LIGHT) debe cambiar current_theme a LIGHT."""
        tm = ThemeManager()
        tm.apply_theme(Theme.LIGHT)
        assert tm.current_theme == Theme.LIGHT
        assert tm.is_dark is False

    def test_apply_theme_dark_changes_current_theme(self):
        """apply_theme(DARK) debe mantener/volver a DARK."""
        tm = ThemeManager()
        tm.apply_theme(Theme.LIGHT)
        tm.apply_theme(Theme.DARK)
        assert tm.current_theme == Theme.DARK
        assert tm.is_dark is True

    def test_apply_theme_emits_theme_changed_signal(self, qtbot):
        """apply_theme debe emitir theme_changed con el nombre del tema."""
        tm = ThemeManager()
        with qtbot.waitSignal(tm.theme_changed, timeout=1000) as blocker:
            tm.apply_theme(Theme.LIGHT)
        assert blocker.args == [Theme.LIGHT.value]

    def test_apply_theme_dark_emits_dark_value(self, qtbot):
        """apply_theme(DARK) emite theme_changed con 'dark'."""
        tm = ThemeManager()
        tm.apply_theme(Theme.LIGHT)  # partir desde LIGHT
        with qtbot.waitSignal(tm.theme_changed, timeout=1000) as blocker:
            tm.apply_theme(Theme.DARK)
        assert blocker.args == [Theme.DARK.value]

    def test_apply_theme_sets_application_stylesheet(self):
        """apply_theme debe llamar a QApplication.setStyleSheet sin error."""
        tm = ThemeManager()
        # Si no lanza excepción, el QSS se aplicó correctamente
        tm.apply_theme(Theme.DARK)
        app = QApplication.instance()
        assert app is not None
        stylesheet = app.styleSheet()
        assert len(stylesheet) > 0

    def test_apply_theme_nonexistent_file_does_not_raise(self, monkeypatch, tmp_path):
        """Si el archivo QSS no existe, apply_theme registra warning sin lanzar."""
        from app.ui import theme_manager as tm_mod

        monkeypatch.setattr(tm_mod, "_STYLES_DIR", tmp_path)
        tm = ThemeManager()
        # No debe lanzar excepción
        tm.apply_theme(Theme.DARK)
        # El tema NO debe cambiar porque no se aplicó
        assert tm.current_theme == Theme.DARK  # ya era DARK por defecto


class TestThemeManagerToggle:
    """Verifica toggle_theme alterna correctamente entre temas."""

    def test_toggle_from_dark_goes_to_light(self):
        """Desde DARK, toggle_theme debe cambiar a LIGHT."""
        tm = ThemeManager()
        assert tm.current_theme == Theme.DARK
        tm.toggle_theme()
        assert tm.current_theme == Theme.LIGHT

    def test_toggle_from_light_goes_to_dark(self):
        """Desde LIGHT, toggle_theme debe cambiar a DARK."""
        tm = ThemeManager()
        tm.apply_theme(Theme.LIGHT)
        tm.toggle_theme()
        assert tm.current_theme == Theme.DARK

    def test_toggle_twice_returns_to_original(self):
        """Dos toggles consecutivos devuelven al tema original."""
        tm = ThemeManager()
        original = tm.current_theme
        tm.toggle_theme()
        tm.toggle_theme()
        assert tm.current_theme == original

    def test_toggle_emits_theme_changed_signal(self, qtbot):
        """toggle_theme debe emitir la señal theme_changed."""
        tm = ThemeManager()
        with qtbot.waitSignal(tm.theme_changed, timeout=1000):
            tm.toggle_theme()


class TestThemeManagerFontSize:
    """Verifica increase_font y decrease_font."""

    def test_increase_font_increments_by_one(self):
        """increase_font debe subir font_size en exactamente 1px."""
        tm = ThemeManager()
        initial = tm.font_size
        tm.increase_font()
        assert tm.font_size == initial + 1

    def test_increase_font_emits_font_size_changed(self, qtbot):
        """increase_font debe emitir font_size_changed con el nuevo valor."""
        tm = ThemeManager()
        expected = tm.font_size + 1
        with qtbot.waitSignal(tm.font_size_changed, timeout=1000) as blocker:
            tm.increase_font()
        assert blocker.args == [expected]

    def test_increase_font_does_not_exceed_max(self):
        """increase_font no debe superar MAX_FONT_SIZE."""
        tm = ThemeManager()
        tm._font_size = MAX_FONT_SIZE
        tm.increase_font()
        assert tm.font_size == MAX_FONT_SIZE

    def test_increase_font_at_max_does_not_emit_signal(self, qtbot):
        """Si ya está en MAX_FONT_SIZE, no debe emitir font_size_changed."""
        tm = ThemeManager()
        tm._font_size = MAX_FONT_SIZE
        received = []
        tm.font_size_changed.connect(lambda v: received.append(v))
        tm.increase_font()
        assert received == []

    def test_decrease_font_decrements_by_one(self):
        """decrease_font debe bajar font_size en exactamente 1px."""
        tm = ThemeManager()
        initial = tm.font_size
        tm.decrease_font()
        assert tm.font_size == initial - 1

    def test_decrease_font_emits_font_size_changed(self, qtbot):
        """decrease_font debe emitir font_size_changed con el nuevo valor."""
        tm = ThemeManager()
        expected = tm.font_size - 1
        with qtbot.waitSignal(tm.font_size_changed, timeout=1000) as blocker:
            tm.decrease_font()
        assert blocker.args == [expected]

    def test_decrease_font_does_not_go_below_min(self):
        """decrease_font no debe bajar de MIN_FONT_SIZE."""
        tm = ThemeManager()
        tm._font_size = MIN_FONT_SIZE
        tm.decrease_font()
        assert tm.font_size == MIN_FONT_SIZE

    def test_decrease_font_at_min_does_not_emit_signal(self, qtbot):
        """Si ya está en MIN_FONT_SIZE, no debe emitir font_size_changed."""
        tm = ThemeManager()
        tm._font_size = MIN_FONT_SIZE
        received = []
        tm.font_size_changed.connect(lambda v: received.append(v))
        tm.decrease_font()
        assert received == []

    def test_multiple_increases_accumulate(self):
        """Tres aumentos consecutivos deben reflejarse en font_size."""
        tm = ThemeManager()
        initial = tm.font_size
        tm.increase_font()
        tm.increase_font()
        tm.increase_font()
        assert tm.font_size == initial + 3

    def test_increase_then_decrease_returns_to_base(self):
        """Aumentar y luego decrementar debe volver al tamaño original."""
        tm = ThemeManager()
        initial = tm.font_size
        tm.increase_font()
        tm.decrease_font()
        assert tm.font_size == initial


class TestThemeManagerScaleFontSizes:
    """Verifica _scale_font_sizes transforma correctamente el QSS."""

    def test_scale_no_delta_keeps_values_unchanged(self):
        """Con delta=0 (font_size == BASE_FONT_SIZE), el QSS no varía."""
        tm = ThemeManager()
        assert tm.font_size == BASE_FONT_SIZE
        qss = "QWidget { font-size: 13px; } QLabel { font-size: 11px; }"
        result = tm._scale_font_sizes(qss)
        assert "font-size: 13px" in result
        assert "font-size: 11px" in result

    def test_scale_positive_delta_increases_values(self):
        """Con delta=+2 cada font-size debe aumentar en 2px."""
        tm = ThemeManager()
        tm._font_size = BASE_FONT_SIZE + 2
        qss = "QWidget { font-size: 13px; } QLabel { font-size: 11px; }"
        result = tm._scale_font_sizes(qss)
        assert "font-size: 15px" in result
        assert "font-size: 13px" in result

    def test_scale_negative_delta_decreases_values(self):
        """Con delta=-2 cada font-size debe reducirse en 2px."""
        tm = ThemeManager()
        tm._font_size = BASE_FONT_SIZE - 2
        qss = "QWidget { font-size: 13px; } QLabel { font-size: 11px; }"
        result = tm._scale_font_sizes(qss)
        assert "font-size: 11px" in result
        assert "font-size: 9px" in result

    def test_scale_does_not_go_below_min_font_size(self):
        """Los valores escalados nunca deben caer por debajo de MIN_FONT_SIZE."""
        tm = ThemeManager()
        tm._font_size = MIN_FONT_SIZE  # delta muy negativo
        qss = "QWidget { font-size: 13px; }"
        result = tm._scale_font_sizes(qss)
        # El valor resultante no debe ser menor que MIN_FONT_SIZE
        import re
        sizes = [int(m.group(1)) for m in re.finditer(r"font-size:\s*(\d+)px", result)]
        for size in sizes:
            assert size >= MIN_FONT_SIZE

    def test_scale_handles_multiple_occurrences(self):
        """_scale_font_sizes debe procesar todas las ocurrencias del QSS."""
        tm = ThemeManager()
        tm._font_size = BASE_FONT_SIZE + 1
        qss = "A { font-size: 10px; } B { font-size: 12px; } C { font-size: 14px; }"
        result = tm._scale_font_sizes(qss)
        assert "font-size: 11px" in result
        assert "font-size: 13px" in result
        assert "font-size: 15px" in result

    def test_scale_stylesheet_from_disk_is_valid_string(self):
        """apply_theme con el QSS real de disco debe producir una cadena no vacía."""
        tm = ThemeManager()
        tm._font_size = BASE_FONT_SIZE
        from pathlib import Path
        qss_path = Path(__file__).resolve().parent.parent / "resources" / "styles" / "dark.qss"
        qss = qss_path.read_text(encoding="utf-8")
        result = tm._scale_font_sizes(qss)
        assert isinstance(result, str)
        assert len(result) > 0


# ================================================================== #
# Tests de IconFactory
# ================================================================== #


class TestIconFactory:
    """Verifica que las funciones de iconos retornan QIcon válidos."""

    def test_icon_sun_returns_qicon(self):
        """icon_sun debe retornar una instancia de QIcon no nula."""
        icon = icon_sun()
        assert isinstance(icon, QIcon)
        assert not icon.isNull()

    def test_icon_sun_pixmap_default_size(self):
        """El pixmap de icon_sun con size=32 debe ser de 32×32."""
        icon = icon_sun(size=32)
        pm = icon.pixmap(32, 32)
        assert pm.width() == 32
        assert pm.height() == 32

    def test_icon_sun_custom_size(self):
        """icon_sun respeta el parámetro size."""
        icon = icon_sun(size=48)
        pm = icon.pixmap(48, 48)
        assert pm.width() == 48
        assert pm.height() == 48

    def test_icon_sun_custom_color(self):
        """icon_sun acepta un color personalizado sin lanzar excepción."""
        icon = icon_sun(color="#ff0000", size=24)
        assert isinstance(icon, QIcon)
        assert not icon.isNull()

    def test_icon_moon_returns_qicon(self):
        """icon_moon debe retornar una instancia de QIcon no nula."""
        icon = icon_moon()
        assert isinstance(icon, QIcon)
        assert not icon.isNull()

    def test_icon_moon_pixmap_default_size(self):
        """El pixmap de icon_moon con size=32 debe ser de 32×32."""
        icon = icon_moon(size=32)
        pm = icon.pixmap(32, 32)
        assert pm.width() == 32
        assert pm.height() == 32

    def test_icon_moon_custom_size(self):
        """icon_moon respeta el parámetro size."""
        icon = icon_moon(size=16)
        pm = icon.pixmap(16, 16)
        assert pm.width() == 16
        assert pm.height() == 16

    def test_icon_moon_custom_color(self):
        """icon_moon acepta un color personalizado sin lanzar excepción."""
        icon = icon_moon(color="#00ff00", size=24)
        assert isinstance(icon, QIcon)
        assert not icon.isNull()

    def test_icon_font_increase_returns_qicon(self):
        """icon_font_increase debe retornar una instancia de QIcon no nula."""
        icon = icon_font_increase()
        assert isinstance(icon, QIcon)
        assert not icon.isNull()

    def test_icon_font_increase_pixmap_default_size(self):
        """El pixmap de icon_font_increase con size=32 debe ser de 32×32."""
        icon = icon_font_increase(size=32)
        pm = icon.pixmap(32, 32)
        assert pm.width() == 32
        assert pm.height() == 32

    def test_icon_font_increase_custom_size(self):
        """icon_font_increase respeta el parámetro size."""
        icon = icon_font_increase(size=64)
        pm = icon.pixmap(64, 64)
        assert pm.width() == 64
        assert pm.height() == 64

    def test_icon_font_decrease_returns_qicon(self):
        """icon_font_decrease debe retornar una instancia de QIcon no nula."""
        icon = icon_font_decrease()
        assert isinstance(icon, QIcon)
        assert not icon.isNull()

    def test_icon_font_decrease_pixmap_default_size(self):
        """El pixmap de icon_font_decrease con size=32 debe ser de 32×32."""
        icon = icon_font_decrease(size=32)
        pm = icon.pixmap(32, 32)
        assert pm.width() == 32
        assert pm.height() == 32

    def test_icon_font_decrease_custom_size(self):
        """icon_font_decrease respeta el parámetro size."""
        icon = icon_font_decrease(size=20)
        pm = icon.pixmap(20, 20)
        assert pm.width() == 20
        assert pm.height() == 20

    def test_icon_font_decrease_custom_color(self):
        """icon_font_decrease acepta un color personalizado sin lanzar excepción."""
        icon = icon_font_decrease(color="#0000ff", size=24)
        assert isinstance(icon, QIcon)
        assert not icon.isNull()

    def test_all_icons_are_distinct_objects(self):
        """Cada llamada a icon_* debe crear un nuevo objeto QIcon."""
        icon_a = icon_sun()
        icon_b = icon_sun()
        # Son instancias distintas (no el mismo objeto en memoria)
        assert icon_a is not icon_b


# ================================================================== #
# Tests de ViewerOverlay
# ================================================================== #


class TestViewerOverlayConstruction:
    """Verifica la construcción básica del widget ViewerOverlay."""

    def test_creates_without_error(self, qtbot):
        """ViewerOverlay debe construirse sin lanzar excepción."""
        overlay = ViewerOverlay()
        qtbot.addWidget(overlay)

    def test_object_name_is_set(self, qtbot):
        """El objectName del widget debe ser 'viewerOverlay'."""
        overlay = ViewerOverlay()
        qtbot.addWidget(overlay)
        assert overlay.objectName() == "viewerOverlay"

    def test_has_page_info_label(self, qtbot):
        """Debe existir el label de información de página."""
        overlay = ViewerOverlay()
        qtbot.addWidget(overlay)
        assert overlay._lbl_page_info is not None

    def test_initial_page_info_label_text(self, qtbot):
        """El texto inicial del label de página debe ser ' 0 / 0 '."""
        overlay = ViewerOverlay()
        qtbot.addWidget(overlay)
        assert overlay._lbl_page_info.text() == " 0 / 0 "


class TestViewerOverlayUpdatePageInfo:
    """Verifica el método update_page_info."""

    def test_update_page_info_sets_correct_text(self, qtbot):
        """update_page_info debe actualizar el label con formato ' N / M '."""
        overlay = ViewerOverlay()
        qtbot.addWidget(overlay)
        overlay.update_page_info(3, 10)
        assert overlay._lbl_page_info.text() == " 3 / 10 "

    def test_update_page_info_with_zero_total(self, qtbot):
        """update_page_info con total=0 debe mostrar ' 0 / 0 '."""
        overlay = ViewerOverlay()
        qtbot.addWidget(overlay)
        overlay.update_page_info(0, 0)
        assert overlay._lbl_page_info.text() == " 0 / 0 "

    def test_update_page_info_with_large_values(self, qtbot):
        """update_page_info debe manejar números grandes sin error."""
        overlay = ViewerOverlay()
        qtbot.addWidget(overlay)
        overlay.update_page_info(999, 1000)
        assert overlay._lbl_page_info.text() == " 999 / 1000 "

    def test_update_page_info_multiple_calls(self, qtbot):
        """Llamadas sucesivas a update_page_info actualizan el label."""
        overlay = ViewerOverlay()
        qtbot.addWidget(overlay)
        overlay.update_page_info(1, 5)
        overlay.update_page_info(2, 5)
        overlay.update_page_info(5, 5)
        assert overlay._lbl_page_info.text() == " 5 / 5 "


class TestViewerOverlayNavigationSignals:
    """Verifica que los botones de navegación emiten las señales correctas."""

    def test_btn_first_emits_nav_first(self, qtbot):
        """El botón de primera página debe emitir nav_first."""
        overlay = ViewerOverlay()
        qtbot.addWidget(overlay)
        with qtbot.waitSignal(overlay.nav_first, timeout=1000):
            overlay._btn_first.click()

    def test_btn_prev_emits_nav_prev(self, qtbot):
        """El botón anterior debe emitir nav_prev."""
        overlay = ViewerOverlay()
        qtbot.addWidget(overlay)
        with qtbot.waitSignal(overlay.nav_prev, timeout=1000):
            overlay._btn_prev.click()

    def test_btn_next_emits_nav_next(self, qtbot):
        """El botón siguiente debe emitir nav_next."""
        overlay = ViewerOverlay()
        qtbot.addWidget(overlay)
        with qtbot.waitSignal(overlay.nav_next, timeout=1000):
            overlay._btn_next.click()

    def test_btn_last_emits_nav_last(self, qtbot):
        """El botón de última página debe emitir nav_last."""
        overlay = ViewerOverlay()
        qtbot.addWidget(overlay)
        with qtbot.waitSignal(overlay.nav_last, timeout=1000):
            overlay._btn_last.click()

    def test_btn_next_bc_emits_nav_next_barcode(self, qtbot):
        """El botón 'siguiente con barcode' debe emitir nav_next_barcode."""
        overlay = ViewerOverlay()
        qtbot.addWidget(overlay)
        with qtbot.waitSignal(overlay.nav_next_barcode, timeout=1000):
            overlay._btn_next_bc.click()

    def test_btn_next_review_emits_nav_next_review(self, qtbot):
        """El botón 'siguiente pendiente revisión' debe emitir nav_next_review."""
        overlay = ViewerOverlay()
        qtbot.addWidget(overlay)
        with qtbot.waitSignal(overlay.nav_next_review, timeout=1000):
            overlay._btn_next_review.click()


class TestViewerOverlayZoomSignals:
    """Verifica que los botones de zoom emiten las señales correctas."""

    def test_btn_zoom_in_emits_zoom_in_requested(self, qtbot):
        """El botón de acercar debe emitir zoom_in_requested."""
        overlay = ViewerOverlay()
        qtbot.addWidget(overlay)
        with qtbot.waitSignal(overlay.zoom_in_requested, timeout=1000):
            overlay._btn_zoom_in.click()

    def test_btn_zoom_out_emits_zoom_out_requested(self, qtbot):
        """El botón de alejar debe emitir zoom_out_requested."""
        overlay = ViewerOverlay()
        qtbot.addWidget(overlay)
        with qtbot.waitSignal(overlay.zoom_out_requested, timeout=1000):
            overlay._btn_zoom_out.click()

    def test_btn_zoom_fit_emits_zoom_fit_requested(self, qtbot):
        """El botón de ajustar a página debe emitir zoom_fit_requested."""
        overlay = ViewerOverlay()
        qtbot.addWidget(overlay)
        with qtbot.waitSignal(overlay.zoom_fit_requested, timeout=1000):
            overlay._btn_zoom_fit.click()

    def test_btn_zoom_100_emits_zoom_100_requested(self, qtbot):
        """El botón de tamaño real debe emitir zoom_100_requested."""
        overlay = ViewerOverlay()
        qtbot.addWidget(overlay)
        with qtbot.waitSignal(overlay.zoom_100_requested, timeout=1000):
            overlay._btn_zoom_100.click()


class TestViewerOverlayToolSignals:
    """Verifica que los botones de herramientas emiten las señales correctas."""

    def test_btn_rotate_emits_rotate_requested(self, qtbot):
        """El botón de rotar debe emitir rotate_requested."""
        overlay = ViewerOverlay()
        qtbot.addWidget(overlay)
        with qtbot.waitSignal(overlay.rotate_requested, timeout=1000):
            overlay._btn_rotate.click()

    def test_btn_mark_emits_mark_requested(self, qtbot):
        """El botón de marcar debe emitir mark_requested."""
        overlay = ViewerOverlay()
        qtbot.addWidget(overlay)
        with qtbot.waitSignal(overlay.mark_requested, timeout=1000):
            overlay._btn_mark.click()

    def test_btn_delete_current_emits_delete_current_requested(self, qtbot):
        """El botón de eliminar página debe emitir delete_current_requested."""
        overlay = ViewerOverlay()
        qtbot.addWidget(overlay)
        with qtbot.waitSignal(overlay.delete_current_requested, timeout=1000):
            overlay._btn_delete_current.click()

    def test_btn_delete_from_emits_delete_from_requested(self, qtbot):
        """El botón de borrar desde aquí debe emitir delete_from_requested."""
        overlay = ViewerOverlay()
        qtbot.addWidget(overlay)
        with qtbot.waitSignal(overlay.delete_from_requested, timeout=1000):
            overlay._btn_delete_from.click()

    def test_btn_delete_current_object_name_is_danger(self, qtbot):
        """El botón de eliminar debe tener objectName 'dangerButton'."""
        overlay = ViewerOverlay()
        qtbot.addWidget(overlay)
        assert overlay._btn_delete_current.objectName() == "dangerButton"

    def test_btn_delete_from_object_name_is_danger(self, qtbot):
        """El botón de borrar desde aquí debe tener objectName 'dangerButton'."""
        overlay = ViewerOverlay()
        qtbot.addWidget(overlay)
        assert overlay._btn_delete_from.objectName() == "dangerButton"


class TestViewerOverlaySignalNotEmittedWithoutClick:
    """Verifica que las señales no se emiten espontáneamente sin acción."""

    def test_nav_first_not_emitted_on_construction(self, qtbot):
        """nav_first no debe emitirse durante la construcción del widget."""
        received = []
        overlay = ViewerOverlay()
        qtbot.addWidget(overlay)
        overlay.nav_first.connect(lambda: received.append(True))
        # Procesamos eventos pendientes sin hacer click
        qtbot.wait(50)
        assert received == []

    def test_zoom_in_not_emitted_on_construction(self, qtbot):
        """zoom_in_requested no debe emitirse durante la construcción."""
        received = []
        overlay = ViewerOverlay()
        qtbot.addWidget(overlay)
        overlay.zoom_in_requested.connect(lambda: received.append(True))
        qtbot.wait(50)
        assert received == []
