# Phase 11.3-B2-A 调查报告 — 前端分类趋势实现调查

> 阶段：Phase 11.3-B2-A（Frontend Category Trend Investigation）  
> 分支：`phase11/dashboard`  
> 基线 HEAD：`27e3a41161cfa86ee2956ba0b3626a2bcc71eec7`  
> 调查日期：2026-11-14  
> 性质：**严格只读调查**。本阶段未修改任何前端、后端、测试、配置、数据库、`docs/DEVELOPMENT_STATUS.md` 或既有 Phase 报告；唯一新增文件为本报告。  
> 调查结论：**推荐方案 B —— 保留现有 `TrendChart.vue`，新增独立 `CategoryTrendChart.vue`，复用现有 SVG 几何/格式化工具，并以 additive 方式增加多系列几何函数。B2-B 必须同时修复现有图表在 DAY/WEEK 切换期间“旧 points + 新 granularity”不一致的问题。**

---

## 1. 调查结论摘要

### 1.1 当前事实

1. `/insights` 页面由 `frontend/src/views/InsightsView.vue` 实现。
2. 现有 Review/Finding 趋势图由 `frontend/src/components/insights/TrendChart.vue` 实现。
3. `TrendChart.vue` **只支持两条硬编码 series**：
   - `reviewCount`
   - `findingCount`
   - `highSeverityFindingCount` 只出现在图表下方的数据表中，不是 SVG 折线。
4. 现有趋势图已有：
   - SVG 折线 + 面积；
   - 原生 SVG `<title>` 悬停提示；
   - Y 轴 5 个刻度；
   - X 轴按桌面/窄屏采样 8/4 个刻度；
   - `<details>` 数据表；
   - 空状态。
5. 现有图例是 `aria-hidden="true"` 的两项颜色色块，只用于视觉参考。
6. `StatisticsTrendPoint` 当前没有分类字段。
7. Phase 11.3-B1 后端 DTO 已真实包含：
   - `bugCount`
   - `securityCount`
   - `performanceCount`
   - `qualityCount`
   - `unknownCategoryCount`
8. 后端字段为 Java primitive `long`，JSON 使用默认 camelCase，字段始终存在且为数字，不会为 `null`。
9. 当前 `InsightsView` 在 DAY/WEEK 切换时立即修改 `granularity` ref，但 `overview` 仍是上一次响应。切换请求完成前，`TrendChart` 会收到“旧 points + 新 granularity”，存在标签与数据不一致的过期显示风险。
10. 当前 composable 已具备：
    - 单飞请求；
    - `AbortController`；
    - 单调 sequence guard；
    - unmount abort。
    请求竞争本身已有保护，但 UI 层仍需避免展示过期快照。

### 1.2 推荐结论

**推荐方案 B：新增独立 `CategoryTrendChart.vue`。**

理由：

- 不触碰现有 `TrendChart.vue`，现有 Review/Finding 图表零回归风险。
- 新图表可以使用单一 `StatisticsTrend` 快照 prop，强制 points、hasData、granularity 来自同一个 overview 响应。
- 复用现有 `trend-geometry.ts` 的坐标/刻度算法和 `statistics-format.ts` 的格式化函数。
- 新图表可以独立设计五系列图例、虚线样式、标记点和数据表，不把现有两系列组件变成条件分支集合。
- 后续增加分类或调整颜色/线型时，不需要修改已验收的 Review/Finding 图表。

### 1.3 B2-B 必须解决的关键问题

1. 给 `StatisticsTrendPoint` 增加 5 个 required `number` 字段。
2. 新增五系列 SVG 折线图，且：
   - 不新增 ECharts / Chart.js / 任何图表依赖；
   - 五条线同时可区分；
   - 图例、数据表、零值、UNKNOWN 均完整；
   - 全部为 0 时仍显示图表而不是空状态。
3. `InsightsView` 必须用 **同一个 overview 响应中的 `trend.granularity` 与 `trend.points`** 驱动两张趋势图。
4. DAY/WEEK 切换期间不得把旧 points 当作新 granularity 展示。
5. 不修改后端；只消费 B1 已验收字段。

---

## 2. 当前分支、HEAD 与工作区基线

### 2.1 Git 基线

调查开始时执行并记录：

```text
分支：phase11/dashboard
HEAD：27e3a41161cfa86ee2956ba0b3626a2bcc71eec7
HEAD 提交：Merge pull request #8 from zhangyu1108l/feature/phase10-mysql-history
HEAD 提交时间：2026-11-10 19:39:25 +0800
main..HEAD：0
HEAD..main：0
```

### 2.2 工作区状态

`git status --short --branch` 统计：

```text
已修改（tracked）：6
已删除（tracked）：1
status 行数：61
未跟踪文件（git ls-files --others --exclude-standard）：128
```

已修改文件：

```text
.gitignore
backend/spring-service/src/main/java/cn/codesentinel/review/ReviewHistoryQueryService.java
backend/spring-service/src/main/java/cn/codesentinel/task/ReviewReportRepository.java
backend/spring-service/src/main/resources/application.yml
backend/spring-service/src/test/java/cn/codesentinel/CodeSentinelApplicationTests.java
docs/DEVELOPMENT_STATUS.md
```

已删除文件：

```text
frontend/.gitkeep
```

`git diff --stat` 基线：

```text
 .gitignore                                         |   6 +
 .../review/ReviewHistoryQueryService.java          |   8 +-
 .../codesentinel/task/ReviewReportRepository.java  |  44 +++++-
 .../src/main/resources/application.yml             |   3 +
 .../codesentinel/CodeSentinelApplicationTests.java |   4 +
 docs/DEVELOPMENT_STATUS.md                         | 156 ++++++++++++++++-----
 frontend/.gitkeep                                  |   0
 7 files changed, 182 insertions(+), 39 deletions(-)
```

`git diff --name-only` 基线：

```text
.gitignore
backend/spring-service/src/main/java/cn/codesentinel/review/ReviewHistoryQueryService.java
backend/spring-service/src/main/java/cn/codesentinel/task/ReviewReportRepository.java
backend/spring-service/src/main/resources/application.yml
backend/spring-service/src/test/java/cn/codesentinel/CodeSentinelApplicationTests.java
docs/DEVELOPMENT_STATUS.md
frontend/.gitkeep
```

关键事实：

- Phase 11 的前端源码整体仍为未跟踪文件，尚未形成 Phase 11 提交。
- 当前 HEAD 与 `main` 指向同一个 Phase 10 合并提交。
- 上述修改、删除、未跟踪内容均为本任务开始前已存在，本阶段未覆盖、未恢复、未清理。
- `docs/DEVELOPMENT_STATUS.md` 基线 mtime 为 `2026-11-10 20:07:48`，本阶段未修改。
- 本阶段未执行任何 Git 写操作。

### 2.3 本阶段实际读取范围

本阶段只读取了：

```text
frontend/src/views/InsightsView.vue
frontend/src/components/insights/*
frontend/src/api/statistics.ts
frontend/src/api/client.ts
frontend/src/api/index.ts
frontend/src/types/statistics.ts
frontend/src/types/api.ts
frontend/src/composables/*
frontend/src/utils/*
frontend/src/__tests__/*
frontend/vitest.config.ts
frontend/vite.config.ts
frontend/package.json
frontend/tsconfig.app.json
frontend/src/assets/styles/main.css
frontend/src/layouts/DashboardLayout.vue
frontend/src/router/index.ts
frontend/src/components/SidebarNav.vue
frontend/components.d.ts
backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsTrendPoint.java
backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsTrend.java
backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsService.java
backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsOverviewResponse.java
backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsRange.java
backend/spring-service/src/main/java/cn/codesentinel/controller/DashboardStatisticsController.java
backend/spring-service/src/test/java/cn/codesentinel/controller/DashboardStatisticsControllerTest.java
docs/reports/Phase11_3_B1_Implementation_Report.md
docs/reports/Phase11_2_4_C_Acceptance_Report.md
docs/reports/Phase11_3_A_Investigation_Report.md
```

本阶段未运行前端测试、构建或类型检查，以保持严格只读；现有测试基线来自 Phase 11.2.4-C 验收报告，且 B1 未修改前端。

---

## 3. Insights 页面当前组件结构

### 3.1 路由与入口

路由定义于 `frontend/src/router/index.ts`：

```text
/insights
  name: insights
  component: () => import('@/views/InsightsView.vue')
  meta.title: Review Insights
```

侧边栏 `frontend/src/components/SidebarNav.vue` 中对应菜单项为：

```text
Review Insights
```

### 3.2 `InsightsView.vue` 的组件依赖

真实 import：

```text
@/components/insights/DistributionBars.vue
@/components/insights/InsightsFilterBar.vue
@/components/insights/ReviewComparisonTable.vue
@/components/insights/StatCard.vue
@/components/insights/TrendChart.vue
@/composables/useReviewStatistics
@/composables/useStatisticsOverview
@/types/statistics
@/utils/statistics-format
```

