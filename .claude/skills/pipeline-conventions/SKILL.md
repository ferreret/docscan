---
name: pipeline-conventions
description: Convenciones del pipeline de DocScan Studio. Usar al implementaro revisar cualquier paso de pipeline (steps.py, executor.py, context.py),o cuando se mencionen PipelineContext, ScriptStep, ConditionStep o repeat_step.
---

## Tipos de paso válidos
ImageOpStep, BarcodeStep, OcrStep, AiStep, ScriptStep, ConditionStep, HttpRequestStep.
No crear tipos nuevos sin actualizar el serializador y el executor.

## PipelineContext — API obligatoria
- pipeline.skip_step(step_id)
- pipeline.skip_to(step_id)
- pipeline.abort(reason="")
- pipeline.repeat_step(step_id)  # máx MAX_STEP_REPEATS=3, configurable
- pipeline.replace_image(ndarray)
- pipeline.get_step_result(step_id)
- pipeline.set_metadata(key, value) / get_metadata(key)

## Reglas críticas
- BarcodeStep es agnóstico: acumula en page.barcodes sin semántica de rol.
  El rol (separador/contenido) lo asigna un ScriptStep posterior.
- repeat_step SIEMPRE verifica el contador antes de ejecutar. Si >= MAX_STEP_REPEATS
  → PipelineAbortError, no loop infinito.
- Scripts se compilan UNA SOLA VEZ al cargar la app (cachear por step.id).
  Nunca compilar en cada invocación del paso.
- ScriptEngine captura TODAS las excepciones sin crashear el proceso.

## Antipatrones prohibidos
- No distinguir barcode separador/contenido en el motor
- No referenciar barcodes como objeto independiente (siempre page.barcodes)
- No permitir repeat_step sin límite