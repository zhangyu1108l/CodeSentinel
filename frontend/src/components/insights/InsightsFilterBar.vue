<script setup lang="ts">
import { Delete, Search } from '@element-plus/icons-vue'
import { reactive, ref } from 'vue'

import type {
  AiStatus,
  PublishStatus,
  TaskStatus,
} from '@/types/api'
import type { StatisticsFilters } from '@/types/statistics'

const props = withDefaults(
  defineProps<{
    zoneId?: string
  }>(),
  {
    zoneId: '',
  },
)

const emit = defineEmits<{
  (event: 'apply', filters: StatisticsFilters): void
  (event: 'reset'): void
}>()

interface FilterForm {
  owner: string
  repo: string
  prNumber: number | null | undefined
  taskStatus: TaskStatus | ''
  aiStatus: AiStatus | ''
  publishStatus: PublishStatus | ''
  createdRange: [string, string] | null
}

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
const filterError = ref('')

function daysBetweenInclusive(from: string, to: string): number {
  const start = Date.parse(`${from}T00:00:00Z`)
  const end = Date.parse(`${to}T00:00:00Z`)
  if (!Number.isFinite(start) || !Number.isFinite(end)) {
    return Number.NaN
  }
  return Math.floor((end - start) / 86_400_000) + 1
}

function toFilters(form: FilterForm): StatisticsFilters {
  const result: StatisticsFilters = {}

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
    const [from, to] = form.createdRange
    result.createdFrom = `${from}T00:00:00`
    result.createdTo = `${to}T23:59:59.999999`
  }

  return result
}

function applyFilters() {
  filterError.value = ''

  if (filters.createdRange) {
    const [from, to] = filters.createdRange
    if (from && to && from > to) {
      filterError.value =
        'The created-from date must not be after the created-to date.'
      return
    }
    if (from && to && daysBetweenInclusive(from, to) > 366) {
      filterError.value =
        'The selected date range must not exceed 366 calendar days.'
      return
    }
  }

  emit('apply', toFilters(filters))
}

function resetFilters() {
  Object.assign(filters, createEmptyFilters())
  filterError.value = ''
  emit('reset')
}
</script>

<template>
  <form class="panel filter-panel" @submit.prevent="applyFilters">
    <div class="filter-grid">
      <label class="filter-field" data-testid="insights-filter-owner">
        <span class="filter-label">Owner</span>
        <el-input
          v-model="filters.owner"
          placeholder="Exact owner"
          clearable
          maxlength="255"
        />
      </label>

      <label class="filter-field" data-testid="insights-filter-repo">
        <span class="filter-label">Repository</span>
        <el-input
          v-model="filters.repo"
          placeholder="Exact repository"
          clearable
          maxlength="255"
        />
      </label>

      <label class="filter-field" data-testid="insights-filter-pr-number">
        <span class="filter-label">Pull request</span>
        <el-input-number
          v-model="filters.prNumber"
          :min="1"
          :max="2147483647"
          :controls="false"
          placeholder="PR number"
        />
      </label>

      <label class="filter-field" data-testid="insights-filter-task-status">
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

      <label class="filter-field" data-testid="insights-filter-ai-status">
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

      <label
        class="filter-field"
        data-testid="insights-filter-publish-status"
      >
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
        data-testid="insights-filter-created-range"
      >
        <span class="filter-label">Report created on</span>
        <el-date-picker
          v-model="filters.createdRange"
          type="daterange"
          value-format="YYYY-MM-DD"
          range-separator="to"
          start-placeholder="From date"
          end-placeholder="To date"
          unlink-panels
        />
      </label>
    </div>

    <div class="filter-actions">
      <div class="filter-meta">
        <p v-if="filterError" class="filter-error" role="alert">
          {{ filterError }}
        </p>
        <p class="time-note">
          Time basis: application local time
          <template v-if="props.zoneId">({{ props.zoneId }})</template>.
          Date boundaries are inclusive; empty range uses the backend default
          (last 30 calendar days).
        </p>
      </div>

      <div class="filter-buttons">
        <el-button type="primary" native-type="submit" :icon="Search">
          Apply filters
        </el-button>
        <el-button :icon="Delete" @click="resetFilters">
          Clear filters
        </el-button>
      </div>
    </div>
  </form>
</template>

<style scoped>
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
  gap: 16px;
  align-items: flex-start;
  justify-content: space-between;
  padding-top: 14px;
  margin-top: 16px;
  border-top: 1px solid #f1f5f9;
}

.filter-meta {
  min-width: 0;
}

.filter-error {
  margin: 0 0 6px;
  color: #b91c1c;
  font-size: 12px;
}

.time-note {
  max-width: 640px;
  margin: 0;
  color: #94a3b8;
  font-size: 11px;
  line-height: 1.5;
}

.filter-buttons {
  display: flex;
  flex: none;
  flex-wrap: wrap;
  gap: 8px;
  margin-left: auto;
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

  .filter-actions {
    flex-direction: column;
  }

  .filter-buttons {
    margin-left: 0;
  }
}

@media (max-width: 640px) {
  .filter-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .filter-field--wide {
    grid-column: auto;
  }
}
</style>