### 3.3 页面状态

`InsightsView.vue` 当前维护：

```text
appliedFilters: StatisticsFilters
granularity: StatisticsGranularity = 'DAY'
page = 1
size = 20
sort = 'createdAt'
direction = 'desc'

overviewState = useStatisticsOverview()
reviewState = useReviewStatistics()
```

派生状态：

```text
overview / overviewLoading / overviewError
reviews / reviewsLoading / reviewsError
summary / dataQuality / range
initialOverviewLoading
initialReviewsLoading
refreshingOverview
refreshingReviews
isEmpty = overview 存在且 summary.reviewCount === 0
qualityMessages
workspace warning
totalReviewRows
rangeLabel
各 StatCard 格式化值
```

### 3.4 页面模板纵向顺序

当前真实顺序：

```text
1. page-heading
   - eyebrow / 标题 / 副标题
   - 状态 pill
   - Refresh 按钮

2. range-strip
   - Range
   - Time basis
   - Generated

3. InsightsFilterBar
   - owner / repo / prNumber
   - taskStatus / aiStatus / publishStatus
   - createdRange
   - Apply filters / Clear filters

4. quality-alert（有数据质量警告时）

5. overview-error（首次 overview 失败且无数据时）

6. template v-if="overview || !overviewError"
   a. overview 刷新失败 inline-warning
   b. summary-section
      - 10 个 StatCard
      - 首次加载 skeleton
      - refreshingOverview 的 “Updating statistics…”
      - isEmpty 时 empty-banner
      - scope-note
   c. insights-grid（2 列）
      - Findings by category（DistributionBars）
      - Findings by severity（DistributionBars）
      - GitHub publish status（DistributionBars）
      - AI delivery status（DistributionBars）
   d. trend-panel（全宽）
      - 标题 Review and finding trend
      - DAY/WEEK granularity-toggle
      - TrendChart

7. comparison-panel（全宽）
   - 首次加载 skeleton
   - 首次失败 error
   - 刷新失败 inline-warning
   - refreshing note
   - el-empty 或 ReviewComparisonTable

8. quality-panel（全宽）
   - 9 个数据质量计数
```

### 3.5 布局关系

`insights-grid` 的真实 CSS：

```css
.insights-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
```

`@media (max-width: 900px)` 时变为单列。

`summary-grid` 使用：

```css
grid-template-columns: repeat(auto-fit, minmax(185px, 1fr));
```

页面容器 `.page` 来自 `frontend/src/assets/styles/main.css`：

```css
width: 100%;
max-width: 1440px;
padding: 26px 30px 40px;
margin: 0 auto;
```

`@media (max-width: 720px)` 时页面 padding 变为 `20px 16px 32px`。

### 3.6 加载与刷新流程

```text
onMounted
  → loadAll()
      → Promise.allSettled([
           loadOverview(overviewQuery()),
           loadReviews(reviewsQuery()),
         ])

handleApply(filters)
  → appliedFilters = filters
  → page = 1
  → loadAll()

handleReset()
  → appliedFilters = {}
  → page = 1
  → loadAll()

handleGranularityChange(next)
  → 相同值直接返回
  → granularity.value = next
  → loadOverview()（只刷新 overview）

handlePageChange / handleSizeChange / handleSortChange
  → 只刷新 reviews

Refresh 按钮
  → loadAll()

onBeforeUnmount
  → overviewState.abort()
  → reviewState.abort()
```

### 3.7 现有空状态

`isEmpty` 只判断 `summary.reviewCount === 0`。当 overview 存在但没有任何报告时：

- 显示 `data-testid="insights-empty"` 的 empty-banner；
- trend 面板仍然渲染，`TrendChart` 内部根据 `hasData=false` 显示空状态；
- 四个分布图使用 `DistributionBars` 的空提示；
- comparison 使用 `el-empty`。

---

## 4. `TrendChart.vue` 真实实现分析

文件：`frontend/src/components/insights/TrendChart.vue`

### 4.1 Props

```ts
const props = defineProps<{
  points: StatisticsTrendPoint[]
  hasData: boolean
  granularity: StatisticsGranularity
}>()
```

组件没有接收分类字段，也没有接收 `StatisticsTrend` 对象。

### 4.2 视口检测

```ts
const compact = ref(false)
let mediaQuery: MediaQueryList | undefined

onMounted(() => {
  mediaQuery = window.matchMedia('(max-width: 640px)')
  compact.value = mediaQuery.matches
  mediaQuery.addEventListener('change', syncViewport)
})

onBeforeUnmount(() => {
  mediaQuery?.removeEventListener('change', syncViewport)
})
```

### 4.3 数据到几何的映射

```ts
const geometry = computed(() =>
  buildTrendGeometry(
    props.points.map((point) => point.reviewCount),
    props.points.map((point) => point.findingCount),
    compact.value
      ? {
          width: 360,
          height: 230,
          paddingLeft: 34,
          paddingRight: 12,
          paddingTop: 16,
          paddingBottom: 32,
          maxXTicks: 4,
        }
      : {},
  ),
)
```

桌面默认几何参数来自 `frontend/src/utils/trend-geometry.ts`：

```text
width = 720
height = 260
paddingLeft = 46
paddingRight = 18
paddingTop = 18
paddingBottom = 36
maxXTicks = 8
```

### 4.4 SVG 绘制内容

当前 SVG 包含：

1. 5 条 Y 轴网格线；
2. 5 个 Y 轴标签；
3. 2 个面积 path：
   - `trend-area--finding`
   - `trend-area--review`
4. 2 个折线 path：
   - `trend-line--finding`
   - `trend-line--review`
5. Review 系列每个点一个 `<circle>`，内嵌 `<title>`；
6. Finding 系列每个点一个 `<circle>`，内嵌 `<title>`；
7. X 轴采样标签；
8. `role="img"`、`aria-label`、`<title>`、`<desc>`。

关键事实：

- SVG 只画 **两条线**。
- `highSeverityFindingCount` 只出现在下方数据表中，不是第三条线。
- 没有多系列抽象，没有 series 数组，没有动态图例。
- 没有自定义 tooltip / crosshair / hover overlay；只有 SVG 原生 `<title>` 悬停提示。

### 4.5 图例

```html
<div class="trend-legend" aria-hidden="true">
  <span class="trend-legend__item">
    <span class="trend-swatch trend-swatch--review" />
    Review reports
  </span>
  <span class="trend-legend__item">
    <span class="trend-swatch trend-swatch--finding" />
    Findings
  </span>
</div>
```

特点：

- 两项；
- 纯颜色色块；
- 整个图例 `aria-hidden="true"`；
- 屏幕阅读器不会读取图例，但 SVG 的 `aria-label` 和 `<title>`/`<desc>` 提供总体描述。

### 4.6 数据表

```html
<details class="trend-table">
  <summary>Data table</summary>
  <table>
    <thead>
      <tr>
        <th scope="col">Bucket</th>
        <th scope="col">Reviews</th>
        <th scope="col">Findings</th>
        <th scope="col">High + Critical</th>
      </tr>
    </thead>
    ...
  </table>
</details>
```

数据表提供：

- bucket 起止日期；
- reviewCount；
- findingCount；
- highSeverityFindingCount。

这是当前图表唯一的键盘/屏幕阅读器可访问的精确值入口。

### 4.7 空状态

```html
<el-empty
  v-if="!hasPoints"
  class="trend-empty"
  description="No review reports in the selected range."
/>
```

`hasPoints = hasData && points.length > 0`。

因此：

- 没有报告 → 空状态；
- 有报告但所有 Finding 为 0 → 仍显示图表（因为 `hasData=true`、points 非空）。

### 4.8 响应式处理

- `matchMedia('(max-width: 640px)')`；
- 窄屏 viewBox `0 0 360 230`；
- 最多 4 个 X 轴刻度；
- SVG `width: 100%; height: auto; preserveAspectRatio="xMidYMid meet"`；
- 图例 `flex-wrap: wrap`；
- 数据表容器 `overflow-x: auto`；
- `@media (max-width: 640px)` 时 X 轴字体和数据表字体略小。

### 4.9 现有图表能否直接支持五系列

不能直接支持。需要至少以下改造之一：

- 把 `TrendChart` 改成通用多系列组件；
- 新增一个通用多系列组件；
- 在 `TrendChart` 内增加 `mode` / `series` / `categoryPoints` 等条件分支。

`trend-geometry.ts` 当前的 `buildTrendGeometry(reviewValues, findingValues, options)` 也固定返回：

```text
reviewPoints
findingPoints
```

它不能直接表达 5 条 series 的数组。

### 4.10 可复用部分

可以复用的现有工具：

