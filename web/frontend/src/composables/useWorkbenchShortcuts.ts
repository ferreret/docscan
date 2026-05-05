import { onMounted, onUnmounted } from "vue";
import {
  SHORTCUTS,
  matchShortcut,
  eventToKeyString,
  type ShortcutAction,
} from "@/constants/shortcuts";

interface ShortcutsOptions {
  handlers: Partial<Record<ShortcutAction, () => void | Promise<void>>>;
  isReadOnly: () => boolean;
  fireKeyEvent?: (key: string) => void;
}

/**
 * Captura keydown global y dispara handlers según el catálogo de shortcuts.
 *
 * - Ignora si el foco está en input/textarea/select/contenteditable o dentro
 *   de un [role=dialog].
 * - Respeta isReadOnly: las acciones con editOnly=true son no-op.
 * - Teclas no mapeadas con modificador (Ctrl/Alt/Meta) se reenvían como
 *   on_key_event vía fireKeyEvent.
 */
export function useWorkbenchShortcuts(options: ShortcutsOptions) {
  function isEditableTarget(target: EventTarget | null): boolean {
    // Cualquier diálogo modal abierto desactiva los atajos globales,
    // incluso si el foco se pierde y target queda en <body>. Esto evita
    // que con un dialog abierto (p.ej. AddBarcodeDialog) pulsar R rote
    // la página de fondo o Esc cierre el lote en vez del modal.
    if (document.querySelector('[role="dialog"][aria-modal="true"]'))
      return true;
    if (!(target instanceof HTMLElement)) return false;
    const tag = target.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
    if (
      target.isContentEditable ||
      target.getAttribute("contenteditable") === "true"
    )
      return true;
    if (target.closest('[role="dialog"]')) return true;
    return false;
  }

  function buildFallbackKeyString(event: KeyboardEvent): string {
    const k = event.key;
    const letter = k.length === 1 ? k.toLowerCase() : k;
    if (event.ctrlKey) return `Ctrl+${letter}`;
    if (event.altKey) return `Alt+${letter}`;
    if (event.metaKey) return `Meta+${letter}`;
    return eventToKeyString(event);
  }

  function onKeyDown(event: KeyboardEvent): void {
    if (isEditableTarget(event.target)) return;

    const shortcut = matchShortcut(event);
    if (shortcut) {
      if (shortcut.editOnly && options.isReadOnly()) {
        event.preventDefault();
        return;
      }
      event.preventDefault();
      const handler = options.handlers[shortcut.action];
      handler?.();
      return;
    }

    // No mapeada: si tiene modificador y hay fireKeyEvent, enviar como on_key_event.
    // Ignoramos si solo se pulsa el modificador (Alt, Control, Meta, Shift) para
    // evitar ruido — el evento se dispara al combinarlo con otra tecla.
    const isModifierAlone =
      event.key === "Alt" ||
      event.key === "Control" ||
      event.key === "Meta" ||
      event.key === "Shift";
    if (
      !isModifierAlone &&
      (event.ctrlKey || event.altKey || event.metaKey) &&
      options.fireKeyEvent
    ) {
      const keyStr = buildFallbackKeyString(event);
      options.fireKeyEvent(keyStr);
    }
  }

  onMounted(() => {
    document.addEventListener("keydown", onKeyDown, { capture: true });
  });

  onUnmounted(() => {
    document.removeEventListener("keydown", onKeyDown, { capture: true });
  });

  return { SHORTCUTS };
}
