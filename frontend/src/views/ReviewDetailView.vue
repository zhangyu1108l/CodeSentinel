<script setup lang="ts">
import { ArrowLeft, Refresh, WarningFilled } from '@element-plus/icons-vue'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import {
  getReviewComments,
  getReviewDetail,
  getReviewFindings,
} from '@/api'
import type {
  ReviewComment,
  ReviewDetailReport,
  ReviewFinding,
} from '@/types/api'
import { toApiError } from '@/utils/api-error'
import {
  aiStatusType,
  categoryType,
  formatConfidence,
  formatCount,
  formatDateTime,
  formatLineRange,
  formatSummaryCommentId,
  formatText,
  publishStatusType,
  severityType,
  taskStatusType,
} from '@/utils/review-display'

type PageStatus =
  | 'loading'
  | 'ready'
  | 'invalid'
  | 'not-found'
  | 'incomplete'
  | 'error'

const PAGE_SIZES: number[] = [10, 20, 50, 100]
const DEFAULT_PAGE_SIZE = 20

const route = useRoute()

const pageStatus = ref<PageStatus>('loading')
const pageError = ref('')
const report = ref<ReviewDetailReport | null>(null)
const refreshing = ref(false)

const findings = ref<ReviewFinding[]>([])
const findingsPage = ref(1)
const findingsSize = ref(DEFAULT_PAGE_SIZE)
const findingsTotalItems = ref(0)
const findingsLoading = ref(false)
const findingsError = ref('')
const findingsIncomplete = ref(false)

const comments = ref<ReviewComment[]>([])
const commentsPage = ref(1)
const commentsSize = ref(DEFAULT_PAGE_SIZE)
const commentsTotalItems = ref(0)
const commentsLoading = ref(false)
const commentsError = ref('')
const commentsIncomplete = ref(false)

let reportController: AbortController | null = null
let findingsController: AbortController | null = null
let commentsController: AbortController | null = null
let reportSequence = 0
let findingsSequence = 0
let commentsSequence = 0
let disposed = false

const taskId = computed(() => parseTaskId(route.params.taskId))

const taskIdLabel = computed(() => {
  if (taskId.value !== null) {
    return String(taskId.value)
  }
  const raw = route.params.taskId
  const value = Array.isArray(raw) ? raw[0] : raw
  return typeof value === 'string' ? value : 'unknown'
})

const statusPillText = computed(() => {
  if (pageStatus.value === 'loading') {
    return 'Loading'
  }
  if (refreshing.value) {
    return 'Updating'
  }
  if (pageStatus.value === 'ready' && report.value) {
    return `${report.value.findingCount} ${
      report.value.findingCount === 1 ? 'finding' : 'findings'
    }`
  }
  switch (pageStatus.value) {
    case 'invalid':
      return 'Invalid review id'
    case 'not-found':
      return 'Not found'
    case 'incomplete':
      return 'Incomplete'
    case 'error':
      return 'Error'
    default:
      return ''
  }
})

const findingsEmptyDescription = computed(() =>
  findingsTotalItems.value > 0
    ? 'No findings on this page'
    : 'No findings stored for this review',
)

const commentsEmptyDescription = computed(() =>
  commentsTotalItems.value > 0
    ? 'No published comments on this page'
    : 'No published inline comments stored for this review',
)

function parseTaskId(raw: unknown): number | null {
  const value = Array.isArray(raw) ? raw[0] : raw
  if (typeof value !== 'string' || !/^\d+$/.test(value)) {
    return null
  }
  const parsed = Number(value)
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null
}

function resetFindingsState() {
  findings.value = []
  findingsPage.value = 1
  findingsSize.value = DEFAULT_PAGE_SIZE
  findingsTotalItems.value = 0
  findingsLoading.value = false
  findingsError.value = ''
  findingsIncomplete.value = false
}

function resetCommentsState() {
  comments.value = []
  commentsPage.value = 1
  commentsSize.value = DEFAULT_PAGE_SIZE
  commentsTotalItems.value = 0
  commentsLoading.value = false
  commentsError.value = ''
  commentsIncomplete.value = false
}

function resetDetailState() {
  report.value = null
  pageError.value = ''
  refreshing.value = false
  resetFindingsState()
  resetCommentsState()
}

