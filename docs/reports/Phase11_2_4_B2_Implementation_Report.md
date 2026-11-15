# Phase 11.2.4-B2 实施报告 — Vue Review Insights 页面

> 执行日期：2026-11-13  
> 分支：`phase11/dashboard`  
> HEAD：`27e3a41161cfa86ee2956ba0b3626a2bcc71eec7`  
> 阶段：Phase 11.2.4-B2（前端 Insights 页面）  
> 范围：新增独立 `/insights` 页面，消费 B1 的只读统计 API；不进入 Phase 11.2.4-C，不进入 Phase 12。  
> 结论：**B2 已完成。页面、筛选、DAY/WEEK 趋势、分布、逐 Review 对比表、数据质量披露、Loading / Empty / Partial / Error / Retry 状态均已实现；前端四项验收命令全部通过；已用实际运行的 B1 接口响应核对字段集合与关键数字。未新增依赖，未修改 B1 后端、Phase 10 API、`DashboardLocalAccessFilter` 或 `docs/DEVELOPMENT_STATUS.md`，未执行任何 Git 写操作。**

---

## 1. 完成内容

### 1.1 已实现

- 新增 `/insights` 路由，路由名 `insights`，标题 `Review Insights`。
- 侧边栏新增 `Review Insights` 入口，使用既有 `@element-plus/icons-vue` 的 `TrendCharts` 图标，并补充 active 状态匹配。
- 新增 `InsightsView.vue`，页面包含：
  - 页面标题、范围/时区/生成时间说明、刷新按钮；
  - 8 个筛选条件：`owner`、`repo`、`prNumber`、`taskStatus`、`publishStatus`、`aiStatus`、`createdFrom`、`createdTo`；
  - 10 个 Summary 卡片，覆盖 B1 `summary` 的全部指标；
  - Finding Category / Severity、Publish Status、AI Status 四个分布区；
  - DAY / WEEK 双线趋势图（Review 数 + Finding 数）及可展开数据表；
  - 逐 Review 对比表：分页、白名单排序、声明/实际计数、一致性徽标、未知值徽标、禁用详情链接；
  - `dataQuality` 警告与 9 项数据质量计数；
  - Loading、Empty、Partial Data、Error、Retry 状态。
- 新增两个 composable：
  - `useStatisticsOverview`：单飞、序列号防陈旧响应、AbortController、卸载中止；
  - `useReviewStatistics`：同样的请求生命周期控制，供分页/排序独立刷新。
- 新增前端统计类型、API client、格式化工具、SVG 几何工具、错误映射。
- 新增/扩展 44 个 Vitest 测试用例。

### 1.2 明确未做

- 未在首页 `DashboardView` 增加统计卡片。
- 未新增 Pinia、ECharts、Chart.js 或任何依赖。
- 未增加自动刷新、WebSocket、CSV 导出、定时报表、RAG / Milvus。
- 未做历史数据回填（backfill）。
- 未修改 B1 后端统计实现。
- 未修改 Phase 10 Review History / Detail API。
- 未修改 `DashboardLocalAccessFilter`。
- 未修改 `docs/DEVELOPMENT_STATUS.md`。
- 未执行 commit、push、merge、rebase、reset、clean 或 checkout。
- 未进入 Phase 11.2.4-C，未进入 Phase 12。

---

## 2. 文件清单

### 2.1 新增文件

