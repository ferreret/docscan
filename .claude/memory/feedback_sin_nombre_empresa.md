---
name: feedback-sin-nombre-empresa
description: La empresa que comercializa FlexibarNET10 no se nombra en ningún sitio; DocScan es de Nicolás Barceló
metadata:
  type: feedback
---

DocScan Studio figura como **desarrollado por Nicolás Barceló**. La empresa que comercializa
FlexibarNET10 **no se nombra en ningún sitio**: README, aplicación (Acerca de, splash),
instaladores (editor de Inno Setup, id del AppImage, AppUserModelID), manual web, informes,
paquete del portfolio, código de la web archivada (el tenant especial es «Plataforma», slug
`plataforma`) ni memoria. Decisión de Nicolás del 2026-10-27, que sustituye a la del 2026-10-26
que permitía nombrarla en el portfolio.

**Why:** Nicolás no quiere asociar el proyecto a esa empresa; el proyecto es suyo.

**How to apply:** FlexibarNET10 y sus hospitales (p. ej. el Arnau de Vilanova) sí se pueden
nombrar. Para referirse al producto, «un producto de captura documental en .NET». Las rutas
locales que llevan el nombre se escriben como `<carpeta>`; el repo privado de Flexibar se
localiza con `gh api user/repos --paginate -q '.[].full_name' | grep '/FlexibarNET10$'`.
Antes de cada commit, `git grep -i` del nombre debe salir vacío. El historial de git y los
binarios de releases ya publicadas (≤ v0.1.8) aún lo contienen. Ver [[project_ficha_portfolio]].
