# Phase 11.3-B2-B 实施报告 — 前端分类趋势图

> 阶段：Phase 11.3-B2-B（Frontend Category Trend Implementation）  
> 分支：`phase11/dashboard`  
> 基线 HEAD：`27e3a41161cfa86ee2956ba0b3626a2bcc71eec7`  
> 实施日期：2026-11-15  
> 依据：`docs/reports/Phase11_3_B2_A_Investigation_Report.md`  
> 结论：**已按调查报告的方案 B 完成。现有 `TrendChart.vue` 未修改；新增独立五分类趋势图；两张趋势图统一使用 `overview.trend` 快照；DAY/WEEK 切换期间旧数据不再与新粒度混用。type-check、lint、150 个单元测试、生产构建和 headless Chrome 验证均通过。**

---

## 1. 实际修改和新增文件

### 1.1 修改

| 文件 | 变更 |
|---|---|
| `frontend/src/types/statistics.ts` | `StatisticsTrendPoint` 增加 5 个 required `number` 字段 |
| `frontend/src/utils/trend-geometry.ts` | additive 增加 `MultiSeriesGeometry`、`buildMultiSeriesGeometry`；未改动现有函数 |
| `frontend/src/views/InsightsView.vue` | 引入新面板；统一趋势快照；修复 DAY/WEEK 旧数据错配；新增统一 pending/error 状态 |
| `frontend/src/__tests__/trend-geometry.spec.ts` | 增加 6 个多系列几何测试 |
| `frontend/src/__tests__/InsightsView.spec.ts` | 补充分类字段 fixture；增加 7 个集成测试 |
| `frontend/src/__tests__/TrendChart.spec.ts` | 仅给 `point()` fixture 补 5 个零字段，现有断言未改 |

### 1.2 新增

| 文件 | 说明 |
|---|---|
| `frontend/src/utils/category-trend.ts` | 五系列静态配置 |
| `frontend/src/components/insights/CategoryTrendChart.vue` | 独立五分类 SVG 趋势图 |
| `frontend/src/__tests__/CategoryTrendChart.spec.ts` | 16 个组件测试 |
| `docs/reports/Phase11_3_B2_B_Implementation_Report.md` | 本报告 |

### 1.3 工具自动生成

| 文件 | 说明 |
|---|---|
| `frontend/components.d.ts` | `npm run build` 自动加入 `CategoryTrendChart` 声明。该文件原本即为未跟踪文件，未手工编辑，未恢复。 |
| `frontend/dist/**` | 构建产物；命中 `frontend/.gitignore:12:dist`，未进入 Git 状态。 |

### 1.4 明确未修改

```text
frontend/src/components/insights/TrendChart.vue
frontend/src/api/statistics.ts
frontend/src/api/client.ts
frontend/src/api/index.ts
frontend/src/composables/useStatisticsOverview.ts
frontend/src/composables/useReviewStatistics.ts
frontend/package.json
frontend/package-lock.json
backend/**（全部）
数据库结构 / 数据 / 迁移
docs/DEVELOPMENT_STATUS.md
任何既有 Phase 报告
```

---

## 2. 组件结构

### 2.1 页面纵向结构

```text
InsightsView
├── page-heading
├── range-strip
├── InsightsFilterBar
├── quality-alert / overview-error / overview-refresh-error
├── summary-section
├── insights-grid（4 个分类/状态分布）
├── trend-panel（现有 Review and finding trend）
│   ├── DAY/WEEK 唯一切换控件
│   ├── pending skeleton 或 granularity error
│   └── TrendChart
├── category-trend-panel（新增）
│   ├── 标题 + loaded granularity badge
│   └── CategoryTrendChart
├── comparison-panel
└── quality-panel
```

新面板位于现有趋势面板之后、comparison 面板之前，全宽展示。

### 2.2 `CategoryTrendChart.vue`

