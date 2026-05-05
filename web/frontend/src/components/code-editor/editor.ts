import { Compartment, EditorState } from '@codemirror/state'
import { EditorView, keymap, lineNumbers, highlightActiveLine } from '@codemirror/view'
import { defaultKeymap, indentWithTab, history, historyKeymap } from '@codemirror/commands'
import {
  indentOnInput,
  bracketMatching,
  HighlightStyle,
  syntaxHighlighting,
} from '@codemirror/language'
import { closeBrackets, closeBracketsKeymap } from '@codemirror/autocomplete'
import { autocompletion } from '@codemirror/autocomplete'
import type { CompletionContext, CompletionResult, Completion } from '@codemirror/autocomplete'
import { python } from '@codemirror/lang-python'
import { tags as t } from '@lezer/highlight'
import type { ContextVariable } from '@/api/script-context-help'

export interface CreateEditorArgs {
  parent: HTMLElement
  initialDoc: string
  contextVariables: ContextVariable[]
  onChange: (doc: string) => void
}

export interface EditorHandle {
  insertAtCursor: (text: string) => void
  setTheme: (theme: 'light' | 'dark') => void
  destroy: () => void
}

export function shouldPrefixNewline(currentLineText: string): boolean {
  return currentLineText.trim().length > 0
}

export function buildContextSuggestions(
  prefix: string,
  vars: ContextVariable[],
): Completion[] {
  const dotMatch = prefix.match(/([\w.]+)\.$/)
  if (dotMatch) {
    const varName = dotMatch[1]
    const variable = vars.find((v) => v.name === varName)
    if (!variable?.members) return []
    return variable.members.map((m) => ({
      label: m.name,
      type: m.signature ? 'method' : 'property',
      detail: m.signature,
      info: m.description,
    }))
  }
  return vars.map((v) => ({
    label: v.name,
    type: 'variable',
    info: v.summary,
  }))
}

function buildContextCompletions(vars: ContextVariable[]) {
  return (context: CompletionContext): CompletionResult | null => {
    const line = context.state.doc.lineAt(context.pos)
    const textBeforeCursor = line.text.slice(0, context.pos - line.from)

    const dotMatch = textBeforeCursor.match(/([\w.]+)\.(\w*)$/)
    if (dotMatch) {
      const suggestions = buildContextSuggestions(`${dotMatch[1]}.`, vars)
      if (suggestions.length === 0) return null
      return {
        from: context.pos - dotMatch[2].length,
        options: suggestions,
        validFor: /^\w*$/,
      }
    }

    const wordMatch = textBeforeCursor.match(/(\w+)$/)
    if (wordMatch) {
      return {
        from: context.pos - wordMatch[1].length,
        options: buildContextSuggestions('', vars),
        validFor: /^\w*$/,
      }
    }

    if (context.explicit) {
      return {
        from: context.pos,
        options: buildContextSuggestions('', vars),
        validFor: /^\w*$/,
      }
    }
    return null
  }
}

// ---------------------------------------------------------------------
// Themes y syntax highlighting
//
// El editor se monta dentro del configurador, que respeta el tema activo
// de la app (claro/oscuro). Antes solo había un lightTheme con fondo
// blanco aplicado siempre, por lo que sobre tema oscuro el editor se
// veía como una franja blanca incongruente y, peor, los tokens de syntax
// (colores oscuros por defecto) quedaban con bajo contraste si algún
// CSS global cambiaba el fondo. Ahora elegimos el theme según el
// `data-theme` de <html> al montar.
// ---------------------------------------------------------------------

