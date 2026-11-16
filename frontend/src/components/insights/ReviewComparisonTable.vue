<script setup lang="ts">
import { RouterLink } from 'vue-router'

import type {
  StatisticsReviewItem,
  StatisticsSort,
  StatisticsSortDirection,
} from '@/types/statistics'
import {
  aiStatusType,
  formatDateTime,
  publishStatusType,
  taskStatusType,
} from '@/utils/review-display'
import {
  formatMetricNumber,
  formatStatusLabel,
} from '@/utils/statistics-format'

const props = defineProps<{
  items: StatisticsReviewItem[]
  page: number
  size: number
  totalItems: number
  totalPages: number
  sort: StatisticsSort
  direction: StatisticsSortDirection
}>()

const emit = defineEmits<{
  (event: 'page-change', page: number): void
  (event: 'size-change', size: number): void
  (
    event: 'sort-change',
    payload: { sort: StatisticsSort; direction: StatisticsSortDirection },
  ): void
}>()

const PAGE_SIZES: number[] = [10, 20, 50, 100]

const SORT_BY_PROP: Record<string, StatisticsSort> = {
  createdAt: 'createdAt',
  actualFindingCount: 'actualFindingCount',
  highSeverityFindingCount: 'highSeverityFindingCount',
  actualCommentCount: 'actualCommentCount',
}

interface TableSortChange {
  prop: string | null
  order: 'ascending' | 'descending' | null
}

function defaultSortOrder() {
  return props.direction === 'asc' ? 'ascending' : 'descending'
}

function handleSortChange(change: TableSortChange) {
  const sort = SORT_BY_PROP[change.prop ?? ''] ?? 'createdAt'
  if (!change.order) {
    emit('sort-change', { sort: 'createdAt', direction: 'desc' })
    return
  }
  emit('sort-change', {
    sort,
    direction: change.order === 'ascending' ? 'asc' : 'desc',
  })
}

function handlePageChange(nextPage: number) {
  if (nextPage !== props.page) {
    emit('page-change', nextPage)
  }
}

function handleSizeChange(nextSize: number) {
  if (nextSize !== props.size) {
    emit('size-change', nextSize)
  }
}
</script>

