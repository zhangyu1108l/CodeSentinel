<script setup lang="ts">
import {
  Delete,
  Document,
  Refresh,
  Search,
  WarningFilled,
} from '@element-plus/icons-vue'
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { getReviewHistory } from '@/api'
import type {
  AiStatus,
  PublishStatus,
  ReviewHistoryFilters,
  ReviewHistoryItem,
  ReviewHistoryPage,
  TaskStatus,
} from '@/types/api'
import { getErrorMessage } from '@/utils/api-error'
import {
  aiStatusType,
  formatCount,
  formatDateTime,
  formatSummaryComment,
  publishStatusType,
  taskStatusType,
} from '@/utils/review-display'

interface FilterForm {
  owner: string
  repo: string
  prNumber: number | null | undefined
  taskStatus: TaskStatus | ''
  aiStatus: AiStatus | ''
  publishStatus: PublishStatus | ''
  createdRange: [string, string] | null
}

const PAGE_SIZES: number[] = [10, 20, 50, 100]
const DEFAULT_PAGE_SIZE = 20
const DATE_TIME_FORMAT = 'YYYY-MM-DD[T]HH:mm:ss'

const taskStatusOptions: Array<{ label: string; value: TaskStatus }> = [
  { label: 'Pending', value: 'PENDING' },
  { label: 'Running', value: 'RUNNING' },
  { label: 'Completed', value: 'COMPLETED' },
  { label: 'Failed', value: 'FAILED' },
]

const aiStatusOptions: Array<{ label: string; value: AiStatus }> = [
  { label: 'Completed', value: 'COMPLETED' },
  { label: 'Degraded', value: 'DEGRADED' },
]

const publishStatusOptions: Array<{ label: string; value: PublishStatus }> = [
  { label: 'Pending', value: 'PENDING' },
  { label: 'Published', value: 'PUBLISHED' },
  { label: 'Partial', value: 'PARTIAL' },
  { label: 'Failed', value: 'FAILED' },
]

function createEmptyFilters(): FilterForm {
  return {
    owner: '',
    repo: '',
    prNumber: undefined,
    taskStatus: '',
    aiStatus: '',
    publishStatus: '',
    createdRange: null,
  }
}

const filters = reactive<FilterForm>(createEmptyFilters())
const appliedFilters = ref<ReviewHistoryFilters>({})

const items = ref<ReviewHistoryItem[]>([])
const page = ref(1)
const size = ref(DEFAULT_PAGE_SIZE)
const totalItems = ref(0)
const totalPages = ref(0)
const loading = ref(true)
const errorMessage = ref('')
const filterError = ref('')

let activeRequest: AbortController | null = null
let requestSequence = 0
let disposed = false

const hasActiveFilters = computed(
  () => Object.keys(appliedFilters.value).length > 0,
)

const initialLoading = computed(
  () => loading.value && items.value.length === 0,
)

const updating = computed(
  () => loading.value && items.value.length > 0,
)

const itemRange = computed(() => {
  if (totalItems.value === 0) {
    return 'No stored reviews'
  }
  const first = (page.value - 1) * size.value + 1
  const last = Math.min(page.value * size.value, totalItems.value)
  return `Showing ${first}–${last} of ${totalItems.value}`
})

const emptyDescription = computed(() =>
  totalItems.value > 0
    ? 'No reviews on this page'
    : 'No reviews match the current filters',
)

function toAppliedFilters(form: FilterForm): ReviewHistoryFilters {
  const result: ReviewHistoryFilters = {}

  const owner = form.owner.trim()
  if (owner) {
    result.owner = owner
  }

  const repo = form.repo.trim()
  if (repo) {
    result.repo = repo
  }

  if (form.prNumber !== undefined && form.prNumber !== null) {
    result.prNumber = form.prNumber
  }

  if (form.taskStatus) {
    result.taskStatus = form.taskStatus
  }

  if (form.aiStatus) {
    result.aiStatus = form.aiStatus
  }

  if (form.publishStatus) {
    result.publishStatus = form.publishStatus
  }

  if (form.createdRange) {
    result.createdFrom = form.createdRange[0]
    result.createdTo = form.createdRange[1]
  }

  return result
}

function applyPage(result: ReviewHistoryPage) {
  items.value = result.items
  page.value = result.page
  size.value = result.size
  totalItems.value = result.totalItems
  totalPages.value = result.totalPages
}

