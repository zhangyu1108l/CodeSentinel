# Phase 11.3-A 调查报告 — Dashboard 整体收尾调查

> 执行日期：2026-11-14  
> 分支：`phase11/dashboard`  
> HEAD：`27e3a41161cfa86ee2956ba0b3626a2bcc71eec7`  
> 阶段：Phase 11.3-A（只读调查）  
> 性质：本阶段不修改源码、测试、配置、数据库、`docs/DEVELOPMENT_STATUS.md` 或既有报告，只新增本报告。  
> 最终结论：**Phase 11.1–11.2.4 已实现；11.2.3–11.2.4 已通过验收（11.2.4 为 PASS WITH WARNINGS）。Phase 11 整体暂不能无条件宣布完成。原始 Dashboard 清单中的 Security / Bug / Performance / Quality 四类趋势尚未实现，需要在“最小补齐”与“正式降级”之间做出明确决策。**

---

## 1. 调查结论

### 1.1 总体判断

Phase 11 已交付的部分是完整、可运行、经过真实验收的：

- Dashboard 布局、路由、侧边栏与响应式基础（11.1）；
- Review History 列表、筛选、分页与详情入口（11.2.2）；
- Review Detail 的报告、Finding、Comment 三块只读详情（11.2.3）；
- Review Insights 的 Summary、分布、DAY/WEEK 趋势、逐 Review 对比表与数据质量披露（11.2.4）；
- 浏览器使用的只读 Dashboard BFF，以及 `/api/dashboard/**` 的 loopback 安全边界。

Phase 11.2.4-C 的验收结论是 **PASS WITH WARNINGS**，11.2.4 交付范围内未发现 P0 / P1 / P2 缺陷，只有 5 项非阻塞警告/验证限制。

但是，把当前实现与最初登记的 Dashboard 清单逐项对照后，存在一个明确的需求缺口：

> `docs/DEVELOPMENT_STATUS.md` §16 的六项 Dashboard 目标中，Review History、Finding Statistics 已完成；Security Trend、Bug Trend、Performance Trend、Quality Trend 四项未实现。

当前 Insights 的趋势只有：

- Review 数；
- Finding 数；
- High + Critical Finding 数。

它没有按 BUG / SECURITY / PERFORMANCE / QUALITY 分类的时间序列。Category 分布是“整个范围内的聚合”，不是“随时间变化的趋势”，两者不能互相替代。因此，当前实现不能诚实地勾选原始清单中的四项分类趋势。

### 1.2 六个必答问题

| # | 问题 | 结论 |
|---|---|---|
| 1 | PROJECT_DESIGN 第二阶段 Dashboard 目标是否全部实现？ | **否。** Review History、Finding Statistics 已实现；Security / Bug / Performance / Quality 四类趋势未实现。 |
| 2 | History / Detail / Insights 是否形成完整流程？ | **是。** `/reviews` → `/reviews/:taskId` → `/insights` 均有路由、API、加载/空/错误状态和互相链接；C 验收已覆盖。 |
| 3 | 是否存在阻断正式完成的缺陷？ | **存在 1 个 P1 原始需求缺口（四类趋势）；没有 P0 / P2 代码缺陷；另有若干收尾前置条件（未提交、状态文档未更新）。** |
| 4 | C 报告 5 项警告哪些需 Phase 11 内解决？ | **没有必须在 Phase 11 内解决的。** 5 项都可以转为技术债/验证债；W4 可在收尾时顺手修复，W1 可用组件测试部分补强。 |
| 5 | 是否还需新 Dashboard 功能？ | **只需要四类分类趋势**（对应已有设计目标）；首页真实统计摘要属于可选增强，不是原始清单要求。 |
| 6 | 是否具备宣布 Phase 11 完成的条件？ | **不能无条件宣布。** 若四类趋势正式降级并完成状态/提交/PR 收尾，则可以；否则应先补最小分类趋势。 |

### 1.3 建议的收尾路径

推荐 **方案 A：最小补齐四类分类趋势，再关闭 Phase 11**。

理由：

1. 四项趋势是 `DEVELOPMENT_STATUS.md` §16 明确登记的目标，不是新发明的需求。
2. 现有数据已经具备：`review_finding.category` 已经持久化，后端逐报告聚合查询也已经返回 BUG / SECURITY / PERFORMANCE / QUALITY 计数。
3. 不需要新增数据库表、字段、索引或前端依赖。
4. 改动可以限制在趋势 DTO、趋势聚合和趋势图组件内，风险可控。
5. 补齐后可以如实勾选原始清单，不需要在“Phase 11 已完成”与“还有未勾选项”之间留下矛盾。

如果产品上明确认为四类趋势不属于 Phase 11 收尾范围，也可以选择 **方案 B：正式降级**，但必须留下书面决策，不能默默把 Phase 11 标记为完成。方案 B 的条件见第 10 节。

---

## 2. 项目当前状态与 Git 基线

### 2.1 Git 状态

调查开始时的实际状态：

```text
分支：phase11/dashboard
HEAD：27e3a41161cfa86ee2956ba0b3626a2bcc71eec7
HEAD 提交：Merge pull request #8 from zhangyu1108l/feature/phase10-mysql-history
main..HEAD：0 个提交
工作区：6 个已修改、1 个已删除、52 个未跟踪条目（含目录）
```

本报告新增后，未跟踪条目变为 53 个；除此之外工作区没有变化。

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

未跟踪内容主要是 Phase 11 前端、后端统计/历史 Controller、测试、Phase 10/11 报告与截图资源。

关键事实：

- `phase11/dashboard` 当前与 `main` 指向同一个 Phase 10 合并提交；
- Phase 11 的全部实现仍只存在于工作区，尚未形成任何 Phase 11 提交；
- HEAD 不是 Phase 11 的实现提交，而是 Phase 10 的合并提交。

这意味着：即使功能与验收已经完成，**正式宣布 Phase 11 完成仍然需要一次提交 + PR + 合并**，否则 Phase 11 的代码只存在于本地工作区，无法被仓库历史、评审和后续分支可靠引用。

本调查没有执行任何 Git 写操作：没有 commit、push、merge、rebase、reset、clean、stash 或 checkout。

### 2.2 文档状态