function cancelReportRequest() {
  reportController?.abort()
  reportController = null
}

function cancelFindingsRequest() {
  findingsController?.abort()
  findingsController = null
}

function cancelCommentsRequest() {
  commentsController?.abort()
  commentsController = null
}

function cancelAllRequests() {
  reportSequence++
  findingsSequence++
  commentsSequence++
  cancelReportRequest()
  cancelFindingsRequest()
  cancelCommentsRequest()
}

function isCurrentReportRequest(
  controller: AbortController,
  sequence: number,
): boolean {
  return (
    !disposed
    && !controller.signal.aborted
    && sequence === reportSequence
  )
}

function isCurrentSectionRequest(
  controller: AbortController,
  sequence: number,
  currentSequence: number,
): boolean {
  return (
    !disposed
    && !controller.signal.aborted
    && sequence === currentSequence
  )
}

function applyReportError(error: unknown) {
  const apiError = toApiError(error)
  report.value = null

  if (apiError.status === 404 || apiError.code === 'review_not_found') {
    pageStatus.value = 'not-found'
    pageError.value = ''
    return
  }

  if (
    apiError.status === 409
    || apiError.code === 'review_history_incomplete'
  ) {
    pageStatus.value = 'incomplete'
    pageError.value = ''
    return
  }

  pageStatus.value = 'error'
  pageError.value = apiError.message
}

async function loadFindings(id: number) {
  cancelFindingsRequest()
  const controller = new AbortController()
  findingsController = controller
  const sequence = ++findingsSequence

  findingsLoading.value = true
  findingsError.value = ''
  findingsIncomplete.value = false

  try {
    const result = await getReviewFindings(
      id,
      { page: findingsPage.value, size: findingsSize.value },
      controller.signal,
    )
    if (!isCurrentSectionRequest(controller, sequence, findingsSequence)) {
      return
    }
    findings.value = result.items
    findingsPage.value = result.page
    findingsSize.value = result.size
    findingsTotalItems.value = result.totalItems
  } catch (error) {
    if (!isCurrentSectionRequest(controller, sequence, findingsSequence)) {
      return
    }
    const apiError = toApiError(error)
    findingsIncomplete.value =
      apiError.status === 409
      || apiError.code === 'review_history_incomplete'
    findingsError.value = findingsIncomplete.value
      ? 'The stored finding count does not match the stored findings. Partial data is not shown.'
      : apiError.message
  } finally {
    if (!disposed && sequence === findingsSequence) {
      findingsLoading.value = false
      if (findingsController === controller) {
        findingsController = null
      }
    }
  }
}

async function loadComments(id: number) {
  cancelCommentsRequest()
  const controller = new AbortController()
  commentsController = controller
  const sequence = ++commentsSequence

  commentsLoading.value = true
  commentsError.value = ''
  commentsIncomplete.value = false

  try {
    const result = await getReviewComments(
      id,
      { page: commentsPage.value, size: commentsSize.value },
      controller.signal,
    )
    if (!isCurrentSectionRequest(controller, sequence, commentsSequence)) {
      return
    }
    comments.value = result.items
    commentsPage.value = result.page
    commentsSize.value = result.size
    commentsTotalItems.value = result.totalItems
  } catch (error) {
    if (!isCurrentSectionRequest(controller, sequence, commentsSequence)) {
      return
    }
    const apiError = toApiError(error)
    commentsIncomplete.value =
      apiError.status === 409
      || apiError.code === 'review_history_incomplete'
    commentsError.value = commentsIncomplete.value
      ? 'The stored published-comment count does not match the stored comments. Partial data is not shown.'
      : apiError.message
  } finally {
    if (!disposed && sequence === commentsSequence) {
      commentsLoading.value = false
      if (commentsController === controller) {
        commentsController = null
      }
    }
  }
}

