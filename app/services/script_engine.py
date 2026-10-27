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
from dataclasses import dataclass
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


@dataclass(frozen=True)
class EventOutcome:
    """Resultado de ejecutar un evento con ``run_event_checked``.

    Attributes:
        ran: False si el evento no está definido en la aplicación.
        value: Valor devuelto por la función del script.
        error: Descripción del fallo; vacío si terminó bien.
        rejected: El script rechazó la operación a propósito (lanzó una de
            las excepciones de rechazo): ``error`` es solo su mensaje.
    """

    ran: bool
    value: Any = None
    error: str = ""
    rejected: bool = False

    @property
    def failed(self) -> bool:
        """True si el script se ejecutó y falló."""
        return bool(self.error)


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
        # Fuentes que no compilan, por hash: se intenta una sola vez y el
        # error se reporta en cada página sin recompilar cada vez.
        self._compile_error_by_hash: dict[str, str] = {}
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
        if source_hash in self._compile_error_by_hash:
            return None

        label = getattr(step, "label", "") or step.id
        log.info("Compilando el script '%s'", label)
        try:
            self.compile_script(step.id, source, label)
        except ScriptCompilationError as e:
            log.error("No se pudo compilar el script '%s': %s", label, e)
            self._compile_error_by_hash[source_hash] = str(e)
            return None
        return self._code_by_hash.get(source_hash)

    def compile_error_for(self, step: Any) -> str:
        """Error de compilación del fuente actual de un paso, o ``""``."""
        source = getattr(step, "script", None)
        if not isinstance(source, str):
            return ""
        return self._compile_error_by_hash.get(self._source_hash(source), "")

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
            reason = self.compile_error_for(step) or "el script no está compilado"
            self._record_error(
                page, step.id, step.entry_point, ScriptCompilationError(reason)
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
                self._record_error(
                    page,
                    step.id,
                    step.entry_point,
                    AttributeError(
                        f"El script no define la función '{step.entry_point}'"
                    ),
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

    def run_event_checked(
        self,
        script_id: str,
        entry_point: str | None = None,
        *,
        rejection_types: tuple[type[BaseException], ...] = (),
        **kwargs: Any,
    ) -> EventOutcome:
        """Ejecuta un evento distinguiendo «no definido», «falló» y «devolvió».

        Pensado para los eventos cuyo fallo debe detener algo (validación y
        transferencia avanzada): ``run_event`` devuelve ``None`` tanto si el
        script no existe como si lanza, y quien lo llama no puede saber que
        algo ha ido mal. Paridad con FlexibarNET10 v1.20/v1.26: un fallo de
        script nunca se trata como éxito.

        Args:
            script_id: ID del script compilado.
            entry_point: Función a llamar (por defecto, ``script_id``).
            rejection_types: Excepciones que el script lanza a propósito para
                rechazar (p. ej. ``ValueError`` en la validación). Se
                registran como aviso, sin traza: son una regla de negocio, no
                un fallo del programa.
            **kwargs: Argumentos para la función (app, batch, pages…).

        Returns:
            EventOutcome con ``ran=False`` si el evento no está compilado, o
            con ``error`` relleno si no define la función o lanza.
        """
        if not self.is_compiled(script_id):
            return EventOutcome(ran=False)
        try:
            value = self.run_event_raw(script_id, entry_point or script_id, **kwargs)
        except rejection_types as e:
            log.warning("Evento '%s' rechazado: %s", script_id, e)
            return EventOutcome(ran=True, error=str(e), rejected=True)
        except Exception as e:
            log.exception("Error ejecutando evento '%s'", script_id)
            return EventOutcome(ran=True, error=f"{type(e).__name__}: {e}")
        return EventOutcome(ran=True, value=value)

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
            # El hilo sigue atrapado en el script y Python no permite
            # matarlo. Si se reutilizara el pool, todas las páginas
            # siguientes se encolarían detrás y expirarían una a una: un
            # solo script colgado dejaría el resto del lote sin scripting
            # y con 30s de espera por página. Se descarta el pool y se
            # abre uno limpio; el hilo viejo queda como daemon.
            self._renew_executor()
            raise ScriptTimeoutError(
                f"Script excedió el timeout de {self._script_timeout}s"
            )

    def _renew_executor(self) -> None:
        """Sustituye el pool de ejecución por uno limpio."""
        old = self._executor
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        # No esperar: el hilo antiguo sigue ocupado por el script colgado.
        old.shutdown(wait=False)
        log.warning(
            "Pool de scripts renovado tras un timeout; "
            "el hilo anterior sigue ocupado por el script colgado"
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
        # Paridad FlexibarNET10 v1.20: un script que falla no es invisible.
        # El pipeline sigue, pero la página queda a revisión con el motivo.
        flags = getattr(page, "flags", None)
        if flags is not None and hasattr(flags, "needs_review"):
            flags.needs_review = True
            if not getattr(flags, "review_reason", ""):
                flags.review_reason = f"Ha fallado el script del paso {step_id}"


def find_script_errors(
    pipeline_json: str,
    events_json: str,
    transfer_json: str = "{}",
) -> list[str]:
    """Errores de sintaxis de todos los scripts de una aplicación.

    Lo usa el Configurador para no guardar una App con scripts que no
    compilan (paridad FlexibarNET10 v1.20/v1.26). Antes se guardaba sin
    comprobar nada y el fallo solo se veía, si acaso, en el log al abrir
    el Workbench.

    Args:
        pipeline_json: JSON de pasos del pipeline.
        events_json: JSON de eventos (``{nombre: código}`` o
            ``{nombre: {"script": código}}``), incluido el panel de verificación.
        transfer_json: JSON de transferencia (script de nombre de fichero).

    Returns:
        Un mensaje por script que no compila, con su origen y la línea.
    """
    from app.pipeline.serializer import deserialize
    from app.pipeline.steps import ScriptStep

    errors: list[str] = []

    def check(source: str, origin: str) -> None:
        if not source or not source.strip():
            return
        try:
            compile(source, f"<{origin}>", "exec")
        except SyntaxError as e:
            errors.append(f"{origin}, línea {e.lineno}: {e.msg}")

    try:
        steps = deserialize(pipeline_json or "[]")
    except Exception as e:
        errors.append(f"Pipeline: no se puede leer la configuración ({e})")
        steps = []
    for step in steps:
        if isinstance(step, ScriptStep):
            check(step.script, f"Paso de pipeline «{step.label or step.id}»")

    try:
        events = json.loads(events_json or "{}")
    except json.JSONDecodeError as e:
        errors.append(f"Eventos: no se puede leer la configuración ({e})")
        events = {}
    for name, config in (events if isinstance(events, dict) else {}).items():
        source = config.get("script", "") if isinstance(config, dict) else config
        if isinstance(source, str):
            check(source, f"Evento {name}")

    try:
        transfer = json.loads(transfer_json or "{}")
    except json.JSONDecodeError as e:
        errors.append(f"Transferencia: no se puede leer la configuración ({e})")
        transfer = {}
    if isinstance(transfer, dict) and transfer.get("name_mode") == "script":
        check(transfer.get("file_name_script", ""), "Script de nombre de fichero")
    return errors