`docs/DEVELOPMENT_STATUS.md` 的当前内容仍写着：

- “Phase 11：Dashboard — 未开始（尚未启动，等待人工决策）”；
- §16 的 Dashboard 六项清单全部未勾选；
- 下一步仍是“人工确认 Phase 11 的范围与启动方式”。

这与已经完成的 11.1–11.2.4 明显不一致。该文件在调查开始时已有未提交修改，但修改内容是 Phase 10 状态更新，不是 Phase 11 完成状态。按本次任务要求，调查期间没有修改它。

这属于“收尾前置条件”，不是代码缺陷：在正式宣布 Phase 11 完成前，必须更新该文档，否则项目状态会自相矛盾。

### 2.3 调查边界

本次调查只读取了：

- 项目文档与既有 Phase 报告；
- 前端路由、视图、组件、API、类型、测试文件；
- 后端 Controller、Service、Repository、DTO、安全过滤器、配置；
- Git 状态与测试产物。

没有安装依赖，没有修改源代码、测试、配置、数据库或既有文档，没有执行 Phase 12，也没有运行会改变工作区的构建/测试命令。

---

## 3. 原始 Dashboard 需求逐项对照

### 3.1 需求来源

原始 Dashboard 目标出现在两处：

1. `docs/PROJECT_DESIGN.md` §23“第二阶段扩展”：

```text
Web Dashboard
      ↓
Review History
      ↓
Finding Statistics
      ↓
Code Quality Trend
```

并明确列出可以展示：

```text
Bug 趋势
Security 趋势
Performance 趋势
Quality 趋势
```

2. `docs/DEVELOPMENT_STATUS.md` §16“第二阶段计划”：

```text
- [ ] Review History
- [ ] Finding Statistics
- [ ] Security Trend
- [ ] Bug Trend
- [ ] Performance Trend
- [ ] Quality Trend
```

`PROJECT_DESIGN.md` 使用的是“可以展示”这种偏可选措辞，但 `DEVELOPMENT_STATUS.md` 把它拆成了六个可勾选条目。项目实际以 `DEVELOPMENT_STATUS.md` 作为阶段状态账本，因此在没有明确降级决策的情况下，这四项应视为 Phase 11 的登记目标。

### 3.2 逐项对照

| # | 原始需求 | 当前实现 | 证据 | 判定 |
|---|---|---|---|---|
| 1 | Review History | `/reviews` 列表：筛选、分页、加载/空/错误状态、详情入口 | `frontend/src/views/ReviewHistoryView.vue`；`DashboardReviewController`；Phase 11.2.2-B/B.1 报告 | ✅ 已实现 |
| 2 | Finding Statistics | `/insights`：10 个 Summary 指标、4 个分布、逐 Review 对比表、数据质量面板 | `frontend/src/views/InsightsView.vue`；`DashboardStatisticsController`；Phase 11.2.4-B1/B2/C 报告 | ✅ 已实现 |
| 3 | Security Trend | 只有 Security 的聚合分布，没有按时间分桶的 Security 序列 | `ReviewStatisticsTrendPoint` 只有 `reviewCount` / `findingCount` / `highSeverityFindingCount`；`TrendChart.vue` 只画 Review 与 Finding 两条线 | ❌ 未实现 |
| 4 | Bug Trend | 只有 Bug 的聚合分布，没有时间序列 | 同上 | ❌ 未实现 |
| 5 | Performance Trend | 只有 Performance 的聚合分布，没有时间序列 | 同上 | ❌ 未实现 |
| 6 | Quality Trend | 只有 Quality 的聚合分布，没有时间序列 | 同上 | ❌ 未实现 |

### 3.3 为什么“分布”不能替代“趋势”

当前 `/insights` 的 Category 分布回答的是：

> 所选范围内，BUG / SECURITY / PERFORMANCE / QUALITY 各有多少 Finding？

它不回答：

> 这些类别的数量在每一天/每一周如何变化？

趋势至少需要两个维度：类别 + 时间桶。当前趋势点没有 category 字段，只有总量与 High+Critical；当前 Category 分布没有时间桶。两者是正交的，不能互相替代。

此外，High + Critical 是 severity 维度，不是 category 维度。它可能间接反映安全问题的严重程度，但不能替代 Security / Bug / Performance / Quality 四条分类趋势。

### 3.4 结论

- 原始六项中，**2 项完成，4 项未完成**。
- `PROJECT_DESIGN` 的 `Code Quality Trend` 是这四项分类趋势的伞形目标；四项未实现，伞形目标自然也未完整实现。
- 这不是“实现有 Bug”，而是“登记目标未全部交付”。
- 在没有明确降级决策前，这构成 Phase 11 正式收尾的 **P1 需求缺口**。
- 若用户/ChatGPT 明确把四项趋势降级为后续技术债，则该缺口可以转为 P3 级 backlog，Phase 11 可在完成状态/提交/PR 收尾后关闭。

---

## 4. 前端实现情况

### 4.1 路由与导航

前端路由定义在 `frontend/src/router/index.ts`：

| 路径 | 名称 | 视图 | 作用 |
|---|---|---|---|
| `/` | `dashboard` | `DashboardView.vue` | Dashboard 首页/工作区状态 |
| `/reviews` | `review-history` | `ReviewHistoryView.vue` | Review History 列表 |
| `/reviews/:taskId(\d+)` | `review-detail` | `ReviewDetailView.vue` | 单次 Review 详情 |
| `/insights` | `insights` | `InsightsView.vue` | Review Insights 统计与趋势 |
| `/:pathMatch(.*)*` | `not-found` | `NotFoundView.vue` | 404 |

`SidebarNav.vue` 提供 Dashboard、Review History、Review Insights 三个入口；`ReviewHistoryView` 和 `ReviewComparisonTable` 都用 `RouterLink` 指向 `/reviews/{taskId}`。因此 History → Detail 与 Insights → Detail 的跳转是通的。

### 4.2 Review History

已实现：

- owner / repo / PR number / task status / publish status / AI status 筛选；
- 时间范围筛选（`datetimerange`）；
- 服务端分页，固定 `createdAt DESC, id DESC`；
- loading、empty、error、retry；
- 每行 task id 可点击进入详情；
- 与 `/api/dashboard/reviews` 对接。

