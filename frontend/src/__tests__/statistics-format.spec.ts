import { describe, expect, it } from 'vitest'

import {
  formatBucketLabel,
  formatDateOnly,
  formatDecimal,
  formatLocalDateTime,
  formatMetricNumber,
  formatRatio,
  formatStatisticsRange,
  formatStatusLabel,
  formatTrendBucketLabel,
} from '@/utils/statistics-format'

describe('statistics formatting', () => {
  it('formats integer counters and placeholders', () => {
    expect(formatMetricNumber(0)).toBe('0')
    expect(formatMetricNumber(48)).toBe('48')
    expect(formatMetricNumber(null)).toBe('—')
    expect(formatMetricNumber(undefined)).toBe('—')
    expect(formatMetricNumber(Number.NaN)).toBe('—')
    expect(formatMetricNumber(Number.POSITIVE_INFINITY)).toBe('—')
  })

  it('formats averages and medians with one decimal', () => {
    expect(formatDecimal(9.6)).toBe('9.6')
    expect(formatDecimal(1)).toBe('1.0')
    expect(formatDecimal(null)).toBe('—')
    expect(formatDecimal(Number.NaN)).toBe('—')
    expect(formatDecimal(1.234, 2)).toBe('1.23')
  })

  it('formats ratios as percentages and never turns a null denominator into 0%', () => {
    expect(formatRatio(0)).toBe('0%')
    expect(formatRatio(0.2)).toBe('20%')
    expect(formatRatio(0.3958333333333333)).toBe('39.6%')
    expect(formatRatio(0.1234)).toBe('12.3%')
    expect(formatRatio(null)).toBe('—')
    expect(formatRatio(undefined)).toBe('—')
    expect(formatRatio(Number.NaN)).toBe('—')
  })

  it('labels known and unknown distribution buckets without discarding raw values', () => {
    expect(formatBucketLabel('BUG')).toBe('Bug')
    expect(formatBucketLabel('PERFORMANCE')).toBe('Performance')
    expect(formatBucketLabel('UNKNOWN')).toBe('Unknown')
    expect(formatBucketLabel('unknown')).toBe('Unknown')
    expect(formatBucketLabel('MYSTERY')).toBe('Unknown (MYSTERY)')
    expect(formatBucketLabel('  MYSTERY  ')).toBe('Unknown (MYSTERY)')
    expect(formatBucketLabel('')).toBe('—')
  })

  it('labels review statuses while preserving the stored unknown value', () => {
    expect(formatStatusLabel('COMPLETED')).toBe('Completed')
    expect(formatStatusLabel('DEGRADED')).toBe('Degraded')
    expect(formatStatusLabel('UNKNOWN')).toBe('Unknown (UNKNOWN)')
    expect(formatStatusLabel('MYSTERY')).toBe('Unknown (MYSTERY)')
    expect(formatStatusLabel(null)).toBe('—')
  })

  it('formats application-local timestamps without browser time-zone conversion', () => {
    expect(formatDateOnly('2026-11-01T10:00:00')).toBe('2026-11-01')
    expect(formatDateOnly('2026-11-01')).toBe('2026-11-01')
    expect(formatDateOnly(null)).toBe('—')

    expect(formatTrendBucketLabel('2026-11-01')).toBe('11-01')
    expect(formatLocalDateTime('2026-11-01T10:00:00.123456')).toBe(
      '2026-11-01 10:00:00',
    )
    expect(formatLocalDateTime(null)).toBe('—')

    expect(
      formatStatisticsRange(
        '2026-10-15T00:00:00',
        '2026-11-13T23:59:59.999999',
      ),
    ).toBe('2026-10-15 00:00:00 to 2026-11-13 23:59:59')
  })
})
