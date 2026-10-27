---
name: pipeline-conventions
description: Convenciones del pipeline de DocScan Studio. Usar al implementar o revisar cualquier paso de pipeline (steps.py, executor.py, context.py, serializer.py), o cuando se mencionen PipelineContext, ScriptStep, BarcodeStep, separadores de documento o repeat_step.
---

## Tipos de paso válidos
ImageOpStep, BarcodeStep, OcrStep, ScriptStep (los únicos de `app/pipeline/steps.py`).
ConditionStep y HttpRequestStep están descartados: su función la cubre ScriptStep.
No crear tipos nuevos sin actualizar a la vez el serializador, el executor y el
editor del Configurador.

## PipelineContext — API
- pipeline.skip_step(step_id)
- pipeline.skip_to(step_id)
- pipeline.abort(reason="")  # la página queda needs_review con el motivo
- pipeline.repeat_step(step_id)  # máx MAX_STEP_REPEATS=3, configurable
- pipeline.replace_image(ndarray)
- pipeline.get_step_result(step_id)
- pipeline.set_metadata(key, value) / get_metadata(key)
  **Solo duran una página**: el executor crea un PipelineContext nuevo por página.
  No sirven para pasar datos de una página a la siguiente (por ejemplo, el id del
  documento a sus adjuntos). Eso lo resuelve el separador de página (ver abajo).

## Reglas críticas
- BarcodeStep no asigna roles a los barcodes: acumula en page.barcodes sin semántica
  de separador/contenido. Puede declarar una condición de separador (campos
  `separator_*`, paridad con FlexibarNET10) que marca la PÁGINA
  (page.is_separator / page.separator_value), nunca el barcode. Los scripts pueden
  sobrescribir page.is_separator. Ver docs/diseno_separadores_documento_2026-10-26.md.
  (Estado a 2026-10-26: diseñado, aún no implementado.)
- repeat_step SIEMPRE verifica el contador antes de ejecutar. Si >= MAX_STEP_REPEATS
  → PipelineAbortError, no loop infinito.
- Los scripts se compilan UNA SOLA VEZ y se cachean por **hash del código fuente**
  (no por step.id): editar un script nunca puede ejecutar la versión anterior.
- ScriptEngine captura las excepciones de los scripts para que el proceso no caiga,
  pero **un fallo nunca se trata como éxito** (lógica de FlexibarNET10 v1.20/v1.26).
  Debe quedar a la vista: en page.flags.script_errors, en el panel Log o como fallo
  de la transferencia. Un ScriptStep que falla (excepción, no compila, falta la
  función) o un paso cuyo motor no está disponible deja la página needs_review con
  el motivo; el pipeline continúa. Los eventos cuyo fallo debe detener algo se
  ejecutan con ScriptEngine.run_event_checked (validación y transferencia avanzada,
  ver app/services/transfer_flow.py).
- Las regex de usuario se evalúan con app/utils/safe_regex (acotadas en tiempo).

## Antipatrones prohibidos
- Distinguir barcode separador/contenido en el motor de lectura
- Referenciar barcodes como objeto independiente (siempre page.barcodes)
- Permitir repeat_step sin límite
- Usar pipeline metadata como estado entre páginas
- Convertir el fallo de un script en «sin resultado» o en éxito