async function loadReport(id: number, mode: 'initial' | 'refresh') {
  cancelReportRequest()
  cancelFindingsRequest()
  cancelCommentsRequest()
  findingsSequence++
  commentsSequence++

  const controller = new AbortController()
  reportController = controller
  const sequence = ++reportSequence

  if (mode === 'initial') {
    pageStatus.value = 'loading'
    pageError.value = ''
  } else {
    refreshing.value = true
  }

  try {
    const result = await getReviewDetail(id, controller.signal)
    if (!isCurrentReportRequest(controller, sequence)) {
      return
    }

    report.value = result
    pageError.value = ''
    pageStatus.value = 'ready'

    if (mode === 'refresh') {
      await Promise.allSettled([
        loadFindings(id),
        loadComments(id),
      ])
    } else {
      void loadFindings(id)
      void loadComments(id)
    }
  } catch (error) {
    if (!isCurrentReportRequest(controller, sequence)) {
      return
    }
    applyReportError(error)
  } finally {
    if (!disposed && sequence === reportSequence) {
      if (mode === 'refresh') {
        refreshing.value = false
      }
      if (reportController === controller) {
        reportController = null
      }
    }
  }
}

async function initialise() {
  cancelAllRequests()
  resetDetailState()

  const id = taskId.value
  if (id === null) {
    pageStatus.value = 'invalid'
    return
  }

  await loadReport(id, 'initial')
}

function refresh() {
  const id = taskId.value
  if (id === null) {
    return
  }
  void loadReport(id, 'refresh')
}

function retryPage() {
  const id = taskId.value
  if (id === null) {
    return
  }
  void loadReport(id, report.value ? 'refresh' : 'initial')
}

function retryFindings() {
  const id = taskId.value
  if (id === null) {
    return
  }
  void loadFindings(id)
}

function retryComments() {
  const id = taskId.value
  if (id === null) {
    return
  }
  void loadComments(id)
}

function handleFindingsPageChange(nextPage: number) {
  if (nextPage === findingsPage.value || taskId.value === null) {
    return
  }
  findingsPage.value = nextPage
  void loadFindings(taskId.value)
}

function handleFindingsSizeChange(nextSize: number) {
  if (nextSize === findingsSize.value || taskId.value === null) {
    return
  }
  findingsSize.value = nextSize
  findingsPage.value = 1
  void loadFindings(taskId.value)
}

function handleCommentsPageChange(nextPage: number) {
  if (nextPage === commentsPage.value || taskId.value === null) {
    return
  }
  commentsPage.value = nextPage
  void loadComments(taskId.value)
}

function handleCommentsSizeChange(nextSize: number) {
  if (nextSize === commentsSize.value || taskId.value === null) {
    return
  }
  commentsSize.value = nextSize
  commentsPage.value = 1
  void loadComments(taskId.value)
}

function cleanReferences(
  references: Array<string | null> | null | undefined,
): string[] {
  if (!Array.isArray(references)) {
    return []
  }
  return references.filter(
    (reference): reference is string =>
      typeof reference === 'string' && reference.trim().length > 0,
  )
}

onMounted(() => {
  void initialise()
})

watch(
  () => route.params.taskId,
  () => {
    void initialise()
  },
)

onBeforeUnmount(() => {
  disposed = true
  cancelAllRequests()
})
</script>