关键文件：

- `frontend/src/views/ReviewHistoryView.vue`
- `frontend/src/api/review-history.ts`
- `frontend/src/types/api.ts`

### 4.3 Review Detail

已实现：

- 报告摘要；
- Finding 列表（分页）；
- Comment 列表（分页）；
- 报告不存在、历史不完整、非法 task id、分页错误的明确状态；
- 与 `/api/dashboard/reviews/{taskId}`、`/findings`、`/comments` 对接。

关键文件：

- `frontend/src/views/ReviewDetailView.vue`
- `frontend/src/api/review-detail.ts`

### 4.4 Review Insights

已实现：

- 10 个 Summary 指标：Review 数、Finding 数、平均/中位/最大 Finding、含 Finding 的 Review 数、High+Critical 数、发布 Inline Comment 数、含 Inline Comment 的 Review 数、Summary Comment 存在数等；
- 4 个分布：Category、Severity、Publish Status、AI Status；
- DAY / WEEK 双线趋势：Review 数 + Finding 数；
- 趋势数据表：Review 数、Finding 数、High+Critical 数；
- 逐 Review 对比表：分页、排序、跳转详情；
- 数据质量面板：Finding/Comment 计数不一致、未知 category/severity/AI status/publish status；
- Loading、Empty、Partial、Error、Retry；
- 范围、时区、生成时间说明。

`useStatisticsOverview` 与 `useReviewStatistics` 都实现单飞、序列号防陈旧响应、卸载/下一次请求 abort；Overview 与 Reviews 的失败互不阻塞（`Promise.allSettled`）。

关键文件：

- `frontend/src/views/InsightsView.vue`
- `frontend/src/components/insights/TrendChart.vue`
- `frontend/src/components/insights/DistributionBars.vue`
- `frontend/src/components/insights/StatCard.vue`
- `frontend/src/components/insights/ReviewComparisonTable.vue`
- `frontend/src/components/insights/InsightsFilterBar.vue`
- `frontend/src/composables/useStatisticsOverview.ts`
- `frontend/src/composables/useReviewStatistics.ts`
- `frontend/src/api/statistics.ts`
- `frontend/src/types/statistics.ts`

### 4.5 首页与文案现状

`DashboardView.vue` 当前是“工作区状态页”，不是统计摘要页：

- Backend API 健康检查是真实的；
- Review History 卡片是静态的 “Stored reports”；
- Review pipeline 卡片写死 “Phases 1–10 complete”；
- “Next up” 路线图仍写 “Quality insights — 11.3”；
- Pipeline 步骤是静态展示。

`DashboardLayout.vue` 有 3 处页头/页脚仍写 `Phase 11.1`；`SidebarNav.vue` 仍写 `Phase 11.2`；`frontend/README.md` 仍写 “Review details, finding statistics, charts ... out of scope”，并说 ECharts 会随第一个图表实现加入（实际图表用原生 SVG，未引入 ECharts）。

这些是文案/文档技术债，不影响功能正确性，但会误导阅读者，尤其是 “Quality insights 11.3” 与实际 11.2.4 已交付的 Insights 冲突。这看起来说明 Phase 11.3 的编号在实现过程中发生过重编号；收尾时应统一版本标识，避免把已交付的 Insights 误认为未来功能。

### 4.6 流程完整性判断

就“已交付范围”而言，History、Detail、Insights 已经形成完整流程：

```text
侧边栏 / Dashboard
      ↓
/reviews  （筛选、分页、空/错误状态）
      ↓
/reviews/{taskId}  （报告 + Finding + Comment）
      ↓
/insights  （汇总、分布、趋势、逐 Review 对比）
      ↓
/reviews/{taskId}  （从对比表回到详情）
```

首页本身不展示真实统计摘要，但侧边栏可以直接进入 Insights。A 报告 Q10 已明确把“首页摘要卡片”列为后续可选增强，因此这不是流程断裂，而是产品取舍。

---

## 5. 后端实现与 API 契约

### 5.1 API 清单

| Method | Path | 作用 | 分页/排序 | 主要错误码 |
|---|---|---|---|---|
| GET | `/api/dashboard/reviews` | Review History 列表 | `page` / `size`；固定 `createdAt DESC, id DESC`；SQL `Pageable` | `invalid_pagination`、`invalid_filter`、`internal_error` |
| GET | `/api/dashboard/reviews/{taskId}` | 单次 Review 报告 | 无 | `invalid_task_id`、`review_not_found`、`review_history_incomplete`、`internal_error` |
| GET | `/api/dashboard/reviews/{taskId}/findings` | Finding 列表 | `page` / `size` | 同上 |
| GET | `/api/dashboard/reviews/{taskId}/comments` | Comment 列表 | `page` / `size` | 同上 |
| GET | `/api/dashboard/statistics/overview` | Summary + Trend + Data Quality | DAY / WEEK；默认 30 天，最大 366 天 | `invalid_filter`、`invalid_granularity`、`invalid_range`、`internal_error` |
| GET | `/api/dashboard/statistics/reviews` | 逐 Review 对比表 | `page` / `size`；排序白名单；Java 内存排序/分页 | `invalid_pagination`、`invalid_filter`、`invalid_sort`、`invalid_range`、`internal_error` |

错误响应体字段是 `error`，不是 `code`。这是项目实际契约，前端 `api-error` 与 C 验收均已按此验证。

### 5.2 统计口径

`ReviewStatisticsService` 的当前口径：

- 报告级指标使用范围内所有 `review_report`；
- Finding 指标只使用“实际 Finding 行数 == 声明 `finding_count`”的报告；
- Comment 指标只使用“实际 Comment 行数 == 声明 `published_comment_count`”的报告；
- 不完整报告不会被静默丢弃，而是进入 `dataQuality` 披露；
- 未知 category / severity / AI status / publish status 进入 `UNKNOWN` 桶，不丢失、不伪造；
- 趋势按 `review_report.created_at` 分桶；
- DAY 为零填充自然日；WEEK 为 ISO-8601 周（周一开始），首尾周可能超出所选范围；
- 无报告时 `hasData=false`、`points=[]`，不画一整屏 0；
- 时间使用应用本地墙钟时间，SQL 不使用 `NOW()` / `CURDATE()`；前端 daterange 发送 `T00:00:00` / `T23:59:59.999999`，后端按左闭右闭处理；
- 默认 30 个自然日，最大 366 个自然日；
- 只读事务，隔离级别 `REPEATABLE_READ`；
- 不调用 GitHub、Python AI Service 或 LLM。

