export interface HealthResponse {
  status: string
  service: string
}

export interface ApiErrorPayload {
  code?: string
  message?: string
  error?: string
}

export type TaskStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'

export type AiStatus = 'COMPLETED' | 'DEGRADED'

export type PublishStatus = 'PENDING' | 'PUBLISHED' | 'PARTIAL' | 'FAILED'

export type FindingCategory =
  | 'BUG'
  | 'SECURITY'
  | 'PERFORMANCE'
  | 'QUALITY'

export type FindingSeverity =
  | 'CRITICAL'
  | 'HIGH'
  | 'MEDIUM'
  | 'LOW'
  | 'INFO'

/**
 * One review report returned by the local Dashboard BFF
 * (`GET /api/dashboard/reviews`).
 */
export interface ReviewHistoryItem {
  taskId: number
  owner: string
  repo: string
  prNumber: number
  commitSha: string
  taskStatus: TaskStatus
  aiStatus: AiStatus
  publishStatus: PublishStatus
  findingCount: number
  publishedCommentCount: number
  summaryCommentId: number | null
  publishedAt: string | null
  createdAt: string
  updatedAt: string
}

export interface ReviewPage<T> {
  items: T[]
  page: number
  size: number
  totalItems: number
  totalPages: number
  hasNext: boolean
}

export type ReviewHistoryPage = ReviewPage<ReviewHistoryItem>

/** `GET /api/dashboard/reviews/{taskId}` returns the same report shape. */
export type ReviewDetailReport = ReviewHistoryItem

/**
 * One stored finding. `ordinal` is 0-based and stable inside a report.
 * `references` can contain `null` elements; display code must filter them.
 */
export interface ReviewFinding {
  ordinal: number
  category: FindingCategory
  severity: FindingSeverity
  confidence: number
  ruleId: string
  title: string
  filePath: string
  startLine: number
  endLine: number
  description: string
  reason: string
  suggestion: string
  references: Array<string | null>
}

/**
 * One inline comment confirmed as published to GitHub. Summary comments
 * are not part of this list, and comment bodies are not stored.
 */
export interface ReviewComment {
  findingOrdinal: number
  githubCommentId: number | null
  filePath: string
  startLine: number
  endLine: number
}

export type ReviewFindingPage = ReviewPage<ReviewFinding>

export type ReviewCommentPage = ReviewPage<ReviewComment>

/** Exact-match filters supported by the review history API. */
export interface ReviewHistoryFilters {
  owner?: string
  repo?: string
  prNumber?: number
  taskStatus?: TaskStatus
  aiStatus?: AiStatus
  publishStatus?: PublishStatus
  createdFrom?: string
  createdTo?: string
}

export interface ReviewHistoryQuery extends ReviewHistoryFilters {
  page: number
  size: number
}