| 文件 | 说明 |
|---|---|
| `frontend/src/types/statistics.ts` | B1 两个接口的 TypeScript 契约；状态字段保持 `string`，保留未知原始值 |
| `frontend/src/api/statistics.ts` | `getStatisticsOverview` / `getStatisticsReviews`，查询参数序列化与 AbortSignal |
| `frontend/src/utils/statistics-format.ts` | 计数、平均值、中位数、百分比、日期、未知桶标签格式化 |
| `frontend/src/utils/trend-geometry.ts` | SVG 坐标、轴刻度、折线/面积路径纯函数 |
| `frontend/src/utils/statistics-error.ts` | B1 错误码到用户文案的映射，不含后端原始载荷 |
| `frontend/src/composables/useStatisticsOverview.ts` | Overview 请求生命周期 |
| `frontend/src/composables/useReviewStatistics.ts` | Reviews 请求生命周期 |
| `frontend/src/components/insights/StatCard.vue` | Summary 指标卡 |
| `frontend/src/components/insights/DistributionBars.vue` | 通用横向分布条 |
| `frontend/src/components/insights/TrendChart.vue` | 原生 SVG 双线趋势图与数据表 fallback |
| `frontend/src/components/insights/ReviewComparisonTable.vue` | 逐 Review 对比表、排序、分页、完整性/未知值徽标 |
| `frontend/src/components/insights/InsightsFilterBar.vue` | 筛选表单、日期边界转换、Apply / Clear |
| `frontend/src/views/InsightsView.vue` | 页面编排、两个接口协调、全部状态与数据质量披露 |
| `frontend/src/__tests__/statistics-api.spec.ts` | API 参数、AbortSignal、错误映射 |
| `frontend/src/__tests__/statistics-format.spec.ts` | 空值、百分比、未知标签、时间格式 |
| `frontend/src/__tests__/trend-geometry.spec.ts` | n=0 / n=1 / 全零 / 正常序列 / 轴刻度 |
| `frontend/src/__tests__/TrendChart.spec.ts` | SVG 渲染、空数据、单点、WEEK、窄屏几何 |
| `frontend/src/__tests__/ReviewComparisonTable.spec.ts` | 行内容、未知状态、禁用链接、分页、排序 |
| `frontend/src/__tests__/InsightsView.spec.ts` | 初始加载、双请求、筛选、粒度、竞态、取消、失败重试、空状态、数据质量 |

### 2.2 修改的既有文件

| 文件 | 修改内容 |
|---|---|
| `frontend/src/api/index.ts` | 导出 statistics API |
| `frontend/src/router/index.ts` | 新增 `/insights` 路由 |
| `frontend/src/components/SidebarNav.vue` | 新增 Review Insights 菜单、图标与 active 分支 |
| `frontend/src/__tests__/router.spec.ts` | 新增 `/insights` 路由断言 |
| `frontend/src/__tests__/DashboardLayout.spec.ts` | 验证 Review Insights 菜单与 active 标题 |

### 2.3 未修改

- `frontend/package.json`、`frontend/package-lock.json`（无新依赖）。
- `backend/spring-service/**`（B2 未改后端）。
- `backend/spring-service/src/main/java/cn/codesentinel/security/DashboardLocalAccessFilter.java`。
- `docs/DEVELOPMENT_STATUS.md`。
- `docs/reports/Phase10_*.md`、`docs/reports/Phase11_2_3_*.md`、`docs/reports/Phase11_2_4_A_Investigation_Report.md`、`docs/reports/Phase11_2_4_B1_*.md`。

---

## 3. 页面结构与交互

### 3.1 路由与导航

```text
/insights        name: insights        title: Review Insights
```

侧边栏顺序：

```text
Dashboard
Review History
Review Insights
```

`/insights` 使用独立页面，不复用首页布局内的卡片区域；首页保持不变。

### 3.2 Summary 卡片

页面展示 B1 `summary` 的全部指标：

| 卡片 | 字段 |
|---|---|
| Review count | `reviewCount` |
| Finding count | `findingCount` + `findingStatsReviewCount` |
| Average findings | `averageFindingsPerReview` |
| Median findings | `medianFindingsPerReview` |
| Max findings | `maxFindingsInReview` |
| High + Critical | `highSeverityFindingCount` + `highSeverityRatio` |
| Reviews with findings | `reviewsWithFindings` + `reviewsWithFindingsRatio` |
| Inline comments | `publishedInlineCommentCount` + `commentStatsReviewCount` |
| Reviews with inline comments | `reviewsWithInlineComments` + `reviewsWithInlineCommentsRatio` |
| Summary comment IDs | `summaryCommentIdPresentCount` |