```text
props
├── trend: StatisticsTrend
└── granularity: StatisticsGranularity

派生状态
├── activeGranularity = trend.granularity
├── granularityMismatch
├── missingCategorySeries
├── contractIncomplete
├── hasPoints / hasBucketsWithoutData
├── seriesValues（5 × N）
├── geometry = buildMultiSeriesGeometry(...)
├── seriesPaths（5 条 path）
├── allCategoriesZero
├── markerLimit / showMarkers
└── chartLabel

渲染
├── el-empty（无 points）
├── contract warning（缺字段 / 非有限值 / 粒度不匹配）
├── legend（5 项，可被读屏器读取）
├── SVG（网格、Y 轴、5 条折线、阈值内标记点、X 轴、title/desc）
├── WEEK ISO 说明
├── 全 0 提示
└── details 数据表（7 列）
```

`CategoryTrendChart` 不读取 `summary.categoryCounts`，不重新分桶，不从 Review History / Detail 推导数据。

---

## 3. 五系列字段映射

配置位于 `frontend/src/utils/category-trend.ts`：

| 顺序 | key | field | 图例文本 | 颜色 | 线型 |
|---:|---|---|---|---|---|
| 1 | `BUG` | `bugCount` | Bug | `#4f46e5` | 实线 |
| 2 | `SECURITY` | `securityCount` | Security | `#dc2626` | `8 4` |
| 3 | `PERFORMANCE` | `performanceCount` | Performance | `#b45309` | `2 4` |
| 4 | `QUALITY` | `qualityCount` | Quality | `#047857` | `10 4 2 4` |
| 5 | `UNKNOWN` | `unknownCategoryCount` | Unknown | `#64748b` | `4 4` |

字段类型为 required `number`：

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

约束：

- 直接读取后端 B1 字段；
- 不从 `summary.categoryCounts` 推导时间趋势；
- 不把 UNKNOWN 合并到 QUALITY；
- 不把缺失字段静默当作 `0`；
- 数据表 `Findings` 列直接使用 `point.findingCount`，不把五类相加。

---

## 4. 几何算法设计

`frontend/src/utils/trend-geometry.ts` 采用 additive 变更：

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

设计：

1. 所有系列共享同一 `pointCount`、X 轴坐标和 Y 轴比例。
2. 多系列长度不一致时取最短长度，保证每条线覆盖相同 bucket。
3. `axisMax = niceAxisMax(所有系列最大值)`。
4. 全 0 时 `niceAxisMax(0) = 4`，所有点落在 baseline。
5. 空数组返回 `seriesPoints: []`（或对应空数组）、`xTicks: []`，不产生 NaN。
6. 单点使用 `plotLeft + plotWidth / 2` 居中。
7. X 轴刻度继续使用 `sampleTickIndexes`。
8. 默认尺寸与现有图表一致：720×260、8 个 X 刻度；窄屏 360×230、4 个 X 刻度。
9. 未修改 `buildTrendGeometry`、`buildLinePath`、`buildAreaPath`、`niceAxisMax`、`sampleTickIndexes` 的签名或行为。

新增几何测试覆盖：

- 全部系列最大值；
- 全 0 / `axisMax = 4`；
- 单点居中；
- 空输入无 NaN；
- X 轴采样一致；
- 不等长系列截断。

---

## 5. DAY/WEEK 同步方案

### 5.1 数据来源

```text
请求粒度：granularity ref（用户选择）
图表粒度：overview.trend.granularity（已加载快照）
图表 points：overview.trend.points
图表 hasData：overview.trend.hasData
```

现有 `TrendChart` 的 `granularity` 由原来的 `granularity` ref 改为：

```vue
:granularity="overview.trend.granularity"
```

新图接收同一快照：

```vue
<CategoryTrendChart
  :trend="overview.trend"
  :granularity="overview.trend.granularity"
/>
```

因此两张图不会出现“一张新粒度、一张旧 points”。

