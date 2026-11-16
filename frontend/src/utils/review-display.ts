/**
 * Shared display helpers for the review history list and the review
 * detail page. These functions never throw on unknown enum values; they
 * fall back to a neutral tag or a placeholder.
 */
export type TagType = 'success' | 'warning' | 'danger' | 'info'

const PLACEHOLDER = '—'

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return PLACEHOLDER
  }
  return value.replace('T', ' ').replace(/\.\d+$/, '')
}

export function formatCount(value: number | null | undefined): string {
  return typeof value === 'number' && Number.isFinite(value)
    ? String(value)
    : PLACEHOLDER
}

/** List style: `Summary #900` / `No summary`. */
export function formatSummaryComment(
  value: number | null | undefined,
  emptyLabel = 'No summary',
): string {
  return typeof value === 'number' && Number.isFinite(value)
    ? `Summary #${value}`
    : emptyLabel
}

/** Detail style: `#900` / `Not available`. */
export function formatSummaryCommentId(
  value: number | null | undefined,
  emptyLabel = 'Not available',
): string {
  return typeof value === 'number' && Number.isFinite(value)
    ? `#${value}`
    : emptyLabel
}

export function formatText(value: string | null | undefined): string {
  return value && value.trim() ? value : PLACEHOLDER
}

/** Formats a 0.0–1.0 confidence as a percentage without ever emitting NaN. */
export function formatConfidence(value: number | null | undefined): string {
  if (
    typeof value !== 'number'
    || !Number.isFinite(value)
    || value < 0
    || value > 1
  ) {
    return PLACEHOLDER
  }
  return `${Math.round(value * 100)}%`
}

export function formatLineRange(
  startLine: number | null | undefined,
  endLine: number | null | undefined,
): string {
  const start = startLine
  const end = endLine
  if (
    typeof start !== 'number'
    || typeof end !== 'number'
    || !Number.isInteger(start)
    || !Number.isInteger(end)
    || start < 1
    || end < 1
  ) {
    return PLACEHOLDER
  }
  return start === end ? `L${start}` : `L${start}–${end}`
}

export function taskStatusType(status: string): TagType {
  switch (status) {
    case 'COMPLETED':
      return 'success'
    case 'FAILED':
      return 'danger'
    case 'RUNNING':
      return 'warning'
    default:
      return 'info'
  }
}

export function aiStatusType(status: string): TagType {
  switch (status) {
    case 'COMPLETED':
      return 'success'
    case 'DEGRADED':
      return 'warning'
    default:
      return 'info'
  }
}

export function publishStatusType(status: string): TagType {
  switch (status) {
    case 'PUBLISHED':
      return 'success'
    case 'PARTIAL':
      return 'warning'
    case 'FAILED':
      return 'danger'
    default:
      return 'info'
  }
}

export function severityType(severity: string): TagType {
  switch (severity) {
    case 'CRITICAL':
    case 'HIGH':
      return 'danger'
    case 'MEDIUM':
      return 'warning'
    case 'LOW':
    case 'INFO':
    default:
      return 'info'
  }
}

export function categoryType(category: string): TagType {
  switch (category) {
    case 'SECURITY':
      return 'danger'
    case 'BUG':
    case 'PERFORMANCE':
      return 'warning'
    case 'QUALITY':
    default:
      return 'info'
  }
}