### 5.3 数据访问与性能

`ReviewStatisticsRepository` 是只读原生 SQL：

- 根表 `review_report`；
- `review_task` 只用于关联与筛选；
- 不读取 `review_result_delivery`；
- 不解析 `review_finding.references_json`；
- 所有用户输入使用命名参数；
- 没有写方法。

性能现状：

- `/api/dashboard/reviews`（History 列表）使用 Spring Data `Pageable`，由 SQL 完成分页；
- `/api/dashboard/statistics/reviews`（对比表）会加载范围内全部报告，再在 Java 内存中排序、分页；
- `review_report.created_at` 没有索引，统计范围查询会全表扫描；
- 当前验收库只有 6 份报告，因此这些成本可接受，但不能外推到生产数据量。

C 报告警告 2 的原文是“`/reviews` 仍在 Java 内存中排序、分页”。这里需要区分：

- `/api/dashboard/reviews` 不是内存分页，是 SQL 分页；
- 真正内存排序/分页的是 `/api/dashboard/statistics/reviews`。

这是文档表述需要澄清的点，不是新增缺陷。

### 5.4 错误处理

统计 Controller 和详情 Controller 都有最后兜底 `Exception` handler，响应固定为 `{"error":"internal_error"}`，日志只记录异常类名或安全的消息（不记录 SQL、绑定值、Token、堆栈）。

History 列表 Controller 有分页、筛选、类型不匹配、数据完整性 handler，但没有显式 `Exception` 兜底。Spring Boot 默认错误响应不会包含异常消息/堆栈（`server.error.include-message` 默认 `never`），因此不构成敏感信息泄漏；但从错误契约一致性看，可以作为一个很低的 P3 清理项，不属于本轮阻塞。

### 5.5 与 Python / GitHub 的边界

Dashboard 统计与历史查询只读 MySQL：

- 不调用 Python AI Service；
- 不调用 DeepSeek；
- 不调用 GitHub API；
- 不读取 Phase 10 的 `review_result_delivery`；
- 不修改任何 Review/Finding/Comment 数据。

这符合 AGENTS.md 中“Spring Boot 负责 GitHub 集成与业务后端，Python 负责 AI 分析”的边界。

---

## 6. 安全边界

### 6.1 `/api/dashboard/**` 的本机访问边界

`DashboardLocalAccessFilter` 的核心行为：

- 只对 `/api/dashboard` 及其子路径生效；
- 使用 `HttpServletRequest#getRemoteAddr()` 的 TCP peer 地址判断是否 loopback；
- 不信任 `X-Forwarded-For`、`Forwarded`、`X-Real-IP`、`Host` 等代理头；
- `application.yml` 显式设置 `server.forward-headers-strategy: none`；
- 使用 Spring MVC 的 `RequestPath` / `PathPattern` 解析路径；
- 对编码、矩阵参数、双斜杠、`.`/`..`、反斜杠等变体做 fail-closed 规范化；
- 解析失败时按 Dashboard 请求处理，而不是放行。

浏览器前端：

- 不发送 `X-Internal-Token`；
- 不在浏览器存储中保存内部 Token；
- 只通过同源 `/api/dashboard/**` BFF 读取；
- Vite 开发服务器显式绑定 `127.0.0.1`，代理 `/api` 到 `http://localhost:8080`。

Phase 10 的服务间 `/api/reviews/**` 仍由 `X-Internal-Token` 保护，Dashboard 过滤器不会误伤它。

### 6.2 验收证据

C 报告记录：

- 默认端口 8080：32 个请求用例，367/367 项检查通过；
- context path `/sentinel`：33 个请求用例，378/378 项检查通过；
- 非 loopback 直接访问 `/api/dashboard/statistics/overview` → 403，空响应体；
- 非 loopback + 伪造 `X-Forwarded-For` / `X-Real-IP` / `Forwarded` / `Host` → 403；
- 非 loopback 编码路径、矩阵参数、双斜杠、`.`/`..` → 403；
- 非 loopback 反斜杠/编码斜杠/null byte → 400（容器拒绝，非 200）；
- 所有响应体敏感关键字扫描通过；
- 所有响应头 `X-Internal-Token` 检查为 0；
- 非 Dashboard 路径 `/api/dashboard-other` → 404，不被误伤；
- Phase 10 `/api/reviews/7` → 401，不被 Dashboard 过滤器误伤。

补充证据：11.2.3-B 验收对 Review Detail 做了 XSS 检查，恶意 HTML 作为文本显示、`window.__xss` 未定义、危险 DOM 节点 0 个、页面无 `v-html` 节点。

### 6.3 残余边界

- 这是**应用级本机访问边界，不是用户认证**。任何运行在同一台主机上的反向代理，对 Spring 来说都来自 loopback；如果要把 Dashboard 暴露到局域网/公网，反向代理必须先做自己的认证。
- 当前没有用户级鉴权、会话、RBAC。这是项目已接受的个人使用边界，不是 Phase 11 的缺陷。
- `frontend/README.md` 已经写明了“不要 `vite --host 0.0.0.0`”和“同主机反向代理必须自行认证”，但该 README 的其它范围说明已过期，收尾时应一并更新。
- `/actuator/health` 不在 Dashboard 过滤器范围内，C 报告确认非 loopback 也可返回 200；这是既有运维端点边界。若未来把服务暴露到不可信网络，应单独评估 `management.endpoint.health.show-details` 与 actuator 路径限制，而不是依赖 Dashboard 过滤器。

---

## 7. 测试与验收证据

### 7.1 当前测试产物

后端 `target` 目录中存在本轮 C 验收生成的报告：

```text
Surefire：47 个测试集，541 个测试，0 失败 / 0 错误 / 0 跳过
Failsafe：10 个测试集，76 个测试，0 失败 / 0 错误 / 0 跳过
```

产物目录时间戳为 2026-11-14 18:13，晚于主要源码修改时间（2026-11-13），与 C 报告记录一致。

