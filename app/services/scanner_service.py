"""Servicio de escáner multiplataforma.

Backends disponibles según plataforma:
- Linux: SANE (python-sane)
- Windows: TWAIN (pytwain), WIA (pywin32/win32com)

La selección es configurable por aplicación. Si el backend preferido
falla al listar fuentes, se ofrece el siguiente automáticamente.
"""

from __future__ import annotations

import logging
import platform
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np

log = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Configuración de escaneo
# ------------------------------------------------------------------


@dataclass
class ScanConfig:
    """Parámetros de captura."""

    resolution: int = 300  # DPI
    mode: str = "Color"  # "Color", "Gray", "Lineart"
    duplex: bool = False
    page_size: str = ""  # "", "A4", "Letter"
    brightness: int | None = None
    contrast: int | None = None
    source_type: str = "flatbed"  # "flatbed" o "adf"
    show_ui: bool = False  # Mostrar diálogo nativo (TWAIN/WIA)
    extra_options: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeviceOption:
    """Opción individual de un dispositivo SANE."""

    name: str  # Nombre Python-safe (ej: "resolution")
    title: str  # Título legible (ej: "Scan resolution")
    description: str  # Descripción larga
    type: str  # "bool", "int", "fixed", "string", "button"
    unit: str  # "none", "pixel", "bit", "mm", "dpi", "percent", "microsecond"
    constraint: Any  # None, (min, max, step), o list de valores
    value: Any  # Valor actual
    is_active: bool = True
    is_settable: bool = True


# ------------------------------------------------------------------
# Abstracción base
# ------------------------------------------------------------------


