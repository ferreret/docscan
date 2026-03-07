"""PipelineExecutor — ejecuta el pipeline completo para una página.

Stateless entre páginas; crear una instancia por aplicación.
"""

from __future__ import annotations

import logging
from typing import Any

from app.pipeline.context import PipelineAbortError, PipelineContext
from app.pipeline.steps import (
    AiStep,
    BarcodeStep,
    ImageOpStep,
    OcrStep,
    PipelineStep,
    ScriptStep,
)
from app.services.image_pipeline import ImagePipelineService
from app.services.script_engine import ScriptEngine

log = logging.getLogger(__name__)

MAX_STEP_REPEATS: int = 3


class StepError(Exception):
    """Error en la ejecución de un paso del pipeline."""


class PipelineExecutor:
    """Ejecuta el pipeline de pasos para una página concreta.

    Args:
        steps: Lista ordenada de pasos del pipeline.
        image_service: Servicio de operaciones de imagen.
        script_engine: Motor de scripts de usuario.
        barcode_service: Servicio de lectura de barcodes (opcional).
        ocr_service: Servicio de OCR (opcional).
        ai_service: Servicio de IA (opcional).
        max_repeats: Límite de repeticiones por paso.
    """

    def __init__(
        self,
        steps: list[PipelineStep],
        image_service: ImagePipelineService,
        script_engine: ScriptEngine,
        barcode_service: Any = None,
        ocr_service: Any = None,
        ai_service: Any = None,
        max_repeats: int = MAX_STEP_REPEATS,
    ) -> None:
        self._steps = steps
        self._image_service = image_service
        self._script_engine = script_engine
        self._barcode_service = barcode_service
        self._ocr_service = ocr_service
        self._ai_service = ai_service
        self._max_repeats = max_repeats

    def execute(self, page: Any, batch: Any, app: Any) -> Any:
        """Ejecuta todos los pasos habilitados en orden.

        Los ScriptStep pueden modificar el flujo vía PipelineContext.
        Captura errores de pasos individuales sin detener el pipeline
        (salvo abort explícito).

        Args:
            page: Contexto de la página (con image, barcodes, flags, etc.).
            batch: Contexto del lote.
            app: Contexto de la aplicación.

        Returns:
            El objeto page con los resultados del pipeline.
        """
        ctx = PipelineContext(
            steps=self._steps,
            max_repeats=self._max_repeats,
        )

        while ctx.has_next():
            step = ctx.next_step()

            if not step.enabled or ctx.is_skipped(step.id):
                continue

            try:
                result = self._execute_step(step, page, batch, app, ctx)
                ctx.set_step_result(step.id, result)
            except PipelineAbortError as e:
                log.warning(
                    "Pipeline abortado en paso %s: %s", step.id, e,
                )
                if hasattr(page, "flags"):
                    page.flags.needs_review = True
                    if str(e):
                        page.flags.review_reason = str(e)
                break
            except StepError as e:
                log.error("Error en paso %s (%s): %s", step.id, step.type, e)
                self._record_processing_error(page, step, e)

        return page

    def _execute_step(
        self,
        step: PipelineStep,
        page: Any,
        batch: Any,
        app: Any,
        ctx: PipelineContext,
    ) -> Any:
        """Despacha la ejecución al handler correcto según el tipo."""
        try:
            match step.type:
                case "image_op":
                    return self._run_image_op(step, page, ctx)
                case "barcode":
                    return self._run_barcode(step, page, ctx)
                case "ocr":
                    return self._run_ocr(step, page, ctx)
                case "ai":
                    return self._run_ai(step, page, batch, app, ctx)
                case "script":
                    return self._run_script(step, page, batch, app, ctx)
                case _:
                    raise StepError(f"Tipo de paso desconocido: '{step.type}'")
        except PipelineAbortError:
            raise
        except Exception as e:
            raise StepError(str(e)) from e

    # ------------------------------------------------------------------
    # Handlers por tipo
    # ------------------------------------------------------------------

    def _run_image_op(
        self, step: ImageOpStep, page: Any, ctx: PipelineContext,
    ) -> Any:
        """Ejecuta una operación de imagen."""
        image = self._get_image(page, ctx)
        processed = self._image_service.execute(
            image, step.op, step.params, step.window,
        )
        ctx.replace_image(processed)
        return {"op": step.op, "shape": processed.shape}

    def _run_barcode(
        self, step: BarcodeStep, page: Any, ctx: PipelineContext,
    ) -> Any:
        """Ejecuta lectura de barcodes."""
        if self._barcode_service is None:
            log.warning("BarcodeService no configurado, saltando paso %s", step.id)
            return None

        image = self._get_image(page, ctx)
        results = self._barcode_service.read(
            image=image,
            engine=step.engine,
            symbologies=step.symbologies,
            regex=step.regex,
            regex_include_symbology=step.regex_include_symbology,
            orientations=step.orientations,
            quality_threshold=step.quality_threshold,
            window=step.window,
            step_id=step.id,
        )
        # Acumular en page.barcodes (no reemplazar)
        if hasattr(page, "barcodes"):
            page.barcodes.extend(results)
        return results

    def _run_ocr(
        self, step: OcrStep, page: Any, ctx: PipelineContext,
    ) -> Any:
        """Ejecuta reconocimiento OCR."""
        if self._ocr_service is None:
            log.warning("OcrService no configurado, saltando paso %s", step.id)
            return None

        image = self._get_image(page, ctx)
        text = self._ocr_service.recognize(
            image=image,
            engine=step.engine,
            languages=step.languages,
            full_page=step.full_page,
            window=step.window,
        )
        if hasattr(page, "ocr_text"):
            page.ocr_text = text
        return text

    def _run_ai(
        self, step: AiStep, page: Any, batch: Any, app: Any,
        ctx: PipelineContext,
    ) -> Any:
        """Ejecuta extracción/clasificación por IA."""
        if self._ai_service is None:
            log.warning("AiService no configurado, saltando paso %s", step.id)
            return None

        image = self._get_image(page, ctx)
        try:
            fields = self._ai_service.extract(
                image=image,
                provider=step.provider,
                template_id=step.template_id,
                page=page,
                batch=batch,
                app=app,
            )
        except Exception as e:
            if step.fallback_provider:
                log.warning(
                    "IA falló (%s), intentando fallback '%s'",
                    e, step.fallback_provider,
                )
                fields = self._ai_service.extract(
                    image=image,
                    provider=step.fallback_provider,
                    template_id=step.template_id,
                    page=page,
                    batch=batch,
                    app=app,
                )
            else:
                raise

        if hasattr(page, "ai_fields"):
            page.ai_fields.update(fields)
        return fields

    def _run_script(
        self, step: ScriptStep, page: Any, batch: Any, app: Any,
        ctx: PipelineContext,
    ) -> Any:
        """Ejecuta un script de usuario."""
        return self._script_engine.run_step(step, page, batch, app, ctx)

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def _get_image(self, page: Any, ctx: PipelineContext) -> Any:
        """Obtiene la imagen actual (del contexto o de la página)."""
        if ctx.current_image is not None:
            return ctx.current_image
        if hasattr(page, "image"):
            return page.image
        return None

    def _record_processing_error(
        self, page: Any, step: PipelineStep, error: Exception,
    ) -> None:
        """Registra un error de procesado en page.flags."""
        error_msg = f"[{step.id}/{step.type}] {error}"
        if hasattr(page, "flags") and hasattr(page.flags, "processing_errors"):
            page.flags.processing_errors.append(error_msg)
