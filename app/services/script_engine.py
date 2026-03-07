"""ScriptEngine — compilación y ejecución de scripts de usuario.

Compila el código Python una vez al cargar la aplicación (cache por step_id).
Captura TODAS las excepciones sin crashear la app ni detener el pipeline.
"""

from __future__ import annotations

import logging
import re
import json
import datetime
from pathlib import Path
from types import CodeType
from typing import Any, Protocol

from app.pipeline.context import PipelineAbortError

log = logging.getLogger(__name__)


class ScriptCompilationError(Exception):
    """Error de sintaxis al compilar un script de usuario."""


class _HasFlags(Protocol):
    """Protocolo mínimo para objetos que exponen flags de errores."""

    script_errors: list[dict[str, Any]]


class ScriptEngine:
    """Compila y ejecuta scripts Python de usuario.

    - Compila el código una vez al cargar la aplicación (cache por id)
    - Captura TODAS las excepciones sin crashear la app
    - Expone el contexto completo al script

    Args:
        http_client: Cliente httpx preconfigurado (opcional).
    """

    def __init__(self, http_client: Any = None) -> None:
        self._compiled_cache: dict[str, CodeType] = {}
        self._http_client = http_client

    # ------------------------------------------------------------------
    # Compilación
    # ------------------------------------------------------------------

    def compile_script(
        self,
        script_id: str,
        source: str,
        label: str = "",
    ) -> None:
        """Pre-compila un script y lo almacena en cache.

        Args:
            script_id: Identificador único (step.id o nombre del evento).
            source: Código fuente Python.
            label: Nombre descriptivo para mensajes de error.

        Raises:
            ScriptCompilationError: Si el código tiene errores de sintaxis.
        """
        display_name = label or script_id
        try:
            code = compile(source, f"<script:{display_name}>", "exec")
            self._compiled_cache[script_id] = code
        except SyntaxError as e:
            raise ScriptCompilationError(
                f"Error de sintaxis en '{display_name}': {e}"
            ) from e

    def compile_step(self, step: Any) -> None:
        """Compila un ScriptStep (conveniencia).

        Args:
            step: Objeto con atributos id, script y label.
        """
        self.compile_script(step.id, step.script, step.label)

    def is_compiled(self, script_id: str) -> bool:
        """¿El script está compilado en cache?"""
        return script_id in self._compiled_cache

    def clear_cache(self) -> None:
        """Limpia la cache de scripts compilados."""
        self._compiled_cache.clear()

    # ------------------------------------------------------------------
    # Ejecución de ScriptStep del pipeline
    # ------------------------------------------------------------------

    def run_step(
        self,
        step: Any,
        page: Any,
        batch: Any,
        app: Any,
        pipeline: Any,
    ) -> Any:
        """Ejecuta el entry point de un ScriptStep del pipeline.

        Captura excepciones y las registra en page.flags sin detener
        el pipeline ni crashear la app.

        Args:
            step: ScriptStep con id, entry_point, label.
            page: PageContext de la página actual.
            batch: BatchContext del lote.
            app: AppContext de la aplicación.
            pipeline: PipelineContext para control de flujo.

        Returns:
            El valor retornado por la función del script, o None si falla.
        """
        code = self._compiled_cache.get(step.id)
        if not code:
            log.warning(
                "Script '%s' no compilado, ignorando",
                step.label or step.id,
            )
            return None

        namespace = self._build_namespace(
            page=page, batch=batch, app=app, pipeline=pipeline,
        )

        try:
            exec(code, namespace)
            func = namespace.get(step.entry_point)
            if func is None or not callable(func):
                log.warning(
                    "Entry point '%s' no encontrado en script '%s'",
                    step.entry_point,
                    step.label or step.id,
                )
                return None
            return func(app=app, batch=batch, page=page, pipeline=pipeline)
        except PipelineAbortError:
            raise  # Propagar abort al executor
        except Exception as e:
            self._record_error(page, step.id, step.entry_point, e)
            return None

    # ------------------------------------------------------------------
    # Ejecución de entry points de ciclo de vida
    # ------------------------------------------------------------------

    def run_event(
        self,
        script_id: str,
        entry_point: str,
        **kwargs: Any,
    ) -> Any:
        """Ejecuta un entry point de ciclo de vida (eventos de app).

        A diferencia de run_step, no requiere page/pipeline y acepta
        kwargs arbitrarios que se pasan a la función.

        Args:
            script_id: ID del script compilado.
            entry_point: Nombre de la función a llamar.
            **kwargs: Argumentos para la función (app, batch, page, etc.).

        Returns:
            El valor retornado por la función, o None si falla.
        """
        code = self._compiled_cache.get(script_id)
        if not code:
            return None

        namespace = self._build_namespace(**kwargs)

        try:
            exec(code, namespace)
            func = namespace.get(entry_point)
            if func is None or not callable(func):
                log.warning(
                    "Entry point '%s' no encontrado en evento '%s'",
                    entry_point,
                    script_id,
                )
                return None
            return func(**kwargs)
        except Exception as e:
            log.error(
                "Error ejecutando evento '%s.%s': %s",
                script_id, entry_point, e,
            )
            return None

    # ------------------------------------------------------------------
    # Evaluación de expresiones (para ConditionStep)
    # ------------------------------------------------------------------

    def eval_expression(
        self,
        expression: str,
        page: Any = None,
        batch: Any = None,
        app: Any = None,
        pipeline: Any = None,
    ) -> Any:
        """Evalúa una expresión Python de una línea.

        Usada por ConditionStep para evaluar condiciones.

        Args:
            expression: Expresión Python (ej: "len(page.barcodes) > 0").

        Returns:
            El resultado de la expresión, o False si falla.
        """
        namespace = self._build_namespace(
            page=page, batch=batch, app=app, pipeline=pipeline,
        )
        try:
            return eval(expression, namespace)
        except Exception as e:
            log.error("Error evaluando expresión '%s': %s", expression, e)
            return False

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _build_namespace(self, **kwargs: Any) -> dict[str, Any]:
        """Construye el namespace para exec/eval."""
        ns: dict[str, Any] = {
            "__builtins__": __builtins__,
            "log": log,
            "http": self._http_client,
            "re": re,
            "json": json,
            "datetime": datetime,
            "Path": Path,
        }
        # Añadir los contextos que se hayan pasado
        for key in ("app", "batch", "page", "pages", "pipeline",
                     "fields", "result"):
            if key in kwargs:
                ns[key] = kwargs[key]
        return ns

    def _record_error(
        self,
        page: Any,
        step_id: str,
        entry_point: str,
        error: Exception,
    ) -> None:
        """Registra un error de script en page.flags."""
        error_info = {
            "step_id": step_id,
            "entry_point": entry_point,
            "error": str(error),
            "type": type(error).__name__,
        }
        log.error(
            "Error ejecutando '%s' (paso %s): %s",
            entry_point, step_id, error,
        )
        # Intentar registrar en page si tiene la interfaz esperada
        if hasattr(page, "script_errors"):
            page.script_errors.append(error_info)
        elif hasattr(page, "flags") and hasattr(page.flags, "script_errors"):
            page.flags.script_errors.append(error_info)