前端有 15 个测试文件：

```text
TrendChart.spec.ts
trend-geometry.spec.ts
statistics-format.spec.ts
statistics-api.spec.ts
router.spec.ts
ReviewHistoryView.spec.ts
ReviewDetailView.spec.ts
ReviewComparisonTable.spec.ts
review-history-api.spec.ts
review-detail-api.spec.ts
InsightsView.spec.ts
DashboardView.spec.ts
DashboardLayout.spec.ts
App.spec.ts
api-error.spec.ts
```

C 报告记录前端为 15 个测试文件、121 个测试通过。

验收库为 `codesentinel_accept_1123b`，规模为 6 份报告、50 条 Finding、26 条评论、7 条其他记录；这是刻意构造的小数据集，不是生产数据。

### 7.2 C 验收维度

| 维度 | 结果 | 证据 |
|---|---|---|
| 后端编译 | PASS | `mvn -DskipTests compile` 退出码 0 |
| 后端单元测试 | PASS | 47 个测试集，541 个测试 |
| MySQL 集成测试 | PASS | 10 个 IT 类，76 个测试 |
| 验收库定向 IT | PASS | `ReviewStatisticsAcceptanceDbIT` 12/12 |
| 前端静态检查 | PASS | `type-check`、`lint:check` 退出码 0 |
| 前端单元测试 | PASS | 15 个测试文件，121 个测试 |
| 前端生产构建 | PASS | Vite 8.3.7 构建成功，`InsightsView` 独立 chunk |
| 真实 B1 API 集成 | PASS | 28 个场景，155/155 项检查 |
| 真实浏览器 E2E | PASS | Chrome 157 + CDP，20 个场景，141/141 项断言 |
| 安全边界（默认端口） | PASS | 32 个请求用例，367/367 项检查 |
| 安全边界（context path） | PASS | `/sentinel`，33 个请求用例，378/378 项检查 |
| 验收数据库只读性 | PASS | 前后 `6 / 50 / 26 / 7`，校验和完全一致 |
| SQL EXPLAIN | PASS（只读） | 3 条查询计划；确认全表扫描与现有索引边界 |
| 真实 UI 翻页 | NOT VERIFIED | 6 行数据 < 页面最小 10 行；后端分页 API 已验证 |
| 生产性能 | NOT VERIFIED | 仅 6 行验收数据上的 EXPLAIN 估算 |

### 7.3 本轮调查是否重跑测试

**没有重跑。**

原因：

- 本轮任务是只读调查，重点是对照需求、实现和既有验收证据；
- C 报告生成于同一天，HEAD 未变化，源码修改时间早于测试产物时间；
- 重跑 `build`、`type-check`、`test`、`lint` 可能写入 `dist`、缓存或增量构建文件，扩大工作区变化；
- 按用户要求，不为调查制造额外的工作区改动。

因此，本报告对测试结论的引用基于：

1. 当前 `target/surefire-reports` 与 `target/failsafe-reports` 的实际 XML 汇总；
2. Phase 11.2.4-C 验收报告；
3. 前端 15 个 spec 文件的实际存在。

这不是“重新验收”，而是“核对既有验收证据与当前工作区一致”。

### 7.4 验收未覆盖的内容

C 报告已明确标记：

- 真实 UI 第 2 页翻页；
- 生产数据量下的查询性能；
- 浏览器 UI 的 403 错误文案；
- 生产构建产物的浏览器 E2E；
- 真机移动端 / 多浏览器；
- context path 下的浏览器 UI；
- 截图完整高度；
- 并发、慢查询、连接池压力；
- GitHub / LLM / Redis 链路。

这些都属于验证覆盖限制，不是已发现的代码缺陷。

---

## 8. 问题分级

### 8.1 P0

**无。**

没有发现核心闭环中断、数据损坏、未授权访问、Secret 泄漏或不可恢复错误。

### 8.2 P1

#### P1-01：Security / Bug / Performance / Quality 四类趋势未实现

**事实：**

- `docs/DEVELOPMENT_STATUS.md` §16 将四项列为 Dashboard 目标；
- `ReviewStatisticsTrendPoint` 只有 `bucketStart`、`bucketEnd`、`reviewCount`、`findingCount`、`highSeverityFindingCount`；
- `TrendChart.vue` 只渲染 Review 与 Finding 两条线；
- Insights 只有 Category 聚合分布，没有按时间分桶的 Category 序列；
- Phase 11.2.2-B 报告明确把 “Security / Bug / Performance / Quality Trends” 列为未实现；
- Phase 11.2.4-A 报告明确把 11.2.4 的范围限制在 Review/Finding 趋势，未把分类趋势纳入 B1/B2。

**影响：**

- 原始 Dashboard 清单无法全部勾选；
- 用户无法观察四类问题随时间的变化；
- 如果现在宣布 Phase 11 完成，会在 `DEVELOPMENT_STATUS.md` 中留下 4 个未勾选项与“已完成”结论的矛盾；
- 这不是运行时故障，但属于阶段验收目标缺口。

**定级理由：**

- 按项目“正确性 > 稳定性 > 可维护性 > 性能 > 功能数量”的优先级，登记目标未交付应阻断阶段验收；
- 它不是 P0，因为没有破坏核心 Review 闭环；
- 它不是 P2，因为 P2 通常表示“可在阶段内带着走”的非阻塞问题，而这里是明确的原始清单缺口；
- 因此定为 **P1**。如果用户/ChatGPT 明确降级，可转为 P3 backlog。

**建议修复：**

- 按第 11 节的最小任务补齐四类趋势；
- 或在第 10 节方案 B 中留下正式降级记录。

### 8.3 P2

**交付范围内未发现 P2 缺陷。**

以下事项属于“收尾前置条件”或“技术债”，不是 P2 代码缺陷：

- Phase 11 全部实现尚未提交；
- `DEVELOPMENT_STATUS.md` 仍写 Phase 11 未开始；
- 首页摘要为静态内容；
- 分类趋势缺失（已单列 P1，不重复计 P2）。

### 8.4 P3

