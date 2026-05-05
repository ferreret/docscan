/**
 * Catálogo de estados de batch compartido entre el badge (representación
 * visual de un único batch) y los selectores de filtro (listado).
 *
 * Mantener este archivo como fuente única evita que las labels diverjan
 * (ej: "procesando…" en el badge vs "Procesando" en el filtro) y centraliza
 * el conocimiento de qué estados existen — un nuevo estado en backend
 * requiere un solo punto de edición.
 */

export type BatchState =
  | 'created'
  | 'running'
  | 'read'
  | 'transferring'
  | 'transferred'
  | 'error_read'

export interface BatchStateInfo {
  /** Identificador interno (literal del backend). */
  value: BatchState
  /** Etiqueta corta para el filtro (capitalizada). */
  filterLabel: string
  /** Etiqueta para el badge (puede llevar puntos suspensivos cuando indica
   *  acción en curso). */
  badgeLabel: string
  /** Clases Tailwind del badge. */
  badgeClass: string
  /** Indica que el estado es transitorio y el badge debe pulsar. */
  pulse?: boolean
}

export const BATCH_STATES: BatchStateInfo[] = [
  {
    value: 'created',
    filterLabel: 'Creado',
    badgeLabel: 'creado',
    badgeClass: 'bg-warning-soft text-warning border-warning/30',
  },
  {
    value: 'running',
    filterLabel: 'Procesando',
    badgeLabel: 'procesando…',
    badgeClass: 'bg-primary-soft text-primary border-primary/30',
    pulse: true,
  },
  {
    value: 'read',
    filterLabel: 'Procesado',
    badgeLabel: 'procesado',
    badgeClass: 'bg-primary-soft text-primary border-primary/30',
  },
  {
    value: 'transferring',
    filterLabel: 'Transfiriendo',
    badgeLabel: 'transfiriendo…',
    badgeClass: 'bg-warning-soft text-warning border-warning/30',
    pulse: true,
  },
  {
    value: 'transferred',
    filterLabel: 'Transferido',
    badgeLabel: 'transferido',
    badgeClass: 'bg-success-soft text-success border-success/30',
  },
  {
    value: 'error_read',
    filterLabel: 'Error',
    badgeLabel: 'error',
    badgeClass: 'bg-danger-soft text-danger border-danger/30',
  },
]

const BY_VALUE: ReadonlyMap<string, BatchStateInfo> = new Map(
  BATCH_STATES.map((s) => [s.value, s]),
)

/**
 * Devuelve la info de presentación de un estado. Para `error_*` desconocidos
 * (ej: `error_running`) cae al genérico de error. Para estados desconocidos
 * devuelve un descriptor neutro con el literal del backend.
 */
export function getBatchStateInfo(state: string): BatchStateInfo {
  const known = BY_VALUE.get(state)
  if (known) return known
  if (state.startsWith('error')) {
    return BY_VALUE.get('error_read')!
  }
  return {
    value: state as BatchState,
    filterLabel: state,
    badgeLabel: state,
    badgeClass: 'bg-mantle text-subtext border-surface-0',
  }
}
