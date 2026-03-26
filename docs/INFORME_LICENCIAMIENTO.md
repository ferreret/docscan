# Informe de Licenciamiento y Monetización — DocScan Studio

**Versión:** 1.0
**Fecha:** 2026-03-26
**Autor:** Equipo de Desarrollo
**Destinatarios:** Dirección de Tecnomedia

---

## 1. Resumen ejecutivo

DocScan Studio es una plataforma de captura, procesamiento e indexación de documentos que compite en un segmento dominado por soluciones de alto coste (ABBYY FlexiCapture, Kofax). Actualmente se distribuye como código abierto en GitHub sin monetización.

**Situación actual:**
- Producto funcional con pipeline composable, reconocimiento de códigos de barras, OCR e IA generativa
- Stack técnico maduro (Python 3.14, PySide6, SQLAlchemy, OpenCV)
- Multiplataforma: Linux (AppImage) y Windows (Inno Setup)
- Sin ingresos directos

**Recomendación principal:** Estrategia en dos fases — distribución gratuita inicial para captar usuarios, seguida de modelo Open Core con edición Professional de pago.

---

## 2. Marco legal — Licencias del stack

### 2.1 PySide6 (LGPL v3)

PySide6 se distribuye bajo **LGPL v3**, lo que permite:
- Uso comercial sin coste de licencia
- Distribución de aplicaciones cerradas (propietarias)
- Sin obligación de publicar el código fuente de DocScan Studio

**Condiciones:**
- Mantener PySide6 como librería enlazada dinámicamente (PyInstaller lo hace por defecto)
- Incluir la licencia LGPL de PySide6 en la distribución
- Si se modifica PySide6, publicar solo esas modificaciones

**Diferencia clave con PyQt6:** PyQt6 requiere licencia comercial (~550/dev/año) para uso comercial. PySide6 no.

### 2.2 Dependencias y compatibilidad comercial

| Dependencia | Licencia | Uso comercial | Notas |
|-------------|----------|---------------|-------|
| Python 3.14 | PSF License | Sí | Permisiva |
| PySide6 | LGPL v3 | Sí | Enlace dinámico |
| SQLAlchemy | MIT | Sí | Permisiva |
| OpenCV | Apache 2.0 | Sí | Permisiva |
| PyMuPDF (fitz) | AGPL v3 | **Atención** | Ver sección 2.3 |
| RapidOCR | Apache 2.0 | Sí | Permisiva |
| pytesseract | Apache 2.0 | Sí | Wrapper de Tesseract |
| pyzbar | MIT | Sí | Permisiva |
| zxing-cpp | Apache 2.0 | Sí | Permisiva |
| Anthropic SDK | MIT | Sí | Permisiva |
| OpenAI SDK | Apache 2.0 | Sí | Permisiva |
| httpx | BSD-3 | Sí | Permisiva |
| cryptography | Apache 2.0/BSD | Sí | Permisiva |
| Pillow | HPND | Sí | Permisiva |
| watchdog | Apache 2.0 | Sí | Permisiva |
| APScheduler | MIT | Sí | Permisiva |
| pydantic-settings | MIT | Sí | Permisiva |
| Alembic | MIT | Sí | Permisiva |
| packaging | Apache 2.0/BSD | Sí | Permisiva |

### 2.3 PyMuPDF — Caso especial (AGPL v3)

PyMuPDF se distribuye bajo **AGPL v3**, que requiere:
- Si se distribuye el software (incluso como servicio), publicar **todo** el código fuente
- Esto afectaría a un modelo de código cerrado

**Opciones:**
1. **Licencia comercial de Artifex** (~contactar para precio) — elimina la obligación AGPL
2. **Mantener el proyecto open source** — AGPL no supone problema
3. **Reemplazar PyMuPDF** por alternativas:
   - `pypdf` (BSD) — funcionalidad básica de PDF
   - `pikepdf` (MPL 2.0) — manipulación avanzada
   - `reportlab` (BSD) — generación de PDF

**Recomendación:** Para la fase gratuita (open source), no hay problema. Si se opta por código cerrado, adquirir licencia comercial de Artifex o migrar a `pypdf` + `pikepdf`.