| ID | 问题 | 证据 | 影响 | 建议 |
|---|---|---|---|---|
| P3-01 | 过期文案与路线图 | `DashboardView.vue` 写 “Quality insights — 11.3”；`DashboardLayout.vue` 3 处写 Phase 11.1；`SidebarNav.vue` 写 Phase 11.2；`frontend/README.md` 说详情/统计/图表 out of scope | 误导阅读者，Phase 编号与实际交付不一致 | 收尾时统一更新为 Phase 11 完成状态；删除或改写 11.3 路线图条目 |
| P3-02 | 首页没有真实统计摘要 | `DashboardView.vue` 的 Review History 卡片是静态 “Stored reports”，pipeline 卡片写死 Phases 1–10 | 首页不能一眼看到真实 Review/Finding 数字 | 可选增强；A 报告 Q10 已明确列为后续，不是 Phase 11 必须项 |
| P3-03 | `review_report.created_at` 无索引 | `review_history.sql` 只有主键与 `uk_review_report_task`；C 报告 EXPLAIN 确认全表扫描 | 生产数据量大时统计查询变慢 | 记录为性能技术债；达到阈值后再评估索引/迁移 |
| P3-04 | 统计对比表在 Java 内存排序/分页 | `ReviewStatisticsService.reviews` 加载全部报告后 `sorted` + `subList` | 大范围/大报告量时内存与 CPU 成本上升 | 记录阈值；未来可下推 SQL；当前 6 行数据可接受 |
| P3-05 | 验收库 IT 默认禁用 | C 报告记录标准 `-Pmysql-it verify` 不自动执行验收库测试 | 回归时容易漏跑 | 文档记录显式命令；未来 CI 增加专项 job |
| P3-06 | 范围条省略微秒 | 页面把 `23:59:59.999999` 显示为 `23:59:59` | 仅显示层，实际请求边界正确 | 可在收尾时顺手修；不修则记录为文案债 |
| P3-07 | 真实 UI 翻页未验证 | 验收库 6 行，页面最小页大小 10 | 第 2 页交互未经真实浏览器验证 | 后端 API 已验证；可用组件测试模拟多页，或后续补大数据 E2E |
| P3-08 | E2E 环境限制 | 仅 Chrome headless、Vite dev server、390×844 模拟；未在生产构建/多浏览器/真机验证 | 覆盖不完整 | 记录为验证债；未来补生产 preview 与多浏览器 |
| P3-09 | `DEVELOPMENT_STATUS.md` 与交付状态不一致 | 仍写 Phase 11 未开始，§16 全部未勾选 | 项目状态账本失真 | 收尾时必须更新；本次调查按用户要求未改 |
| P3-10 | 仓库尚无 CI | Phase 10 遗留；C 验收为本地执行 | 回归保障依赖人工 | 记录为工程债；不属于 Phase 11 功能范围 |
| P3-11 | History 列表 Controller 无显式 `Exception` 兜底 | `DashboardReviewController` 只有分页/筛选/类型/完整性 handler | 未预期异常走 Spring 默认错误体；默认不泄漏消息/堆栈 | 可作为一致性清理项，优先级很低 |

### 8.5 收尾前置条件（不是缺陷）

| ID | 条件 | 说明 |
|---|---|---|
| C-01 | 决定四类趋势：补齐或正式降级 | 见第 10 节；这是 Phase 11 能否关闭的前提 |
| C-02 | 提交 Phase 11 代码 | 当前 `main..HEAD = 0`；Phase 11 全部在工作区 |
| C-03 | 创建 PR 并评审合并 | 按 AGENTS.md GitHub Flow，不得直接改 `main` |
| C-04 | 更新 `docs/DEVELOPMENT_STATUS.md` | 六项勾选/降级记录、Phase 11 状态、下一步 |
| C-05 | 更新过期文案/README | P3-01；避免交付后文档自相矛盾 |
| C-06 | 记录 5 项警告的处置 | 可写入收尾报告或技术债清单 |

---

## 9. C 报告 5 项警告的处理建议

| # | C 警告 | 是否阻塞 Phase 11 | 建议处置 | 理由 |
|---|---|---|---|---|
| W1 | 真实 UI 第 2 页翻页未验证 | 否 | 留验证债；可在收尾时补一个多页组件测试；不必为此改生产代码 | 验收库只有 6 行，页面最小 10 行；后端 `page=2&size=2` 已验证 totalItems/totalPages 正确 |
| W2 | `review_report.created_at` 无索引；统计对比表在 Java 内存排序/分页 | 否 | 留性能技术债；澄清 `/api/dashboard/reviews` 是 SQL 分页，真正内存分页的是 `/api/dashboard/statistics/reviews`；未来按数据量阈值加索引/下推 SQL | 当前 6 行数据可接受；最大范围 366 天；个人使用场景 |
| W3 | 验收库 IT 默认禁用 | 否 | 留测试流程债；在 README/验收文档记录显式命令（`-Dit.test=ReviewStatisticsAcceptanceDbIT -Dcodesentinel.acceptance.db=true ...`）；未来 CI 增加专项 job | 不影响功能正确性，只影响回归便利性 |
| W4 | 范围条省略微秒 | 否 | 可选顺手修；不修则留文案债 | 实际请求 `23:59:59.999999` 正确，仅显示层省略小数秒 |
| W5 | E2E 方法/截图限制 | 否 | 留验证债；未来补生产构建 preview、多浏览器、真机 | 交付范围已在 Chrome headless + Vite dev server 验证；生产构建单独通过 |

**结论：**

- 5 项警告**没有一项必须在 Phase 11 内修复**；
- 它们都可以作为技术债/验证债记录，不阻断 Phase 11 收尾；
- 如果做收尾 PR，W4 是最便宜的顺手修复；W1 可以用一个组件测试部分补强；W2/W3/W5 更适合留到后续工程/性能/CI 任务。

---

## 10. Phase 11 结束判定

### 10.1 已完成的部分

| 子阶段 | 内容 | 状态 |
|---|---|---|
| 11.1 | Dashboard 布局、导航、路由、API client、响应式基础 | 完成 |
| 11.2.2 | Review History 列表、筛选、分页、详情入口 | 完成 |
| 11.2.3 | Review Detail 报告/Finding/Comment | 完成 |
| 11.2.4 | Insights 统计 API + 页面 + 验收 | 完成，PASS WITH WARNINGS |