### 5.2 pending / failed 判断

```ts
const trendGranularityPending = computed(
  () =>
    !!overview.value &&
    overviewLoading.value &&
    loadedGranularity.value !== granularity.value,
)

const trendGranularityFailed = computed(
  () =>
    !!overview.value &&
    !!overviewError.value &&
    !overviewLoading.value &&
    loadedGranularity.value !== granularity.value,
)
```

### 5.3 切换流程

```text
点击 Weekly
  → granularity = 'WEEK'
  → loadOverview()（只刷新 overview）
  → overview 仍是 DAY 快照
  → pending = true
  → 现有趋势面板显示 skeleton，TrendChart 不渲染
  → category-trend-panel 整体不渲染
  → WEEK 成功
  → overview.trend = WEEK 快照
  → 两张图同时使用 WEEK points / granularity 渲染

WEEK 失败
  → overview 仍是 DAY 快照
  → failed = true
  → 两张图均不渲染
  → 现有趋势面板显示唯一 granularity error + Retry
  → Retry 调用 loadOverview()

同粒度刷新失败
  → loaded === requested
  → failed = false
  → 两张图继续显示最后一次成功快照
  → 保留现有 inline warning 语义
```

页面只保留原有的一套 DAY/WEEK 控件；新面板使用 `soft-badge` 显示已加载粒度。

---

## 6. 请求竞争与过期数据处理

未修改 `useStatisticsOverview` / `useReviewStatistics`。现有机制继续生效：

- 新请求先 `abort()` 上一个请求；
- 单调 sequence guard 丢弃旧响应；
- unmount 时 abort；
- granularity 相同值直接返回；
- 页面切换粒度只调用 `loadOverview()`，不重复请求 reviews。

页面层新增快照判断后：

- 旧请求即使 resolve，也不会写入 composable 的 `data`；
- 即使写入，页面也不会把旧快照标记为新粒度；
- 快速 DAY→WEEK→DAY 时，旧 WEEK 响应不能覆盖最终 DAY 状态。

测试已断言：

- 旧请求 `signal.aborted === true`；
- 过期 WEEK 响应中的 777 不出现在最终页面；
- 最终 DAY 响应 222 正常显示；
- reviews 请求次数不因粒度切换增加。

---

## 7. loading / error / empty 状态

| 场景 | 现有趋势面板 | 新分类面板 | 数据 |
|---|---|---|---|
| 首次加载，无 overview | 不渲染 | 不渲染 | 无 |
| 首次 overview 失败 | 页面级 `overview-error` | 不渲染 | 无 |
| 同粒度刷新中 | 保留旧图 | 保留旧图 | 上次成功快照 |
| 同粒度刷新失败 | 保留旧图 + inline warning | 保留旧图 + warning | 上次成功快照 |
| DAY/WEEK 切换中 | skeleton，隐藏旧 points | 整体隐藏 | 无 |
| DAY/WEEK 切换失败 | 统一 error + Retry，隐藏旧 points | 整体隐藏 | 无 |
| `hasData=false` | `el-empty` | `el-empty` | 空 |
| 有报告但五类全 0 | 正常显示 | 正常五系列图 + 全 0 提示 | 后端 0 |
| 分类字段缺失/非法 | 正常显示 | 契约警告，不画分类线，表格显示 `—` | 不完整响应 |

新增 test id：

```text
trend-granularity-loading
trend-granularity-error
category-trend-panel
category-trend-empty
category-trend-contract-warning
category-trend-all-zero
category-trend-table
```

粒度切换失败时，通用 `overview-refresh-error` 被抑制，避免出现两个 Retry 和互相矛盾的状态；同粒度刷新失败时仍保留该 warning。

全 0 处理：

- 不把“五类总和为 0”当空状态；
- 仍绘制 5 条 baseline 折线；
- 显示 “All category counts are zero in the selected range.”；
- 数据表所有分类显示 `0`。

---