### 2.4 Riesgos legales y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Violación LGPL PySide6 | Baja | Medio | PyInstaller enlaza dinámicamente por defecto |
| Violación AGPL PyMuPDF | Media | Alto | Licencia comercial o reemplazo |
| Conflicto de patentes OCR | Muy baja | Bajo | Tesseract/RapidOCR son open source establecidos |
| Restricciones de API de IA | Baja | Medio | ToS de Anthropic/OpenAI permiten uso comercial |

---

## 3. Modelos de negocio analizados

### 3.1 Comparativa

| Modelo | Descripción | Ingresos estimados (año 1) | Viabilidad | Tiempo implementación |
|--------|-------------|---------------------------|------------|----------------------|
| **Open Source puro** | Gratis, soporte/consultoría | 5-15K EUR | Inmediata | 0 |
| **Licencia perpetua** | 199-499 EUR/dispositivo | 15-50K EUR | 1-2 meses | Medio |
| **Suscripción** | 29-49 EUR/usuario/mes | 20-80K EUR (recurrente) | 2-3 meses | Alto |
| **Open Core** | Community gratis + Pro | 30-100K EUR | 3-4 meses | Alto |
| **Pay-per-document** | 0.01-0.50 EUR/doc | Variable | 4+ meses | Muy alto |

### 3.2 Detalle por modelo

**Open Source puro:**
- Sin barrera de entrada, máxima adopción
- Monetización indirecta: consultoría, formación, soporte premium
- Riesgo: difícil escalar ingresos

**Licencia perpetua (per-device):**
- Familiar para el mercado de captura documental
- Competitivo frente a ABBYY (15K+) y Kofax
- Precio sugerido: 299 EUR/dispositivo (incluye 1 año de actualizaciones)
- Renovación soporte: 59 EUR/año

**Suscripción mensual:**
- Ingresos recurrentes predecibles
- Precio sugerido: 39 EUR/usuario/mes
- Incluye actualizaciones + soporte
- Riesgo: mercado de captura documental acostumbrado a perpetuas

**Open Core (recomendado para fase 2):**
- Community Edition: gratuita, funcionalidad completa de captura + pipeline
- Professional Edition: AI MODE avanzado, prioridad en soporte, scripts premium
- Precio Pro: 249 EUR/año por dispositivo
- Máxima adopción + monetización sostenible

**Pay-per-document:**
- Requiere infraestructura de conteo/telemetría
- Complejo de implementar y auditar
- Solo viable con volúmenes altos (>100K docs/mes)

---

## 4. Análisis competitivo

### 4.1 Competidores principales

| Producto | Precio | Fortalezas | Debilidades |
|----------|--------|-----------|-------------|
| **ABBYY FlexiCapture** | 15K-300K EUR/año | Líder del mercado, OCR premium | Caro, pesado, solo Windows |
| **Kofax PowerPDF** | 129-179 EUR/lic | Buena integración Office | PDF-centric, no pipeline |
| **Flexibar.NET** | ~1K-5K EUR | Barcode + captura | Solo Windows, .NET legacy |
| **PaperStream Capture** | Bundled con Fujitsu | Integrado con escáneres | Solo Fujitsu, limitado |
| **DocScan Studio** | Gratis (actual) | Multiplataforma, pipeline composable, IA, open source | Nuevo, sin base instalada |

### 4.2 Posicionamiento

DocScan Studio se posiciona como **alternativa de precio medio-bajo** con diferenciadores:
- **Pipeline composable:** único en el segmento — cada paso configurable sin código
- **IA generativa integrada:** Anthropic + OpenAI para clasificación e indexación inteligente
- **Multiplataforma:** Linux + Windows (la mayoría de competidores son solo Windows)
- **Scripting Python:** extensibilidad sin límite para integradores
- **Open source base:** transparencia, auditabilidad, sin vendor lock-in

---

## 5. Plataformas de licencia

### 5.1 Comparativa