```text
frontend/src/utils/trend-geometry.ts
  - niceAxisMax
  - sampleTickIndexes
  - buildLinePath
  - ChartPoint
  - ChartTick
  - ChartAxisTick
  - TrendGeometryOptions

frontend/src/utils/statistics-format.ts
  - formatDateOnly
  - formatMetricNumber
  - formatTrendBucketLabel
  - formatBucketLabel
```

不能直接复用：

```text
TrendChart.vue 的 props、数据映射、图例、SVG 模板、数据表列定义
buildTrendGeometry 的固定双系列返回结构
```

---

## 5. API 与 TypeScript 类型分析

### 5.1 统计 API 文件

文件：`frontend/src/api/statistics.ts`

常量：

```ts
export const STATISTICS_OVERVIEW_ENDPOINT =
  '/api/dashboard/statistics/overview'
export const STATISTICS_REVIEWS_ENDPOINT =
  '/api/dashboard/statistics/reviews'
```

Overview 请求：

```ts
export function getStatisticsOverview(
  query: StatisticsOverviewQuery,
  signal?: AbortSignal,
): Promise<StatisticsOverviewResponse> {
  return apiGet<StatisticsOverviewResponse>(
    STATISTICS_OVERVIEW_ENDPOINT,
    signal,
    {
      ...toFilterParams(query),
      granularity: query.granularity,
    },
  )
}
```

`toFilterParams` 会：

- trim `owner` / `repo`；
- 省略空白字符串；
- 传递 `prNumber`、`taskStatus`、`publishStatus`、`aiStatus`；
- 传递 `createdFrom` / `createdTo`；
- 始终发送 `granularity`。

### 5.2 当前 TypeScript 类型

文件：`frontend/src/types/statistics.ts`

```ts
export type StatisticsGranularity = 'DAY' | 'WEEK'

export interface StatisticsTrendPoint {
  bucketStart: string
  bucketEnd: string
  reviewCount: number
  findingCount: number
  highSeverityFindingCount: number
}

export interface StatisticsTrend {
  granularity: StatisticsGranularity
  hasData: boolean
  points: StatisticsTrendPoint[]
}

export interface StatisticsOverviewResponse {
  range: StatisticsRange
  generatedAt: string
  summary: StatisticsSummary
  trend: StatisticsTrend
  dataQuality: StatisticsDataQuality
}
```

`StatisticsRange` 也包含 `granularity`：

```ts
export interface StatisticsRange {
  createdFrom: string
  createdTo: string
  zoneId: string
  granularity: StatisticsGranularity
}
```

`StatisticsSummary.categoryCounts` 是：

```ts
categoryCounts: StatisticsCount[]
```

`StatisticsCount` 是：

```ts
export interface StatisticsCount {
  key: string
  count: number
}
```

### 5.3 当前分类数据的类型缺口

`StatisticsTrendPoint` **没有**以下字段：

```text
bugCount
securityCount
performanceCount
qualityCount
unknownCategoryCount
```

而 `StatisticsReviewItem`（逐 Review 行）已经包含这 5 个字段，但它们不是时间序列，不能用于趋势图。

### 5.4 B2-B 需要调整的类型

只需要在 `StatisticsTrendPoint` 中追加 5 个 required `number` 字段：

```ts
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
```

不建议把这些字段改成 optional。原因：

- B1 后端 DTO 使用 primitive `long`；
- Jackson 不会输出 `null`；
- 字段缺失属于契约违约，不应被类型系统默认为“可能存在”。

运行时仍应在图表组件中做防御性校验，见第 8 节。

### 5.5 Overview 请求与刷新机制

Composable：`frontend/src/composables/useStatisticsOverview.ts`

行为：

```text
load(query)
  → activeRequest?.abort()
  → new AbortController()
  → sequence = ++requestSequence
  → loading = true
  → error = ''
  → getStatisticsOverview(query, signal)
  → 成功后检查 disposed / aborted / sequence
  → data = result
  → 失败后检查 disposed / aborted / sequence
  → error = getStatisticsErrorMessage(...)
  → finally 仅在最新 sequence 时 loading = false
```

Composable 返回：

```ts
{ data, loading, error, load, abort }
```

`useReviewStatistics.ts` 使用完全相同的单飞 / sequence / abort 模式。

### 5.6 DAY/WEEK 切换传递方式

当前：

```ts
const granularity = ref<StatisticsGranularity>('DAY')

function overviewQuery() {
  return {
    ...appliedFilters.value,
    granularity: granularity.value,
  }
}

function handleGranularityChange(next: StatisticsGranularity): void {
  if (next === granularity.value) {
    return
  }
  granularity.value = next
  void loadOverview()
}
```

因此：

- 请求参数中的 `granularity` 来自 ref；
- 切换时 ref 立即变化；
- 旧 `overview` 仍然保留到新响应成功；
- 当前 `TrendChart` 接收 `:granularity="granularity"`，会立即显示新标签，但 points 还是旧响应的。

**这是 B2-B 必须修复的过期显示问题。**

### 5.7 重复请求与请求竞争风险

已有保护：

- 每次 `load` 先 abort 上一次；
- sequence guard 丢弃旧响应；
- unmount 时 abort；
- `loadAll()` 使用 `Promise.allSettled`，overview 与 reviews 独立失败；
- granularity 相同值直接 return；
- page/size/sort 只刷新 reviews。

当前没有发现：

- `onMounted` 重复触发；
- watch 导致的双重请求；
- overview 与 reviews 共享请求；
- 同一 composable 内并行请求未被 abort 的路径。

需要注意但不由 composable 解决：

- granularity ref 与旧 data 的 UI 错配；
- 筛选条件变化时旧 overview 仍短暂显示（现有 “Updating statistics…” 行为）；
- `loadAll()` 在 Refresh 时会同时刷新两个端点，属于设计选择，不是重复请求。

### 5.8 API 类型是否需要调整

- `frontend/src/api/statistics.ts`：不需要修改。
- `frontend/src/api/client.ts`：不需要修改。
- `frontend/src/api/index.ts`：不需要修改。
- `frontend/src/composables/useStatisticsOverview.ts`：不需要修改。
- `frontend/src/composables/useReviewStatistics.ts`：不需要修改。
- 仅 `frontend/src/types/statistics.ts` 需要追加趋势字段。

---

## 6. Phase 11.3-B1 后端接口核对

### 6.1 DTO 真实源码

文件：`backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsTrendPoint.java`

```java
public record ReviewStatisticsTrendPoint(
        LocalDate bucketStart,
        LocalDate bucketEnd,
        long reviewCount,
        long findingCount,
        long highSeverityFindingCount,
        long bugCount,
        long securityCount,
        long performanceCount,
        long qualityCount,
        long unknownCategoryCount) {
}
```

### 6.2 JSON 字段名与类型

后端没有针对 statistics DTO 的 `@JsonProperty`，也没有发现全局 Jackson naming strategy 配置；`application.yml` 中无 `spring.jackson.property-naming-strategy`。因此使用 Jackson 默认 record component 名称：

```json
{
  "bucketStart": "2026-11-01",
  "bucketEnd": "2026-11-01",
  "reviewCount": 1,
  "findingCount": 45,
  "highSeverityFindingCount": 18,
  "bugCount": 12,
  "securityCount": 11,
  "performanceCount": 11,
  "qualityCount": 11,
  "unknownCategoryCount": 0
}
```

类型：

```text
bucketStart / bucketEnd : string（LocalDate，YYYY-MM-DD）
reviewCount              : number（Java long）
findingCount             : number（Java long）
highSeverityFindingCount : number（Java long）
bugCount                 : number（Java long）
securityCount            : number（Java long）
performanceCount         : number（Java long）
qualityCount             : number（Java long）
unknownCategoryCount     : number（Java long）
```

### 6.3 Controller 序列化测试证据

`backend/spring-service/src/test/java/cn/codesentinel/controller/DashboardStatisticsControllerTest.java`

测试 `shouldSerializeCategoryTrendCountsForDayAndWeek` 明确断言：

```text
$.trend.points[0].bugCount
$.trend.points[0].securityCount
$.trend.points[0].performanceCount
$.trend.points[0].qualityCount
$.trend.points[0].unknownCategoryCount
```

并验证：

- DAY 响应包含新字段；
- WEEK 响应包含新字段；
- 0 值序列化为 `0`；
- 原有 `reviewCount` / `findingCount` / `highSeverityFindingCount` 仍存在；
- 空趋势仍为 `hasData=false`、`points=[]`。

### 6.4 统计口径

`ReviewStatisticsService.buildTrend`：

```text
reviewCount++
if (findingsConsistent(report)) {
  findingCount += ...
  highSeverityFindingCount += CRITICAL + HIGH
  bugCount += ...
  securityCount += ...
  performanceCount += ...
  qualityCount += ...
  unknownCategoryCount += ...
}
```

分类计数与 `summary.categoryCounts` 使用：

- 同一个 `Snapshot`；
- 同一批 `ReportStatisticsRow` / `FindingAggregateRow`；
- 同一个 `findingsConsistent` 过滤；
- 同一组 `FindingAggregateRow` getter。