## 8. 可访问性

- SVG：`role="img"`、`aria-label`、`<title>`、`<desc>`。
- `aria-label` 包含 Daily/Weekly 与首尾 bucket 日期。
- 图例使用 `<ul aria-label="Category trend legend">`，5 个文本项可被读屏器读取；色块 SVG 设置 `aria-hidden`。
- 五系列不只依赖颜色：颜色 + 实线/虚线 + 图例文本 + 数据表列名 + 标记点 `<title>`。
- 标记点 `<title>` 包含日期范围和数量，例如：
  `2026-11-01: 4 Bug findings`。
- 标记点不设置 `tabindex`，避免大量 Tab 停靠点；精确值通过数据表获取。
- loading 使用 `role="status"` + `aria-live="polite"`；趋势面板设置 `aria-busy`。
- granularity error 与 contract warning 使用 `role="alert"`。
- 数据表使用 `<details>/<summary>`、`scope="col"`、`scope="row"`。
- 数据表容器 `overflow-x: auto`，窄屏可横向滚动。

---

## 9. 响应式设计

沿用现有断点，不新增布局系统：

```text
桌面：viewBox 0 0 720 260，maxXTicks 8
≤640px：viewBox 0 0 360 230，maxXTicks 4
```

- SVG：`width: 100%; height: auto; preserveAspectRatio="xMidYMid meet"`。
- 图例：`flex-wrap: wrap`，窄屏换行。
- 面板标题沿用 `.trend-panel .panel-heading` 的 ≤640px 纵向布局。
- 数据表：`white-space: nowrap` + `overflow-x: auto`。
- 图表本身不横向滚动，整体缩放。
- 标记点阈值：桌面 ≤31 个 bucket 显示，窄屏 ≤10 个；超过阈值只保留折线和数据表。
- 单点始终显示 5 个标记点，半径为 5。

headless Chrome 390×844 实测：

- 图例 2 行；
- SVG 宽度 306px，位于 348px 宽面板内；
- X 轴 4 个刻度；
- 数据表容器 clientWidth 306、scrollWidth 506，可横向滚动；
- 页面无水平溢出。

---

## 10. 测试结果

### 10.1 修改前基线

```text
Test Files  15 passed (15)
Tests       121 passed (121)
```

### 10.2 修改后

```text
Test Files  16 passed (16)
Tests       150 passed (150)
失败        0
```

新增测试 29 个：

| 文件 | 数量 |
|---|---:|
| `CategoryTrendChart.spec.ts` | 16 |
| `trend-geometry.spec.ts` 新增 | 6 |
| `InsightsView.spec.ts` 新增 | 7 |

定向测试：

```text
CategoryTrendChart.spec.ts
InsightsView.spec.ts
TrendChart.spec.ts
trend-geometry.spec.ts

Test Files  4 passed (4)
Tests       51 passed (51)
```

覆盖重点：

- 五系列、五图例、字段映射、UNKNOWN 独立；
- DAY/WEEK 标签与 ISO 周说明；
- 单分类 0、五类全 0、空 points、单点；
- 缺失字段、`NaN` 字段、契约警告、表格 `—`；
- 标记点 title、阈值、窄屏 viewBox / 4 ticks；
- 数据表行数与列值；
- 页面新面板、trend 优先于 summary；
- 切换中隐藏两图、切换成功同步、切换失败统一错误、Retry 只刷新 overview；
- 同粒度刷新失败保留旧快照；
- 快速 DAY→WEEK→DAY 的 abort 与旧响应丢弃；
- 现有 Review/Finding 图无回归。

`TrendChart.spec.ts` 仅补 fixture 字段，未删除或弱化任何原断言。

### 10.3 type-check / lint

```text
npm run type-check  → PASS
npm run lint:check  → PASS（oxlint + eslint）
```

---

## 11. 构建结果

```text
npm run build → PASS
```

构建内容：

