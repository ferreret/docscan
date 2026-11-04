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
import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

log = logging.getLogger(__name__)

#: Recibe cada página en cuanto el escáner la termina (en el hilo del escaneo).
PageCallback = Callable[[np.ndarray], None]
#: Devuelve True cuando el usuario ha pedido cancelar el escaneo.
StopCheck = Callable[[], bool]


# ------------------------------------------------------------------
# Configuración de escaneo
# ------------------------------------------------------------------


# Tamaños de página en mm (ancho, alto). Los escáneres de alimentador
# (canon_dr, fujitsu...) no detectan el final de la hoja: escanean el alto
# configurado, que por defecto es Carta (279 mm) y corta las A4.
PAGE_SIZES_MM: dict[str, tuple[float, float]] = {
    "A4": (210.0, 297.0),
    "A5": (148.0, 210.0),
    "Letter": (215.9, 279.4),
    "Legal": (215.9, 355.6),
}


class ScannerGoneError(RuntimeError):
    """El escáner USB elegido ya no está conectado en esa dirección.

    SANE nombra los escáneres USB por su dirección en el bus
    (``canon_dr:libusb:003:010``) y esa dirección cambia al desconectar y
    reconectar el escáner. Se lanza cuando la dirección guardada ya no
    responde y no se ha podido localizar el escáner en otra.

    Attributes:
        source: Nombre guardado que ha dejado de valer.
        sources: Dispositivos encontrados al volver a buscar, o ``None``
            si todavía no se ha buscado.
    """

    def __init__(
        self, source: str, sources: list[str] | None = None, detail: str = ""
    ) -> None:
        super().__init__(
            f"El escáner {source} ya no está conectado en esa dirección; elígelo en ⚙"
        )
        self.source = source
        self.sources = sources
        self.detail = detail


class ScanIncompleteError(RuntimeError):
    """El escáner falló después de entregar algunas páginas.

    Un atasco o una doble alimentación a mitad de lote no es el final
    normal del alimentador: se conservan las páginas ya capturadas en
    ``images`` y el error debe llegar al usuario.
    """

    def __init__(self, message: str, images: list[np.ndarray]) -> None:
        super().__init__(message)
        self.images = images


@dataclass
class ScanConfig:
    """Parámetros de captura."""

    resolution: int = 300  # DPI
    mode: str = "Color"  # "Color", "Gray", "Lineart"
    duplex: bool = False
    page_size: str = "A4"  # clave de PAGE_SIZES_MM; "" = el del escáner
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
        self,
        source: str,
        config: ScanConfig,
        on_page: PageCallback | None = None,
        should_stop: StopCheck | None = None,
    ) -> list[np.ndarray]:
        """Adquiere una o más páginas del escáner.

        Args:
            source: Dispositivo.
            config: Parámetros de captura.
            on_page: Si el backend lo admite, recibe cada página en cuanto
                está completa, sin esperar al final del lote (FlexibarNET10:
                cada página se entrega y se guarda en cuanto llega).
            should_stop: Si el backend lo admite, se consulta durante la
                captura; al devolver True se para el escáner y se devuelven
                las páginas ya completas, sin error.

        Returns:
            **Todas** las páginas capturadas, también las ya entregadas por
            ``on_page``: quien llama descarta las que ya recibió. Un backend
            que no admite ``on_page`` las devuelve solo aquí.
        """

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

    def source_missing(self, source: str) -> bool:
        """True si se sabe, sin abrirlo, que ``source`` ya no está conectado.

        Es una comprobación inmediata; solo SANE la implementa.
        """
        return False

    def resolve_source(self, source: str, force: bool = False) -> str:
        """Devuelve el nombre con el que hay que abrir ``source`` ahora.

        Solo SANE relocaliza (los escáneres USB cambian de nombre al
        reconectarlos); el resto de backends devuelve ``source`` tal cual.
        """
        return source


