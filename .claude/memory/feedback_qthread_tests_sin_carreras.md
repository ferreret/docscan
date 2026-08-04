---
name: feedback_qthread_tests_sin_carreras
description: "En tests de QThread, disparar la interrupción con DirectConnection; una conexión en cola hace el test una lotería en CI."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 3a574282-e6b0-4206-b4f4-4b8af65e1b75
  modified: 2026-07-28T10:19:55.400Z
---

**Al probar la cancelación de un QThread, conectar el disparador de
`requestInterruption()` con `Qt.ConnectionType.DirectConnection`.**

**Why**: con la conexión por defecto (en cola hacia el hilo principal), no hay
garantía de que la petición llegue antes de que el worker vacíe su cola. Pasó el
2026-07-28: un test que afirmaba «quedaba trabajo pendiente» pasaba en local y
falló en el CI —máquina más rápida, executor simulado que devuelve al instante—
tumbando la verificación del commit de release. Con DirectConnection el flag
queda puesto en el propio hilo del worker antes de la siguiente vuelta del bucle.

**How to apply**: `worker.page_processed.connect(lambda *a:
worker.requestInterruption(), Qt.ConnectionType.DirectConnection)`. Y, en
general, **no afirmar sobre progreso parcial dependiente de temporización**
(«procesó menos de N») sin hacer determinista el disparador; la aserción que
importa suele ser la del contrato (qué señal se emite y cuál no). Antes de dar
por bueno un test de concurrencia, repetirlo en bucle (10-15 veces) en lugar de
fiarse de una pasada.

Relacionado: [[project_lotes_flexibarnet_ejecutados]].