B1 报告已用单元测试、真实 MySQL IT、只读验收库 IT 验证：

```text
SUM(trend.bugCount)
+ SUM(trend.securityCount)
+ SUM(trend.performanceCount)
+ SUM(trend.qualityCount)
+ SUM(trend.unknownCategoryCount)
= summary.categoryCounts 的对应分类总数
```

前端不应重新定义分类口径，也不应从 Review History / Review Detail 推导分类趋势。

### 6.5 零填充与空范围

- 范围有报告时：范围内每个 DAY/WEEK 桶都返回，空桶所有计数为 `0`；
- 范围无报告时：`hasData=false`、`points=[]`；
- DAY 桶：应用本地自然日；
- WEEK 桶：ISO-8601 周（周一到周日），首尾周可能超出请求边界；
- 最大范围：366 个自然日；
- 默认范围：最近 30 个自然日。

---

## 7. 方案 A / 方案 B 对比

### 7.1 方案 A：扩展现有 `TrendChart.vue` 支持多系列

可能做法：

- 增加 `series` prop；
- 增加 `categoryPoints` prop；
- 增加 `mode: 'review-finding' | 'category'`；
- 修改 `buildTrendGeometry` 或新增多系列分支；
- 在模板中用 `v-if` 切换两套图例、SVG 路径和数据表。

优点：

- 只维护一个图表组件；
- 图例、表格、空状态等结构完全复用；
- 页面只引入一个趋势组件。

缺点：

- 现有组件从“固定两系列”变成“多模式条件组件”，复杂度明显上升；
- 现有 Review/Finding 图表的面积、图例、数据表、aria 文案都要加条件；
- 现有 5 个 `TrendChart.spec.ts` 测试需要扩展或调整；
- 任何多系列改动都可能影响已验收的两系列图表；
- 五系列图例、虚线、标记点、表格列会让单文件继续膨胀；
- 后续再增加系列或改变分类展示时，条件分支继续增加。

### 7.2 方案 B：保留 `TrendChart.vue`，新增 `CategoryTrendChart.vue`

可能做法：

- 新增 `CategoryTrendChart.vue`；
- 新增 `utils/category-trend.ts` 定义五系列；
- 在 `trend-geometry.ts` 中 additive 增加 `buildMultiSeriesGeometry`；
- 复用 `niceAxisMax`、`sampleTickIndexes`、`buildLinePath`、格式化函数；
- 页面并列使用两个趋势组件。

优点：

- 现有 `TrendChart.vue` **完全不改**，现有图表行为零回归；
- 新组件只处理五系列分类趋势，职责单一；
- 可以使用 `StatisticsTrend` 整体 prop，天然保证 points / hasData / granularity 同源；
- 新图表可以独立决定图例、虚线、标记点、数据表；
- 测试可以分开：现有 `TrendChart.spec.ts` 不动，新组件新增 spec；
- 后续扩展只改新组件和 series 配置；
- 仍然复用现有 SVG 几何和格式化工具，不重复造轮子。

缺点：

- 多一个组件文件；
- 需要新增一个多系列几何函数；
- 图例/视口监听等少量模板逻辑会与现有图表相似；
- 页面上会出现两个趋势面板。

### 7.3 对比表

| 维度 | 方案 A：扩展现有 TrendChart | 方案 B：新增 CategoryTrendChart |
|---|---|---|
| 对现有图表影响 | 高，需要改 props、模板、样式、测试 | **无**，现有组件不动 |
| 组件复用程度 | 高，但以条件分支为代价 | 中高，复用几何/格式化工具，组件职责独立 |
| 测试复杂度 | 高，需要覆盖两种模式及回归 | 中，新组件独立测试，现有测试保持 |
| 响应式布局 | 两种模式共用逻辑，窄屏风险集中 | 新图表可独立调优，风险隔离 |
| 代码耦合 | 高，五系列逻辑进入已验收组件 | 低，分类逻辑集中在新组件 |
| 后续扩展能力 | 中，继续加条件分支 | 高，扩展 series 配置即可 |
| 对现有 Review/Finding 趋势的破坏风险 | 中高 | **低** |
| 是否新增依赖 | 否 | 否 |
| 推荐度 | 不推荐 | **推荐** |

### 7.4 最终推荐

**采用方案 B。**

默认目标全部满足：

1. 保留现有 Review/Finding/High+Critical 趋势图的含义和显示效果；
2. 新增独立的 Findings by Category 图表；
3. 五个系列：BUG / SECURITY / PERFORMANCE / QUALITY / UNKNOWN；
4. 支持 DAY/WEEK；
5. 图例清晰；
6. 支持查看具体日期/周及分类数量；
7. 所有分类为 0 时仍正确显示；
8. loading/error/empty 状态清晰；
9. 适配桌面和窄屏；
10. 不增加 ECharts、Chart.js 或其他图表依赖。

---

## 8. 推荐的组件设计与页面布局

### 8.1 新增文件

```text
frontend/src/components/insights/CategoryTrendChart.vue
frontend/src/utils/category-trend.ts
```

### 8.2 `category-trend.ts`

建议定义：

```ts
import type { StatisticsTrendPoint } from '@/types/statistics'

export type CategoryTrendKey =
  | 'BUG'
  | 'SECURITY'
  | 'PERFORMANCE'
  | 'QUALITY'
  | 'UNKNOWN'

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
  dasharray: string | null
}

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
```

设计要点：

- `field` 用联合类型锁死，避免拼写错误；
- `dasharray` 让五条线不仅依赖颜色；
- 颜色沿用项目现有 indigo / red / amber / emerald / slate 语感；
- UNKNOWN 使用 slate，而不是浅灰，保证白底可见性；
- 图例文本仍使用 `Bug` / `Security` / `Performance` / `Quality` / `Unknown`，与现有 `formatBucketLabel` 一致。

### 8.3 `CategoryTrendChart.vue` props

建议使用单个 `StatisticsTrend` prop：

```ts
const props = defineProps<{
  trend: StatisticsTrend
}>()
```

理由：

- `points`、`hasData`、`granularity` 必须来自同一个 overview 响应；
- 避免调用方把 A 响应的 points 和 B 响应的 granularity 拼在一起；
- 比 `points + hasData + granularity` 三个独立 props 更安全。

### 8.4 多系列几何函数

建议在 `frontend/src/utils/trend-geometry.ts` 中 **additive** 增加：

```ts
export interface MultiSeriesGeometry {
  width: number
  height: number
  plotLeft: number
  plotTop: number
  plotRight: number
  baselineY: number
  axisMax: number
  seriesPoints: ChartPoint[][]
  xTicks: ChartTick[]
  yTicks: ChartAxisTick[]
}

export function buildMultiSeriesGeometry(
  seriesValues: number[][],
  options: TrendGeometryOptions = {},
): MultiSeriesGeometry
```

实现要求：

- 复用 `niceAxisMax`；
- 复用 `sampleTickIndexes`；
- 复用现有 padding 默认值和坐标公式；
- `axisMax` 取所有 series 的最大值；
- 全 0 时 `niceAxisMax(0)` 返回 4，所有点落在 baseline；
- `n=0` 返回空数组，不产生 `NaN`；
- `n=1` 单点居中；
- 不修改现有 `buildTrendGeometry` 的返回结构或行为。

这样：

- 现有 `TrendChart.vue` 继续使用 `buildTrendGeometry`；
- 新组件使用 `buildMultiSeriesGeometry`；
- 两者共享同一套轴/刻度算法。

### 8.5 SVG 绘制设计

新组件建议包含：

```text
1. 图例
   - 5 项
   - 每项：虚线/实线样本 + 文本标签
   - 图例不使用 aria-hidden；文本可被屏幕阅读器读取

2. SVG
   - role="img"
   - aria-label="Daily/Weekly findings by category trend from ... to ..."
   - <title> 与 <desc>
   - 5 条 Y 轴网格线
   - 5 个 Y 轴标签
   - 5 条 series path（points.length > 1 时）
   - 可选标记点（见性能章节）
   - X 轴采样标签

3. 周粒度说明
   - granularity === 'WEEK' 时显示 ISO-8601 周说明

4. 全 0 提示
   - 所有分类计数为 0 时显示：
     "All category counts are zero in the selected range."

5. 数据表
   - <details><summary>Data table</summary>
   - 列：Bucket / Bug / Security / Performance / Quality / Unknown / Findings
   - 所有数值直接来自 StatisticsTrendPoint
```

### 8.6 不使用面积填充

现有两系列图使用面积填充，是因为只有两条线。五条线如果都加面积，会互相遮挡、难以区分，也会增加视觉噪声。

建议新图表：

- 只画折线；
- 不画 area；
- 通过颜色 + 虚线 + 图例 + 数据表区分；
- 保留与现有图表一致的线宽、圆角、字体和坐标轴样式。

### 8.7 分类值映射