<template>
  <div class="comparison-table">
    <el-table
      :data="props.items"
      row-key="taskId"
      table-layout="auto"
      stripe
      :default-sort="{ prop: props.sort, order: defaultSortOrder() }"
      @sort-change="handleSortChange"
    >
      <el-table-column
        label="Created"
        prop="createdAt"
        min-width="152"
        sortable="custom"
      >
        <template #default="{ row }">
          <span class="time-value">
            {{ formatDateTime(row.createdAt) }}
          </span>
        </template>
      </el-table-column>

      <el-table-column label="Review" min-width="190">
        <template #default="{ row }">
          <div class="cell-stack">
            <RouterLink
              v-if="row.findingsConsistent && row.commentsConsistent"
              class="task-id"
              :to="`/reviews/${row.taskId}`"
              :title="`Open review #${row.taskId}`"
            >
              #{{ row.taskId }}
            </RouterLink>
            <span
              v-else
              class="task-id task-id--disabled"
              :title="`Review #${row.taskId} has incomplete stored history and cannot be opened`"
            >
              #{{ row.taskId }}
            </span>

            <code class="commit-sha" :title="row.commitSha">
              {{ row.commitSha.slice(0, 10) }}…
            </code>

            <span class="cell-muted">
              <el-tag
                :type="taskStatusType(row.taskStatus)"
                size="small"
                effect="plain"
              >
                {{ formatStatusLabel(row.taskStatus) }}
              </el-tag>
            </span>
          </div>
        </template>
      </el-table-column>

      <el-table-column label="Repository" min-width="180">
        <template #default="{ row }">
          <div class="cell-stack">
            <span class="repo-name" :title="`${row.owner}/${row.repo}`">
              {{ row.owner }}/{{ row.repo }}
            </span>
            <span class="cell-muted">PR #{{ row.prNumber }}</span>
          </div>
        </template>
      </el-table-column>

      <el-table-column label="AI / Publish" min-width="150">
        <template #default="{ row }">
          <div class="tag-stack">
            <el-tag :type="aiStatusType(row.aiStatus)" size="small" effect="light">
              {{ formatStatusLabel(row.aiStatus) }}
            </el-tag>
            <el-tag
              :type="publishStatusType(row.publishStatus)"
              size="small"
              effect="light"
            >
              {{ formatStatusLabel(row.publishStatus) }}
            </el-tag>
          </div>
        </template>
      </el-table-column>

      <el-table-column
        label="Findings"
        prop="actualFindingCount"
        min-width="128"
        align="center"
        sortable="custom"
      >
        <template #default="{ row }">
          <div class="cell-stack cell-stack--center">
            <span class="count-value">
              {{ formatMetricNumber(row.actualFindingCount) }}
              <span class="count-separator">/</span>
              {{ formatMetricNumber(row.declaredFindingCount) }}
            </span>
            <el-tag
              v-if="!row.findingsConsistent"
              type="warning"
              size="small"
              effect="plain"
            >
              Inconsistent
            </el-tag>
          </div>
        </template>
      </el-table-column>

      <el-table-column
        label="High + Critical"
        prop="highSeverityFindingCount"
        min-width="126"
        align="center"
        sortable="custom"
      >
        <template #default="{ row }">
          <span class="count-value">
            {{ formatMetricNumber(row.highSeverityFindingCount) }}
          </span>
        </template>
      </el-table-column>

      <el-table-column
        label="Comments"
        prop="actualCommentCount"
        min-width="122"
        align="center"
        sortable="custom"
      >
        <template #default="{ row }">
          <div class="cell-stack cell-stack--center">
            <span class="count-value">
              {{ formatMetricNumber(row.actualCommentCount) }}
              <span class="count-separator">/</span>
              {{ formatMetricNumber(row.declaredCommentCount) }}
            </span>
            <el-tag
              v-if="!row.commentsConsistent"
              type="warning"
              size="small"
              effect="plain"
            >
              Inconsistent
            </el-tag>
          </div>
        </template>
      </el-table-column>

      <el-table-column label="Data" min-width="100">
        <template #default="{ row }">
          <el-tag
            v-if="row.findingsConsistent && row.commentsConsistent"
            type="success"
            size="small"
            effect="plain"
          >
            Complete
          </el-tag>
          <el-tag v-else type="warning" size="small" effect="plain">
            Incomplete
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column label="Unknown values" min-width="118" align="center">
        <template #default="{ row }">
          <div
            v-if="row.unknownCategoryCount === 0 && row.unknownSeverityCount === 0"
            class="cell-muted"
          >
            —
          </div>
          <div v-else class="tag-stack tag-stack--center">
            <el-tag
              v-if="row.unknownCategoryCount > 0"
              type="info"
              size="small"
              effect="plain"
            >
              Category: {{ row.unknownCategoryCount }}
            </el-tag>
            <el-tag
              v-if="row.unknownSeverityCount > 0"
              type="info"
              size="small"
              effect="plain"
            >
              Severity: {{ row.unknownSeverityCount }}
            </el-tag>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="props.totalItems > 0" class="pagination-row">
      <el-pagination
        :current-page="props.page"
        :page-size="props.size"
        :page-sizes="PAGE_SIZES"
        :total="props.totalItems"
        layout="total, sizes, prev, pager, next"
        background
        @current-change="handlePageChange"
        @size-change="handleSizeChange"
      />
    </div>
  </div>
</template>

<style scoped>
.comparison-table {
  min-width: 0;
}

.comparison-table :deep(th.el-table__cell) {
  background: #f8fafc;
  color: #64748b;
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.comparison-table :deep(.el-table__cell) {
  padding: 11px 0;
}

.cell-stack {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.cell-stack--center {
  align-items: center;
}

.task-id {
  align-self: flex-start;
  color: #1e293b;
  font-family: var(--cs-mono);
  font-size: 12px;
  font-weight: 650;
}

a.task-id:hover {
  color: var(--cs-accent);
  text-decoration: underline;
}

.task-id--disabled {
  color: #94a3b8;
  text-decoration: line-through;
  cursor: not-allowed;
}

.commit-sha {
  display: block;
  max-width: 180px;
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

.tag-stack {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.tag-stack--center {
  flex-direction: column;
  align-items: center;
}

.count-value {
  color: #334155;
  font-family: var(--cs-mono);
  font-size: 12px;
  font-weight: 650;
}

.count-separator {
  color: #cbd5e1;
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

@media (max-width: 640px) {
  .pagination-row {
    justify-content: flex-start;
  }
}
</style>