class BaseScanner(ABC):
    """Interfaz abstracta de escáner."""

    @abstractmethod
    def list_sources(self) -> list[str]:
        """Lista los dispositivos/fuentes disponibles."""

    @abstractmethod
    def acquire(
        self, source: str, config: ScanConfig,
    ) -> list[np.ndarray]:
        """Adquiere una o más páginas del escáner."""

    @abstractmethod
    def close(self) -> None:
        """Libera recursos del backend."""

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Nombre del backend ("sane", "twain", "wia")."""

    def get_device_options(self, source: str) -> list[DeviceOption]:
        """Consulta las opciones disponibles del dispositivo.

        Solo implementado en SANE. TWAIN/WIA usan diálogo nativo.
        """
        return []

    @property
    def supports_native_ui(self) -> bool:
        """Indica si el backend tiene diálogo nativo de configuración."""
        return False


# ------------------------------------------------------------------
# Backend SANE (Linux)
# ------------------------------------------------------------------

# Mapeo de constantes de tipo SANE a strings legibles
_SANE_TYPE_MAP: dict[int, str] = {}
_SANE_UNIT_MAP: dict[int, str] = {}


def _init_sane_maps() -> None:
    """Inicializa los mapas de tipos/unidades SANE bajo demanda."""
    if _SANE_TYPE_MAP:
        return
    import _sane
    _SANE_TYPE_MAP.update({
        _sane.TYPE_BOOL: "bool",
        _sane.TYPE_INT: "int",
        _sane.TYPE_FIXED: "fixed",
        _sane.TYPE_STRING: "string",
        _sane.TYPE_BUTTON: "button",
    })
    _SANE_UNIT_MAP.update({
        _sane.UNIT_NONE: "none",
        _sane.UNIT_PIXEL: "pixel",
        _sane.UNIT_BIT: "bit",
        _sane.UNIT_MM: "mm",
        _sane.UNIT_DPI: "dpi",
        _sane.UNIT_PERCENT: "percent",
        _sane.UNIT_MICROSECOND: "microsecond",
    })


class SaneScanner(BaseScanner):
    """Escáner via SANE (Linux/macOS)."""

    def __init__(self) -> None:
        self._initialized = False
        self._init_thread_id: int | None = None
        self._cached_options: dict[str, list[DeviceOption]] = {}

    def _ensure_init(self) -> None:
        import threading
        current = threading.current_thread().ident
        if self._initialized and self._init_thread_id == current:
            return
        # Reinicializar si cambiamos de hilo (SANE no es thread-safe)
        if self._initialized:
            import sane
            sane.exit()
            self._initialized = False
        import sane
        sane.init()
        self._initialized = True
        self._init_thread_id = current

    @property
    def backend_name(self) -> str:
        return "sane"

    def list_sources(self) -> list[str]:
        self._ensure_init()
        import sane
        devices = sane.get_devices()
        return [dev[0] for dev in devices]

    def get_device_options(self, source: str) -> list[DeviceOption]:
        """Consulta las opciones reales del dispositivo SANE.

        Cachea el resultado para evitar reabrir el dispositivo USB
        antes de la adquisición.
        """
        if source in self._cached_options:
            return self._cached_options[source]

        self._ensure_init()
        _init_sane_maps()
        import sane

        dev = sane.open(source)
        try:
            options: list[DeviceOption] = []
            for py_name, opt in dev.opt.items():
                if not opt.is_active() or not opt.is_settable():
                    continue

                type_str = _SANE_TYPE_MAP.get(opt.type, "unknown")
                if type_str in ("button", "unknown"):
                    continue

                unit_str = _SANE_UNIT_MAP.get(opt.unit, "none")

                # Leer valor actual
                try:
                    value = getattr(dev, py_name)
                except Exception:
                    value = None

                options.append(DeviceOption(
                    name=py_name,
                    title=opt.title or py_name,
                    description=opt.desc or "",
                    type=type_str,
                    unit=unit_str,
                    constraint=opt.constraint,
                    value=value,
                    is_active=opt.is_active(),
                    is_settable=opt.is_settable(),
                ))
            self._cached_options[source] = options
            return options
        finally:
            dev.close()

    def acquire(
        self, source: str, config: ScanConfig,
    ) -> list[np.ndarray]:
        """Adquiere páginas usando scanimage (subprocess).

        SANE no es thread-safe, así que delegamos la captura al CLI
        ``scanimage`` que se ejecuta en su propio proceso.
        """
        import subprocess
        import tempfile
        import cv2

        # Construir opciones desde extra_options (diálogo) o config
        resolution = config.extra_options.get("resolution", config.resolution)
        mode = config.extra_options.get("mode", config.mode)
        sane_source = config.extra_options.get("source", "")

        # Si no hay source explícito, inferir de source_type
        if not sane_source and config.source_type == "adf":
            sane_source = "ADF Front"

        log.info(
            "Escaneando con scanimage: device='%s', resolution=%s, mode=%s, source='%s'",
            source, resolution, mode, sane_source,
        )

        images: list[np.ndarray] = []
        page_index = 0

        while True:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name

            cmd = [
                "scanimage",
                "-d", source,
                "--resolution", str(resolution),
                "--mode", mode,
                "--format=png",
                "-o", tmp_path,
            ]
            if sane_source:
                cmd.extend(["--source", sane_source])

            # Opciones numéricas extra
            for opt_name in ("brightness", "contrast", "threshold", "swdespeck"):
                val = config.extra_options.get(opt_name)
                if val is None:
                    val = getattr(config, opt_name, None)
                if val is not None and val != 0:
                    cmd.extend([f"--{opt_name.replace('_', '-')}", str(val)])

            # Opciones booleanas extra
            for opt_name in ("swdeskew", "swcrop", "rollerdeskew",
                             "df_thickness", "df_length", "stapledetect"):
                if config.extra_options.get(opt_name):
                    cmd.extend([f"--{opt_name.replace('_', '-')}=yes"])

            # Dropout color
            for opt_name in ("dropout_front", "dropout_back"):
                val = config.extra_options.get(opt_name)
                if val and val != "None":
                    cmd.extend([f"--{opt_name.replace('_', '-')}", val])

            log.debug("Ejecutando: %s", " ".join(cmd))

            result = subprocess.run(
                cmd, capture_output=True, timeout=120,
            )

            if result.returncode != 0:
                stderr = result.stderr.decode(errors="replace").strip()
                if "out of documents" in stderr.lower() and images:
                    log.info("ADF agotado tras %d páginas", len(images))
                    break
                if images:
                    log.info("ADF finalizado tras %d páginas: %s", len(images), stderr)
                    break
                raise RuntimeError(
                    f"Error de escaneo: {stderr or 'código ' + str(result.returncode)}"
                )

            # Leer imagen capturada
            from pathlib import Path
            tmp_file = Path(tmp_path)
            if tmp_file.exists() and tmp_file.stat().st_size > 0:
                image = cv2.imread(tmp_path, cv2.IMREAD_COLOR)
                if image is not None:
                    images.append(image)
                    log.debug("Página %d capturada OK (%s)", page_index, image.shape)
                    page_index += 1
                tmp_file.unlink(missing_ok=True)
            else:
                tmp_file.unlink(missing_ok=True)
                if images:
                    break
                raise RuntimeError("scanimage no generó imagen de salida")

            # En modo flatbed, solo una página
            if config.source_type != "adf" and "adf" not in sane_source.lower():
                break

        log.info("Captura completada: %d páginas", len(images))
        return images

    def close(self) -> None:
        if self._initialized:
            import sane
            sane.exit()
            self._initialized = False

    def _apply_config(self, dev: Any, config: ScanConfig) -> None:
        """Aplica la configuración al dispositivo SANE."""
        # Primero aplicar opciones extra (dinámicas del diálogo)
        for opt_name, opt_value in config.extra_options.items():
            # Saltar valores vacíos o None que pueden crashear el driver
            if opt_value is None or opt_value == "":
                continue
            try:
                setattr(dev, opt_name, opt_value)
            except Exception as e:
                log.debug("No se pudo establecer %s=%r: %s", opt_name, opt_value, e)

        # Seleccionar fuente ADF si corresponde
        if config.source_type == "adf":
            # Si ya se estableció 'source' via extra_options, no sobreescribir
            if "source" not in config.extra_options:
                for source_name in ("ADF", "ADF Front", "Automatic Document Feeder", "adf"):
                    try:
                        dev.source = source_name
                        break
                    except Exception:
                        continue

        # Solo aplicar si no vienen en extra_options (el diálogo tiene prioridad)
        if "resolution" not in config.extra_options:
            try:
                dev.resolution = config.resolution
            except Exception:
                log.debug("No se pudo establecer resolución %d", config.resolution)

        if "mode" not in config.extra_options:
            mode_map = {"Color": "Color", "Gray": "Gray", "Lineart": "Lineart"}
            sane_mode = mode_map.get(config.mode, "Color")
            try:
                dev.mode = sane_mode
            except Exception:
                log.debug("No se pudo establecer modo '%s'", sane_mode)

        if config.brightness is not None and "brightness" not in config.extra_options:
            try:
                dev.brightness = config.brightness
            except Exception:
                pass

        if config.contrast is not None and "contrast" not in config.extra_options:
            try:
                dev.contrast = config.contrast
            except Exception:
                pass


# ------------------------------------------------------------------
# Backend TWAIN (Windows)
# ------------------------------------------------------------------


class TwainScanner(BaseScanner):
    """Escáner via TWAIN (Windows).

    Requiere pytwain y TWAIN DSM 64-bit si Python es 64-bit.
    Guarda las capabilities del driver entre escaneos y las restaura
    en la siguiente sesión para conservar la configuración del usuario.
    """

    def __init__(self) -> None:
        self._sm = None
        self._src = None
        self._hwnd: int = 0
        self._current_source: str = ""
        self._saved_caps: dict[int, tuple] | None = None

    @property
    def backend_name(self) -> str:
        return "twain"

    @property
    def supports_native_ui(self) -> bool:
        return True

    def list_sources(self) -> list[str]:
        try:
            import twain
            sm = twain.SourceManager(0)
            sources = sm.source_list
            sm.close()
            return list(sources)
        except Exception as e:
            log.error("Error listando fuentes TWAIN: %s", e)
            return []

    def _close_session(self) -> None:
        """Cierra source, SourceManager y HWND."""
        if self._src is not None:
            try:
                self._src.close()
            except Exception:
                pass
            self._src = None
        if self._sm is not None:
            try:
                self._sm.close()
            except Exception:
                pass
            self._sm = None
        if self._hwnd:
            import ctypes
            ctypes.windll.user32.DestroyWindow(self._hwnd)
            self._hwnd = 0

    @staticmethod
    def _cap_type_map() -> dict[int, int]:
        """Mapa de capability -> tipo TWAIN (construido una sola vez)."""
        import twain
        return {
            twain.ICAP_XRESOLUTION: twain.TWTY_FIX32,
            twain.ICAP_YRESOLUTION: twain.TWTY_FIX32,
            twain.ICAP_PIXELTYPE: twain.TWTY_UINT16,
            twain.ICAP_BITDEPTH: twain.TWTY_UINT16,
            twain.ICAP_BRIGHTNESS: twain.TWTY_FIX32,
            twain.ICAP_CONTRAST: twain.TWTY_FIX32,
            twain.ICAP_THRESHOLD: twain.TWTY_FIX32,
            twain.ICAP_UNITS: twain.TWTY_UINT16,
            twain.CAP_DUPLEXENABLED: twain.TWTY_BOOL,
            twain.CAP_FEEDERENABLED: twain.TWTY_BOOL,
            twain.CAP_XFERCOUNT: twain.TWTY_INT16,
        }

    def _save_driver_caps(self, src) -> None:
        """Guarda las capabilities actuales del driver tras el escaneo."""
        saved = {}
        for cap in self._cap_type_map():
            try:
                saved[cap] = src.get_capability_current(cap)
            except Exception:
                pass
        if saved:
            self._saved_caps = saved

    def _restore_driver_caps(self, src) -> None:
        """Restaura las capabilities guardadas en el source."""
        if not self._saved_caps:
            return
        cap_types = self._cap_type_map()
        for cap, val in self._saved_caps.items():
            try:
                src.set_capability(cap, cap_types[cap], val)
            except Exception:
                pass

    _wnd_proc_ref = None
    _class_registered = False

    @staticmethod
    def _create_hwnd() -> int:
        """Crea una ventana oculta para el message loop de TWAIN."""
        import ctypes
        from ctypes import wintypes

        _user32 = ctypes.windll.user32
        _kernel32 = ctypes.windll.kernel32
        hinstance = _kernel32.GetModuleHandleW(None)

        if not TwainScanner._class_registered:
            LRESULT = ctypes.c_longlong
            _WNDPROC = ctypes.WINFUNCTYPE(
                LRESULT, wintypes.HWND, wintypes.UINT,
                wintypes.WPARAM, wintypes.LPARAM,
            )

            _user32.DefWindowProcW.argtypes = [
                wintypes.HWND, wintypes.UINT,
                wintypes.WPARAM, wintypes.LPARAM,
            ]
            _user32.DefWindowProcW.restype = LRESULT

            def _wnd_proc(hwnd, msg, wparam, lparam):
                return _user32.DefWindowProcW(hwnd, msg, wparam, lparam)

            TwainScanner._wnd_proc_ref = _WNDPROC(_wnd_proc)

            class WNDCLASSW(ctypes.Structure):
                _fields_ = [
                    ("style", ctypes.c_uint),
                    ("lpfnWndProc", _WNDPROC),
                    ("cbClsExtra", ctypes.c_int),
                    ("cbWndExtra", ctypes.c_int),
                    ("hInstance", wintypes.HINSTANCE),
                    ("hIcon", wintypes.HICON),
                    ("hCursor", wintypes.HANDLE),
                    ("hbrBackground", wintypes.HBRUSH),
                    ("lpszMenuName", wintypes.LPCWSTR),
                    ("lpszClassName", wintypes.LPCWSTR),
                ]

            wc = WNDCLASSW()
            wc.lpfnWndProc = TwainScanner._wnd_proc_ref
            wc.lpszClassName = "DocScanTwainHidden"
            wc.hInstance = hinstance
            _user32.RegisterClassW(ctypes.byref(wc))
            TwainScanner._class_registered = True

        hwnd = _user32.CreateWindowExW(
            0, "DocScanTwainHidden", "DocScan TWAIN",
            0, 0, 0, 0, 0, 0, 0, hinstance, 0,
        )
        return hwnd

    def acquire(
        self, source: str, config: ScanConfig,
    ) -> list[np.ndarray]:
        import twain
        import cv2
        import tempfile
        import os
        from PIL import Image

        images: list[np.ndarray] = []

        # HWND nuevo cada vez para evitar mensajes residuales
        self._close_session()
        hwnd = self._create_hwnd()
        self._hwnd = hwnd

        sm = twain.SourceManager(hwnd)
        self._sm = sm
        src = sm.open_source(source)
        self._src = src

        show_ui = bool(config.show_ui)

        if self._saved_caps and show_ui:
            # Con UI: restaurar la config que el usuario eligió la última vez
            self._restore_driver_caps(src)
        else:
            # Sin UI o primer escaneo: usar config de la app
            src.set_capability(
                twain.ICAP_XRESOLUTION, twain.TWTY_FIX32, config.resolution,
            )
            src.set_capability(
                twain.ICAP_YRESOLUTION, twain.TWTY_FIX32, config.resolution,
            )
            pixel_type_map = {"Lineart": 0, "Gray": 1, "Color": 2}
            pixel_type = pixel_type_map.get(config.mode, 2)
            src.set_capability(
                twain.ICAP_PIXELTYPE, twain.TWTY_UINT16, pixel_type,
            )

        # ADF: escanear todas las páginas disponibles (-1 = sin límite)
        try:
            src.set_capability(
                twain.CAP_XFERCOUNT, twain.TWTY_INT16, -1,
            )
        except Exception:
            pass

        caps_saved = False

        def _on_image(img_obj, more: int) -> None:
            """Callback por cada página adquirida."""
            nonlocal caps_saved
            # Guardar caps en la primera página (source activo en state 6/7)
            if not caps_saved:
                self._save_driver_caps(src)
                caps_saved = True
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(
                    suffix=".bmp", delete=False,
                ) as f:
                    tmp_path = f.name
                img_obj.save(tmp_path)
                pil_img = Image.open(tmp_path)
                arr = np.array(pil_img)
                if arr.dtype == bool:
                    arr = arr.astype(np.uint8) * 255
                if arr.ndim == 3:
                    arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
                images.append(arr)
            finally:
                img_obj.close()
                if tmp_path:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

        try:
            src.acquire_natively(
                after=_on_image,
                show_ui=show_ui,
                modal=show_ui,
            )
        finally:
            self._close_session()

        return images

    def close(self) -> None:
        """Cierra la sesión TWAIN y libera recursos."""
        self._close_session()


# ------------------------------------------------------------------
# Backend WIA (Windows)
# ------------------------------------------------------------------


class WiaScanner(BaseScanner):
    """Escáner via WIA (Windows Image Acquisition).

    Alternativa a TWAIN sin problemas de drivers 32/64-bit.
    Requiere pywin32.
    """

    @property
    def backend_name(self) -> str:
        return "wia"

    @property
    def supports_native_ui(self) -> bool:
        return True

    def list_sources(self) -> list[str]:
        try:
            import win32com.client
            wia = win32com.client.Dispatch("WIA.DeviceManager")
            sources = []
            for i in range(1, wia.DeviceInfos.Count + 1):
                info = wia.DeviceInfos.Item(i)
                sources.append(info.Properties("Name").Value)
            return sources
        except Exception as e:
            log.error("Error listando fuentes WIA: %s", e)
            return []

    def acquire(
        self, source: str, config: ScanConfig,
    ) -> list[np.ndarray]:
        import win32com.client
        from PIL import Image
        import io

        # Si show_ui, usar CommonDialog con interfaz nativa
        if config.show_ui:
            return self._acquire_with_dialog()

        wia = win32com.client.Dispatch("WIA.DeviceManager")
        device = None

        for i in range(1, wia.DeviceInfos.Count + 1):
            info = wia.DeviceInfos.Item(i)
            if info.Properties("Name").Value == source:
                device = info.Connect()
                break

        if device is None:
            raise RuntimeError(f"Dispositivo WIA no encontrado: '{source}'")

        item = device.Items(1)

        # Configurar propiedades
        self._set_property(item, 6146, config.resolution)  # DPI horizontal
        self._set_property(item, 6147, config.resolution)  # DPI vertical

        # Modo color: 1=Color, 2=Grayscale, 4=B&W
        mode_map = {"Color": 1, "Gray": 2, "Lineart": 4}
        self._set_property(
            item, 4103, mode_map.get(config.mode, 1),
        )

        transfer = item.Transfer("{B96B3CAE-0728-11D3-9D7B-0000F81EF32E}")  # BMP
        img_data = transfer.FileData.BinaryData
        pil_img = Image.open(io.BytesIO(bytes(img_data)))
        image = np.array(pil_img)

        if len(image.shape) == 3:
            import cv2
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

        return [image]

    def _acquire_with_dialog(self) -> list[np.ndarray]:
        """Adquiere usando el diálogo nativo WIA."""
        import win32com.client
        from PIL import Image
        import io

        dlg = win32com.client.Dispatch("WIA.CommonDialog")
        # ScannerDeviceType=1, ColorIntent=1 (Color)
        wia_image = dlg.ShowAcquireImage(1, 1, 0,
            "{B96B3CAE-0728-11D3-9D7B-0000F81EF32E}",  # BMP
            False, True, False,
        )
        if wia_image is None:
            return []  # Usuario canceló

        img_data = wia_image.FileData.BinaryData
        pil_img = Image.open(io.BytesIO(bytes(img_data)))
        image = np.array(pil_img)

        if len(image.shape) == 3:
            import cv2
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

        return [image]

    def close(self) -> None:
        pass

    def _set_property(self, item: Any, prop_id: int, value: Any) -> None:
        try:
            for prop in item.Properties:
                if prop.PropertyID == prop_id:
                    prop.Value = value
                    return
        except Exception:
            pass


# ------------------------------------------------------------------
# Factoría de escáneres
# ------------------------------------------------------------------

_SYSTEM = platform.system()


_cached_backends: list[str] | None = None


def get_available_backends() -> list[str]:
    """Devuelve los backends disponibles para la plataforma actual."""
    global _cached_backends
    if _cached_backends is not None:
        return _cached_backends
    backends: list[str] = []
    if _SYSTEM == "Linux" or _SYSTEM == "Darwin":
        try:
            import sane
            backends.append("sane")
        except ImportError:
            pass
    elif _SYSTEM == "Windows":
        try:
            import twain
            backends.append("twain")
        except ImportError:
            pass
        try:
            import win32com.client
            backends.append("wia")
        except ImportError:
            pass
    _cached_backends = backends
    return backends


def create_scanner(backend: str | None = None) -> BaseScanner:
    """Crea una instancia del escáner según el backend solicitado.

    Args:
        backend: "sane", "twain" o "wia". Si es None, elige
                 el mejor disponible para la plataforma.

    Returns:
        Instancia de BaseScanner.

    Raises:
        RuntimeError: Si no hay backends disponibles.
    """
    available = get_available_backends()

    if backend and backend in available:
        return _instantiate(backend)

    # Auto-selección por plataforma
    if backend and backend not in available:
        log.warning(
            "Backend '%s' no disponible, usando alternativa", backend,
        )

    if not available:
        raise RuntimeError(
            f"No hay backends de escáner disponibles en {_SYSTEM}. "
            f"Instala python-sane (Linux) o pytwain/pywin32 (Windows)."
        )

    return _instantiate(available[0])


def _instantiate(backend: str) -> BaseScanner:
    match backend:
        case "sane":
            return SaneScanner()
        case "twain":
            return TwainScanner()
        case "wia":
            return WiaScanner()
        case _:
            raise ValueError(f"Backend desconocido: '{backend}'")
