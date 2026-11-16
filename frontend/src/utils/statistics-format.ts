import { formatDateTime } from '@/utils/review-display'

const PLACEHOLDER = '—'

const BUCKET_LABELS: Record<string, string> = {
  BUG: 'Bug',
  SECURITY: 'Security',
  PERFORMANCE: 'Performance',
  QUALITY: 'Quality',
  CRITICAL: 'Critical',
  HIGH: 'High',
  MEDIUM: 'Medium',
  LOW: 'Low',
  INFO: 'Info',
  COMPLETED: 'Completed',
  DEGRADED: 'Degraded',
  PUBLISHED: 'Published',
  PARTIAL: 'Partial',
  FAILED: 'Failed',
  PENDING: 'Pending',
  RUNNING: 'Running',
}

/**
 * Formats an integer counter without ever emitting `NaN`. A missing or
 * non-finite backend value is shown as an em dash.
 */
export function formatMetricNumber(
  value: number | null | undefined,
): string {
  return typeof value === 'number' && Number.isFinite(value)
    ? String(value)
    : PLACEHOLDER
}

/** Formats an average or median with one decimal. Null means "no sample". */
export function formatDecimal(
  value: number | null | undefined,
  fractionDigits = 1,
): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return PLACEHOLDER
  }
  return value.toFixed(fractionDigits)
}

/**
 * Formats a 0.0–1.0 ratio as a percentage. A null ratio means the backend had
 * no denominator; it is rendered as `—`, never as `0%`.
 */
export function formatRatio(value: number | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return PLACEHOLDER
  }
  const percent = Math.round(value * 1000) / 10
  return Number.isInteger(percent)
    ? `${percent}%`
    : `${percent.toFixed(1)}%`
}

/**
 * Human-readable label for a distribution bucket. Known values are title
 * cased. `UNKNOWN` is shown as `Unknown`; any other stored value keeps its
 * original text inside the label instead of being dropped.
 */
export function formatBucketLabel(key: string): string {
  const raw = key.trim()
  if (!raw) {
    return PLACEHOLDER
  }
  if (raw.toUpperCase() === 'UNKNOWN') {
    return 'Unknown'
  }
  return BUCKET_LABELS[raw.toUpperCase()] ?? `Unknown (${raw})`
}

/**
 * Label for a raw status value returned on a review row. Unlike a bucket
 * label, this always preserves the stored value, including `UNKNOWN`.
 */
export function formatStatusLabel(value: string | null | undefined): string {
  const raw = value?.trim()
  if (!raw) {
    return PLACEHOLDER
  }
  if (raw.toUpperCase() === 'UNKNOWN') {
    return `Unknown (${raw})`
  }
  return BUCKET_LABELS[raw.toUpperCase()] ?? `Unknown (${raw})`
}

/** Returns `YYYY-MM-DD` without applying a browser time-zone conversion. */
export function formatDateOnly(value: string | null | undefined): string {
  if (!value) {
    return PLACEHOLDER
  }
  return value.length >= 10 ? value.slice(0, 10) : value
}

/** Compact x-axis label for a trend bucket (`MM-DD`). */
export function formatTrendBucketLabel(bucketStart: string): string {
  return formatDateOnly(bucketStart).slice(5)
}

/** Formats an application-local wall-clock timestamp without time-zone math. */
export function formatLocalDateTime(
  value: string | null | undefined,
): string {
  return formatDateTime(value)
}

/** Descriptive, accessible range label used by the trend chart. */
export function formatStatisticsRange(
  createdFrom: string,
  createdTo: string,
): string {
  return `${formatLocalDateTime(createdFrom)} to ${formatLocalDateTime(createdTo)}`
}
