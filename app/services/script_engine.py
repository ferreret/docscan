"""ScriptEngine — compilación y ejecución de scripts de usuario.

Compila el código Python una vez al cargar la aplicación. La cache se
indexa por **hash del código fuente**, no por el identificador del paso:
si el usuario edita un script y el engine sobrevive al guardado, la
siguiente ejecución compila la versión nueva en lugar de reutilizar la
antigua.
Captura TODAS las excepciones sin crashear la app ni detener el pipeline.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import inspect
import logging
import re
import json
import datetime
from pathlib import Path
from types import CodeType
from typing import Any, Protocol

from app.pipeline.context import PipelineAbortError

log = logging.getLogger(__name__)

# Timeout por defecto para ejecución de scripts (segundos)
DEFAULT_SCRIPT_TIMEOUT = 30


class ScriptCompilationError(Exception):
    """Error de sintaxis al compilar un script de usuario."""


class ScriptTimeoutError(Exception):
    """El script excedió el tiempo máximo de ejecución."""


class _HasFlags(Protocol):
    """Protocolo mínimo para objetos que exponen flags de errores."""

    script_errors: list[dict[str, Any]]


class ScriptEngine:
    """Compila y ejecuta scripts Python de usuario.

    - Compila el código una vez al cargar la aplicación (cache por hash
      del fuente: editar un script invalida su entrada automáticamente)
    - Captura TODAS las excepciones sin crashear la app
    - Expone el contexto completo al script

    Args:
        http_client: Cliente httpx preconfigurado (opcional).
    """

    def __init__(
        self,
        http_client: Any = None,
        script_timeout: int = DEFAULT_SCRIPT_TIMEOUT,
    ) -> None:
        # Código compilado indexado por hash del fuente (evita ejecutar
        # una versión antigua tras editar el script).
        self._code_by_hash: dict[str, CodeType] = {}
        # Último hash conocido de cada script_id (para los eventos de
        # ciclo de vida, que no llevan el fuente en la llamada).
        self._hash_by_id: dict[str, str] = {}
        self._http_client = http_client
        self._script_timeout = script_timeout
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

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
        source_hash = self._source_hash(source)
        if source_hash not in self._code_by_hash:
            display_name = label or script_id
            try:
                code = compile(source, f"<script:{display_name}>", "exec")
            except SyntaxError as e:
                raise ScriptCompilationError(
                    f"Error de sintaxis en '{display_name}': {e}"
                ) from e
            self._code_by_hash[source_hash] = code
        self._hash_by_id[script_id] = source_hash

    def compile_step(self, step: Any) -> None:
        """Compila un ScriptStep (conveniencia).

        Args:
            step: Objeto con atributos id, script y label.
        """
        self.compile_script(step.id, step.script, step.label)

    def is_compiled(self, script_id: str) -> bool:
        """¿El script está compilado en cache?"""
        return script_id in self._hash_by_id

    def clear_cache(self) -> None:
        """Limpia la cache de scripts compilados."""
        self._code_by_hash.clear()
        self._hash_by_id.clear()

    @staticmethod
    def _source_hash(source: str) -> str:
        """Huella del código fuente que identifica la versión compilada."""
        return hashlib.sha256((source or "").encode("utf-8")).hexdigest()

    def _code_for_id(self, script_id: str) -> CodeType | None:
        """Devuelve el código compilado asociado a un script_id."""
        source_hash = self._hash_by_id.get(script_id)
        if source_hash is None:
            return None
        return self._code_by_hash.get(source_hash)

    def _code_for_step(self, step: Any) -> CodeType | None:
        """Devuelve el código compilado vigente de un ScriptStep.

        Resuelve por el **contenido actual** del paso: si el script se
        editó después de la compilación inicial, lo recompila al vuelo en
        lugar de ejecutar la versión cacheada anterior.

        Returns:
            El objeto código, o None si no se pudo obtener.
        """
        source = getattr(step, "script", None)
        if not isinstance(source, str):
            # Paso duck-typed sin fuente accesible: resolver por id.
            return self._code_for_id(step.id)

        source_hash = self._source_hash(source)
        code = self._code_by_hash.get(source_hash)
        if code is not None:
            self._hash_by_id[step.id] = source_hash
            return code

        label = getattr(step, "label", "") or step.id
        log.info("Script '%s' modificado desde la carga; recompilando", label)
        try:
            self.compile_script(step.id, source, label)
        except ScriptCompilationError as e:
            log.error("No se pudo recompilar el script '%s': %s", label, e)
            return None
        return self._code_by_hash.get(source_hash)

    def shutdown(self) -> None:
        """Libera el ThreadPoolExecutor."""
        self._executor.shutdown(wait=False)

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
        code = self._code_for_step(step)
        if not code:
            log.warning(
                "Script '%s' no compilado, ignorando",
                step.label or step.id,
            )
            return None

        namespace = self._build_namespace(
            page=page,
            batch=batch,
            app=app,
            pipeline=pipeline,
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
            return self._execute_with_timeout(
                func,
                kwargs=dict(app=app, batch=batch, page=page, pipeline=pipeline),
            )
        except PipelineAbortError:
            raise  # Propagar abort al executor
        except ScriptTimeoutError as e:
            self._record_error(page, step.id, step.entry_point, e)
            return None
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
        code = self._code_for_id(script_id)
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
            try:
                sig = inspect.signature(func)
                if any(
                    p.kind == inspect.Parameter.VAR_KEYWORD
                    for p in sig.parameters.values()
                ):
                    filtered = kwargs
                else:
                    filtered = {k: v for k, v in kwargs.items() if k in sig.parameters}
            except ValueError, TypeError:
                filtered = kwargs
            return func(**filtered)
        except Exception as e:
            log.error(
                "Error ejecutando evento '%s.%s': %s",
                script_id,
                entry_point,
                e,
            )
            return None

    def run_event_raw(
        self,
        script_id: str,
        entry_point: str,
        **kwargs: Any,
    ) -> Any:
        """Ejecuta un entry point de ciclo de vida SIN capturar excepciones.

        Variante de ``run_event`` pensada para callers que necesitan distinguir
        "script devolvió None" de "script lanzó excepción" (p.ej. el
        event_dispatcher web, que gestiona timeout+error por su cuenta).

        Args:
            script_id: ID del script compilado.
            entry_point: Nombre de la función a llamar.
            **kwargs: Argumentos para la función (app, batch, page, etc.).

        Returns:
            El valor retornado por la función del script.

        Raises:
            KeyError: Si el script no está compilado.
            AttributeError: Si el entry point no existe o no es callable.
            Exception: Cualquier excepción lanzada por el script del usuario.
        """
        code = self._code_for_id(script_id)
        if not code:
            raise KeyError(f"Script '{script_id}' no está compilado en cache")

        namespace = self._build_namespace(**kwargs)
        exec(code, namespace)  # noqa: S102 — script de usuario aislado en namespace

        func = namespace.get(entry_point)
        if func is None or not callable(func):
            raise AttributeError(
                f"Entry point '{entry_point}' no encontrado en script '{script_id}'"
            )

        try:
            sig = inspect.signature(func)
            if any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
            ):
                filtered = kwargs
            else:
                filtered = {k: v for k, v in kwargs.items() if k in sig.parameters}
        except ValueError, TypeError:
            filtered = kwargs

        return func(**filtered)

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _execute_with_timeout(
        self,
        func: Any,
        kwargs: dict[str, Any],
    ) -> Any:
        """Ejecuta una función con timeout usando ThreadPoolExecutor.

        Args:
            func: Función a ejecutar.
            kwargs: Argumentos para la función.

        Returns:
            El resultado de la función.

        Raises:
            ScriptTimeoutError: Si excede el timeout.
            PipelineAbortError: Propagada desde el script.
        """
        future = self._executor.submit(func, **kwargs)
        try:
            return future.result(timeout=self._script_timeout)
        except concurrent.futures.TimeoutError:
            raise ScriptTimeoutError(
                f"Script excedió el timeout de {self._script_timeout}s"
            )

    def _build_namespace(self, **kwargs: Any) -> dict[str, Any]:
        """Construye el namespace para exec/eval."""
        from app.services.image_lib import ImageLib

        ns: dict[str, Any] = {
            "__builtins__": __builtins__,
            "log": log,
            "http": self._http_client,
            "re": re,
            "json": json,
            "datetime": datetime,
            "Path": Path,
            "ImageLib": ImageLib,
        }
        # Añadir los contextos que se hayan pasado
        for key in ("app", "batch", "page", "pages", "pipeline", "fields", "result"):
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
            entry_point,
            step_id,
            error,
        )
        # Intentar registrar en page si tiene la interfaz esperada
        if hasattr(page, "script_errors"):
            page.script_errors.append(error_info)
        elif hasattr(page, "flags") and hasattr(page.flags, "script_errors"):
            page.flags.script_errors.append(error_info)
