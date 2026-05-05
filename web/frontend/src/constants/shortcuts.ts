/**
 * Catálogo único de atajos de teclado del Workbench web.
 * Usado tanto por useWorkbenchShortcuts como por ShortcutsHelpDialog.
 */

export type ShortcutCategory = "batch" | "edit" | "nav" | "zoom";

export type ShortcutAction =
  | "runPipeline"
  | "transfer"
  | "closeBatch"
  | "openHelp"
  | "rotate"
  | "toggleReview"
  | "toggleExcluded"
  | "reprocessPage"
  | "insertBarcode"
  | "deletePage"
  | "prevPage"
  | "nextPage"
  | "nextReviewPage"
  | "navigateScript"
  | "zoom100"
  | "zoomIn"
  | "zoomOut"
  | "fitPage";

export interface ShortcutDef {
  /** Tecla en formato KeyboardEvent.key (o sintético: "Shift+ArrowRight"). */
  key: string;
  /** Identificador del handler que se llamará (mapping en WorkbenchView). */
  action: ShortcutAction;
  /** Texto humano para el cheatsheet. */
  label: string;
  /** Categoría para el modal. */
  category: ShortcutCategory;
  /** True si requiere !isReadOnly para ejecutarse. */
  editOnly: boolean;
  /** Label amigable de la tecla (para el <kbd>). */
  display: string;
}

export const SHORTCUTS: ShortcutDef[] = [
  {
    key: "F5",
    action: "runPipeline",
    label: "Ejecutar pipeline",
    category: "batch",
    editOnly: true,
    display: "F5",
  },
  {
    key: "t",
    action: "transfer",
    label: "Transferir lote",
    category: "batch",
    editOnly: true,
    display: "T",
  },
  {
    key: "w",
    action: "closeBatch",
    label: "Cerrar lote",
    category: "batch",
    editOnly: false,
    display: "W",
  },
  {
    key: "Escape",
    action: "closeBatch",
    label: "Cerrar lote",
    category: "batch",
    editOnly: false,
    display: "Esc",
  },
  {
    key: "?",
    action: "openHelp",
    label: "Abrir ayuda",
    category: "batch",
    editOnly: false,
    display: "?",
  },
  {
    key: "h",
    action: "openHelp",
    label: "Abrir ayuda",
    category: "batch",
    editOnly: false,
    display: "H",
  },

  {
    key: "r",
    action: "rotate",
    label: "Rotar página 90°",
    category: "edit",
    editOnly: true,
    display: "R",
  },
  {
    key: "m",
    action: "toggleReview",
    label: "Toggle revisión",
    category: "edit",
    editOnly: true,
    display: "M",
  },
  {
    key: "x",
    action: "toggleExcluded",
    label: "Toggle excluida",
    category: "edit",
    editOnly: true,
    display: "X",
  },
  {
    key: "p",
    action: "reprocessPage",
    label: "Reprocesar página",
    category: "edit",
    editOnly: true,
    display: "P",
  },
  {
    key: "b",
    action: "insertBarcode",
    label: "Añadir barcode",
    category: "edit",
    editOnly: true,
    display: "B",
  },
  {
    key: "Delete",
    action: "deletePage",
    label: "Eliminar página",
    category: "edit",
    editOnly: true,
    display: "Del",
  },

  {
    key: "ArrowLeft",
    action: "prevPage",
    label: "Página anterior",
    category: "nav",
    editOnly: false,
    display: "←",
  },
  {
    key: "ArrowRight",
    action: "nextPage",
    label: "Página siguiente",
    category: "nav",
    editOnly: false,
    display: "→",
  },
  {
    key: "Shift+ArrowRight",
    action: "nextReviewPage",
    label: "Siguiente con revisión",
    category: "nav",
    editOnly: false,
    display: "Shift+→",
  },
  {
    key: "Ctrl+g",
    action: "navigateScript",
    label: "Script de navegación",
    category: "nav",
    editOnly: false,
    display: "Ctrl+G",
  },

  {
    key: "0",
    action: "zoom100",
    label: "Zoom 100%",
    category: "zoom",
    editOnly: false,
    display: "0",
  },
  {
    key: "+",
    action: "zoomIn",
    label: "Zoom in",
    category: "zoom",
    editOnly: false,
    display: "+",
  },
  {
    key: "-",
    action: "zoomOut",
    label: "Zoom out",
    category: "zoom",
    editOnly: false,
    display: "−",
  },
  {
    key: "f",
    action: "fitPage",
    label: "Fit to page",
    category: "zoom",
    editOnly: false,
    display: "F",
  },
];

export const CATEGORY_LABELS: Record<ShortcutCategory, string> = {
  batch: "Lote",
  edit: "Edición",
  nav: "Navegación",
  zoom: "Zoom",
};

/**
 * Convierte un KeyboardEvent en el string sintético que usamos como índice.
 * Reglas:
 * - F5, Escape, ArrowLeft, ArrowRight, Delete: se devuelven tal cual.
 * - Shift+ArrowRight: combinación especial.
 * - Ctrl+g: Ctrl + letra minúscula.
 * - ?, +, -, 0, r, m, x, t, w, p, b, h, f: tecla tal cual (minúscula).
 */
export function eventToKeyString(event: KeyboardEvent): string {
  const k = event.key;
  if (k === "ArrowRight" && event.shiftKey) return "Shift+ArrowRight";
  if (event.ctrlKey && !event.shiftKey && !event.altKey && k.length === 1) {
    return `Ctrl+${k.toLowerCase()}`;
  }
  if (["F5", "Escape", "ArrowLeft", "ArrowRight", "Delete"].includes(k))
    return k;
  if (k.length === 1) return k.toLowerCase() === k ? k : k.toLowerCase();
  return k;
}

/**
 * Devuelve la ShortcutDef que coincide con el evento, o null.
 */
export function matchShortcut(event: KeyboardEvent): ShortcutDef | null {
  const keyStr = eventToKeyString(event);
  return SHORTCUTS.find((s) => s.key === keyStr) || null;
}