处理规则：

- `null` 平均值 / 中位数 / 最大值显示 `—`。
- `null` 比例显示 `—`，并说明“没有对应样本”，绝不显示 `0%`。
- `0` 是真实计数，正常显示 `0`。
- Summary comment ID 明确标注为存在性指标，且与 inline comment 区分。

### 3.3 筛选

筛选栏包含：

```text
owner
repo
prNumber
taskStatus
publishStatus
aiStatus
createdFrom / createdTo（daterange）
```

行为：

- 点击 `Apply filters` 后，Overview 与 Reviews 都从第 1 页重新请求。
- 点击 `Clear filters` 清空表单并从第 1 页重新请求。
- 前端校验 `from > to` 与范围超过 366 个自然日。
- 日期发送：

```text
createdFrom = YYYY-MM-DDT00:00:00
createdTo   = YYYY-MM-DDT23:59:59.999999
```

- 空白字符串、`undefined`、`null` 不发送，交由后端应用默认范围。
- Owner / Repo 在发送前 trim。

按照 A 报告的建议，筛选使用显式 Apply 按钮，而不是在每个输入字符变化时立即请求；分页、排序、DAY/WEEK 切换则立即触发对应请求。

### 3.4 分布

四个分布区分别对应：

```text
categoryCounts
severityCounts
publishStatusCounts
aiStatusCounts
```

- 每个桶保留后端返回的 `key` 与 `count`。
- 已知 key 使用可读标签（`BUG` → `Bug` 等）。
- `UNKNOWN` 显示为 `Unknown`，使用中性色。
- 其他未知原始 key 显示为 `Unknown (原始值)`，不丢弃。
- 总数使用 B1 对应分母：Finding 分布用 `findingCount`，状态分布用 `reviewCount`。
- 总数为 0 时显示空文案，不输出 `0%`。

### 3.5 逐 Review 对比表

表格列：

```text
Created
Review（taskId / commit / task status）
Repository（owner/repo + PR）
AI / Publish
Findings（actual / declared）
High + Critical
Comments（actual / declared）
Data（Complete / Incomplete）
Unknown values（Category / Severity 计数）
```

- 排序白名单：`createdAt`、`actualFindingCount`、`highSeverityFindingCount`、`actualCommentCount`。
- 排序方向：`asc` / `desc`；清空排序时回到 `createdAt desc`。
- 分页大小：10 / 20 / 50 / 100，默认 20。
- `findingsConsistent=false` 或 `commentsConsistent=false` 时：
  - 显示 `Incomplete` 与 `Inconsistent`；
  - 详情链接禁用，以删除线文本展示 `#taskId`，不伪造可访问路由。
- `aiStatus` / `publishStatus` 保持原始字符串；`UNKNOWN` 与未知值均显示为 `Unknown (原始值)`。

### 3.6 DAY / WEEK

- 趋势区提供 Daily / Weekly 按钮组。
- 切换粒度只重新请求 Overview，不重新请求 Reviews。
- `WEEK` 时显示 ISO-8601 周说明：周一至周日，首尾桶可能超出所选范围。
- 趋势数据表包含每个桶的 Review 数、Finding 数与 High + Critical 数。

---

## 4. API 集成

### 4.1 请求路径

```text
GET /api/dashboard/statistics/overview
GET /api/dashboard/statistics/reviews
```

前端只使用同源 Dashboard BFF，不发送 `X-Internal-Token`，不访问 GitHub / AI Service。

### 4.2 Overview 请求

```text
{所有筛选参数, granularity}
```

`granularity` 取 `DAY` / `WEEK`。

### 4.3 Reviews 请求

```text
{page, size, sort, direction, 所有筛选参数}
```