const lightTheme = EditorView.theme(
  {
    '&': {
      fontSize: '13px',
      backgroundColor: '#fafafa',
      color: '#1f2937',
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
    '.cm-selectionMatch': { backgroundColor: '#dbeafe' },
    '.cm-matchingBracket': { backgroundColor: '#fde68a', outline: 'none' },
  },
  { dark: false },
)

const darkTheme = EditorView.theme(
  {
    '&': {
      fontSize: '13px',
      // Fondo levemente más claro que mantle/base para destacar el bloque
      // editable dentro del panel (que ya es bg-base oscuro).
      backgroundColor: '#1e293b',
      color: '#e2e8f0',
      height: '100%',
    },
    '.cm-content': {
      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
      caretColor: '#f1f5f9',
    },
    '.cm-gutters': {
      backgroundColor: '#0f172a',
      color: '#64748b',
      border: 'none',
    },
    '.cm-activeLine': { backgroundColor: '#334155' },
    '.cm-activeLineGutter': { backgroundColor: '#1e293b', color: '#cbd5e1' },
    '.cm-selectionBackground, ::selection': { backgroundColor: '#475569 !important' },
    '.cm-cursor': { borderLeftColor: '#f1f5f9' },
    '.cm-selectionMatch': { backgroundColor: '#3b82f680' },
    '.cm-matchingBracket': { backgroundColor: '#475569', outline: 'none', color: '#fde047' },
  },
  { dark: true },
)

// HighlightStyle para tema oscuro: colores saturados claros sobre fondo
// slate 800. Inspirado en One Dark / Tokyo Night.
const darkHighlightStyle = HighlightStyle.define([
  { tag: [t.keyword, t.modifier, t.controlKeyword], color: '#c084fc', fontWeight: '600' },
  { tag: [t.string, t.special(t.string)], color: '#86efac' },
  { tag: [t.number, t.bool, t.null, t.atom], color: '#fbbf24' },
  { tag: [t.comment, t.lineComment, t.blockComment], color: '#94a3b8', fontStyle: 'italic' },
  { tag: [t.function(t.variableName), t.function(t.propertyName)], color: '#60a5fa' },
  { tag: [t.definition(t.variableName), t.definition(t.function(t.variableName))], color: '#60a5fa' },
  { tag: [t.className, t.typeName], color: '#22d3ee' },
  { tag: [t.operator, t.derefOperator, t.compareOperator, t.logicOperator], color: '#fb7185' },
  { tag: [t.propertyName], color: '#a5b4fc' },
  { tag: [t.variableName], color: '#e2e8f0' },
  { tag: [t.bracket, t.paren, t.brace, t.squareBracket], color: '#cbd5e1' },
  { tag: [t.punctuation], color: '#94a3b8' },
  { tag: [t.invalid], color: '#f87171', textDecoration: 'underline wavy' },
])

// HighlightStyle para tema claro: tonos oscuros y saturados para
// contraste alto sobre fondo casi blanco (#fafafa). Inspirado en
// Solarized Light / GitHub Light. Las variables usan slate 900 casi
// negro porque eran ilegibles antes (#e2e8f0 sobre #fafafa).
const lightHighlightStyle = HighlightStyle.define([
  { tag: [t.keyword, t.modifier, t.controlKeyword], color: '#7c3aed', fontWeight: '600' },
  { tag: [t.string, t.special(t.string)], color: '#15803d' },
  { tag: [t.number, t.bool, t.null, t.atom], color: '#b45309' },
  { tag: [t.comment, t.lineComment, t.blockComment], color: '#64748b', fontStyle: 'italic' },
  { tag: [t.function(t.variableName), t.function(t.propertyName)], color: '#1d4ed8' },
  { tag: [t.definition(t.variableName), t.definition(t.function(t.variableName))], color: '#1d4ed8' },
  { tag: [t.className, t.typeName], color: '#0e7490' },
  { tag: [t.operator, t.derefOperator, t.compareOperator, t.logicOperator], color: '#be123c' },
  { tag: [t.propertyName], color: '#4338ca' },
  { tag: [t.variableName], color: '#0f172a' },
  { tag: [t.bracket, t.paren, t.brace, t.squareBracket], color: '#475569' },
  { tag: [t.punctuation], color: '#475569' },
  { tag: [t.invalid], color: '#dc2626', textDecoration: 'underline wavy' },
])

// El Compartment del tema agrupa la pareja (theme + highlightStyle)
// porque ambos cambian juntos al alternar claro↔oscuro.
function bundleFor(name: 'light' | 'dark') {
  if (name === 'dark') return [darkTheme, syntaxHighlighting(darkHighlightStyle)]
  return [lightTheme, syntaxHighlighting(lightHighlightStyle)]
}

function pickBundle() {
  try {
    return document.documentElement.dataset.theme === 'dark'
      ? bundleFor('dark')
      : bundleFor('light')
  } catch {
    return bundleFor('light')
  }
}

export async function createEditor(args: CreateEditorArgs): Promise<EditorHandle> {
  const updateListener = EditorView.updateListener.of((update) => {
    if (update.docChanged) {
      args.onChange(update.state.doc.toString())
    }
  })

  // Compartment del tema: permite cambiar light↔dark en caliente sin
  // recrear el editor ni perder el doc. Lo reconfigura `setTheme()`.
  const themeCompartment = new Compartment()

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
      autocompletion({ override: [buildContextCompletions(args.contextVariables)] }),
      keymap.of([
        ...closeBracketsKeymap,
        ...defaultKeymap,
        ...historyKeymap,
        indentWithTab,
      ]),
      themeCompartment.of(pickBundle()),
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

  function setTheme(name: 'light' | 'dark'): void {
    view.dispatch({
      effects: themeCompartment.reconfigure(bundleFor(name)),
    })
  }

  function destroy(): void {
    view.destroy()
  }

  return { insertAtCursor, setTheme, destroy }
}