```ts
const seriesValues = computed(() =>
  CATEGORY_TREND_SERIES.map((series) =>
    props.trend.points.map((point) => point[series.field]),
  ),
)
```

关键点：

- 直接读取 5 个字段；
- 不使用 `summary.categoryCounts`；
- 不按 `review_finding` 重新聚合；
- 不从 review rows 推导；
- 不把 `categoryCounts` 总量平均到时间桶；
- UNKNOWN 是独立 series，不能合并进其他分类；
- 0 保持为 0。

### 8.8 缺失字段防御

B1 DTO 使用 primitive `long`，正常契约保证字段存在且非 `null`。但前端仍应防御：

```ts
function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}
```

建议：

```ts
const contractIncomplete = computed(() =>
  props.trend.points.some((point) =>
    CATEGORY_TREND_SERIES.some(
      (series) => !isFiniteNumber(point[series.field]),
    ),
  ),
)
```

行为：

- 正常情况 `false`，绘制图表；
- 如果旧后端、代理裁剪或错误 mock 导致字段缺失：
  - 不画折线；
  - 不把缺失值当成 0；
  - 显示 `role="alert"` 的契约警告；
  - 数据表中的缺失值使用 `formatMetricNumber` 显示 `—`；
  - 明确提示 “The category trend response is incomplete; missing values are not treated as zero.”

### 8.9 页面布局建议

推荐在当前 `trend-panel` 之后、`comparison-panel` 之前新增一个全宽面板：

```text
summary-section
insights-grid（四个分布面板）
trend-panel（现有 Review and finding trend）
category-trend-panel（新增 Findings by category over time）
comparison-panel（逐 Review 对比表）
quality-panel（数据质量）
```

新增面板建议结构：

```vue
<section
  v-if="overview"
  class="panel trend-panel category-trend-panel"
  aria-label="Findings by category trend"
  data-testid="category-trend-panel"
>
  <div class="panel-heading">
    <div>
      <h2 class="section-title">Findings by category over time</h2>
      <p class="section-subtitle">
        One line per category from finding-consistent reports. UNKNOWN is
        preserved as its own series. Uses the same Daily/Weekly selection as
        the review trend above.
      </p>
    </div>
    <span class="soft-badge">{{ loadedGranularityLabel }}</span>
  </div>

  <CategoryTrendChart :trend="overview.trend" />
</section>
```

设计理由：

- 不新增第二个 DAY/WEEK 控件，避免两个控件控制同一请求；
- 复用现有 `trend-panel` 的间距、响应式标题布局和 `soft-badge` 风格；
- 标题与现有 “Findings by category” 分布面板区分明显；
- 新面板全宽，五条线在桌面端有足够宽度；
- 窄屏下与现有 trend 面板一样纵向堆叠。

### 8.10 是否需要第二个 granularity toggle

不建议。

当前页面只有一个 overview 请求，DAY/WEEK 是同一个状态。新增第二个 toggle 会带来：

- 两个控件同一状态，读屏器出现两个同名 group；
- 两个控件可能不同步的视觉误解；
- 额外的测试歧义（现有测试通过文本查找 “Weekly” 按钮）。

保留现有 trend-panel 中的 toggle，新面板用 `soft-badge` 显示当前已加载的粒度即可。

---

## 9. DAY/WEEK 数据映射设计

### 9.1 核心原则

```text
请求参数 granularity = 用户选择（requestedGranularity）
图表数据 granularity = overview.trend.granularity（loadedGranularity）
points = overview.trend.points
hasData = overview.trend.hasData
```

**绝不允许：**

```text
points 来自上一次响应 + granularity 来自本次 ref
```

### 9.2 推荐 computed

```ts
const loadedTrend = computed(() => overview.value?.trend ?? null)

const loadedGranularity = computed(
  () => loadedTrend.value?.granularity ?? null,
)

const trendGranularityPending = computed(
  () =>
    !!overview.value &&
    overviewLoading.value &&
    overview.value.trend.granularity !== granularity.value,
)

const trendGranularityFailed = computed(
  () =>
    !!overview.value &&
    !!overviewError.value &&
    overview.value.trend.granularity !== granularity.value,
)
```

### 9.3 图表 props

现有 `TrendChart`：

```vue
<TrendChart
  :points="overview.trend.points"
  :has-data="overview.trend.hasData"
  :granularity="overview.trend.granularity"
/>
```

新 `CategoryTrendChart`：

```vue
<CategoryTrendChart :trend="overview.trend" />
```

### 9.4 DAY/WEEK 切换状态

```text
用户点击 Weekly
  → granularity = 'WEEK'
  → loadOverview()（abort 旧请求）
  → overview 仍是 DAY 快照
  → trendGranularityPending = true
  → 两个趋势图 body 显示 skeleton
  → 不渲染旧 DAY points
  → WEEK 响应成功
  → overview.trend.granularity = 'WEEK'
  → pending = false
  → 两个图表使用同一 WEEK points/granularity 渲染
```

如果 WEEK 请求失败：

```text
  → overview 仍是 DAY 快照
  → overviewError 非空
  → trendGranularityFailed = true
  → 两个趋势图不渲染旧 DAY points
  → 显示趋势粒度错误 + Retry
  → Retry 调用 loadOverview()，仍请求 WEEK
```

如果只是同一粒度的 Refresh 失败：

```text
  → granularity 与 overview.trend.granularity 相同
  → trendGranularityFailed = false
  → 图表保留上一次成功快照
  → 页面已有 inline warning 说明 “Showing the last successful response”
```

### 9.5 不在前端重新分桶

前端禁止：

- 把 DAY points 聚合成 WEEK；
- 把 WEEK points 拆成 DAY；
- 用 `createdAt` 重新按周分组；
- 用 `summary.categoryCounts` 平均/分配到桶；
- 用 Review History / Review Detail 推导分类趋势。

所有桶边界、零填充、ISO 周、时区语义均由后端负责。

### 9.6 UNKNOWN 处理

- `unknownCategoryCount` 必须是第五条独立 series；
- 不能合并到 QUALITY 或其他分类；
- 即使 UNKNOWN 全为 0，也保留图例和数据表列；
- 图例文本使用 `Unknown`，与现有 `formatBucketLabel('UNKNOWN')` 一致；
- 后端未识别 category 的语义不在前端重新解释。

### 9.7 零值策略

- 后端返回 `0` 时，前端显示 `0`；
- 全部分类为 0 时，图表仍渲染，所有线落在 baseline；
- 显示 “All category counts are zero in the selected range.”；
- 数据表所有分类单元格显示 `0`；
- 不使用“总和为 0”作为空状态判断；
- 空状态只由 `hasData === false` 或 `points.length === 0` 触发。

### 9.8 null / 缺失字段策略

- B1 契约明确保证 5 个字段存在且为非 null 的 primitive 数字；
- 因此 TypeScript 类型使用 required `number` 是合理的；
- 运行时仍做 `Number.isFinite` 防御；
- 缺失值显示 `—`，不显示 `0`；
- 缺失值不参与折线绘制；
- 组件显示契约警告，避免伪造趋势。

### 9.9 与 Summary 的一致性

后端保证：

```text
SUM(trend.bugCount) = summary.categoryCounts.BUG
SUM(trend.securityCount) = summary.categoryCounts.SECURITY
SUM(trend.performanceCount) = summary.categoryCounts.PERFORMANCE
SUM(trend.qualityCount) = summary.categoryCounts.QUALITY
SUM(trend.unknownCategoryCount) = summary.categoryCounts.UNKNOWN
```

前端：

- 不重新计算这些总量；
- 不修改后端口径；
- 不在数据表中增加“前端重新汇总”的分类总量；
- 数据表只展示每个 bucket 的后端字段值；
- `Findings` 列直接使用 `point.findingCount`，不是五类相加。

---

## 10. loading / error / empty 状态设计

### 10.1 状态矩阵

| 场景 | summary | 现有 trend 面板 | 新 category 面板 | 数据来源 |
|---|---|---|---|---|
| 首次加载，无 overview | 10 个 skeleton | 不渲染（overview 为空） | 不渲染 | 无 |
| 首次 overview 失败 | 页面 error panel | 不渲染 | 不渲染 | 无 |
| 同粒度刷新中 | 保留旧 summary + “Updating statistics…” | 保留旧图表 | 保留旧图表 | 上一次成功快照 |
| 同粒度刷新失败 | 保留旧 summary + inline warning | 保留旧图表 + warning | 保留旧图表 + warning | 上一次成功快照 |
| DAY/WEEK 切换中 | 保留 summary（与粒度无关） | **skeleton，隐藏旧 points** | **skeleton，隐藏旧 points** | 无（等待新响应） |
| DAY/WEEK 切换失败 | 保留 summary | **不渲染旧 points；显示粒度错误 + Retry** | **不渲染旧 points；显示粒度错误 + Retry 或共享错误** | 无 |
| `hasData=false` | 正常 summary | `el-empty` | `el-empty` | 空 |
| 有报告但五类全 0 | 正常 summary | 正常两系列图 | **正常五系列图 + 全 0 提示** | 后端零值 |
| 分类字段缺失 | 正常 summary | 正常 | **契约警告，不画分类线，表格显示 `—`** | 不完整响应 |

