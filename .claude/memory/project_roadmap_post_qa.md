---
name: Roadmap post-QA web SaaS
description: Lista priorizada de features pendientes acordadas con el usuario el 2026-05-05 tras cerrar la bitácora QA. Cada item es candidato a sesión propia con brainstorming previo.
type: project
originSessionId: 5dba77bc-3e76-4326-b472-d97aff33c74e
---
Roadmap de features acordadas el 2026-05-05 para la web SaaS de DocScan, en orden de implementación.

**Why:** Tras cerrar la bitácora QA web 2026-04-27 (40 entradas, todos los hallazgos resueltos) y consolidar `feature/web` en `main`, el usuario priorizó las siguientes piezas para llegar a una primera versión SaaS publicable. Cada una es proyecto en sí mismo y merece sesión dedicada con plan previo.

**How to apply:** Empezar la próxima sesión preguntando al usuario por cuál atacar (probablemente superadmin/tenants, que es la base de plataforma). No mezclar varias en la misma sesión — cada una requiere brainstorming, plan TDD y verificación e2e separados.

## Orden propuesto

1. **Superadmin + creación de tenants y usuarios** (plataforma — base de todo lo demás)
   - Rol `superadmin` que controla todo (cross-tenant)
   - Onboarding: crear tenant + primer admin
   - UI de gestión global (lista tenants, suspender/borrar, cuotas)
   - Hoy `RegisterView` crea tenant+admin pero no hay control administrativo

2. **Cliente local web** (escáner TWAIN/SANE + transferencia local desde el navegador)
   - Agente local = `docscan_worker` + mini FastAPI según el plan original
   - Permite escanear desde el navegador a través del agente local instalado en la estación de trabajo
   - Transferencia desde cliente local web a destinos del PC del usuario
   - Reutiliza el código existente de `scanner_service.py` y `transfer_service.py`

3. **Editor de scripts web** (Monaco con syntax highlighting + run preview)
   - Hoy hay editor de eventos lifecycle, pero no de ScriptStep dentro del pipeline
   - Necesario para que un admin web pueda crear pipelines completos sin desktop

4. **Multiidioma (i18n)**
   - Frontend: vue-i18n con catálogos es/en mínimo
   - Backend: respuestas de error tienen labels en español hardcoded — extraer a catálogos
   - Desktop ya tiene infra de i18n con QSettings (`DocScanStudio/i18n/language`); aprender de ella

5. **Smoke test extenso e2e**
   - Cubrir TODAS las posibilidades antes de publicar
   - Multi-tenant cross-isolation, todos los pasos pipeline, todos los escenarios de error
   - Probablemente Playwright e2e + scripts curl + matriz de roles

6. **Primera versión SaaS publicable** (v0.2.0 web)
   - Nuevo workflow CI que construya/publique imagen Docker (GHCR) además del desktop
   - Doc de despliegue (docker compose en VPS, certificados, env vars)
   - Tag y release notes diferenciados del desktop

7. **AI Mode web** (último — confirmado por el usuario)
   - Reintroducir capacidades AI dentro del pipeline web (eliminadas en sesión 2026-03-20 del desktop)
   - Provider abstraction ya existente en `app/providers/`
   - Multi-tenant: gestión de API keys por tenant (Fernet encryption)

## Pendientes laterales (no bloquean)
- Barridos cosméticos: Prettier global (~120 archivos), ruff format global. No urgente, hacer en tooling-only commits para no contaminar funcionales.
- Verificación visual desktop v0.1.1/v0.1.2 en Windows (requiere otra máquina).
