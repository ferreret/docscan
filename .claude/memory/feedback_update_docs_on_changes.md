---
name: Actualizar docs en cada cambio
description: Tras cada cambio funcional, actualizar README.md y CHANGELOG.md antes de commit
type: feedback
---

Al hacer cambios en el código, actualizar siempre el README y CHANGELOG.md antes del commit final.

**Desde el 2026-10-27 el README es bilingüe** (decisión de Nicolás): `README.md` en inglés (el que muestra
GitHub) y `README.es.md` en castellano, con el mismo contenido. Un cambio va a los dos. Las cifras salen de
`docs/portfolio/metricas.md` (se vuelven a medir allí, no a ojo). El manual que se mantiene es el web
(`docs-web/`); el `.docx` se retiró. Ver [[project_ficha_portfolio]].

**Why:** El usuario quiere que la documentación pública esté siempre sincronizada con el estado real del proyecto. El README es el escaparate en GitHub y el CHANGELOG el historial para usuarios.

**How to apply:** Antes de hacer commit de cambios funcionales, revisar si afectan a README.md y README.es.md (métricas, features, screenshots) o CHANGELOG.md (nueva entrada o actualización de la sección en curso). Incluir las actualizaciones en el mismo commit o en uno inmediatamente posterior.
