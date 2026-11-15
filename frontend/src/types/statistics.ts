import type {
  AiStatus,
  PublishStatus,
  ReviewPage,
  TaskStatus,
} from '@/types/api'

/** Granularity supported by `GET /api/dashboard/statistics/overview`. */
export type StatisticsGranularity = 'DAY' | 'WEEK'

/** Sort whitelist supported by `GET /api/dashboard/statistics/reviews`. */
export type StatisticsSort =
  | 'createdAt'
  | 'actualFindingCount'
  | 'highSeverityFindingCount'
  | 'actualCommentCount'

export type StatisticsSortDirection = 'asc' | 'desc'

/**
 * Exact-match filters shared by both statistics endpoints. They follow the
 * same semantics as the Review History filters: trimmed exact matches and
 * inclusive application-local wall-clock date bounds.
 */
export interface StatisticsFilters {
  owner?: string
  repo?: string
  prNumber?: number
  taskStatus?: TaskStatus
  publishStatus?: PublishStatus
  aiStatus?: AiStatus
  createdFrom?: string
  createdTo?: string
}

export interface StatisticsOverviewQuery extends StatisticsFilters {
  granularity: StatisticsGranularity
}

export interface StatisticsReviewsQuery extends StatisticsFilters {
  page: number
  size: number
  sort: StatisticsSort
  direction: StatisticsSortDirection
}

/** One ordered distribution bucket returned by the backend. */
export interface StatisticsCount {
  key: string
  count: number
}

export interface StatisticsRange {
  createdFrom: string
  createdTo: string
  zoneId: string
  granularity: StatisticsGranularity
}

/**
 * Overview summary. Ratios and averages are `null` when their denominator is
 * zero; `null` means "no sample", not "0%".
 */
export interface StatisticsSummary {
  reviewCount: number
  findingStatsReviewCount: number
  findingCount: number
  averageFindingsPerReview: number | null
  medianFindingsPerReview: number | null
  maxFindingsInReview: number | null
  reviewsWithFindings: number
  reviewsWithFindingsRatio: number | null
  highSeverityFindingCount: number
  highSeverityRatio: number | null
  commentStatsReviewCount: number
  publishedInlineCommentCount: number
  reviewsWithInlineComments: number
  reviewsWithInlineCommentsRatio: number | null
  summaryCommentIdPresentCount: number
  categoryCounts: StatisticsCount[]
  severityCounts: StatisticsCount[]
  publishStatusCounts: StatisticsCount[]
  aiStatusCounts: StatisticsCount[]
}

export interface StatisticsTrendPoint {
  bucketStart: string
  bucketEnd: string
  reviewCount: number
  findingCount: number
  highSeverityFindingCount: number
  bugCount: number
  securityCount: number
  performanceCount: number
  qualityCount: number
  unknownCategoryCount: number
}

export interface StatisticsTrend {
  granularity: StatisticsGranularity
  hasData: boolean
  points: StatisticsTrendPoint[]
}

/**
 * Explicit disclosure of reports excluded from Finding or comment aggregates,
 * plus the number of stored values outside the known enumerations.
 */
export interface StatisticsDataQuality {
  totalReportCount: number
  findingsConsistentReportCount: number
  commentsConsistentReportCount: number
  reportsExcludedFromFindingStats: number
  reportsExcludedFromCommentStats: number
  unknownCategoryFindingCount: number
  unknownSeverityFindingCount: number
  unknownAiStatusReportCount: number
  unknownPublishStatusReportCount: number
}

export interface StatisticsOverviewResponse {
  range: StatisticsRange
  generatedAt: string
  summary: StatisticsSummary
  trend: StatisticsTrend
  dataQuality: StatisticsDataQuality
}

/**
 * One row of the review comparison table. Status fields stay as raw strings
 * so a stored value outside the known union is preserved, never discarded by
 * the frontend.
 */
export interface StatisticsReviewItem {
  taskId: number
  owner: string
  repo: string
  prNumber: number
  commitSha: string
  createdAt: string
  taskStatus: string
  aiStatus: string
  publishStatus: string
  declaredFindingCount: number
  actualFindingCount: number
  findingsConsistent: boolean
  declaredCommentCount: number
  actualCommentCount: number
  commentsConsistent: boolean
  criticalCount: number
  highCount: number
  highSeverityFindingCount: number
  mediumCount: number
  lowCount: number
  infoCount: number
  unknownSeverityCount: number
  bugCount: number
  securityCount: number
  performanceCount: number
  qualityCount: number
  unknownCategoryCount: number
}

export type StatisticsReviewPage = ReviewPage<StatisticsReviewItem>
