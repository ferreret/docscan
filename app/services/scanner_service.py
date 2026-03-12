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
        """Adquiere una o más páginas del escáner.

        Args:
            source: Identificador del dispositivo.
            config: Parámetros de captura.

        Returns:
            Lista de imágenes (una por página escaneada).
        """

    @abstractmethod
    def close(self) -> None:
        """Libera recursos del backend."""

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Nombre del backend ("sane", "twain", "wia")."""


# ------------------------------------------------------------------
# Backend SANE (Linux)
# ------------------------------------------------------------------


class SaneScanner(BaseScanner):
    """Escáner via SANE (Linux/macOS)."""

    def __init__(self) -> None:
        self._initialized = False

    def _ensure_init(self) -> None:
        if not self._initialized:
            import sane
            sane.init()
            self._initialized = True

    @property
    def backend_name(self) -> str:
        return "sane"

    def list_sources(self) -> list[str]:
        self._ensure_init()
        import sane
        devices = sane.get_devices()
        return [dev[0] for dev in devices]

    def acquire(
        self, source: str, config: ScanConfig,
    ) -> list[np.ndarray]:
        self._ensure_init()
        import sane

        dev = sane.open(source)
        try:
            self._apply_config(dev, config)
            images: list[np.ndarray] = []

            while True:
                try:
                    pil_image = dev.snap()
                except Exception:
                    if images:
                        break  # ADF agotado, retornamos lo capturado
                    raise  # Error real si no hay ninguna imagen

                image = np.array(pil_image)
                if len(image.shape) == 3 and image.shape[2] == 3:
                    import cv2
                    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                images.append(image)

                # Solo capturar una página en modo flatbed
                if config.source_type != "adf":
                    break

            return images
        finally:
            dev.close()

    def close(self) -> None:
        if self._initialized:
            import sane
            sane.exit()
            self._initialized = False

    def _apply_config(self, dev: Any, config: ScanConfig) -> None:
        """Aplica la configuración al dispositivo SANE."""
        # Seleccionar fuente ADF si corresponde
        if config.source_type == "adf":
            for source_name in ("ADF", "Automatic Document Feeder", "adf"):
                try:
                    dev.source = source_name
                    break
                except Exception:
                    continue

        try:
            dev.resolution = config.resolution
        except Exception:
            log.debug("No se pudo establecer resolución %d", config.resolution)

        mode_map = {"Color": "Color", "Gray": "Gray", "Lineart": "Lineart"}
        sane_mode = mode_map.get(config.mode, "Color")
        try:
            dev.mode = sane_mode
        except Exception:
            log.debug("No se pudo establecer modo '%s'", sane_mode)

        if config.brightness is not None:
            try:
                dev.brightness = config.brightness
            except Exception:
                pass

        if config.contrast is not None:
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
    """

    @property
    def backend_name(self) -> str:
        return "twain"

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

    def acquire(
        self, source: str, config: ScanConfig,
    ) -> list[np.ndarray]:
        import twain

        sm = twain.SourceManager(0)
        src = sm.open_source(source)
        try:
            # Configurar resolución y modo
            src.set_capability(
                twain.CAP_XRESOLUTION, twain.TWTY_FIX32, config.resolution,
            )
            src.set_capability(
                twain.CAP_YRESOLUTION, twain.TWTY_FIX32, config.resolution,
            )

            pixel_type_map = {"Lineart": 0, "Gray": 1, "Color": 2}
            pixel_type = pixel_type_map.get(config.mode, 2)
            src.set_capability(
                twain.ICAP_PIXELTYPE, twain.TWTY_UINT16, pixel_type,
            )

            src.request_acquire(0, 0)
            info = src.get_image_info()

            # Transferir imagen
            handle = src.xfer_image_natively()
            if handle:
                import ctypes
                # Convertir DIB handle a numpy array
                # (implementación simplificada)
                bmp_data = twain.dib_to_bm_file(handle)
                twain.global_handle_free(handle)

                from PIL import Image
                import io
                pil_img = Image.open(io.BytesIO(bmp_data))
                image = np.array(pil_img)
                if len(image.shape) == 3:
                    import cv2
                    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                return [image]
            return []
        finally:
            src.close()
            sm.close()

    def close(self) -> None:
        pass


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

        # Modo color: 1=Color, 2=Grayscale, 4=B&W (WIA_IPS_CUR_INTENT = 6146 no, 4103)
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


def get_available_backends() -> list[str]:
    """Devuelve los backends disponibles para la plataforma actual."""
    if _SYSTEM == "Linux" or _SYSTEM == "Darwin":
        backends = []
        try:
            import sane
            backends.append("sane")
        except ImportError:
            pass
        return backends
    elif _SYSTEM == "Windows":
        backends = []
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
        return backends
    return []


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