| Plataforma | Coste | Modelo | Self-hosting | SDK Python | Ideal para |
|------------|-------|--------|-------------|------------|------------|
| **Keygen.sh** | Free tier 100 usuarios, luego desde 49$/mes | API REST | Sí (Enterprise) | Sí | Startups, SaaS |
| **Cryptolens** | Desde 0 (community) | API REST | No | Sí | Software desktop |
| **LicenseSpring** | Desde 199$/mes | API REST | No | Sí (limitado) | Enterprise |
| **DIY (JWT+RSA)** | ~30$/mes hosting | Custom | Sí | Custom | Control total |

### 5.2 Recomendación

**Fase A (gratuita):** No necesita plataforma de licencia.

**Fase B (Open Core):** **Keygen.sh** por:
- Free tier suficiente para arrancar (100 máquinas)
- SDK Python oficial
- Licencias offline (important para entornos sin internet)
- Self-hosting disponible si se escala
- Validación por fingerprint de máquina

Alternativa: **Cryptolens** si se prefiere coste cero inicial con menos features.

---

## 6. Plataformas de venta

| Plataforma | Comisión | Fortalezas | Debilidades |
|------------|----------|-----------|-------------|
| **Lemon Squeezy** | 5% + 0.50$ | Diseñado para software, licencias automáticas | Relativamente nuevo |
| **Paddle** | ~5% + fees | Revenue delivery (gestión fiscal global) | Orientado a SaaS |
| **Gumroad** | 10% + 0.50$ | Simple, conocido | Caro, en declive |
| **Stripe directo** | 2.9% + 0.30$ | Máximo control, mínima comisión | Requiere web propia |
| **Web propia + Stripe** | 2.9% + 0.30$ | Control total | Más desarrollo |

**Recomendación:** **Lemon Squeezy** para arrancar (facturación internacional automática, gestión de IVA), migrar a **web propia + Stripe** cuando el volumen lo justifique.

---

## 7. Protección de código

### 7.1 Opciones analizadas

| Método | Eficacia | Coste | Impacto rendimiento | Complejidad |
|--------|----------|-------|-------------------|-------------|
| **Nuitka** (compilar a C) | Alta | Gratis (MIT) | Ninguno (más rápido) | Media |
| **PyArmor** (ofuscación) | Media | 49-249$/año | Mínimo | Baja |
| **Cython** (módulos críticos) | Media-Alta | Gratis | Ninguno | Alta |
| **Sin protección** | N/A | 0 | Ninguno | Ninguna |

### 7.2 Realidad del mercado

La protección total de código Python es **prácticamente imposible**. Cualquier solución puede ser revertida con suficiente esfuerzo. El enfoque correcto es:

1. **Hacer que pagar sea más fácil que piratear** — buen precio, buena experiencia
2. **El valor está en el servicio:** actualizaciones, soporte, documentación
3. **Protección razonable, no absoluta** — dificultar el uso casual sin licencia

### 7.3 Recomendación

- **Fase A:** Sin protección (open source)
- **Fase B:** Nuitka para la Professional Edition (compilación a C, mejor rendimiento, dificulta la ingeniería inversa sin impacto negativo)

---

## 8. Estrategia recomendada

### Fase A — Distribución gratuita (inmediato)

**Objetivo:** Captar usuarios, obtener feedback, construir comunidad.

- Distribuir como open source (licencia MIT o Apache 2.0)
- AppImage para Linux + Inno Setup para Windows
- GitHub Releases para distribución
- Documentación completa (ya existente)
- Soporte via GitHub Issues

**Duración estimada:** 3-6 meses
**Coste:** 0 EUR
**Ingresos:** 0 EUR directos (indirectos por consultoría posible)

### Fase B — Open Core con Professional Edition

**Objetivo:** Monetización sostenible manteniendo la base open source.

**Community Edition (gratuita):**
- Captura y escaneo
- Pipeline completo (image_op, barcode, ocr, script)
- Transferencia a carpeta/PDF
- Un proveedor de IA (OpenAI o Anthropic)
- Actualizaciones de seguridad