async function loadReviews() {
  activeRequest?.abort()

  const request = new AbortController()
  activeRequest = request
  const sequence = ++requestSequence

  loading.value = true
  errorMessage.value = ''
  filterError.value = ''

  try {
    const result = await getReviewHistory(
      {
        page: page.value,
        size: size.value,
        ...appliedFilters.value,
      },
      request.signal,
    )

    if (disposed || request.signal.aborted || sequence !== requestSequence) {
      return
    }

    applyPage(result)
  } catch (error) {
    if (disposed || request.signal.aborted || sequence !== requestSequence) {
      return
    }
    errorMessage.value = getErrorMessage(error)
  } finally {
    if (!disposed && sequence === requestSequence) {
      loading.value = false
      if (activeRequest === request) {
        activeRequest = null
      }
    }
  }
}

function applyFilters() {
  filterError.value = ''

  if (filters.createdRange) {
    const [from, to] = filters.createdRange
    if (from && to && from > to) {
      filterError.value =
        'The created-from time must not be after the created-to time.'
      return
    }
  }

  appliedFilters.value = toAppliedFilters(filters)
  page.value = 1
  void loadReviews()
}

function clearFilters() {
  Object.assign(filters, createEmptyFilters())
  appliedFilters.value = {}
  filterError.value = ''
  page.value = 1
  void loadReviews()
}

function handlePageChange(nextPage: number) {
  if (nextPage === page.value) {
    return
  }
  page.value = nextPage
  void loadReviews()
}

function handleSizeChange(nextSize: number) {
  if (nextSize === size.value) {
    return
  }
  size.value = nextSize
  page.value = 1
  void loadReviews()
}

onMounted(() => {
  void loadReviews()
})

onBeforeUnmount(() => {
  disposed = true
  activeRequest?.abort()
  activeRequest = null
})
</script>