- 翻页、改变每页数量、改变排序只请求 Reviews。
- 筛选 Apply / Clear 同时请求 Overview 与 Reviews。
- 粒度切换只请求 Overview。
- 顶部 Refresh 同时请求两者。

### 4.4 请求竞态与取消

两个 composable 均实现：

```text
同一资源同一时间只保留一个活动请求
新请求开始前 abort 旧请求
单调递增 sequence 校验
旧请求即使 resolve 也丢弃
卸载时 disposed = true 并 abort
```

页面在 `onBeforeUnmount` 中再次调用两个 `abort()`，覆盖路由离开导致的组件卸载路径。

### 4.5 错误

- 使用既有 `toApiError` / `ApiError`。
- 统计错误码映射：

```text
invalid_filter
invalid_range
invalid_granularity
invalid_pagination
invalid_sort
internal_error
```

- 403 显示本地 Dashboard 访问说明。
- 取消请求不显示错误。
- 不展示 SQL、表名、Token 或后端堆栈。
- Overview 失败但 Reviews 成功时，仍展示逐 Review 表；Reviews 失败但 Overview 成功时，仍展示 Summary 与趋势。
- 已有数据时刷新失败，保留最近一次成功数据并显示“刷新失败”提示与 Retry。

---

## 5. 时间语义

- 全部时间按**应用本地 wall-clock**理解，不使用浏览器时区转换。
- `range.zoneId` 来自后端响应，当前验收环境为 `Asia/Shanghai`。
- `createdAt` / `generatedAt` 通过字符串替换显示为 `YYYY-MM-DD HH:mm:ss`，不使用 `new Date()`。
- 日期筛选发送 `00:00:00` 与 `23:59:59.999999`，与 B1 的包含边界一致。
- 页面明确展示：

```text
Time basis: Application local time (Asia/Shanghai)
Range: createdFrom to createdTo
Generated: generatedAt
```

未把 `LocalDateTime` 当成 UTC，也未做 ±8 小时偏移。

---

## 6. Data Quality 与统计口径

### 6.1 页面文案

页面明确区分：

- Review 级指标包含范围内所有报告；
- Finding 指标排除 Finding 行数与声明数不一致的报告；
- Inline Comment 指标排除评论行数与声明数不一致的报告；
- Summary comment ID 单独计数，不属于 inline comment；
- 统计是 Review 活动与交付信号，不是代码质量评分。

### 6.2 警告

满足以下任一条件时显示 `data-quality-warning`：

```text
reportsExcludedFromFindingStats > 0
reportsExcludedFromCommentStats > 0
unknownCategoryFindingCount > 0
unknownSeverityFindingCount > 0
unknownAiStatusReportCount > 0
unknownPublishStatusReportCount > 0
```

警告逐项说明：

- 多少报告被排除出 Finding 统计；
- 多少报告被排除出 Comment 统计；
- 多少 Finding 的 category / severity 未知；
- 多少报告的 AI / Publish 状态未知；
- 明确说明排除项仍计入 Review 计数，未知值保留在 UNKNOWN 桶或原始状态中。

不补造被排除的 Finding / Comment 数据，不把缺失值当作 0。

### 6.3 数据质量面板

固定展示 B1 `dataQuality` 的 9 个字段：

```text
totalReportCount
findingsConsistentReportCount
commentsConsistentReportCount
reportsExcludedFromFindingStats
reportsExcludedFromCommentStats
unknownCategoryFindingCount
unknownSeverityFindingCount
unknownAiStatusReportCount
unknownPublishStatusReportCount
```

无问题时显示 `Complete`，有问题时显示 `Needs attention` 并出现顶部警告。

---

## 7. 趋势图实现