### 10.2 现有状态复用

继续复用：

```text
data-testid="overview-loading"
data-testid="overview-error"
data-testid="overview-refresh-error"
data-testid="insights-empty"
data-testid="reviews-loading"
data-testid="reviews-error"
```

新增建议：

```text
data-testid="trend-granularity-loading"
data-testid="trend-granularity-error"
data-testid="category-trend-panel"
data-testid="category-trend-empty"
data-testid="category-trend-contract-warning"
data-testid="category-trend-all-zero"
data-testid="category-trend-table"
```

### 10.3 Loading 文案

建议：

```text
Updating trend…
```

`skeleton` 外层使用：

```html
<div role="status" aria-live="polite">
```

并给 trend section 加：

```html
:aria-busy="trendGranularityPending"
```

### 10.4 Error 文案

粒度切换失败建议：

```text
Unable to load the weekly category trend. The chart is hidden because the
last successful snapshot is daily. Retry to load the selected granularity.
```

注意：

- 不显示原始后端 payload、SQL、堆栈；
- 复用 `getStatisticsErrorMessage` 的稳定文案；
- Retry 调用 `loadOverview()`，而不是 `loadAll()`，避免无意义刷新 reviews。

### 10.5 Empty 文案

分类趋势空状态建议：

```text
No review reports in the selected range.
```

与现有趋势保持一致。

如果 `hasData=true` 但 `points.length===0`（契约异常），建议显示：

```text
The selected range contains reviews but no trend buckets were returned.
```

不要把它当成正常空范围。

### 10.6 全 0 提示

```html
<p
  v-if="allCategoriesZero"
  class="category-trend-note"
  data-testid="category-trend-all-zero"
>
  All category counts are zero in the selected range.
</p>
```

这是提示，不是空状态；图表和数据表仍然存在。

---

## 11. 响应式布局设计

### 11.1 现有断点

项目已有：

```text
959px：侧边栏在 DashboardLayout 中隐藏，改为移动抽屉
900px：insights-grid 从两列变单列
720px：全局 .page padding 缩小
640px：趋势图 compact geometry、面板标题纵向排列、granularity toggle 拉伸
390px：Phase 11.2.4-C 验收使用的窄屏视口
```

### 11.2 新图表尺寸

建议与现有 `TrendChart` 完全一致：

```text
桌面：
  viewBox 0 0 720 260
  paddingLeft 46
  paddingRight 18
  paddingTop 18
  paddingBottom 36
  maxXTicks 8

窄屏（max-width: 640px）：
  viewBox 0 0 360 230
  paddingLeft 34
  paddingRight 12
  paddingTop 16
  paddingBottom 32
  maxXTicks 4
```

原因：

- 视觉高度与现有趋势面板一致；
- 复用同一套几何默认值；
- 390px 视口下 scaled SVG 不会溢出；
- 不需要引入新的布局系统。

### 11.3 图例

- `display: flex; flex-wrap: wrap; gap: 12px 16px;`
- 每项：`inline-flex; align-items: center; gap: 6px;`
- 文本不截断；
- 窄屏下允许换成两行/三行；
- 不设置固定宽度。

### 11.4 数据表

7 列在 390px 下必然超宽，因此：

```css
.category-trend-table-scroll {
  overflow-x: auto;
}
```

表头和单元格：

```css
white-space: nowrap;
```

这是项目现有 `trend-table__scroll` 的同一模式。

### 11.5 面板标题

复用现有：

```css
@media (max-width: 640px) {
  .trend-panel .panel-heading {
    align-items: flex-start;
    flex-direction: column;
  }
}
```

新面板也使用 `trend-panel` class，因此自动获得同样的窄屏标题布局。

### 11.6 图表本身是否需要横向滚动

不需要。

SVG 使用：

```html
<svg
  class="category-trend-svg"
  :viewBox="..."
  preserveAspectRatio="xMidYMid meet"
/>
```

CSS：

```css
display: block;
width: 100%;
height: auto;
overflow: visible;
```

窄屏下整体缩放，而不是横向滚动。

### 11.7 触摸与 hover

- 桌面：标记点 `<title>` 提供 hover 提示；
- 触摸屏：不依赖 hover；
- 精确值通过 `<details>` 数据表查看；
- 数据表在窄屏可横向滚动。

---

## 12. 可访问性设计

### 12.1 SVG 语义

新图表建议：

```html
<svg
  class="category-trend-svg"
  role="img"
  :aria-label="chartLabel"
  preserveAspectRatio="xMidYMid meet"
>
  <title>{{ chartLabel }}</title>
  <desc>
    Five line series: Bug, Security, Performance, Quality, and Unknown findings.
    Counts come from finding-consistent reports. Use the data table for exact
    values.
  </desc>
  ...
</svg>
```

`chartLabel` 应包含：

- Daily / Weekly；
- 起始 bucket；
- 结束 bucket。

示例：

```text
Daily findings by category trend from 2026-10-15 to 2026-11-13
```

### 12.2 图例

不要复制现有图例的 `aria-hidden="true"`。

建议：

```html
<ul class="category-trend-legend" aria-label="Category trend legend">
  <li v-for="series in CATEGORY_TREND_SERIES" :key="series.key">
    <svg class="category-trend-swatch" aria-hidden="true" focusable="false">
      <line ... :stroke="series.color" :stroke-dasharray="series.dasharray" />
      <circle ... :fill="series.color" />
    </svg>
    <span>{{ series.label }}</span>
  </li>
</ul>
```

这样：

- 视觉用户看到颜色 + 线型；
- 屏幕阅读器读取 5 个系列名称；
- 色盲用户可以通过虚线样式和数据表区分。

### 12.3 不以颜色作为唯一区分

五系列区分方式：

1. 颜色；
2. 虚线/点线/点划线；
3. 图例文本；
4. 数据表列名；
5. 每个标记点的 `<title>` 文本。

即使完全灰度打印，虚线样式和数据表仍然可区分。

### 12.4 数据表

建议：

```html
<details class="category-trend-table">
  <summary>Data table</summary>
  <div class="category-trend-table-scroll">
    <table>
      <thead>
        <tr>
          <th scope="col">Bucket</th>
          <th scope="col">Bug</th>
          <th scope="col">Security</th>
          <th scope="col">Performance</th>
          <th scope="col">Quality</th>
          <th scope="col">Unknown</th>
          <th scope="col">Findings</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(point, index) in trend.points" :key="point.bucketStart">
          <th scope="row">{{ bucketTitle(index) }}</th>
          <td>{{ formatMetricNumber(point.bugCount) }}</td>
          ...
        </tr>
      </tbody>
    </table>
  </div>
</details>
```

数据表是键盘和屏幕阅读器查看精确值的正式入口。

### 12.5 标记点

- 标记点 `<title>` 只作为鼠标悬停辅助；
- 不给 150+ 个 circle 加 `tabindex`，避免大量 Tab 停靠点；
- 键盘用户使用 `<details>` + 数据表；
- 如果标记点被隐藏（点数过多），数据表仍然完整。

### 12.6 状态语义

- loading：`role="status"` + `aria-busy="true"`；
- error：`role="alert"`；
- empty：`el-empty` 的可读描述；
- 全 0 提示：普通 `<p>`，可被读取；
- 契约警告：`role="alert"`。

### 12.7 对比度

建议颜色：

```text
BUG         #4f46e5
SECURITY    #dc2626
PERFORMANCE #b45309
QUALITY     #047857
UNKNOWN     #64748b
```

均在白底上具备可辨识对比度；同时保留虚线样式，避免仅靠颜色。

---

## 13. B2-B 需要修改的文件清单

### 13.1 计划修改

| 文件 | 变更 |
|---|---|
| `frontend/src/types/statistics.ts` | `StatisticsTrendPoint` 增加 5 个 required `number` 字段 |
| `frontend/src/utils/trend-geometry.ts` | additive 增加 `MultiSeriesGeometry` 与 `buildMultiSeriesGeometry`，不改变现有函数 |
| `frontend/src/utils/category-trend.ts` | **新增** 五系列配置（key / field / label / color / dasharray） |
| `frontend/src/components/insights/CategoryTrendChart.vue` | **新增** 独立五系列分类趋势图 |
| `frontend/src/views/InsightsView.vue` | 引入新面板；用同一 overview 快照驱动两张图；处理 DAY/WEEK pending/failed；修复现有图的 granularity 来源 |
| `frontend/src/__tests__/CategoryTrendChart.spec.ts` | **新增** 组件测试 |
| `frontend/src/__tests__/trend-geometry.spec.ts` | 增加多系列几何测试 |
| `frontend/src/__tests__/InsightsView.spec.ts` | 扩展 fixtures（新增 5 字段）；增加分类趋势、粒度切换、错误重试、无回归测试 |
| `frontend/src/__tests__/TrendChart.spec.ts` | 仅更新 `point()` fixture，补 5 个零字段；不改变现有行为断言 |
| `docs/reports/Phase11_3_B2_B_Implementation_Report.md` | **新增** B2-B 实施报告 |

