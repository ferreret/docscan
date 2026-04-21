// Wrapper de CodeMirror 6. Concentra todas las importaciones para
// que Vite genere un chunk separado al ser importado dinámicamente.

import { EditorState } from '@codemirror/state'
import { EditorView, keymap, lineNumbers, highlightActiveLine } from '@codemirror/view'
import { defaultKeymap, indentWithTab, history, historyKeymap } from '@codemirror/commands'
import { indentOnInput, bracketMatching } from '@codemirror/language'
import { closeBrackets, closeBracketsKeymap } from '@codemirror/autocomplete'
import { autocompletion } from '@codemirror/autocomplete'
import type { CompletionContext, CompletionResult, Completion } from '@codemirror/autocomplete'
import { python } from '@codemirror/lang-python'
import { CONTEXT_VARIABLES } from '@/api/script-context-help'

export interface CreateEditorArgs {
  parent: HTMLElement
  initialDoc: string
  onChange: (doc: string) => void
}

export interface EditorHandle {
  view: EditorView
  insertAtCursor: (text: string) => void
  destroy: () => void
}

/** True si hay que prefijar `\n` al insertar texto en esa línea. */
export function shouldPrefixNewline(currentLineText: string): boolean {
  return currentLineText.trim().length > 0
}

/**
 * Dado un prefijo textual, devuelve las completions aplicables.
 * - "" → variables top-level
 * - "page."     → members de page
 * - "pipeline." → members de pipeline
 */
export function buildContextSuggestions(prefix: string): Completion[] {
  const dotMatch = prefix.match(/(\w+)\.$/)
  if (dotMatch) {
    const varName = dotMatch[1]
    const variable = CONTEXT_VARIABLES.find((v) => v.name === varName)
    if (variable?.members) {
      return variable.members.map((m) => ({
        label: m.name,
        type: m.signature ? 'method' : 'property',
        detail: m.signature,
        info: m.description,
      }))
    }
    return []
  }
  return CONTEXT_VARIABLES.map((v) => ({
    label: v.name,
    type: 'variable',
    info: v.summary,
  }))
}

function contextCompletions(context: CompletionContext): CompletionResult | null {
  const line = context.state.doc.lineAt(context.pos)
  const textBeforeCursor = line.text.slice(0, context.pos - line.from)

  const dotMatch = textBeforeCursor.match(/(\w+)\.(\w*)$/)
  if (dotMatch) {
    const base = dotMatch[1]
    const fragment = dotMatch[2]
    const suggestions = buildContextSuggestions(`${base}.`)
    if (suggestions.length === 0) return null
    return {
      from: context.pos - fragment.length,
      options: suggestions,
      validFor: /^\w*$/,
    }
  }

  const wordMatch = textBeforeCursor.match(/(\w+)$/)
  if (wordMatch) {
    return {
      from: context.pos - wordMatch[1].length,
      options: buildContextSuggestions(''),
      validFor: /^\w*$/,
    }
  }

  if (context.explicit) {
    return {
      from: context.pos,
      options: buildContextSuggestions(''),
      validFor: /^\w*$/,
    }
  }
  return null
}

const lightTheme = EditorView.theme(
  {
    '&': {
      fontSize: '13px',
      backgroundColor: '#fafafa',
      height: '100%',
    },
    '.cm-content': {
      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
      caretColor: '#1f2937',
    },
    '.cm-gutters': {
      backgroundColor: '#f3f4f6',
      color: '#9ca3af',
      border: 'none',
    },
    '.cm-activeLine': { backgroundColor: '#f1f5f9' },
    '.cm-activeLineGutter': { backgroundColor: '#e5e7eb' },
  },
  { dark: false },
)

export async function createEditor(args: CreateEditorArgs): Promise<EditorHandle> {
  const updateListener = EditorView.updateListener.of((update) => {
    if (update.docChanged) {
      args.onChange(update.state.doc.toString())
    }
  })

  const state = EditorState.create({
    doc: args.initialDoc,
    extensions: [
      lineNumbers(),
      highlightActiveLine(),
      history(),
      python(),
      indentOnInput(),
      bracketMatching(),
      closeBrackets(),
      autocompletion({ override: [contextCompletions] }),
      keymap.of([
        ...closeBracketsKeymap,
        ...defaultKeymap,
        ...historyKeymap,
        indentWithTab,
      ]),
      lightTheme,
      updateListener,
    ],
  })

  const view = new EditorView({ state, parent: args.parent })

  function insertAtCursor(text: string): void {
    const pos = view.state.selection.main.head
    const line = view.state.doc.lineAt(pos)
    const textBefore = line.text.slice(0, pos - line.from)
    const insert = shouldPrefixNewline(textBefore) ? `\n${text}` : text
    view.dispatch({ changes: { from: pos, insert } })
    view.focus()
  }

  function destroy(): void {
    view.destroy()
  }

  return { view, insertAtCursor, destroy }
}