<template>
  <div class="page history-page">
    <header class="page-heading">
      <div>
        <p class="eyebrow">Reviews</p>
        <h1 class="page-title">Review History</h1>
        <p class="page-subtitle">
          Browse stored review reports, AI delivery status, and GitHub
          publication results.
        </p>
      </div>

      <div class="heading-actions">
        <span
          class="status-pill"
          :class="{ 'status-pill--loading': loading }"
        >
          <span class="status-pill__dot" />
          {{
            loading
              ? 'Loading'
              : `${totalItems} ${totalItems === 1 ? 'review' : 'reviews'}`
          }}
        </span>

        <el-button :icon="Refresh" :loading="loading" @click="loadReviews">
          Refresh
        </el-button>
      </div>
    </header>

    <form class="panel filter-panel" @submit.prevent="applyFilters">
      <div class="filter-grid">
        <label class="filter-field" data-testid="filter-owner">
          <span class="filter-label">Owner</span>
          <el-input
            v-model="filters.owner"
            placeholder="Exact owner"
            clearable
            maxlength="255"
          />
        </label>

        <label class="filter-field" data-testid="filter-repo">
          <span class="filter-label">Repository</span>
          <el-input
            v-model="filters.repo"
            placeholder="Exact repository"
            clearable
            maxlength="255"
          />
        </label>

        <label class="filter-field" data-testid="filter-pr-number">
          <span class="filter-label">Pull request</span>
          <el-input-number
            v-model="filters.prNumber"
            :min="1"
            :max="2147483647"
            :controls="false"
            placeholder="PR number"
          />
        </label>

        <label class="filter-field" data-testid="filter-task-status">
          <span class="filter-label">Task status</span>
          <el-select
            v-model="filters.taskStatus"
            placeholder="Any task status"
            clearable
          >
            <el-option
              v-for="option in taskStatusOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </label>

        <label class="filter-field" data-testid="filter-ai-status">
          <span class="filter-label">AI status</span>
          <el-select
            v-model="filters.aiStatus"
            placeholder="Any AI status"
            clearable
          >
            <el-option
              v-for="option in aiStatusOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </label>

        <label class="filter-field" data-testid="filter-publish-status">
          <span class="filter-label">Publish status</span>
          <el-select
            v-model="filters.publishStatus"
            placeholder="Any publish status"
            clearable
          >
            <el-option
              v-for="option in publishStatusOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </label>

        <label
          class="filter-field filter-field--wide"
          data-testid="filter-created-range"
        >
          <span class="filter-label">Created at</span>
          <el-date-picker
            v-model="filters.createdRange"
            type="datetimerange"
            :value-format="DATE_TIME_FORMAT"
            range-separator="to"
            start-placeholder="From"
            end-placeholder="To"
            unlink-panels
          />
        </label>
      </div>

      <div class="filter-actions">
        <p v-if="filterError" class="filter-error" role="alert">
          {{ filterError }}
        </p>

        <div class="filter-buttons">
          <el-button type="primary" native-type="submit" :icon="Search">
            Apply filters
          </el-button>
          <el-button :icon="Delete" @click="clearFilters">
            Clear filters
          </el-button>
        </div>
      </div>
    </form>

    <section
      class="panel results-panel"
      aria-label="Review history results"
      :aria-busy="loading"
    >
      <div
        v-if="initialLoading"
        class="history-loading"
        role="status"
        aria-label="Loading review history"
      >
        <el-skeleton :rows="7" animated />
      </div>

      <div v-else-if="errorMessage" class="history-error" role="alert">
        <span class="state-icon state-icon--danger">
          <el-icon :size="22"><WarningFilled /></el-icon>
        </span>

        <div class="state-copy">
          <h2 class="section-title">Unable to load review history</h2>
          <p>{{ errorMessage }}</p>
        </div>

        <el-button type="primary" :icon="Refresh" @click="loadReviews">
          Retry
        </el-button>
      </div>

      <el-empty
        v-else-if="items.length === 0"
        class="history-empty"
        :description="emptyDescription"
      >
        <template #image>
          <span class="empty-mark">
            <el-icon :size="30"><Document /></el-icon>
          </span>
        </template>

        <p class="empty-copy">
          Stored reviews appear here after a review result has been received.
          Adjust the filters if you expected to see an entry.
        </p>

        <el-button
          v-if="hasActiveFilters"
          :icon="Delete"
          @click="clearFilters"
        >
          Clear filters
        </el-button>
        <el-button v-else :icon="Refresh" @click="loadReviews">
          Refresh
        </el-button>
      </el-empty>

      <template v-else>
        <div class="results-header">
          <div>
            <h2 class="section-title">Stored reviews</h2>
            <p class="section-subtitle">{{ itemRange }}</p>
          </div>

          <span class="soft-badge">
            {{ totalPages }} {{ totalPages === 1 ? 'page' : 'pages' }}
          </span>
        </div>

        <div v-if="updating" class="history-updating" role="status">
          <span class="status-pill__dot" />
          Updating review history…
        </div>

        <el-table
          :data="items"
          row-key="taskId"
          class="history-table"
          table-layout="auto"
          stripe
        >
          <el-table-column label="Review" min-width="190">
            <template #default="{ row }">
              <div class="cell-stack">
                <RouterLink
                  class="task-id"
                  :to="`/reviews/${row.taskId}`"
                  :title="`Open review #${row.taskId}`"
                >
                  #{{ row.taskId }}
                </RouterLink>
                <code class="commit-sha" :title="row.commitSha">
                  {{ row.commitSha }}
                </code>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="Repository" min-width="180">
            <template #default="{ row }">
              <div class="cell-stack">
                <span
                  class="repo-name"
                  :title="`${row.owner}/${row.repo}`"
                >
                  {{ row.owner }}/{{ row.repo }}
                </span>
                <span class="cell-muted">PR #{{ row.prNumber }}</span>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="Task status" min-width="112">
            <template #default="{ row }">
              <el-tag
                :type="taskStatusType(row.taskStatus)"
                size="small"
                effect="light"
              >
                {{ row.taskStatus }}
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column label="AI status" min-width="108">
            <template #default="{ row }">
              <el-tag
                :type="aiStatusType(row.aiStatus)"
                size="small"
                effect="light"
              >
                {{ row.aiStatus }}
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column label="Publish status" min-width="126">
            <template #default="{ row }">
              <el-tag
                :type="publishStatusType(row.publishStatus)"
                size="small"
                effect="light"
              >
                {{ row.publishStatus }}
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column label="Findings" min-width="92" align="center">
            <template #default="{ row }">
              <span class="count-value">
                {{ formatCount(row.findingCount) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="Comments" min-width="140">
            <template #default="{ row }">
              <div class="cell-stack">
                <span class="count-value">
                  {{ formatCount(row.publishedCommentCount) }}
                </span>
                <span class="cell-muted">
                  {{ formatSummaryComment(row.summaryCommentId) }}
                </span>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="Published" min-width="152">
            <template #default="{ row }">
              <span class="time-value">
                {{ formatDateTime(row.publishedAt) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="Created" min-width="152">
            <template #default="{ row }">
              <span class="time-value">
                {{ formatDateTime(row.createdAt) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="Updated" min-width="152">
            <template #default="{ row }">
              <span class="time-value">
                {{ formatDateTime(row.updatedAt) }}
              </span>
            </template>
          </el-table-column>
        </el-table>

      </template>

      <div
        v-if="!initialLoading && !errorMessage && totalItems > 0"
        class="pagination-row"
      >
        <el-pagination
          :current-page="page"
          :page-size="size"
          :page-sizes="PAGE_SIZES"
          :total="totalItems"
          layout="total, sizes, prev, pager, next"
          background
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </section>
  </div>
</template>

<style scoped>
.history-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.heading-actions {
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

.filter-panel {
  padding: 18px 20px;
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px 16px;
}

.filter-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.filter-field--wide {
  grid-column: span 2;
}

.filter-label {
  color: #64748b;
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.filter-field :deep(.el-input),
.filter-field :deep(.el-input-number),
.filter-field :deep(.el-select),
.filter-field :deep(.el-date-editor) {
  width: 100%;
}

.filter-actions {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  padding-top: 14px;
  margin-top: 16px;
  border-top: 1px solid #f1f5f9;
}

.filter-error {
  margin: 0;
  color: #b91c1c;
  font-size: 12px;
}

.filter-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-left: auto;
}

.results-panel {
  min-height: 360px;
  padding: 18px 20px 20px;
}

.history-loading {
  padding: 10px 4px;
}

.history-error {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  align-items: center;
  padding: 28px 8px;
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

.state-copy {
  flex: 1;
  min-width: 220px;
}

.state-copy p {
  margin: 5px 0 0;
  color: var(--cs-muted);
  font-size: 12.5px;
  line-height: 1.6;
}

.history-error .el-button {
  margin-left: auto;
}

.history-empty {
  padding: 24px 0;
}

.empty-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 72px;
  height: 72px;
  color: #6366f1;
  background: #eef2ff;
  border: 1px solid #e0e7ff;
  border-radius: 20px;
}

.empty-copy {
  max-width: 440px;
  margin: 0 auto 18px;
  color: var(--cs-muted);
  font-size: 12.5px;
  line-height: 1.6;
}

.results-header {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 14px;
}

.history-updating {
  display: flex;
  gap: 7px;
  align-items: center;
  padding: 7px 11px;
  margin-bottom: 12px;
  color: #4338ca;
  font-size: 11.5px;
  background: #eef2ff;
  border: 1px solid #e0e7ff;
  border-radius: 8px;
}

.history-updating .status-pill__dot {
  animation: status-pulse 1.2s ease-in-out infinite;
}

.history-table {
  width: 100%;
}

.history-table :deep(th.el-table__cell) {
  background: #f8fafc;
  color: #64748b;
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.history-table :deep(.el-table__cell) {
  padding: 11px 0;
}

.cell-stack {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.task-id {
  color: #1e293b;
  font-family: var(--cs-mono);
  font-size: 12px;
  font-weight: 650;
}

a.task-id:hover {
  color: var(--cs-accent);
  text-decoration: underline;
}

.commit-sha {
  display: block;
  max-width: 182px;
  overflow: hidden;
  color: #64748b;
  font-family: var(--cs-mono);
  font-size: 10.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.repo-name {
  overflow: hidden;
  color: #1e293b;
  font-size: 12.5px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cell-muted {
  color: #94a3b8;
  font-size: 11px;
}

.count-value {
  color: #334155;
  font-family: var(--cs-mono);
  font-size: 12px;
  font-weight: 650;
}

.time-value {
  color: #475569;
  font-family: var(--cs-mono);
  font-size: 11px;
  white-space: nowrap;
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

@media (max-width: 1180px) {
  .filter-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .heading-actions {
    width: 100%;
  }

  .filter-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .filter-field--wide {
    grid-column: auto;
  }

  .filter-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .filter-buttons {
    margin-left: 0;
  }

  .results-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .history-error .el-button {
    margin-left: 0;
  }

  .pagination-row {
    justify-content: flex-start;
  }
}
</style>