def migrate_device_options(
    options_by_device: dict[str, dict[str, Any]], old: str, new: str
) -> dict[str, dict[str, Any]]:
    """Pasa las opciones guardadas de ``old`` a ``new`` (el escáner reconectado).

    Las de ``old`` son las que el operador estaba usando, así que mandan
    sobre unas antiguas que pudiera haber con el nombre nuevo.

    Returns:
        Un diccionario nuevo; el original no se toca.
    """
    migrated = dict(options_by_device)
    if old != new and old in migrated:
        migrated[new] = migrated.pop(old)
    return migrated


# ------------------------------------------------------------------
# Backend SANE (Linux)
# ------------------------------------------------------------------

#: Nodos de los dispositivos USB en Linux (``/dev/bus/usb/BBB/DDD``).
USB_DEVICE_ROOT = Path("/dev/bus/usb")

# «canon_dr:libusb:003:010» → prefijo «canon_dr:libusb:», bus 003, dispositivo 010
_USB_NAME_RE = re.compile(r"^(?P<prefix>[\w.-]+:libusb:)(?P<bus>\d{3}):(?P<dev>\d{3})$")


def usb_name_prefix(source: str) -> str | None:
    """Prefijo de backend (``canon_dr:libusb:``) de un nombre SANE USB, o None."""
    m = _USB_NAME_RE.match(source)
    return m.group("prefix") if m else None


def usb_address_missing(source: str) -> bool:
    """True si ``source`` es ``<backend>:libusb:BBB:DDD`` y ese nodo USB no existe.

    Sin ``/dev/bus/usb`` (otro sistema, contenedor…) no se puede saber y
    se devuelve False: decidirá la apertura del dispositivo.
    """
    m = _USB_NAME_RE.match(source)
    if m is None or not USB_DEVICE_ROOT.is_dir():
        return False
    return not (USB_DEVICE_ROOT / m.group("bus") / m.group("dev")).exists()


def _is_stale_usb_error(source: str, detail: str) -> bool:
    """¿El fallo es el de abrir una dirección USB que ya no es la del escáner?"""
    return usb_name_prefix(source) is not None and "Invalid argument" in detail


# Mapeo de constantes de tipo SANE a strings legibles
_SANE_TYPE_MAP: dict[int, str] = {}
_SANE_UNIT_MAP: dict[int, str] = {}


def _init_sane_maps() -> None:
    """Inicializa los mapas de tipos/unidades SANE bajo demanda."""
    if _SANE_TYPE_MAP:
        return
    import _sane

    _SANE_TYPE_MAP.update(
        {
            _sane.TYPE_BOOL: "bool",
            _sane.TYPE_INT: "int",
            _sane.TYPE_FIXED: "fixed",
            _sane.TYPE_STRING: "string",
            _sane.TYPE_BUTTON: "button",
        }
    )
    _SANE_UNIT_MAP.update(
        {
            _sane.UNIT_NONE: "none",
            _sane.UNIT_PIXEL: "pixel",
            _sane.UNIT_BIT: "bit",
            _sane.UNIT_MM: "mm",
            _sane.UNIT_DPI: "dpi",
            _sane.UNIT_PERCENT: "percent",
            _sane.UNIT_MICROSECOND: "microsecond",
        }
    )


def _is_feeder(sane_source: str) -> bool:
    """True si la fuente SANE es un alimentador.

    Cada backend las nombra a su manera: «ADF Front», «ADF Duplex»,
    «Automatic Document Feeder», «Duplex»...
    """
    name = sane_source.lower()
    return any(word in name for word in ("adf", "feeder", "duplex"))


def _scanimage_error(stderr: str) -> str:
    """Extrae los errores del stderr de scanimage.

    En modo ``--batch`` scanimage mezcla el progreso («Scanning page 3»)
    y avisos de redondeo con el error real; solo interesa este último.
    """
    lines = [
        line.removeprefix("scanimage: ").strip()
        for line in stderr.splitlines()
        if line.startswith("scanimage:") and "rounded value" not in line
    ]
    return "; ".join(lines)