### 13.2 可能由工具生成（不手工编辑）

| 文件 | 说明 |
|---|---|
| `frontend/components.d.ts` | `unplugin-vue-components` 可能在 dev/build 时自动加入 `CategoryTrendChart` 声明；该文件是生成文件，不应手工编辑。若构建后出现 diff，按项目既有约定处理。 |

### 13.3 明确不需要修改

```text
frontend/src/api/statistics.ts
frontend/src/api/client.ts
frontend/src/api/index.ts
frontend/src/composables/useStatisticsOverview.ts
frontend/src/composables/useReviewStatistics.ts
frontend/src/components/insights/TrendChart.vue
frontend/src/components/insights/DistributionBars.vue
frontend/src/components/insights/StatCard.vue
frontend/src/components/insights/InsightsFilterBar.vue
frontend/src/components/insights/ReviewComparisonTable.vue
frontend/src/utils/statistics-format.ts
frontend/src/utils/statistics-error.ts
frontend/package.json
frontend/package-lock.json
backend/**（全部）
数据库结构 / 迁移脚本
docs/DEVELOPMENT_STATUS.md
任何既有 Phase 报告
```

### 13.4 建议实施顺序

```text
1. types/statistics.ts
2. utils/category-trend.ts
3. utils/trend-geometry.ts（additive）
4. trend-geometry.spec.ts
5. CategoryTrendChart.vue
6. CategoryTrendChart.spec.ts
7. InsightsView.vue 集成
8. InsightsView.spec.ts + TrendChart.spec.ts fixture
9. type-check / test:unit / lint:check / build
10. 手工桌面 + 390px 窄屏检查
11. B2-B 实施报告
```

---

## 14. B2-B 测试清单

### 14.1 现有测试工具

```text
Vitest 4
@vue/test-utils
jsdom
unplugin-vue-components + Element Plus resolver
setupFiles: ./src/test/setup.ts
clearMocks: true
restoreMocks: true
```

现有测试文件共 15 个 spec；Phase 11.2.4-C 验收记录为 121 个测试通过。B1 未修改前端。

### 14.2 组件测试 `CategoryTrendChart.spec.ts`

至少覆盖：

| # | 测试 | 断言 |
|---|---|---|
| 1 | 五个系列正确渲染 | 5 条 series path / 5 个图例项 |
| 2 | 字段映射正确 | 每个分类使用对应字段，而不是 summary.categoryCounts |
| 3 | 图例完整 | Bug / Security / Performance / Quality / Unknown 全部存在 |
| 4 | DAY 标签 | `Daily findings by category trend`，无 weekly note |
| 5 | WEEK 标签 | `Weekly findings by category trend`，显示 ISO 周说明 |
| 6 | 某分类全 0 | 该 series 仍在图例/表格中，表格显示 `0` |
| 7 | 全部分类 0 | 仍渲染图表，不显示 empty；显示全 0 提示；表格全是 `0` |
| 8 | 空 points | 不渲染 svg，显示空状态 |
| 9 | 单点 | 显示标记点，不显示折线 path |
| 10 | UNKNOWN 独立 | 即使 summary.categoryCounts 没有 UNKNOWN，图表仍有第五条 series |
| 11 | 缺失字段 | 显示契约警告，不画分类线，表格显示 `—`，不显示虚假 0 |
| 12 | 悬浮提示 | 标记点 `<title>` 包含日期范围和分类数量 |
| 13 | 点数过多 | 超过标记点阈值时不渲染大量 circle，但数据表仍完整 |
| 14 | 窄屏 | mock matchMedia，viewBox `0 0 360 230`，X 轴刻度 ≤ 4 |
| 15 | 数据表 | 行数等于 points 数量；值直接来自 trend 字段 |

### 14.3 几何测试 `trend-geometry.spec.ts`

新增：

| # | 测试 |
|---|---|
| 1 | 多系列 axisMax 取所有 series 最大值 |
| 2 | 全 0 多系列全部落在 baseline，axisMax=4 |
| 3 | 单点居中 |
| 4 | 空 series 返回安全空几何，不产生 NaN |
| 5 | 多系列 xTicks 采样与现有算法一致 |

### 14.4 页面集成测试 `InsightsView.spec.ts`

新增/扩展：

| # | 测试 | 断言 |
|---|---|---|
| 1 | fixtures 补 5 字段 | 现有 121 个测试继续通过 |
| 2 | 新面板渲染 | `category-trend-panel` 存在，标题/图例完整 |
| 3 | 使用 trend 而不是 summary | summary.categoryCounts 与 trend 值不同，图表/表格显示 trend 值 |
| 4 | DAY/WEEK 切换中 | 两个趋势图 body 不显示旧 points；显示 `trend-granularity-loading` |
| 5 | DAY/WEEK 切换成功 | 只调用 overview 一次新增请求；两图使用新 granularity/points |
| 6 | DAY/WEEK 切换失败 | 显示 `trend-granularity-error`；不显示旧 points；Retry 调用 overview |
| 7 | 全 0 分类 | `hasData=true` + 全 0 points 时显示五系列图，不显示 empty |
| 8 | 空范围 | 两个趋势图都显示空状态；现有 `insights-empty` 行为不变 |
| 9 | 现有 Review/Finding 图无回归 | 原 `TrendChart` 仍渲染 Review/Finding 两条线；新面板不替换旧面板 |
| 10 | 请求竞争/Abort | 快速切换 DAY→WEEK→DAY，旧请求 signal aborted，旧响应不覆盖新状态 |
| 11 | 同粒度刷新失败 | 图表保留旧快照 + 现有 inline warning；不误判为 granularity mismatch |

### 14.5 现有测试回归

必须继续通过：

```text
frontend/src/__tests__/TrendChart.spec.ts
frontend/src/__tests__/trend-geometry.spec.ts（原有断言）
frontend/src/__tests__/InsightsView.spec.ts（原有断言）
frontend/src/__tests__/statistics-api.spec.ts
frontend/src/__tests__/statistics-format.spec.ts
frontend/src/__tests__/ReviewComparisonTable.spec.ts
frontend/src/__tests__/DashboardLayout.spec.ts
```

`TrendChart.spec.ts` 只需给 `point()` fixture 补 5 个零字段，不改变：

- 两系列渲染；
- aria-label；
- 数据表；
- 空状态；
- 单点；
- 窄屏 viewBox / 4 ticks。

### 14.6 测试工具限制

当前工具无法验证：

- 真实浏览器 CSS 布局；
- 390px 下实际面板堆叠、图例换行、表格横向滚动；
- SVG 实际像素渲染、线宽、颜色对比度；
- 真实触摸 hover 行为；
- 生产构建后的视觉表现。

`jsdom` 只适合：

- DOM 结构；
- props → 几何/path 属性；
- 文本；
- matchMedia mocked 分支；
- 事件与状态。

真实布局建议在 B2-B 完成后做一次：

```text
Chrome 桌面视口
Chrome 390×844 窄屏视口
DAY / WEEK
有数据 / 空数据 / 全 0 / 单点
```

可作为手工验证，不要求新增 Playwright/Puppeteer/Cypress 依赖。

### 14.7 B2-B 验证命令

```bash
cd frontend
npm run type-check
npm run lint:check
npm run test:unit
npm run build
```

定向测试：

```bash
npx vitest run \
  src/__tests__/CategoryTrendChart.spec.ts \
  src/__tests__/InsightsView.spec.ts \
  src/__tests__/TrendChart.spec.ts \
  src/__tests__/trend-geometry.spec.ts
```

注意：

- `npm run build` 可能触发 `components.d.ts` 生成更新；
- 不要手工编辑生成文件；
- 不新增依赖；
- 不修改 lock 文件。

---

## 15. 性能与风险分析

### 15.1 最大数据量

| 粒度 | 最大范围 | 最大点数 |
|---|---:|---:|
| DAY | 366 个自然日 | 366 |
| WEEK | 366 个自然日 | 最多约 54 个 ISO 周桶 |

WEEK 的 54 来自 ISO 周首尾可能超出请求边界；实际数量由后端分桶决定，前端不重新计算。

### 15.2 SVG 节点估算

静态节点：

```text
5 条网格线
5 个 Y 轴标签
最多 8 个 X 轴标签
5 条 series path
1 个 svg
1 个 title
1 个 desc
```

约 25 个固定 SVG 节点。

标记点：