<template>
  <div class="page detail-page">
    <div class="detail-nav">
      <RouterLink to="/reviews" class="back-link">
        <el-icon :size="14"><ArrowLeft /></el-icon>
        Back to review history
      </RouterLink>

      <div class="detail-nav__actions">
        <span
          class="status-pill"
          :class="{
            'status-pill--loading':
              pageStatus === 'loading' || refreshing,
          }"
        >
          <span class="status-pill__dot" />
          {{ statusPillText }}
        </span>

        <el-button
          v-if="pageStatus !== 'invalid' && pageStatus !== 'not-found'"
          :icon="Refresh"
          :loading="refreshing"
          :disabled="pageStatus === 'loading'"
          @click="refresh"
        >
          Refresh
        </el-button>
      </div>
    </div>

    <header class="page-heading detail-heading">
      <div>
        <p class="eyebrow">Review detail</p>
        <h1 class="page-title">Review #{{ taskIdLabel }}</h1>

        <p v-if="report" class="page-subtitle detail-subtitle">
          <span :title="`${report.owner}/${report.repo}`">
            {{ report.owner }}/{{ report.repo }}
          </span>
          <span class="subtitle-separator">·</span>
          <span>PR #{{ report.prNumber }}</span>
          <span class="subtitle-separator">·</span>
          <code class="commit-sha" :title="report.commitSha">
            {{ report.commitSha }}
          </code>
        </p>
        <p v-else class="page-subtitle">
          Stored review report, findings, and published comment metadata.
        </p>
      </div>
    </header>

    <div
      v-if="pageStatus === 'loading'"
      class="panel detail-loading"
      role="status"
      aria-label="Loading review detail"
    >
      <el-skeleton :rows="9" animated />
    </div>

    <section
      v-else-if="pageStatus === 'invalid' || pageStatus === 'not-found'"
      class="panel detail-state not-found-state"
      role="alert"
    >
      <span class="state-icon state-icon--danger">
        <el-icon :size="22"><WarningFilled /></el-icon>
      </span>

      <div class="state-copy">
        <h2 class="section-title">Review not found</h2>
        <p v-if="pageStatus === 'invalid'">
          This URL does not contain a valid positive review task ID, so no
          request was sent. Open a review from the history list instead.
        </p>
        <p v-else>
          No structured review history is available for this task. It may not
          exist yet, or the review result has not been received.
        </p>
      </div>

      <RouterLink to="/reviews" class="state-action">
        Back to review history
      </RouterLink>
    </section>

    <section
      v-else-if="pageStatus === 'incomplete'"
      class="panel detail-state incomplete-state"
      role="alert"
    >
      <span class="state-icon state-icon--warning">
        <el-icon :size="22"><WarningFilled /></el-icon>
      </span>

      <div class="state-copy">
        <h2 class="section-title">Review history is incomplete</h2>
        <p>
          The stored report counts do not match the stored findings or
          published comments. Partial history is not shown.
        </p>
      </div>

      <el-button type="primary" :icon="Refresh" @click="retryPage">
        Retry
      </el-button>
    </section>

    <section
      v-else-if="pageStatus === 'error'"
      class="panel detail-state error-state"
      role="alert"
    >
      <span class="state-icon state-icon--danger">
        <el-icon :size="22"><WarningFilled /></el-icon>
      </span>

      <div class="state-copy">
        <h2 class="section-title">Unable to load review detail</h2>
        <p>{{ pageError }}</p>
      </div>

      <el-button type="primary" :icon="Refresh" @click="retryPage">
        Retry
      </el-button>
    </section>

    <template v-else-if="pageStatus === 'ready' && report">
      <div class="detail-grid">
        <section class="panel review-info" aria-label="Review information">
          <div class="panel-heading">
            <div>
              <h2 class="section-title">Review information</h2>
              <p class="section-subtitle">
                Metadata recorded with the structured review history.
              </p>
            </div>
          </div>

          <dl class="info-list">
            <div class="info-item">
              <dt>Task ID</dt>
              <dd class="mono">#{{ report.taskId }}</dd>
            </div>

            <div class="info-item">
              <dt>Repository</dt>
              <dd
                class="truncate"
                :title="`${report.owner}/${report.repo}`"
              >
                {{ report.owner }}/{{ report.repo }}
              </dd>
            </div>

            <div class="info-item">
              <dt>Pull request</dt>
              <dd class="mono">#{{ report.prNumber }}</dd>
            </div>

            <div class="info-item info-item--wide">
              <dt>Commit SHA</dt>
              <dd>
                <code class="commit-value" :title="report.commitSha">
                  {{ report.commitSha }}
                </code>
              </dd>
            </div>

            <div class="info-item">
              <dt>Task status</dt>
              <dd>
                <el-tag
                  :type="taskStatusType(report.taskStatus)"
                  size="small"
                  effect="light"
                >
                  {{ report.taskStatus }}
                </el-tag>
              </dd>
            </div>

            <div class="info-item">
              <dt>AI status</dt>
              <dd>
                <el-tag
                  :type="aiStatusType(report.aiStatus)"
                  size="small"
                  effect="light"
                >
                  {{ report.aiStatus }}
                </el-tag>
              </dd>
            </div>

            <div class="info-item">
              <dt>Publish status</dt>
              <dd>
                <el-tag
                  :type="publishStatusType(report.publishStatus)"
                  size="small"
                  effect="light"
                >
                  {{ report.publishStatus }}
                </el-tag>
              </dd>
            </div>

            <div class="info-item">
              <dt>Finding count</dt>
              <dd class="mono">{{ formatCount(report.findingCount) }}</dd>
            </div>

            <div class="info-item">
              <dt>Published comment count</dt>
              <dd class="mono">
                {{ formatCount(report.publishedCommentCount) }}
              </dd>
            </div>

            <div class="info-item">
              <dt>Summary comment ID</dt>
              <dd class="mono">
                {{ formatSummaryCommentId(report.summaryCommentId) }}
              </dd>
            </div>

            <div class="info-item">
              <dt>Published at</dt>
              <dd class="mono">{{ formatDateTime(report.publishedAt) }}</dd>
            </div>

            <div class="info-item">
              <dt>Created at</dt>
              <dd class="mono">{{ formatDateTime(report.createdAt) }}</dd>
            </div>

            <div class="info-item">
              <dt>Last updated</dt>
              <dd class="mono">{{ formatDateTime(report.updatedAt) }}</dd>
            </div>
          </dl>
        </section>

        <section class="panel ai-summary" aria-label="AI review summary">
          <div class="panel-heading">
            <div>
              <h2 class="section-title">AI review summary</h2>
              <p class="section-subtitle">
                Only status and counts persisted with this review.
              </p>
            </div>
          </div>

          <dl class="info-list">
            <div class="info-item">
              <dt>AI status</dt>
              <dd>
                <el-tag
                  :type="aiStatusType(report.aiStatus)"
                  size="small"
                  effect="light"
                >
                  {{ report.aiStatus }}
                </el-tag>
              </dd>
            </div>

            <div class="info-item">
              <dt>Stored findings</dt>
              <dd class="mono">{{ formatCount(report.findingCount) }}</dd>
            </div>

            <div class="info-item">
              <dt>Publication</dt>
              <dd>
                <el-tag
                  :type="publishStatusType(report.publishStatus)"
                  size="small"
                  effect="light"
                >
                  {{ report.publishStatus }}
                </el-tag>
              </dd>
            </div>

            <div class="info-item">
              <dt>Summary comment</dt>
              <dd class="mono">
                {{ formatSummaryCommentId(report.summaryCommentId) }}
              </dd>
            </div>
          </dl>

          <p class="summary-note">
            Narrative summary and risk level are not stored in the structured
            review history and are not shown here. Detailed findings are listed
            below.
          </p>
        </section>
      </div>

      <section
        class="panel findings-section"
        data-testid="findings-section"
        aria-label="Review findings"
        :aria-busy="findingsLoading"
      >
        <div class="panel-heading">
          <div>
            <h2 class="section-title">Findings</h2>
            <p class="section-subtitle">
              Stored findings for this review, ordered by ordinal.
            </p>
          </div>

          <span class="soft-badge">
            {{ findingsTotalItems }}
            {{ findingsTotalItems === 1 ? 'finding' : 'findings' }}
          </span>
        </div>

        <div
          v-if="findingsLoading && findings.length === 0"
          class="section-loading"
          role="status"
          aria-label="Loading findings"
        >
          <el-skeleton :rows="4" animated />
        </div>

        <div v-else-if="findingsError" class="section-error" role="alert">
          <span class="state-icon state-icon--danger">
            <el-icon :size="20"><WarningFilled /></el-icon>
          </span>

          <div class="state-copy">
            <h3 class="section-title">
              {{
                findingsIncomplete
                  ? 'Findings history is incomplete'
                  : 'Unable to load findings'
              }}
            </h3>
            <p>{{ findingsError }}</p>
          </div>

          <el-button :icon="Refresh" @click="retryFindings">
            Retry
          </el-button>
        </div>

        <el-empty
          v-else-if="findings.length === 0"
          class="section-empty"
          :description="findingsEmptyDescription"
        />

        <template v-else>
          <p v-if="findingsLoading" class="section-updating" role="status">
            <span class="status-pill__dot" />
            Updating findings…
          </p>

          <el-table
            :data="findings"
            row-key="ordinal"
            class="detail-table"
            table-layout="auto"
            stripe
          >
            <el-table-column type="expand" width="44">
              <template #default="{ row }">
                <div class="finding-detail">
                  <div class="detail-block">
                    <h4>Description</h4>
                    <p>{{ formatText(row.description) }}</p>
                  </div>

                  <div class="detail-block">
                    <h4>Reason</h4>
                    <p>{{ formatText(row.reason) }}</p>
                  </div>

                  <div class="detail-block">
                    <h4>Suggestion</h4>
                    <p>{{ formatText(row.suggestion) }}</p>
                  </div>

                  <div class="detail-block">
                    <h4>References</h4>
                    <ul
                      v-if="cleanReferences(row.references).length > 0"
                      class="references-list"
                    >
                      <li
                        v-for="(reference, index) in cleanReferences(
                          row.references,
                        )"
                        :key="`${index}-${reference}`"
                      >
                        {{ reference }}
                      </li>
                    </ul>
                    <p v-else class="detail-empty">No references</p>
                  </div>
                </div>
              </template>
            </el-table-column>

            <el-table-column label="Finding" width="90">
              <template #default="{ row }">
                <span class="ordinal">#{{ row.ordinal + 1 }}</span>
              </template>
            </el-table-column>

            <el-table-column label="Severity" width="108">
              <template #default="{ row }">
                <el-tag
                  :type="severityType(row.severity)"
                  size="small"
                  effect="light"
                >
                  {{ row.severity }}
                </el-tag>
              </template>
            </el-table-column>

            <el-table-column label="Category" width="126">
              <template #default="{ row }">
                <el-tag
                  :type="categoryType(row.category)"
                  size="small"
                  effect="light"
                >
                  {{ row.category }}
                </el-tag>
              </template>
            </el-table-column>

            <el-table-column label="Finding" min-width="260">
              <template #default="{ row }">
                <div class="cell-stack">
                  <span class="finding-title">
                    {{ formatText(row.title) }}
                  </span>
                  <span v-if="row.ruleId" class="rule-id">
                    {{ row.ruleId }}
                  </span>
                </div>
              </template>
            </el-table-column>

            <el-table-column label="Location" min-width="250">
              <template #default="{ row }">
                <div class="cell-stack">
                  <code class="file-path" :title="row.filePath">
                    {{ row.filePath }}
                  </code>
                  <span class="line-range">
                    {{ formatLineRange(row.startLine, row.endLine) }}
                  </span>
                </div>
              </template>
            </el-table-column>

            <el-table-column
              label="Confidence"
              width="112"
              align="right"
            >
              <template #default="{ row }">
                <span class="confidence">
                  {{ formatConfidence(row.confidence) }}
                </span>
              </template>
            </el-table-column>
          </el-table>
        </template>

        <div
          v-if="!findingsError && findingsTotalItems > 0"
          class="pagination-row"
        >
          <el-pagination
            :current-page="findingsPage"
            :page-size="findingsSize"
            :page-sizes="PAGE_SIZES"
            :total="findingsTotalItems"
            layout="total, sizes, prev, pager, next"
            background
            @current-change="handleFindingsPageChange"
            @size-change="handleFindingsSizeChange"
          />
        </div>
      </section>

      <section
        class="panel comments-section"
        data-testid="comments-section"
        aria-label="Published inline comments"
        :aria-busy="commentsLoading"
      >
        <div class="panel-heading">
          <div>
            <h2 class="section-title">Published inline comments</h2>
            <p class="section-subtitle">
              Only comments confirmed published to GitHub are stored and shown.
              Failed or skipped comments are not listed. Comment bodies,
              publication times, and GitHub URLs are not stored.
            </p>
          </div>

          <span class="soft-badge">
            {{ commentsTotalItems }}
            {{ commentsTotalItems === 1 ? 'comment' : 'comments' }}
          </span>
        </div>

        <div
          v-if="commentsLoading && comments.length === 0"
          class="section-loading"
          role="status"
          aria-label="Loading published inline comments"
        >
          <el-skeleton :rows="3" animated />
        </div>

        <div v-else-if="commentsError" class="section-error" role="alert">
          <span class="state-icon state-icon--danger">
            <el-icon :size="20"><WarningFilled /></el-icon>
          </span>

          <div class="state-copy">
            <h3 class="section-title">
              {{
                commentsIncomplete
                  ? 'Published comment history is incomplete'
                  : 'Unable to load published comments'
              }}
            </h3>
            <p>{{ commentsError }}</p>
          </div>

          <el-button :icon="Refresh" @click="retryComments">
            Retry
          </el-button>
        </div>

        <el-empty
          v-else-if="comments.length === 0"
          class="section-empty"
          :description="commentsEmptyDescription"
        />

        <template v-else>
          <p v-if="commentsLoading" class="section-updating" role="status">
            <span class="status-pill__dot" />
            Updating published comments…
          </p>

          <el-table
            :data="comments"
            class="detail-table"
            table-layout="auto"
            stripe
          >
            <el-table-column label="Finding" width="100">
              <template #default="{ row }">
                <span class="ordinal">
                  #{{ row.findingOrdinal + 1 }}
                </span>
              </template>
            </el-table-column>

            <el-table-column label="Location" min-width="280">
              <template #default="{ row }">
                <div class="cell-stack">
                  <code class="file-path" :title="row.filePath">
                    {{ row.filePath }}
                  </code>
                  <span class="line-range">
                    {{ formatLineRange(row.startLine, row.endLine) }}
                  </span>
                </div>
              </template>
            </el-table-column>

            <el-table-column label="GitHub comment ID" min-width="180">
              <template #default="{ row }">
                <span class="comment-id">
                  {{
                    row.githubCommentId === null
                      ? 'ID unavailable'
                      : row.githubCommentId
                  }}
                </span>
              </template>
            </el-table-column>
          </el-table>
        </template>

        <div
          v-if="!commentsError && commentsTotalItems > 0"
          class="pagination-row"
        >
          <el-pagination
            :current-page="commentsPage"
            :page-size="commentsSize"
            :page-sizes="PAGE_SIZES"
            :total="commentsTotalItems"
            layout="total, sizes, prev, pager, next"
            background
            @current-change="handleCommentsPageChange"
            @size-change="handleCommentsSizeChange"
          />
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.detail-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.detail-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
}

