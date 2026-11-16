/** Category buckets exposed by the backend trend point. */
export type CategoryTrendKey =
  | 'BUG'
  | 'SECURITY'
  | 'PERFORMANCE'
  | 'QUALITY'
  | 'UNKNOWN'

/** Numeric category counter on `StatisticsTrendPoint`. */
export type CategoryTrendField =
  | 'bugCount'
  | 'securityCount'
  | 'performanceCount'
  | 'qualityCount'
  | 'unknownCategoryCount'

export interface CategoryTrendSeries {
  key: CategoryTrendKey
  field: CategoryTrendField
  label: string
  color: string
  /** `null` means a solid line; every other series uses a distinct dash. */
  dasharray: string | null
}

/**
 * Display order and visual identity of the five category series. The dash
 * patterns matter: the chart must stay distinguishable without colour.
 */
export const CATEGORY_TREND_SERIES: readonly CategoryTrendSeries[] = [
  {
    key: 'BUG',
    field: 'bugCount',
    label: 'Bug',
    color: '#4f46e5',
    dasharray: null,
  },
  {
    key: 'SECURITY',
    field: 'securityCount',
    label: 'Security',
    color: '#dc2626',
    dasharray: '8 4',
  },
  {
    key: 'PERFORMANCE',
    field: 'performanceCount',
    label: 'Performance',
    color: '#b45309',
    dasharray: '2 4',
  },
  {
    key: 'QUALITY',
    field: 'qualityCount',
    label: 'Quality',
    color: '#047857',
    dasharray: '10 4 2 4',
  },
  {
    key: 'UNKNOWN',
    field: 'unknownCategoryCount',
    label: 'Unknown',
    color: '#64748b',
    dasharray: '4 4',
  },
]