- 若 `points.length <= 31`（桌面）或 `<= 10`（窄屏），渲染 5 × N 个 circle；
- 30 个 DAY 点桌面：150 个 circle；
- 54 个 WEEK 点：超过阈值，不渲染 circle；
- 366 个 DAY 点：不渲染 circle。

如果不做阈值限制，最坏情况是：

```text
5 × 366 = 1830 个 circle
+ 1830 个 <title>
```

建议设置阈值，避免不必要的重复 SVG 元素。

### 15.3 数据表 DOM

数据表即使折叠在 `<details>` 中，Vue 仍会渲染其子节点：

```text
366 行 × 7 列 ≈ 2562 个单元格
```

这是可接受的本地 Dashboard 规模，但属于 DOM 成本。若后续真实性能测试发现问题，可以在 B2-B 之后改为：

- `details` 展开时才 `v-if` 渲染表格；
- 或虚拟滚动。

B2-B 不建议为此引入复杂表格依赖。

### 15.4 计算成本

```text
buildMultiSeriesGeometry: O(5 × N)
buildLinePath: O(5 × N)
computed 缓存
N ≤ 366
```

成本很低。

### 15.5 网络与 Token 成本

- 不新增请求；
- 继续使用同一个 overview 响应；
- B1 已评估 366 点新增 5 个 long 字段约增加不超过 15 KB（未压缩）；
- 不发送代码、diff 或敏感数据到前端以外的服务。

### 15.6 风险清单

| 风险 | 影响 | 缓解 |
|---|---|---|
| 旧后端 / mock 缺少 5 字段 | 可能把缺失误画成 0 | 类型 required + 运行时 `Number.isFinite` 契约警告，表格显示 `—` |
| DAY/WEEK 切换旧 points + 新 granularity | 图表标签与数据不一致 | 图表只使用 `overview.trend` 快照；pending 时隐藏旧图 |
| 全 0 五条线重叠 | 只能看到最上层线 | 显示全 0 提示 + 完整数据表；不把全 0 当空状态 |
| 只靠颜色区分 | 色盲用户无法区分 | 颜色 + 虚线样式 + 图例文本 + 数据表 |
| 366 天大量 circle | SVG DOM 膨胀 | 标记点阈值；超阈值只画线 |
| 数据表 7 列过宽 | 窄屏溢出 | `overflow-x: auto` + `white-space: nowrap` |
| 修改现有 TrendChart | 已验收图表回归 | 方案 B：不修改 TrendChart.vue |
| fixture 类型报错 | 测试编译失败 | B2-B 统一补 5 个零字段 |
| 生成 `components.d.ts` | 额外 diff | 不手工编辑；构建后按既有约定处理 |
| 第二 granularity 控件 | 状态不同步/读屏歧义 | 只保留现有 toggle，新面板显示 badge |
| 面板标题与分布图重名 | 测试/用户混淆 | 使用 “Findings by category over time” 和独立 testid |
| 分类口径被前端改变 | 与 Summary 不一致 | 只读 trend 字段；不聚合、不重算、不推导 |

### 15.7 已知既有警告

Phase 11.2.4-C 的 5 项非阻塞警告仍存在：

1. 真实 UI 翻页未验证（验收库 6 行 < 最小页大小 10）；
2. `review_report.created_at` 无索引，统计查询全表扫描（后端未改）；
3. 验收库 IT 默认关闭；
4. 范围条省略微秒（显示层）；
5. E2E 使用 headless Chrome + CDP，窄屏为视口模拟，非真机。

这些不是 B2-A/B2-B 的阻断项，但 B2-B 的真实浏览器验证仍应记录同样的限制。

---

## 16. 明确不修改的文件和范围

本阶段（B2-A）明确未修改：

```text
frontend/**（全部）
backend/**（全部）
数据库结构、索引、迁移脚本
frontend/package.json
frontend/package-lock.json
docs/DEVELOPMENT_STATUS.md
任何既有 Phase 报告
```

本阶段未执行：

```text
git commit
git push
git merge
git rebase
git reset
git clean
git checkout
git switch
git stash
git cherry-pick
```

本阶段未进入：

```text
Phase 11.3-B2-B
Phase 12
```

B2-B 允许修改的范围严格限制在第 13 节列出的前端文件与测试；不允许修改后端、API 契约、数据库、依赖文件或已验收的 `TrendChart.vue` 行为。

---

## 17. Git 与工作区保护检查结果

### 17.1 调查前基线

| 项目 | 值 |
|---|---:|
| 分支 | `phase11/dashboard` |
| HEAD | `27e3a41161cfa86ee2956ba0b3626a2bcc71eec7` |
| `main..HEAD` | 0 |
| tracked modified | 6 |
| tracked deleted | 1 |
| status 行数 | 61 |
| untracked files | 128 |
| `git diff --stat` | 7 files changed, 182 insertions(+), 39 deletions(-) |

### 17.2 调查后核对

本阶段唯一新增文件：

```text
docs/reports/Phase11_3_B2_A_Investigation_Report.md
```

调查结束后将再次执行以下只读命令并与基线对比：

```text
git status --short --branch
git diff --stat
git diff --name-only
git ls-files --others --exclude-standard
git rev-parse HEAD
git branch --show-current
```

预期：

- 分支和 HEAD 不变；
- `git diff --stat` 不变；
- `git diff --name-only` 不变；
- tracked modified / deleted 不变；
- untracked files 仅从 128 变为 129；
- status 行数仅增加本报告；
- `docs/DEVELOPMENT_STATUS.md`、既有 Phase 报告、前端源码、后端源码均未改变。

实际核对结果：

| 项目 | 基线 | 调查后 | 差异 |
|---|---:|---:|---|
| 分支 | `phase11/dashboard` | `phase11/dashboard` | 无 |
| HEAD | `27e3a41161cfa86ee2956ba0b3626a2bcc71eec7` | `27e3a41161cfa86ee2956ba0b3626a2bcc71eec7` | 无 |
| tracked modified | 6 | 6 | 无 |
| tracked deleted | 1 | 1 | 无 |
| `git diff --stat` | 7 files, +182 / -39 | 7 files, +182 / -39 | 无 |
| `git diff --name-only` | 7 个既有路径 | 7 个既有路径 | 无 |
| status 行数 | 61 | 62 | +1（仅本报告） |
| untracked files | 128 | 129 | +1（仅本报告） |

结论：

- `git rev-parse HEAD` 与 `git branch --show-current` 输出与基线一致；
- `git diff --stat` 与 `git diff --name-only` 未变化，受保护文件未被修改；
- untracked 文件从 128 增加到 129，唯一新增文件为 `docs/reports/Phase11_3_B2_A_Investigation_Report.md`；
- 除本报告外，工作区与调查前基线一致。

### 17.3 受保护文件确认

本阶段未触碰：

```text
.gitignore
backend/spring-service/src/main/java/cn/codesentinel/review/ReviewHistoryQueryService.java
backend/spring-service/src/main/java/cn/codesentinel/task/ReviewReportRepository.java
backend/spring-service/src/main/resources/application.yml
backend/spring-service/src/test/java/cn/codesentinel/CodeSentinelApplicationTests.java
docs/DEVELOPMENT_STATUS.md
frontend/.gitkeep（删除状态保持）
frontend/**（全部现有文件）
```

未恢复、未删除、未覆盖任何既有工作区内容。

---

## 18. 最终结论

### 18.1 调查结论

1. 当前前端趋势图只支持 Review / Findings 两条硬编码 series；High + Critical 只在数据表中。
2. 当前 `StatisticsTrendPoint` 缺少 B1 新增的 5 个分类字段，B2-B 必须追加。
3. B1 后端字段、JSON 名称、类型、零填充和空范围语义均已核对，可作为前端稳定输入。
4. 当前 DAY/WEEK 切换存在旧 points 与新 granularity 错配的 UI 风险，B2-B 必须修复。
5. 当前 composable 的 abort + sequence guard 足以防止响应竞争，但界面层仍要避免展示过期快照。
6. 推荐方案 B：新增独立 `CategoryTrendChart.vue`，复用现有几何/格式化工具，不修改现有 `TrendChart.vue`。
7. 新图表必须使用五系列、虚线区分、可访问图例、数据表和全 0 提示，不新增图表依赖。
8. B2-B 的测试需要覆盖五类映射、图例、DAY/WEEK、零值、空数据、loading、error/retry、切换过期、请求竞争、窄屏和现有趋势图无回归。

### 18.2 推荐方案

```text
保留 TrendChart.vue
  +
新增 CategoryTrendChart.vue
  +
新增 category-trend.ts 五系列配置
  +
trend-geometry.ts additive 多系列几何
  +
InsightsView 使用同一个 overview.trend 快照
  +
pending / failed 粒度状态
```

### 18.3 停止点

Phase 11.3-B2-A 到此完成。等待 ChatGPT 审查和用户下一步授权；不进入 Phase 11.3-B2-B，不开始 Phase 12，不修改任何代码。