就“已交付范围”而言，核心闭环是完整的：

```text
Dashboard
  → Review History
  → Review Detail
  → Review Insights
  → 逐 Review 对比
  → 回到 Review Detail
```

### 10.2 不能无条件宣布完成的原因

1. **P1-01**：四类分类趋势未实现，原始清单未全部勾选。
2. **C-02**：Phase 11 全部实现尚未提交，`main..HEAD = 0`。
3. **C-04**：`DEVELOPMENT_STATUS.md` 仍写 Phase 11 未开始。
4. **C-05**：过期文案/README 尚未清理。

其中 2–4 是收尾流程问题，可以在关闭阶段时解决；1 是需求决策问题，必须先做出选择。

### 10.3 方案 A：最小补齐后关闭（推荐）

```text
Phase 11.3-B  分类趋势扩展
      ↓
后端趋势 DTO/聚合 + 前端趋势图/测试
      ↓
重新验收（单元/IT/前端/真实 API/浏览器）
      ↓
更新 DEVELOPMENT_STATUS（六项全部勾选）
      ↓
更新文案/README
      ↓
commit + PR + 合并
      ↓
Phase 11 完成
```

适用条件：

- 认可四类趋势属于 Phase 11 原始范围；
- 愿意再投入一个小而可控的子阶段；
- 希望 `DEVELOPMENT_STATUS.md` 六项全部有真实实现对应。

### 10.4 方案 B：正式降级后关闭

```text
书面确认四类趋势不在 Phase 11 收尾范围
      ↓
DEVELOPMENT_STATUS §16 标记为 deferred（不勾选）
      ↓
记录降级原因、目标阶段（如 Phase 12+ / 后续 Dashboard 增强）
      ↓
更新文案/README
      ↓
commit + PR + 合并
      ↓
Phase 11 完成（带明确 backlog）
```

适用条件：

- 产品上认为当前 Review/Finding 趋势已足够支撑 MVP Dashboard；
- 愿意接受原始清单中有 4 项未交付；
- 必须留下书面决策，不能默默勾选“完成”。

### 10.5 最终判定

**当前状态：Phase 11.1–11.2.4 已实现；11.2.3–11.2.4 已通过验收（11.2.4 为 PASS WITH WARNINGS）。Phase 11 整体“待收尾决策”，不能无条件宣布完成。**

- 若选择 A 并完成 11.3-B：具备宣布 Phase 11 完成的条件。
- 若选择 B 并完成书面降级 + 状态/提交/PR 收尾：具备宣布 Phase 11 完成的条件。
- 在 A/B 未决之前：不具备宣布 Phase 11 完成的条件。

---

## 11. 最小必要下一步任务（方案 A）

### 11.1 任务名称

**Phase 11.3-B — Category Trend Extension（分类趋势扩展）**

> 本报告沿用当前 11.3-A 的编号；若团队更习惯按 11.2.x 编号，也可称为 11.2.5。

### 11.2 目标

在现有 Insights 趋势能力上增加 BUG / SECURITY / PERFORMANCE / QUALITY 四条分类时间序列，使原始 Dashboard 六项清单全部有真实实现对应。

### 11.3 后端改动

建议文件：

```text
backend/spring-service/src/main/java/cn/codesentinel/statistics/
├── ReviewStatisticsTrendPoint.java      # 增加分类计数字段
├── ReviewStatisticsService.java         # TrendBucket 增加分类累计
└── （测试）
    ├── ReviewStatisticsServiceTest.java
    ├── DashboardStatisticsControllerTest.java
    └── ReviewStatisticsAcceptanceDbIT.java（如适用）
```

实现要点：

1. `ReviewStatisticsTrendPoint` 增加：
   - `bugCount`
   - `securityCount`
   - `performanceCount`
   - `qualityCount`
   - 可选：`unknownCategoryCount`
2. `ReviewStatisticsService.TrendBucket` 增加对应累计字段。
3. 在 `buildTrend` 中，仅对 `findingsConsistent(report)` 的报告累计分类计数；与现有 `findingCount` 的闸门保持一致。
4. 复用现有 `FindingAggregateRow` 的 `getBugCount()` / `getSecurityCount()` / `getPerformanceCount()` / `getQualityCount()`，不需要改 SQL。
5. 保持现有字段与 JSON 向后兼容；新增字段是 additive change。
6. 补充测试：
   - 多报告跨多桶的分类累计；
   - 未知 category 进入 `UNKNOWN`；
   - Finding 计数不一致的报告不进入分类趋势；
   - DAY/WEEK 零填充；
   - 空范围 `hasData=false`。

### 11.4 前端改动

建议文件：

```text
frontend/src/types/statistics.ts             # StatisticsTrendPoint 增加分类字段
frontend/src/components/insights/TrendChart.vue
  或新增 CategoryTrendChart.vue              # 四条分类序列/可切换图例
frontend/src/views/InsightsView.vue          # 接入新图/说明
frontend/src/__tests__/TrendChart.spec.ts
frontend/src/__tests__/trend-geometry.spec.ts
frontend/src/__tests__/InsightsView.spec.ts
```

实现要点：

1. 避免把 6 条线全部塞进现有双线图造成视觉过载；推荐增加独立的 “Findings by category” 图，或四张小图/可切换序列。
2. 图例、空状态、数据表、WEEK 说明与现有风格一致。
3. 数据表增加四列分类计数（或独立表）。
4. 保持现有 Review/Finding 趋势不变。
5. 补充测试：
   - 四条序列的几何/图例；
   - 部分分类为 0；
   - 空数据；
   - 筛选/粒度切换后的请求参数。

### 11.5 验收标准

```text
[ ] 后端趋势响应包含四类分类计数
[ ] 同一范围下，趋势分类合计与 summary.categoryCounts 一致
[ ] Finding 不一致报告不进入分类趋势
[ ] 未知 category 进入 UNKNOWN，不丢失
[ ] DAY/WEEK 零填充正确
[ ] 前端四条分类趋势可见、可读、有空状态
[ ] 前端趋势数据表包含分类计数
[ ] 后端单元/Controller/IT 通过
[ ] 前端 type-check / lint:check / test:unit / build 通过
[ ] 真实 API 与浏览器检查通过
[ ] 未新增数据库结构、索引或前端依赖
[ ] 未修改 Phase 10 API、安全过滤器或 Phase 12 范围
```