```text
vite v8.3.7
1758 modules transformed
✓ built in 924ms
InsightsView JS: 46.88 kB（gzip 13.35 kB）
InsightsView CSS: 16.21 kB（gzip 3.28 kB）
```

`frontend/components.d.ts` 由构建工具自动加入：

```ts
CategoryTrendChart: typeof import('./src/components/insights/CategoryTrendChart.vue')['default']
```

未手工编辑该文件。

---

## 12. 浏览器验证结果

### 12.1 方法与环境

- 使用本机 `<chrome-executable>`；
- `--headless=new` + CDP；
- 加载生产构建 `frontend/dist`；
- 由临时 Node 静态服务器提供页面和确定性 mock API；
- 临时脚本与截图位于 `<temp-dir>\b2b-browser`，未加入仓库；
- 未新增 Playwright / Puppeteer / Cypress 依赖。

**限制：API 为符合 B1 Schema 的 mock 数据，不是真实 Spring Boot + MySQL 联调；窄屏为 390×844 视口模拟，不是真机。**

### 12.2 桌面 1440×1000

| 场景 | 结果 |
|---|---|
| DAY 有数据 | 2 个趋势面板、5 条分类线、5 个图例项、25 个标记点；面板不重叠；页面无水平溢出 |
| DAY→WEEK pending | 现有面板显示 loading；`trend-svg` 不渲染；category 面板整体消失 |
| WEEK 有数据 | 两图 aria-label 均为 Weekly；5 条线；10 个标记点；ISO 周说明可见 |
| 五类全 0 | 5 条线仍在；全 0 提示可见；不显示空状态 |
| 空范围 | 两个 `el-empty`；无 SVG |
| WEEK 请求失败 | 统一 granularity error；category 面板消失；两图均不渲染旧数据 |

### 12.3 窄屏 390×844

```text
legendRows            2
categoryLines         5
categorySvg width     306px（面板 348px）
x-axis ticks          4
table clientWidth     306
table scrollWidth     506
tableScrollable       true
page overflow         -10（无水平溢出）
```

视觉检查：图例换行正常；SVG 随面板缩放；折线与虚线可区分；新面板不覆盖现有趋势面板或 comparison 面板。

### 12.4 未通过真实后端验证的部分

- 真实 B1 响应未在浏览器中联调；
- 真实 MySQL 数据分布、时区、ISO 周边界只由后端既有测试和 B2-A 调查背书；
- 未做真机触摸、屏幕阅读器、打印灰度和像素级对比度审计。

---

## 13. 与调查报告设计的差异

| 项目 | 调查报告 | 实际实现 | 原因 |
|---|---|---|---|
| Props | 建议单一 `trend` | `trend` + `granularity`，并用 `trend.granularity` 作为有效粒度 | 满足本阶段任务对 props 的要求，同时保留快照一致性 |
| 粒度不匹配 | 未单独定义 | 新增 `granularityMismatch`，隐藏图表并告警 | 防御错误调用方 |
| 切换中布局 | 建议两个图表 body 各自 skeleton | 现有趋势面板显示唯一 skeleton，新面板整体隐藏 | 避免重复状态与读屏器重复提示 |
| 切换失败 | 建议两图错误 | 现有趋势面板显示唯一统一错误，新面板隐藏 | 保证单一 Retry 入口 |
| 通用刷新 warning | 未说明 | 粒度失败时抑制；同粒度失败时保留 | 避免两个互相矛盾的 Retry |
| 非法字段 | 只要求缺失字段 | 同时覆盖 `NaN` 等非有限值 | `Number.isFinite` 契约守卫的自然延伸 |
| 标记点阈值 | 31 / 10 | 31 / 10 | 与调查一致 |
| 面积填充 | 不使用 | 不使用 | 五线面积会互相遮挡 |

其余核心设计（方案 B、五系列配置、颜色/线型、additive 几何、无新依赖、无第二套 toggle）均按调查报告执行。