**Professional Edition (249 EUR/año por dispositivo):**
- Todo lo de Community +
- AI MODE avanzado (múltiples proveedores simultáneos)
- Transferencia avanzada (FTP, API REST, bases de datos)
- Modo directo (headless) para automatización
- Scripts premium preconstruidos (clasificación, separación, indexación)
- Soporte prioritario (email, 48h SLA)
- Actualizaciones de funcionalidad

### Desglose de features por edición

| Feature | Community | Professional |
|---------|:---------:|:------------:|
| Escaneo / importación | Sí | Sí |
| Pipeline composable | Sí | Sí |
| Reconocimiento de barcode | Sí | Sí |
| OCR (RapidOCR + Tesseract) | Sí | Sí |
| Scripts personalizados | Sí | Sí |
| Exportación PDF/carpeta | Sí | Sí |
| AI MODE (1 proveedor) | Sí | Sí |
| AI MODE multi-proveedor | — | Sí |
| Transferencia FTP/API/BD | — | Sí |
| Modo directo (headless) | — | Sí |
| Scripts premium | — | Sí |
| Soporte prioritario | — | Sí |
| Actualizaciones funcionales | 6 meses | Ilimitadas |

### Proyección de ingresos a 12 meses

| Escenario | Usuarios Community | Conversión Pro | Ingresos anuales |
|-----------|-------------------|---------------|-----------------|
| **Conservador** | 200 | 5% (10) | 2.490 EUR |
| **Moderado** | 500 | 8% (40) | 9.960 EUR |
| **Optimista** | 1.000 | 10% (100) | 24.900 EUR |

*Nota: Excluye ingresos por consultoría/formación, que podrían duplicar estas cifras.*

---

## 9. Hoja de ruta de implementación

### Calendario

| Hito | Fecha objetivo | Descripción |
|------|---------------|-------------|
| v0.1.0 | Abril 2026 | Primera release pública (Fase A) |
| Documentación + web | Abril 2026 | Landing page, docs completas |
| Feedback loop | Abril-Julio 2026 | Recoger feedback, iterar |
| v0.2.0 | Junio 2026 | Mejoras basadas en feedback |
| Integración Keygen.sh | Julio 2026 | Sistema de licencias |
| v1.0.0 Pro | Agosto 2026 | Lanzamiento Professional Edition |
| Marketing | Agosto 2026 | Product Hunt, Hacker News, foros especializados |

### Recursos necesarios

| Concepto | Coste estimado |
|----------|---------------|
| Desarrollo (interno) | 0 EUR (equipo actual) |
| Dominio + hosting web | 120 EUR/año |
| Keygen.sh (si >100 users) | 588 EUR/año |
| Lemon Squeezy (comisiones) | ~5% de ventas |
| Certificado code signing Windows | 200-400 EUR/año (opcional) |
| **Total arranque** | **~320 EUR** |

### ROI estimado

- **Inversión primer año:** ~1.000 EUR (hosting + licencia + code signing)
- **Ingresos escenario moderado:** ~10.000 EUR
- **ROI:** ~900%

---

## 10. Próximos pasos y decisiones pendientes

### Decisiones que requieren aprobación de dirección

1. **Licencia del código fuente:** ¿MIT, Apache 2.0 o propietaria?
2. **PyMuPDF:** ¿Adquirir licencia comercial o reemplazar?
3. **Certificado code signing:** ¿Invertir en firma de código para Windows?
4. **Modelo de negocio:** ¿Confirmar Open Core o preferir otro modelo?
5. **Plataforma de venta:** ¿Lemon Squeezy o alternativa?

### Acciones inmediatas (sin aprobación requerida)

- [x] Infraestructura de auto-actualización (completada)
- [x] Specs de PyInstaller para Linux y Windows
- [x] Script de Inno Setup para Windows
- [x] AppImage recipe para Linux
- [x] GitHub Actions CI/CD
- [ ] Primera release de prueba (`v0.1.0-rc1`)
- [ ] Verificación en máquina limpia (sin Python)
- [ ] Primera release pública (`v0.1.0`)

---

*Documento generado el 2026-03-26. Para consultas, contactar al equipo de desarrollo.*