### 11.6 明确不做

- 不新增数据库表/字段/索引；
- 不引入 ECharts/Chart.js；
- 不做 RAG / Milvus；
- 不做自定义规则；
- 不做用户认证/RBAC；
- 不做自动修复/自动评论/自动合并；
- 不修改 Phase 10 服务间 API 契约；
- 不修改 `DashboardLocalAccessFilter` 的边界语义。

---

## 12. 如果选择方案 B（降级）

最小动作：

1. 由用户/ChatGPT 明确确认：Security / Bug / Performance / Quality 四类趋势不在 Phase 11 收尾范围。
2. 在 `docs/DEVELOPMENT_STATUS.md` §16 中：
   - 保留四项为未勾选；
   - 标注 `deferred` / `Phase 12+` / `Post-MVP`；
   - 写明降级原因（例如“当前 Review/Finding 总量趋势已满足 MVP 观察需求，分类趋势留待后续”）。
3. 在收尾报告中记录该决策，避免未来误以为“已实现”。
4. 更新过期文案/README。
5. 提交 Phase 11 代码，创建 PR，评审合并。
6. 将 Phase 11 标记为完成，但明确“带 4 项 backlog”。

方案 B 不是“什么都不做”，而是“明确不做 + 留痕”。如果既不补齐也不降级，Phase 11 不应被标记为完成。

---

## 13. 调查边界与停止点

本次调查：

- 只新增了本报告；
- 未修改任何源代码、测试、配置、数据库、`docs/DEVELOPMENT_STATUS.md` 或既有 Phase 报告；
- 未安装依赖；
- 未执行 Git commit / push / merge / rebase / reset / clean / stash / checkout；
- 未清理工作区；
- 未开始 Phase 12 Custom Rules；
- 未执行来自 PR 的不可信代码。

**调查到此停止，等待 ChatGPT 验收。**

验收后再决定：

```text
A. 进入 Phase 11.3-B 分类趋势扩展
或
B. 正式降级四类趋势并执行 Phase 11 收尾
```

在决策之前，不进入 Phase 12。

---

## 附录 A：主要证据索引

### A.1 需求与状态

- `docs/PROJECT_DESIGN.md` §23（Dashboard / Code Quality Trend / 四类趋势）
- `docs/DEVELOPMENT_STATUS.md` §16（Dashboard 六项清单）
- `docs/DEVELOPMENT_STATUS.md` 当前阶段（Phase 11 未开始）

### A.2 既有验收报告

- `docs/reports/Phase11_2_2_B_Report.md`
- `docs/reports/Phase11_2_2_B_1_Report.md`
- `docs/reports/Phase11_2_3_A_Investigation_Report.md`
- `docs/reports/Phase11_2_3_B_Implementation_Report.md`
- `docs/reports/Phase11_2_3_B_Acceptance_Report.md`
- `docs/reports/Phase11_2_4_A_Investigation_Report.md`
- `docs/reports/Phase11_2_4_B1_Implementation_Report.md`
- `docs/reports/Phase11_2_4_B1_Code_Audit_Report.md`
- `docs/reports/Phase11_2_4_B2_Implementation_Report.md`
- `docs/reports/Phase11_2_4_C_Acceptance_Report.md`

### A.3 前端关键文件

- `frontend/src/router/index.ts`
- `frontend/src/layouts/DashboardLayout.vue`
- `frontend/src/components/SidebarNav.vue`
- `frontend/src/views/DashboardView.vue`
- `frontend/src/views/ReviewHistoryView.vue`
- `frontend/src/views/ReviewDetailView.vue`
- `frontend/src/views/InsightsView.vue`
- `frontend/src/components/insights/TrendChart.vue`
- `frontend/src/components/insights/DistributionBars.vue`
- `frontend/src/components/insights/StatCard.vue`
- `frontend/src/components/insights/ReviewComparisonTable.vue`
- `frontend/src/components/insights/InsightsFilterBar.vue`
- `frontend/src/composables/useStatisticsOverview.ts`
- `frontend/src/composables/useReviewStatistics.ts`
- `frontend/src/api/client.ts`
- `frontend/src/api/statistics.ts`
- `frontend/src/types/statistics.ts`

### A.4 后端关键文件

- `backend/spring-service/src/main/java/cn/codesentinel/controller/DashboardReviewController.java`
- `backend/spring-service/src/main/java/cn/codesentinel/controller/DashboardReviewDetailController.java`
- `backend/spring-service/src/main/java/cn/codesentinel/controller/DashboardStatisticsController.java`
- `backend/spring-service/src/main/java/cn/codesentinel/security/DashboardLocalAccessFilter.java`
- `backend/spring-service/src/main/java/cn/codesentinel/review/ReviewHistoryFilter.java`
- `backend/spring-service/src/main/java/cn/codesentinel/review/ReviewHistoryListService.java`
- `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsService.java`
- `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsRepository.java`
- `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsTrendPoint.java`
- `backend/spring-service/src/main/resources/application.yml`
- `backend/spring-service/src/main/resources/db/review_history.sql`

### A.5 测试产物

- `backend/spring-service/target/surefire-reports/TEST-*.xml`：47 个测试集，541 个测试
- `backend/spring-service/target/failsafe-reports/TEST-*.xml`：10 个测试集，76 个测试
- `frontend/src/__tests__/*.spec.ts`：15 个测试文件

### A.6 本次调查执行的只读命令

```text
git status --short --branch
git log -1 --format='%H %s'
git rev-list --count main..HEAD
git diff --stat
git diff -- docs/DEVELOPMENT_STATUS.md
```

以及只读的文件读取、`Select-String` 测试统计和目录时间戳检查。

---

## 附录 B：结论一句话版

> **Phase 11 的 Dashboard 主体（History / Detail / Insights）已经完成并通过验收，但原始清单中的 Security / Bug / Performance / Quality 四类趋势尚未实现；因此当前只能宣布“11.1–11.2.4 已交付”，不能无条件宣布“Phase 11 已完成”。建议先做最小分类趋势扩展，或正式书面降级后再关闭 Phase 11。**