- 原生 `<svg>` + CSS，无图表库。
- 双线：Review 数（靛蓝）、Finding 数（琥珀）。
- 每条线带半透明面积；点使用 `<title>` 显示桶日期与数值。
- 轴与刻度：
  - `niceAxisMax` 至少为 4，按 1 / 2 / 5 / 10 量级取整；
  - `n=0` 返回空数据，不做除零；
  - `n=1` 将点放在绘图区水平中心；
  - 全零数据落在基线，不产生 `NaN`；
  - x 轴按 `maxTicks` 等距抽样，始终包含首尾点。
- 窄屏：
  - `max-width: 640px` 时切换为 `360 × 230` viewBox；
  - 最多 4 个 x 轴刻度；
  - 面板单列、分页左对齐、筛选栏单列。
- 可访问性：
  - `role="img"` + 动态 `aria-label`；
  - `<title>` / `<desc>`；
  - 可折叠数据表作为 fallback；
  - 图例与标签均带文字，不只依赖颜色。

---

## 8. 测试与验证

### 8.1 新增测试

| 测试文件 | 用例数 | 覆盖 |
|---|---:|---|
| `statistics-api.spec.ts` | 8 | 两个端点、全部参数、空值省略、错误码映射、403、取消 |
| `statistics-format.spec.ts` | 6 | 空值、平均值/中位数、比例、UNKNOWN 标签、时间格式 |
| `trend-geometry.spec.ts` | 7 | 轴最大值、刻度抽样、n=0、n=1、全零、正常序列、路径 |
| `TrendChart.spec.ts` | 5 | SVG、空数据、单点、WEEK、窄屏 viewBox 与刻度数 |
| `ReviewComparisonTable.spec.ts` | 6 | 行内容、未知状态、禁用链接、分页、排序、空分页 |
| `InsightsView.spec.ts` | 10 | 初始加载、双请求、筛选、粒度、分页/排序、空状态、null 指标、数据质量、竞态、取消、失败重试 |
| `router.spec.ts` | +1 | `/insights` 路由 |
| `DashboardLayout.spec.ts` | +1 | Review Insights 菜单与 active 标题 |

合计新增/扩展 44 个测试用例；前端全套 15 个测试文件、121 个用例全部通过。

### 8.2 验收命令

```text
cd frontend
npm run type-check     ✅ 通过
npm run lint:check     ✅ 通过（oxlint + eslint）
npm run test:unit      ✅ 15 files / 121 tests 通过
npm run build          ✅ 通过（vue-tsc + vite build）
```

构建产物中 `InsightsView` 约为：

```text
InsightsView-*.js   37.78 kB / gzip 11.26 kB
InsightsView-*.css  13.31 kB / gzip  2.95 kB
```

### 8.3 实际 B1 API 核对（非 mock）

使用本地 Spring Boot jar，数据库指向验收库 `codesentinel_accept_1123b`，只发送 GET 请求：

| 检查项 | 实际结果 |
|---|---|
| Overview 顶层字段 | `range` / `generatedAt` / `summary` / `trend` / `dataQuality` |
| Summary 字段 | 19 个字段与前端 `StatisticsSummary` 完全一致 |
| DataQuality 字段 | 9 个字段与前端 `StatisticsDataQuality` 完全一致 |
| Review item 字段 | 27 个字段与前端 `StatisticsReviewItem` 完全一致 |
| `reviewCount` | 6 |
| `findingCount` | 48 |
| `averageFindingsPerReview` | 9.6 |
| `medianFindingsPerReview` | 1.0 |
| `maxFindingsInReview` | 45 |
| `highSeverityFindingCount` | 19 |
| `highSeverityRatio` | 0.3958333333333333 |
| `publishedInlineCommentCount` | 25 |
| `summaryCommentIdPresentCount` | 3 |
| `zoneId` | `Asia/Shanghai` |
| DAY 趋势桶 | 30 |
| WEEK 趋势桶 | 5 |
| `publishStatusCounts` | 包含固定 `UNKNOWN` 桶 |
| `categoryCounts` | 包含 `UNKNOWN: 1` |
| Review 行 | 6 行，taskId 1001–1006 |
| 1003 | `findingsConsistent=false` |
| 1005 | `commentsConsistent=false` |
| 1006 | `aiStatus="UNKNOWN"`，原始值保留 |
| 空 owner 查询 | `reviewCount=0`、平均值为 `null`、高严重度比例为 `null`、`trend.hasData=false`、`points=[]`、`items=[]` |
| 非法 granularity | HTTP 400，`{"error":"invalid_granularity"}` |

