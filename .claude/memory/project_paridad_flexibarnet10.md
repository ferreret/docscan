---
name: project_paridad_flexibarnet10
description: "Requisito desde 2026-10-26 — DocScan debe seguir la misma lógica funcional que FlexibarNET10 (separadores, documento, transferencia…)"
metadata:
  node_type: memory
  type: project
  originSessionId: a3179c8e-b715-4850-bc31-8171d2fb96b8
  modified: 2026-10-26T12:37:32.781Z
---

Desde el 2026-10-26, Nicolás exige **paridad funcional con FlexibarNET10** (v1.30.0 en la
fecha del requisito). Lo dijo así: «tiene que funcionar igual que FlexibarNET10» y «ha de
seguir la misma lógica que FlexibarNET10». Lo primero que cubre son los separadores y el
documento lógico, pero vale como criterio general cuando DocScan y Flexibar resuelven lo
mismo.

**Why:** Flexibar está en producción en hospitales y ya pagó los errores de diseño. Por
ejemplo, su modelo de documento v0.5.0 se abandonó tras el smoke real. Nicolás quiere
que DocScan no los repita y que las Apps y la configuración se piensen igual en los dos
productos.

**How to apply:**
- La referencia es el **comportamiento documentado en el manual de Flexibar**. Cuando su
  código contradice su manual, se sigue el manual y se deja anotado. Ejemplos:
  `{separator}` en adjuntos y `{document_id}`, que en su código sale siempre vacío.
- Mismos nombres de claves de configuración (snake_case, `separator_*`), de tokens
  (`{separator}`, `{document_index}`, `{pagefield:}`) y de semántica (por ejemplo, el
  reproceso autoritativo).
- Las desviaciones solo con decisión explícita de Nicolás. La primera aceptada es
  `separator_page = include|exclude`, con `include` por defecto.
- El repo de Flexibar no está clonado de forma permanente. Para consultarlo:
  `gh repo clone $(gh api user/repos --paginate -q '.[].full_name' | grep '/FlexibarNET10$') -- --depth=400` en el scratchpad.
- Diseño de referencia: `docs/diseno_separadores_documento_2026-10-26.md`. Propuestas
  generales: `docs/propuestas_desde_flexibarnet10_2026-10-26.md`.

Relacionado: [[project_propuestas_flexibarnet10]], [[feedback_alinear_sin_pedir_ok]].