.back-link {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  color: #475569;
  font-size: 12.5px;
  font-weight: 600;
  transition: color 140ms ease;
}

.back-link:hover {
  color: var(--cs-accent);
}

.detail-nav__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.status-pill {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  padding: 4px 9px;
  color: #475569;
  font-size: 10.5px;
  font-weight: 650;
  white-space: nowrap;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 999px;
}

.status-pill__dot {
  width: 6px;
  height: 6px;
  background: currentColor;
  border-radius: 50%;
}

.status-pill--loading .status-pill__dot {
  animation: status-pulse 1.2s ease-in-out infinite;
}

@keyframes status-pulse {
  0%,
  100% {
    opacity: 0.35;
  }

  50% {
    opacity: 1;
  }
}

.detail-heading {
  align-items: flex-start;
}

.detail-subtitle {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  max-width: 100%;
}

.subtitle-separator {
  color: #cbd5e1;
}

.commit-sha {
  display: inline-block;
  max-width: 280px;
  overflow: hidden;
  color: #475569;
  font-family: var(--cs-mono);
  font-size: 11.5px;
  text-overflow: ellipsis;
  vertical-align: bottom;
  white-space: nowrap;
}

.detail-loading {
  min-height: 360px;
  padding: 22px;
}

.detail-state {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  align-items: center;
  padding: 28px 22px;
}