---

## 14. 未完成事项和风险

### 14.1 未完成

- 未进行真实后端 + 真实 MySQL 的浏览器联调；
- 未做真实屏幕阅读器、真机触摸、打印灰度验证；
- 未新增 E2E 测试依赖（按任务要求禁止）。

### 14.2 风险

| 风险 | 影响 | 当前缓解 |
|---|---|---|
| 分类字段缺失/非法 | 分类图整体不画线 | 显式契约警告，表格显示 `—`，绝不伪造 0 |
| 366 个 DAY 桶 | 数据表 DOM 较大（约 2562 单元格） | 标记点阈值限制 circle；表格折叠但 DOM 仍存在 |
| 大量 0 值五线重叠 | 视觉上只能看到最上层线 | 全 0 提示 + 完整数据表 |
| 调用方传入错误 `granularity` | 图表可能错标 | `granularityMismatch` 守卫，隐藏图表 |
| 真实后端响应偏离 B1 | 页面可能显示契约警告 | 类型 required + 运行时 `Number.isFinite` |
| `components.d.ts` 自动变化 | 生成文件 diff | 未手工编辑，已在本报告记录 |

---

## 15. Git 工作区前后对比

### 15.1 实施前

| 项目 | 值 |
|---|---:|
| 分支 | `phase11/dashboard` |
| HEAD | `27e3a41161cfa86ee2956ba0b3626a2bcc71eec7` |
| tracked modified | 6 |
| tracked deleted | 1 |
| status 行数 | 62 |
| untracked files | 129 |
| `git diff --stat` | 7 files changed, 182 insertions(+), 39 deletions(-) |

### 15.2 实施后

| 项目 | 值 | 差异 |
|---|---:|---|
| 分支 | `phase11/dashboard` | 无 |
| HEAD | `27e3a41161cfa86ee2956ba0b3626a2bcc71eec7` | 无 |
| tracked modified | 6 | 无 |
| tracked deleted | 1 | 无 |
| status 行数 | 63 | +1（本报告） |
| untracked files | 133 | +4 |
| `git diff --stat` | 7 files changed, 182 insertions(+), 39 deletions(-) | 无 |

untracked +4：

```text
frontend/src/utils/category-trend.ts
frontend/src/components/insights/CategoryTrendChart.vue
frontend/src/__tests__/CategoryTrendChart.spec.ts
docs/reports/Phase11_3_B2_B_Implementation_Report.md
```

说明：

- 前端源码整体仍处于未跟踪状态，因此 `frontend/src/**` 的修改不改变 tracked diff；
- `frontend/components.d.ts` 原本已是未跟踪文件，构建后内容增加了 `CategoryTrendChart` 声明，但不改变 untracked 数量；
- 未执行 commit、push、merge、rebase、reset、clean、checkout、switch、stash、cherry-pick。

---

## 16. 明确未修改的后端、依赖、数据库和保护文件

### 16.1 后端与数据库

```text
backend/**                     未修改
API 契约                       未修改
数据库结构 / 数据 / 迁移       未修改
MySQL / Redis                  未修改
```

### 16.2 依赖

```text
frontend/package.json          未修改
frontend/package-lock.json     未修改
未新增 ECharts / Chart.js / Playwright / Puppeteer / Cypress
```

### 16.3 保护文件

```text
docs/DEVELOPMENT_STATUS.md     未修改
任何既有 Phase 报告            未修改
frontend/src/components/insights/TrendChart.vue   未修改
frontend/src/api/**            未修改
frontend/src/composables/**    未修改
frontend/.gitkeep              删除状态保持
```

### 16.4 结束点

Phase 11.3-B2-B 到此停止：

- 未 commit；
- 未 push；
- 未清理工作区；
- 未修改 `docs/DEVELOPMENT_STATUS.md`；
- 未进入 Phase 12。

等待 ChatGPT 审查和用户验收。
