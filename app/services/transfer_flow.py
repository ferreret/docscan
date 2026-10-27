"""Flujo de transferencia compartido por el Workbench y el worker desatendido.

Antes, cada contexto montaba su propia secuencia (validación, transferencia
estándar, script avanzado) y se habían separado: el worker ignoraba
``standard_enabled``, exigía carpeta de destino aunque la App solo
transfiriera por script, no pasaba ``first_barcode`` y ejecutaba
``on_transfer_advanced`` después de marcar el lote como exportado. Es la
misma divergencia que FlexibarNET10 corrigió en su v1.27 (#460, #488):
aquí hay un único camino.

Reglas (paridad con FlexibarNET10 v1.20/v1.26/v1.27):

- Un campo de lote obligatorio vacío detiene la transferencia antes de
  exportar nada, nombrando los campos pendientes.
- ``on_transfer_validate`` falla cerrado: si lanza, la transferencia no se
  hace; si devuelve ``False``, tampoco.
- Primero la transferencia estándar (si está activada) y después
  ``on_transfer_advanced``, que recibe las páginas y el resultado.
- Si ``on_transfer_advanced`` lanza o devuelve ``False``, la transferencia
  falla y el lote no se marca como exportado.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import cv2

from app.models.document import LogicalDocument, split_documents
from app.pipeline.page_context import AppContext, BatchContext
from app.services.script_engine import EventOutcome
from app.services.transfer_service import (
    NameResolver,
    TransferAbortedError,
    TransferConfig,
    TransferResult,
    document_problems,
)

log = logging.getLogger(__name__)

VALIDATE_EVENT = "on_transfer_validate"
ADVANCED_EVENT = "on_transfer_advanced"
# Script de nombre de fichero (TransferConfig.file_name_script). Define
# ``file_name(page, document, batch, app)`` y devuelve la subruta sin
# extensión ("20261027/12345678"), o None para usar el patrón.
FILE_NAME_SCRIPT_ID = "file_name_script"
FILE_NAME_ENTRY_POINT = "file_name"


# ------------------------------------------------------------------
# Páginas
# ------------------------------------------------------------------


def transfer_page_dict(page: Any) -> dict[str, Any]:
    """Convierte una página de BD al dict que consume la transferencia.

    Args:
        page: Instancia ORM ``Page`` con sus barcodes cargables.

    Returns:
        Dict con image_path, page_index, fields, ocr_text y first_barcode.
    """
    try:
        fields = json.loads(page.index_fields_json or "{}")
    except json.JSONDecodeError, TypeError:
        fields = {}
    barcodes = list(page.barcodes or [])
    return {
        "image_path": page.image_path,
        "page_index": page.page_index,
        "fields": fields,
        "ocr_text": page.ocr_text or "",
        "first_barcode": barcodes[0].value if barcodes else "",
        "is_separator": bool(getattr(page, "is_separator", False)),
        "separator_value": getattr(page, "separator_value", "") or "",
        "barcodes": [{"value": b.value, "symbology": b.symbology} for b in barcodes],
    }


@dataclass
class TransferPage:
    """Página tal como la ve ``on_transfer_advanced``.

    La imagen se lee del disco solo si el script la pide: cargar todas las
    imágenes de un lote grande por adelantado multiplica la memoria sin que
    la mayoría de scripts lleguen a usarlas.
    """

    image_path: str
    page_index: int = 0
    fields: dict[str, Any] = field(default_factory=dict)
    ocr_text: str = ""
    first_barcode: str = ""
    is_separator: bool = False
    separator_value: str = ""
    barcodes: list[Any] = field(default_factory=list)
    _image: Any = field(default=None, repr=False)
    _image_loaded: bool = field(default=False, repr=False)

    @property
    def image(self) -> Any:
        """Imagen de la página (ndarray) leída bajo demanda, o None."""
        if not self._image_loaded:
            self._image = cv2.imread(self.image_path, cv2.IMREAD_UNCHANGED)
            self._image_loaded = True
            if self._image is None:
                log.warning("No se pudo cargar la imagen %s", self.image_path)
        return self._image

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TransferPage:
        """Construye la página a partir del dict de la transferencia."""
        return cls(
            image_path=data.get("image_path", ""),
            page_index=data.get("page_index", 0),
            fields=dict(data.get("fields") or {}),
            ocr_text=data.get("ocr_text", ""),
            first_barcode=data.get("first_barcode", ""),
            is_separator=bool(data.get("is_separator", False)),
            separator_value=data.get("separator_value", "") or "",
            barcodes=[
                SimpleNamespace(**b) if isinstance(b, dict) else b
                for b in data.get("barcodes") or []
            ],
        )


def script_documents(
    pages: list[dict[str, Any]],
) -> tuple[list[TransferPage], list[LogicalDocument]]:
    """Páginas y documentos del lote tal como los ven los scripts."""
    script_pages = [TransferPage.from_dict(p) for p in pages]
    return script_pages, split_documents(script_pages)


def compile_transfer_scripts(script_engine: Any, config: TransferConfig) -> None:
    """Compila el script de nombre de la App, si lo usa.

    Se compila al cargar la App, como los eventos: un script que no compila
    queda registrado y la transferencia falla con el motivo, en lugar de
    caer en silencio al patrón.
    """
    if script_engine is None:
        return
    if config.name_mode == "script" and config.file_name_script.strip():
        try:
            script_engine.compile_script(
                FILE_NAME_SCRIPT_ID,
                config.file_name_script,
                "Script de nombre de fichero",
            )
        except Exception as e:
            log.error("El script de nombre de fichero no compila: %s", e)


def build_name_resolver(
    script_engine: Any,
    config: TransferConfig,
    contexts: dict[str, Any] | None,
) -> NameResolver | None:
    """Prepara el script de nombre para ``TransferService.transfer``.

    Returns:
        None si la App usa patrón.

    Raises:
        TransferAbortedError: Si la App usa script pero no está compilado.
    """
    if config.name_mode != "script" or not config.file_name_script.strip():
        return None
    if script_engine is None or not script_engine.is_compiled(FILE_NAME_SCRIPT_ID):
        raise TransferAbortedError(
            "El script de nombre de fichero no está disponible (¿no compila?)"
        )
    # El script siempre recibe app y batch, aunque el llamador no los pase.
    contexts = {"app": AppContext(), "batch": BatchContext(), **(contexts or {})}

    # Un documento se convierte una sola vez aunque se pidan nombres para
    # todas sus páginas (modo carpeta): si no, un lote grande sin
    # separadores costaría O(n²).
    converted: dict[int, LogicalDocument] = {}

    def resolve(page: dict[str, Any], document: LogicalDocument | None) -> str | None:
        script_page = TransferPage.from_dict(page)
        script_document = None
        if document is not None and id(document) in converted:
            script_document = converted[id(document)]
        elif document is not None:
            script_document = converted[id(document)] = LogicalDocument(
                index=document.index,
                separator_page=(
                    TransferPage.from_dict(document.separator_page)
                    if document.separator_page is not None
                    else None
                ),
                pages=[TransferPage.from_dict(p) for p in document.pages],
            )
        outcome: EventOutcome = script_engine.run_event_checked(
            FILE_NAME_SCRIPT_ID,
            FILE_NAME_ENTRY_POINT,
            page=script_page,
            document=script_document,
            **contexts,
        )
        if outcome.failed:
            raise RuntimeError(outcome.error)
        value = outcome.value
        return value if isinstance(value, str) else None

    return resolve


# ------------------------------------------------------------------
# Validación previa
# ------------------------------------------------------------------


def missing_required_fields(
    fields_def: list[dict[str, Any]],
    batch_fields: dict[str, Any],
) -> list[str]:
    """Campos de lote obligatorios que no tienen valor.

    Los booleanos nunca cuentan como vacíos: una casilla desmarcada es un
    valor. Paridad con FlexibarNET10 v1.6.2, donde la marca de obligatorio
    pasó de decorativa a bloquear la transferencia.

    Args:
        fields_def: Definiciones de campo (``name``, ``type``, ``required``).
        batch_fields: Valores actuales de los campos del lote.

    Returns:
        Nombres de los campos obligatorios vacíos, en orden de definición.
    """
    missing: list[str] = []
    for fdef in fields_def:
        if not fdef.get("required"):
            continue
        # Admite la definición guardada (label, "booleano") y la del panel
        # (name, "Booleano").
        name = fdef.get("name") or fdef.get("label") or ""
        if not name or str(fdef.get("type", "")).lower() == "booleano":
            continue
        value = batch_fields.get(name)
        if value is None or not str(value).strip():
            missing.append(name)
    return missing


def validate_before_transfer(
    *,
    script_engine: Any,
    contexts: dict[str, Any],
    fields_def: list[dict[str, Any]],
    batch_fields: dict[str, Any],
    validate_entry_point: str | None = None,
    pages: list[dict[str, Any]] | None = None,
    config: TransferConfig | None = None,
) -> str | None:
    """Comprueba si el lote se puede transferir.

    Args:
        script_engine: ScriptEngine con los eventos de la App (o None).
        contexts: ``app`` y ``batch`` para el evento.
        fields_def: Definiciones de los campos de lote.
        batch_fields: Valores actuales de los campos del lote.
        validate_entry_point: Función del evento si no se llama como él.
        pages: Dicts de ``transfer_page_dict`` (sin excluidas). El evento
            los recibe como ``pages`` y ``documents``, como el ``Pages`` de
            FlexibarNET10.
        config: Configuración de transferencia, para comprobar los
            documentos (separadores) antes de preguntar nada al operador.

    Returns:
        None si se puede transferir, o el motivo por el que no.
    """
    missing = missing_required_fields(fields_def, batch_fields)
    if missing:
        return "Faltan campos obligatorios: " + ", ".join(missing)

    if (
        pages is not None
        and config is not None
        and config.standard_enabled
        and config.mode != "csv"
    ):
        problem = document_problems(pages, config)
        if problem:
            return problem

    if script_engine is None:
        return None
    event_kwargs = dict(contexts)
    if pages is not None:
        script_pages, documents = script_documents(pages)
        event_kwargs.update(pages=script_pages, documents=documents)
    outcome: EventOutcome = script_engine.run_event_checked(
        VALIDATE_EVENT,
        validate_entry_point,
        **event_kwargs,
    )
    if outcome.failed:
        return f"Ha fallado la validación previa a la transferencia: {outcome.error}"
    if outcome.ran and outcome.value is False:
        return "La validación previa ha rechazado la transferencia"
    return None


# ------------------------------------------------------------------
# Ejecución
# ------------------------------------------------------------------


def execute_transfer(
    *,
    transfer_service: Any,
    config: TransferConfig,
    pages: list[dict[str, Any]],
    batch_fields: dict[str, Any],
    batch_id: int | None,
    script_engine: Any = None,
    contexts: dict[str, Any] | None = None,
    advanced_entry_point: str | None = None,
    on_page_callback: Any = None,
    name_engine: Any = None,
) -> TransferResult:
    """Transferencia estándar y, después, ``on_transfer_advanced``.

    Args:
        transfer_service: TransferService.
        config: Configuración de transferencia de la App.
        pages: Dicts de ``transfer_page_dict`` (sin páginas excluidas).
        batch_fields: Campos del lote para la interpolación de nombres.
        batch_id: ID del lote.
        script_engine: ScriptEngine con los eventos de la App (o None).
        contexts: ``app`` y ``batch`` para el evento avanzado.
        advanced_entry_point: Función del evento si no se llama como él.
        on_page_callback: ``(page_index, success)`` por página copiada.
        name_engine: ScriptEngine con el script de nombre, si no es el
            mismo que ``script_engine`` (el worker solo pasa este último
            cuando la App define ``on_transfer_advanced``).

    Returns:
        TransferResult final. ``success`` es False si cualquiera de las dos
        partes ha fallado.
    """
    has_advanced = script_engine is not None and script_engine.is_compiled(
        ADVANCED_EVENT
    )
    if not config.standard_enabled and not has_advanced:
        return TransferResult(
            success=False,
            errors=[
                "No hay nada que transferir: la transferencia simple está "
                "desactivada y la App no define on_transfer_advanced"
            ],
        )

    if config.standard_enabled:
        if not config.destination:
            return TransferResult(
                success=False,
                errors=["Falta la carpeta de destino de la transferencia"],
            )
        try:
            name_resolver = build_name_resolver(
                name_engine or script_engine, config, contexts
            )
        except TransferAbortedError as e:
            return TransferResult(success=False, errors=[str(e)])
        result = transfer_service.transfer(
            pages=pages,
            config=config,
            batch_fields=batch_fields,
            batch_id=batch_id,
            on_page_callback=on_page_callback,
            name_resolver=name_resolver,
        )
        if not result.success:
            return result
    else:
        result = TransferResult(success=True)

    if not has_advanced:
        return result

    script_pages, documents = script_documents(pages)
    outcome: EventOutcome = script_engine.run_event_checked(
        ADVANCED_EVENT,
        advanced_entry_point,
        pages=script_pages,
        documents=documents,
        result=result,
        **(contexts or {}),
    )
    if outcome.failed:
        result.success = False
        result.errors.append(
            f"Ha fallado el script avanzado de transferencia: {outcome.error}"
        )
    elif outcome.value is False:
        result.success = False
        result.errors.append(
            "El script avanzado de transferencia ha informado de un fallo"
        )
    elif isinstance(outcome.value, TransferResult):
        returned = outcome.value
        if config.standard_enabled:
            result.files_transferred += returned.files_transferred
            result.errors.extend(returned.errors)
            result.success = result.success and returned.success
            result.output_path = result.output_path or returned.output_path
        else:
            result = returned
    elif not config.standard_enabled:
        # Comportamiento previo: el script no informa del recuento y se da
        # por transferido el lote entero.
        result.files_transferred = len(pages)
    return result
