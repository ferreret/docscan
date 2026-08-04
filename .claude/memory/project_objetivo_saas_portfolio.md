---
name: Versión web SaaS como pieza de portfolio del usuario
description: La versión web SaaS de DocScan es una pieza de portfolio profesional del usuario, alojada por él como servicio. Condiciona priorización cloud-first y experiencia visual cuidada.
type: project
originSessionId: 7b6bd88f-a10c-476b-a06b-b548ac8a163e
---
DocScan Studio Web SaaS no es solo un producto vendible — es **pieza de portfolio profesional del usuario**, alojada por él mismo (cloud) como un SaaS al que se accede desde internet. Decisión confirmada en sesión 2026-05-06.

**Why:** El usuario quiere mostrar la SaaS funcionando en su portfolio (probablemente `docscan.tecnomedia.es` o dominio similar). El producto desktop está en otro plano — clientes existentes y un programa estable. El SaaS web es la cara pública nueva.

**How to apply:**

1. **Cloud-first en el sprint del cliente local web**: el agente local debe resolver el caso cloud (servidor remoto que no ve la red del cliente) — descargar páginas para transferencia local, no solo subir al servidor.

2. **Cuidar la experiencia visual** del frontend web por encima de la funcional pura. La UI será evaluada por terceros (reclutadores, clientes potenciales, comunidad). Pixel-perfect y interacciones pulidas tienen valor de portfolio que no tendrían en producto interno.

3. **Demo pública accesible**: en algún momento habrá que tener un endpoint público (`docscan.tecnomedia.es` o similar) con datos demo y cuenta de prueba para visitantes. Considerar esto al planificar deploy y multi-tenancy.

4. **Documentación de arquitectura** importa: el usuario probablemente la mostrará a reclutadores. Diagramas claros, README profesional, manual MkDocs cuidado.

5. **No descuidar desktop**: la versión desktop sigue en producción con clientes reales y NO puede romperse al evolucionar la web. Esto sigue vigente (ver `feedback_no_romper_desktop.md`).

6. **Tag/release de la SaaS** cuando llegue v0.2.0: tag separado del desktop, release notes específicas, posible imagen Docker en GHCR para que cualquiera pueda desplegar su instancia.