结论：前端类型不是只按 mock 设计，已与真实 B1 响应逐字段核对。验证完成后已停止该本地后端进程，8080 端口释放。

---

## 9. Git / 工作区边界

- 分支：`phase11/dashboard`
- HEAD：`27e3a41161cfa86ee2956ba0b3626a2bcc71eec7`
- 本阶段未执行任何 Git 写操作：

```text
未 commit
未 push
未 merge
未 rebase
未 reset
未 clean
未 checkout
```

- 工作区在 B2 开始前已包含大量未提交/未跟踪文件；本阶段未覆盖、未删除、未回滚。
- `docs/DEVELOPMENT_STATUS.md` 的既有修改未被本阶段触碰。
- 未修改 `frontend/package.json` / `frontend/package-lock.json`。
- 未新增任何前端依赖。
- 未修改 B1 后端、Phase 10 API 或 `DashboardLocalAccessFilter`。
- 临时 API 核对脚本位于系统临时目录，不属于仓库内容。

---

## 10. 已知限制

1. **筛选采用 Apply 按钮**：没有对每个输入字符立即发请求，符合 A 报告的推荐；分页、排序、粒度切换会立即请求。
2. **翻页/排序不刷新 Overview**：为避免每次翻页都重复拉取汇总，Summary 与 Trend 保持最近一次 Overview 快照；若数据在此期间变化，表格可能与汇总短暂不一致。点击 Refresh 会同时刷新两者。
3. **不完整报告的详情链接禁用**：B2 未修改 Review Detail 页面；只要 Finding 或 Comment 任一侧不一致，就禁止进入详情，避免展示不完整历史。
4. **未知 category / severity 的原始字符串不可见**：B1 只在分布中返回 `UNKNOWN` 聚合桶，在逐 Review 行中返回未知数量，不返回具体原始字符串；前端显示聚合与计数，不推测原始值。
5. **最大 366 天**：DAY 模式最多可返回 366 个桶；图表会抽样 x 轴标签，数据表仍保留完整桶列表，可能较长。
6. **窄屏使用横向滚动**：对比表列较多，小屏通过表格横向滚动保持信息完整，未隐藏列。
7. **无真实浏览器 E2E / 截图**：验证使用 Vitest + jsdom、生产构建和真实 API 契约核对；未执行浏览器自动化截图。
8. **验收数据不是生产数据**：所有数字来自 `codesentinel_accept_1123b`；生产库为空时页面会显示 Empty，而不是伪造趋势。
9. **符合阶段边界**：未实现缓存、回填、自动刷新、CSV、Pinia、图表库或 Phase 12 功能。

---

## 11. 结论与停点

Phase 11.2.4-B2 已完成：

- `/insights` 独立页面与侧边栏入口可用；
- B1 两个统计接口均已接入，字段与真实响应一致；
- 所有 Summary 指标、四个分布、DAY/WEEK 趋势、逐 Review 对比表、数据质量披露均已实现；
- Loading / Empty / Partial / Error / Retry 状态完整；
- 未知值与空分母处理符合 B1 契约；
- 前端 `type-check`、`lint:check`、`test:unit`、`build` 全部通过；
- 未新增依赖，未修改后端、Phase 10 API、访问过滤器或 `docs/DEVELOPMENT_STATUS.md`；
- 未执行 Git 写操作。

**本阶段到此停止，等待人工验收；未进入 Phase 11.2.4-C，未进入 Phase 12。**