.detail-state .state-copy {
  flex: 1;
  min-width: 240px;
}

.state-icon {
  display: inline-flex;
  flex: none;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border-radius: 12px;
}

.state-icon--danger {
  color: #b91c1c;
  background: #fef2f2;
  border: 1px solid #fee2e2;
}

.state-icon--warning {
  color: #b45309;
  background: #fffbeb;
  border: 1px solid #fef3c7;
}

.state-copy p {
  margin: 5px 0 0;
  color: var(--cs-muted);
  font-size: 12.5px;
  line-height: 1.6;
}

.state-action {
  padding: 8px 14px;
  margin-left: auto;
  color: #fff;
  font-size: 12.5px;
  font-weight: 550;
  white-space: nowrap;
  background: var(--cs-accent);
  border-radius: 8px;
  transition: background 140ms ease;
}

.state-action:hover {
  background: #4338ca;
}

.detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr);
  gap: 18px;
}

.info-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 2px 20px;
  margin: 0;
}

.info-item {
  display: flex;
  gap: 12px;
  align-items: baseline;
  justify-content: space-between;
  min-width: 0;
  padding: 9px 0;
  border-top: 1px solid #f1f5f9;
}

.info-item--wide {
  grid-column: span 2;
}

.info-item dt {
  flex: none;
  color: #64748b;
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.info-item dd {
  min-width: 0;
  margin: 0;
  color: #1e293b;
  font-size: 12.5px;
  font-weight: 550;
  text-align: right;
}

.mono {
  font-family: var(--cs-mono);
  font-size: 11.5px !important;
  white-space: nowrap;
}

.truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.commit-value {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  font-family: var(--cs-mono);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.summary-note {
  padding: 12px 14px;
  margin: 16px 0 0;
  color: #475569;
  font-size: 12px;
  line-height: 1.65;
  background: #f8fafc;
  border: 1px solid #eef2f7;
  border-radius: 10px;
}

.findings-section,
.comments-section {
  padding-bottom: 18px;
}

.section-loading {
  padding: 8px 2px;
}

.section-error {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  padding: 18px 2px;
}

.section-error .state-copy {
  flex: 1;
  min-width: 220px;
}

.section-error .el-button {
  margin-left: auto;
}

.section-empty {
  padding: 16px 0;
}

.section-updating {
  display: flex;
  gap: 7px;
  align-items: center;
  padding: 7px 11px;
  margin: 0 0 12px;
  color: #4338ca;
  font-size: 11.5px;
  background: #eef2ff;
  border: 1px solid #e0e7ff;
  border-radius: 8px;
}

.section-updating .status-pill__dot {
  animation: status-pulse 1.2s ease-in-out infinite;
}

.detail-table {
  width: 100%;
}

.detail-table :deep(th.el-table__cell) {
  background: #f8fafc;
  color: #64748b;
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.detail-table :deep(.el-table__cell) {
  padding: 11px 0;
}

.cell-stack {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.ordinal {
  color: #334155;
  font-family: var(--cs-mono);
  font-size: 12px;
  font-weight: 650;
}

.finding-title {
  color: #1e293b;
  font-size: 12.5px;
  font-weight: 600;
  line-height: 1.45;
}

.rule-id {
  color: #64748b;
  font-family: var(--cs-mono);
  font-size: 10.5px;
}

.file-path {
  display: block;
  max-width: 320px;
  overflow: hidden;
  color: #334155;
  font-family: var(--cs-mono);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.line-range {
  color: #64748b;
  font-family: var(--cs-mono);
  font-size: 10.5px;
}

.confidence {
  color: #334155;
  font-family: var(--cs-mono);
  font-size: 11.5px;
  font-weight: 650;
}

.comment-id {
  color: #334155;
  font-family: var(--cs-mono);
  font-size: 11.5px;
}

.finding-detail {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px 26px;
  padding: 14px 22px 18px;
  background: #fbfcfe;
}

.detail-block h4 {
  margin: 0 0 5px;
  color: #64748b;
  font-size: 10px;
  font-weight: 750;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.detail-block p {
  margin: 0;
  color: #334155;
  font-size: 12.5px;
  line-height: 1.65;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.detail-empty {
  color: #94a3b8 !important;
}

.references-list {
  padding-left: 18px;
  margin: 0;
  color: #334155;
  font-family: var(--cs-mono);
  font-size: 11.5px;
  line-height: 1.7;
  overflow-wrap: anywhere;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  padding-top: 18px;
  margin-top: 2px;
  overflow-x: auto;
  border-top: 1px solid #f1f5f9;
}

.pagination-row :deep(.el-pagination) {
  row-gap: 8px;
  flex-wrap: wrap;
}

@media (max-width: 1080px) {
  .detail-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 720px) {
  .detail-nav {
    align-items: flex-start;
    flex-direction: column;
  }

  .detail-nav__actions {
    width: 100%;
  }

  .info-list {
    grid-template-columns: minmax(0, 1fr);
  }

  .info-item--wide {
    grid-column: auto;
  }

  .finding-detail {
    grid-template-columns: minmax(0, 1fr);
  }

  .state-action {
    margin-left: 0;
  }

  .pagination-row {
    justify-content: flex-start;
  }
}
</style>