class SaneScanner(BaseScanner):
    """Escáner via SANE (Linux/macOS)."""

    # Segundos sin que avance la captura antes de dar el escáner por colgado
    IDLE_TIMEOUT = 120

    def __init__(self) -> None:
        self._initialized = False
        self._init_thread_id: int | None = None
        self._cached_options: dict[str, list[DeviceOption]] = {}
        self._cli_limits: dict[str, dict[str, float | None]] = {}

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

    def source_missing(self, source: str) -> bool:
        """True si ``source`` es un USB de SANE cuyo nodo ya no existe."""
        return usb_address_missing(source)

    def resolve_source(self, source: str, force: bool = False) -> str:
        """Vuelve a localizar un escáner USB que ha cambiado de dirección.

        Al reconectar un escáner USB, SANE le da otro número de dispositivo
        (``canon_dr:libusb:003:010`` pasa a ``…:003:011``). Si la dirección
        guardada ya no existe (o ``force``, porque abrirla ha fallado), se
        vuelve a listar los dispositivos y, si hay **exactamente uno** con el
        mismo backend, se usa ese. Listar puede tardar unos segundos: no
        llamar desde el hilo de la UI.

        Args:
            source: Nombre guardado.
            force: Buscar aunque el nodo USB exista.

        Returns:
            ``source`` si sigue valiendo, o el nombre nuevo.

        Raises:
            ScannerGoneError: No hay ningún escáner de ese backend, o hay
                varios y no se puede saber cuál era.
        """
        prefix = usb_name_prefix(source)
        if prefix is None or not (force or usb_address_missing(source)):
            return source
        # SANE de nuevo desde cero: algunos backends solo vuelven a recorrer
        # el bus USB en sane_init.
        self.close()
        sources = self.list_sources()
        if source in sources:
            return source
        candidates = [s for s in sources if s.startswith(prefix)]
        if len(candidates) != 1:
            log.warning(
                "El escáner %s ya no está en esa dirección y hay %d candidatos: %s",
                source,
                len(candidates),
                candidates,
            )
            raise ScannerGoneError(source, sources)
        new = candidates[0]
        log.info("Escáner reconectado: %s ahora es %s", source, new)
        # Lo cacheado con el nombre viejo puede ser un fallo de abrirlo.
        self._cached_options.pop(source, None)
        self._cli_limits.pop(source, None)
        return new

    def get_device_options(self, source: str) -> list[DeviceOption]:
        """Consulta las opciones reales del dispositivo SANE.

        Cachea el resultado para evitar reabrir el dispositivo USB
        antes de la adquisición.

        Raises:
            ScannerGoneError: La dirección USB ya no es la del escáner.
        """
        if source in self._cached_options:
            return self._cached_options[source]

        self._ensure_init()
        _init_sane_maps()
        import sane

        try:
            dev = sane.open(source)
        except Exception as e:
            if _is_stale_usb_error(source, str(e)):
                raise ScannerGoneError(source, detail=str(e)) from e
            raise
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

                options.append(
                    DeviceOption(
                        name=py_name,
                        title=opt.title or py_name,
                        description=opt.desc or "",
                        type=type_str,
                        unit=unit_str,
                        constraint=opt.constraint,
                        value=value,
                        is_active=opt.is_active(),
                        is_settable=opt.is_settable(),
                    )
                )
            self._cached_options[source] = options
            return options
        finally:
            dev.close()

    def acquire(
        self,
        source: str,
        config: ScanConfig,
        on_page: PageCallback | None = None,
        should_stop: StopCheck | None = None,
    ) -> list[np.ndarray]:
        """Adquiere páginas usando scanimage (subprocess).

        Con alimentador, cada página se entrega a ``on_page`` en cuanto
        ``scanimage`` la termina (la renombra de ``.part`` a ``.png``), y
        ``should_stop`` para el escaneo conservando las páginas completas.

        SANE no es thread-safe, así que delegamos la captura al CLI
        ``scanimage`` que se ejecuta en su propio proceso. Con alimentador
        se lanza **un solo** ``scanimage --batch`` para todo el lote: un
        proceso por página reabre el dispositivo cada vez y pierde el
        reverso en dúplex.

        Raises:
            RuntimeError: El escáner falla sin entregar ninguna página.
            ScanIncompleteError: Falla a mitad de lote (atasco, doble
                alimentación...); lleva las páginas ya capturadas.
            ScannerGoneError: No se puede abrir porque la dirección USB ya
                no es la del escáner (se ha desconectado y reconectado).
        """
        import tempfile

        # La fuente elegida en el diálogo manda sobre Flatbed/ADF del panel ⚙
        sane_source = config.extra_options.get("source", "")
        if sane_source:
            use_adf = _is_feeder(sane_source)
        else:
            use_adf = config.source_type == "adf"
            if use_adf:
                sane_source = "ADF Duplex" if config.duplex else "ADF Front"

        cmd = ["scanimage", "-d", source, *self._build_options(source, config)]
        if sane_source:
            cmd.extend(["--source", sane_source])

        with tempfile.TemporaryDirectory(prefix="docscan-scan-") as tmp:
            out_dir = Path(tmp)
            if use_adf:
                cmd.append(f"--batch={out_dir / 'p%05d.png'}")
            else:
                cmd.extend(["-o", str(out_dir / "p00001.png")])
            log.info("Escaneando: %s", " ".join(cmd))
            images: list[np.ndarray] = []
            read: set[str] = set()

            def collect() -> None:
                # scanimage escribe cada página en «.part» y la renombra al
                # terminarla: solo cuentan las completas.
                for path in sorted(out_dir.glob("p*.png")):
                    if path.name in read:
                        continue
                    read.add(path.name)
                    for image in self._read_images([path]):
                        images.append(image)
                        if on_page is not None:
                            on_page(image)

            # Con cristal se escribe directamente en el fichero final: leerlo
            # antes de que termine daría una imagen a medias.
            returncode, stderr, stopped = self._run_scanimage(
                cmd,
                out_dir,
                on_progress=collect if use_adf else None,
                should_stop=should_stop,
            )
            collect()

        if stopped:
            log.info("Escaneo cancelado tras %d páginas completas", len(images))
            return images
        if returncode != 0:
            detail = _scanimage_error(stderr) or f"código {returncode}"
            if images:
                log.error(
                    "Escaneo interrumpido tras %d páginas: %s", len(images), detail
                )
                raise ScanIncompleteError(
                    f"El escáner se detuvo tras {len(images)} página(s): {detail}",
                    images,
                )
            if "open of device" in detail and _is_stale_usb_error(source, detail):
                raise ScannerGoneError(source, detail=detail)
            raise RuntimeError(f"Error de escaneo: {detail}")
        if not images:
            raise RuntimeError("scanimage no generó imagen de salida")

        log.info("Captura completada: %d páginas", len(images))
        return images

    def _build_options(self, source: str, config: ScanConfig) -> list[str]:
        """Traduce ScanConfig y las opciones del diálogo a argumentos de scanimage."""
        extra = config.extra_options
        opts = [
            "--resolution",
            str(extra.get("resolution", config.resolution)),
            "--mode",
            str(extra.get("mode", config.mode)),
            "--format=png",
        ]
        opts.extend(
            self._geometry_options(source, extra.get("page_size", config.page_size))
        )

        # Opciones numéricas extra
        for opt_name in ("brightness", "contrast", "threshold", "swdespeck"):
            val = extra.get(opt_name)
            if val is None:
                val = getattr(config, opt_name, None)
            if val is not None and val != 0:
                opts.extend([f"--{opt_name.replace('_', '-')}", str(val)])

        # Opciones booleanas extra
        for opt_name in (
            "swdeskew",
            "swcrop",
            "rollerdeskew",
            "df_thickness",
            "df_length",
            "stapledetect",
        ):
            if extra.get(opt_name):
                opts.append(f"--{opt_name.replace('_', '-')}=yes")

        # Dropout color
        for opt_name in ("dropout_front", "dropout_back"):
            val = extra.get(opt_name)
            if val and val != "None":
                opts.extend([f"--{opt_name.replace('_', '-')}", val])
        return opts

    def _geometry_options(self, source: str, page_size: str) -> list[str]:
        """Argumentos de tamaño de página, recortados a lo que admite el dispositivo.

        Los escáneres de alimentador exponen ``--page-width/--page-height``
        (centrado y alto de la hoja) además del área ``-x/-y``; los planos
        solo el área. El máximo de ``-x/-y`` lo fija el tamaño de página, así
        que con ``--page-*`` disponible el área se iguala a la página.
        """
        size = PAGE_SIZES_MM.get(page_size)
        if size is None:
            return []
        limits = self._device_limits(source)
        opts: list[str] = []
        for (page_flag, area_flag), wanted in zip(
            (("--page-width", "-x"), ("--page-height", "-y")), size, strict=True
        ):
            if page_flag in limits:
                page_max = limits[page_flag]
                value = min(wanted, page_max) if page_max else wanted
                opts.extend([page_flag, f"{value:g}"])
            elif area_flag in limits:
                area_max = limits[area_flag]
                value = min(wanted, area_max) if area_max else wanted
            else:
                continue
            if area_flag in limits:
                opts.extend([area_flag, f"{value:g}"])
        return opts

    def _device_limits(self, source: str) -> dict[str, float | None]:
        """Máximos de geometría que declara el dispositivo (``scanimage -A``).

        Se consulta una vez por dispositivo y se cachea. Si la consulta
        falla se devuelve vacío y el escaneo sigue con el tamaño del escáner.
        """
        if source in self._cli_limits:
            return self._cli_limits[source]
        import subprocess

        limits: dict[str, float | None] = {}
        try:
            result = subprocess.run(
                ["scanimage", "-d", source, "-A"],
                capture_output=True,
                timeout=60,
            )
            text = result.stdout.decode(errors="replace")
        except (OSError, subprocess.TimeoutExpired) as e:
            log.warning("No se pudieron consultar las opciones de '%s': %s", source, e)
            text = ""
        for flag in ("--page-width", "--page-height", "-x", "-y"):
            m = re.search(rf"^\s+{re.escape(flag)} [-\d.]+\.\.([\d.]+)mm", text, re.M)
            if m:
                limits[flag] = float(m.group(1))
        self._cli_limits[source] = limits
        return limits

    def _run_scanimage(
        self,
        cmd: list[str],
        out_dir: Any,
        on_progress: Callable[[], None] | None = None,
        should_stop: StopCheck | None = None,
    ) -> tuple[int, str, bool]:
        """Ejecuta scanimage vigilando que la captura avance.

        Un lote de alimentador puede durar minutos, así que no hay un tiempo
        total: se aborta si pasan ``IDLE_TIMEOUT`` segundos sin que crezca
        ninguna imagen. stderr va a un fichero para no bloquear el proceso
        si el driver escribe mucho (p. ej. con ``SANE_DEBUG_*``).

        Args:
            cmd: Orden de scanimage.
            out_dir: Carpeta donde escribe las páginas.
            on_progress: Se llama cada vez que cambia la salida (para
                entregar las páginas ya completas).
            should_stop: Si devuelve True, se para scanimage.

        Returns:
            (código de salida, stderr, True si se paró por ``should_stop``).
        """
        import subprocess
        import tempfile
        import time

        with tempfile.TemporaryFile() as err:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=err)
            progress, last_change = -1, time.monotonic()
            while proc.poll() is None:
                time.sleep(0.5)
                if should_stop is not None and should_stop():
                    self._stop_scanimage(proc)
                    err.seek(0)
                    return proc.returncode, err.read().decode(errors="replace"), True
                if on_progress is not None:
                    try:
                        on_progress()
                    except BaseException:
                        self._stop_scanimage(proc)  # no dejarlo escaneando solo
                        raise
                current = self._output_size(out_dir)
                if current != progress:
                    progress, last_change = current, time.monotonic()
                elif time.monotonic() - last_change > self.IDLE_TIMEOUT:
                    proc.kill()
                    proc.wait()
                    err.seek(0)
                    stderr = err.read().decode(errors="replace")
                    return (
                        -1,
                        f"{stderr}\nscanimage: sin respuesta del escáner en "
                        f"{self.IDLE_TIMEOUT} s",
                        False,
                    )
            err.seek(0)
            return proc.returncode, err.read().decode(errors="replace"), False

    @staticmethod
    def _output_size(out_dir: Any) -> int:
        """Bytes escritos hasta ahora (tolera ficheros renombrados al vuelo)."""
        total = 0
        for f in out_dir.iterdir():
            try:
                total += f.stat().st_size
            except FileNotFoundError:
                pass  # scanimage acaba de renombrar «.part» a «.png»
        return total

    @staticmethod
    def _stop_scanimage(proc: Any) -> None:
        """Para scanimage dejándole cancelar la hoja en curso.

        Con SIGTERM scanimage llama a ``sane_cancel`` y el alimentador
        expulsa la hoja; si no responde en unos segundos, se mata.
        """
        import subprocess

        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    @staticmethod
    def _read_images(paths: list[Any]) -> list[np.ndarray]:
        """Carga las páginas capturadas en orden."""
        import cv2

        images: list[np.ndarray] = []
        for path in paths:
            image = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if image is None:
                log.error("Página ilegible descartada: %s", path.name)
                continue
            images.append(image)
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
                for source_name in (
                    "ADF",
                    "ADF Front",
                    "Automatic Document Feeder",
                    "adf",
                ):
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
                LRESULT,
                wintypes.HWND,
                wintypes.UINT,
                wintypes.WPARAM,
                wintypes.LPARAM,
            )

            _user32.DefWindowProcW.argtypes = [
                wintypes.HWND,
                wintypes.UINT,
                wintypes.WPARAM,
                wintypes.LPARAM,
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
            0,
            "DocScanTwainHidden",
            "DocScan TWAIN",
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            hinstance,
            0,
        )
        return hwnd

    def acquire(
        self,
        source: str,
        config: ScanConfig,
        on_page: PageCallback | None = None,
        should_stop: StopCheck | None = None,
    ) -> list[np.ndarray]:
        # Sin entrega por página ni cancelación (pendiente de probar en
        # Windows): las páginas llegan todas al final, como hasta ahora.
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
                twain.ICAP_XRESOLUTION,
                twain.TWTY_FIX32,
                config.resolution,
            )
            src.set_capability(
                twain.ICAP_YRESOLUTION,
                twain.TWTY_FIX32,
                config.resolution,
            )
            pixel_type_map = {"Lineart": 0, "Gray": 1, "Color": 2}
            pixel_type = pixel_type_map.get(config.mode, 2)
            src.set_capability(
                twain.ICAP_PIXELTYPE,
                twain.TWTY_UINT16,
                pixel_type,
            )

        # ADF: escanear todas las páginas disponibles (-1 = sin límite)
        try:
            src.set_capability(
                twain.CAP_XFERCOUNT,
                twain.TWTY_INT16,
                -1,
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
                    suffix=".bmp",
                    delete=False,
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
        self,
        source: str,
        config: ScanConfig,
        on_page: PageCallback | None = None,
        should_stop: StopCheck | None = None,
    ) -> list[np.ndarray]:
        # Sin entrega por página ni cancelación (pendiente de probar en
        # Windows): las páginas llegan todas al final, como hasta ahora.
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
            item,
            4103,
            mode_map.get(config.mode, 1),
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
        wia_image = dlg.ShowAcquireImage(
            1,
            1,
            0,
            "{B96B3CAE-0728-11D3-9D7B-0000F81EF32E}",  # BMP
            False,
            True,
            False,
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
            import sane  # noqa: F401  # sonda de disponibilidad del backend

            backends.append("sane")
        except ImportError:
            pass
    elif _SYSTEM == "Windows":
        try:
            import twain  # noqa: F401  # sonda de disponibilidad del backend

            backends.append("twain")
        except ImportError:
            pass
        try:
            import win32com.client  # noqa: F401  # sonda de disponibilidad del backend

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
            "Backend '%s' no disponible, usando alternativa",
            backend,
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
