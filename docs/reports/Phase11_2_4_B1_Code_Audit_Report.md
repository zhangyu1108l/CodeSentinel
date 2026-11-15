# Phase 11.2.4-B1 代码审计报告 — Dashboard 只读统计后端

> 审计日期：2026-11-13  
> 分支：`phase11/dashboard`  
> HEAD：`27e3a41161cfa86ee2956ba0b3626a2bcc71eec7`  
> 阶段：Phase 11.2.4-B1（后端只读统计 API）  
> 审计性质：**只读审计。未修改源码、测试、配置、DDL、文档或数据库；未执行 commit / push / merge / rebase / reset / clean / checkout；未进入 B2。**  
> 审计基线：`docs/reports/Phase11_2_4_A_Investigation_Report.md`、`docs/reports/Phase11_2_4_B1_Implementation_Report.md`  
> 最终结论：**PASS WITH WARNINGS**

---

## 1. 审计结论

### 1.1 结论摘要

| 项目 | 结果 |
|---|---|
| P0（阻断 / 数据损坏 / 安全漏洞） | 0 |
| P1（核心口径错误 / 高概率生产故障） | 0 |
| P2（进入 B2 前应修复的显著风险） | 0 |
| P3（低风险偏差 / 文档不一致 / 潜在健壮性问题） | 9 |
| 核心统计口径 | 通过 |
| SQL 与数据完整性 | 通过 |
| 时间语义 | 通过 |
| 安全边界与异常处理 | 通过 |
| 测试证据 | 通过，但存在报告计数与测试环境限制 |
| Git 工作区边界 | 通过 |
| 最终判定 | **PASS WITH WARNINGS** |

### 1.2 判定说明

B1 的实现与 Phase 11.2.4-A 的核心设计一致：以 `review_report` 为统计根，报告级指标覆盖全部报告，Finding / Comment 级指标分别以实际行数与声明计数的一致性作为闸门；时间范围与应用本地时区语义正确；SQL 全部使用命名参数；接口位于 `/api/dashboard/**` 的 loopback 边界内；测试与现有 XML 证据均通过。

未发现 P0 / P1 / P2 问题。发现的 9 项均为 P3：排序 tie-breaker 与 A 文档的差异、`commitSha` 取值来源差异、`NOT IN` 对 NULL 的潜在漏计、验收库 URL 校验未锁定 host/port、日志措辞与报告不完全一致、测试总数与报告不一致、未知 publish status 的契约扩展、大小写/排序规则潜在差异、A 报告错误字段示例与实际契约不一致。这些均不改变当前数据下的统计结果，也不阻断 B1 作为 B2 的基础。

> 本报告只记录问题，不修复问题。任何代码、测试、DDL 或文档修改都应另开任务并重新验证。

---

## 2. 审计文件范围

### 2.1 基线文档

| 文件 | 审计用途 |
|---|---|
| `docs/reports/Phase11_2_4_A_Investigation_Report.md` | 统计口径、SQL 形态、时间语义、响应契约、验收标准的权威设计 |
| `docs/reports/Phase11_2_4_B1_Implementation_Report.md` | B1 实现声明、文件清单、测试声明、已知限制 |

### 2.2 生产代码

| 文件 | 审计重点 |
|---|---|
| `backend/spring-service/src/main/java/cn/codesentinel/controller/DashboardStatisticsController.java` | 路由、参数绑定、错误映射、安全边界 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsService.java` | 范围、聚合、一致性、趋势、排序、分页 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsRepository.java` | 原生 SQL、投影、过滤、只读性 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/StatisticsGranularity.java` | DAY / WEEK 解析 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsRange.java` | 生效范围 DTO |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsOverviewResponse.java` | `/overview` 响应 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsSummary.java` | 汇总 DTO |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsTrend.java` | 趋势 DTO |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsTrendPoint.java` | 趋势桶 DTO |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsDataQuality.java` | 数据质量 DTO |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsReviewItem.java` | `/reviews` 行 DTO |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsCount.java` | 分布桶 DTO |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/InvalidStatisticsGranularityException.java` | 非法粒度异常 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/InvalidStatisticsRangeException.java` | 非法范围异常 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/InvalidStatisticsSortException.java` | 非法排序异常 |

### 2.3 测试代码

| 文件 | 审计重点 |
|---|---|
| `backend/spring-service/src/test/java/cn/codesentinel/statistics/ReviewStatisticsServiceTest.java` | 19 个服务层单元测试 |
| `backend/spring-service/src/test/java/cn/codesentinel/controller/DashboardStatisticsControllerTest.java` | 15 个 Controller / 安全边界测试 |
| `backend/spring-service/src/test/java/cn/codesentinel/statistics/ReviewStatisticsMySqlIT.java` | 9 个 Testcontainers MySQL 集成测试 |
| `backend/spring-service/src/test/java/cn/codesentinel/statistics/ReviewStatisticsAcceptanceDbIT.java` | 12 个只读验收库集成测试 |
| `backend/spring-service/src/test/java/cn/codesentinel/CodeSentinelApplicationTests.java` | B1 唯一修改的既有测试文件 |

### 2.4 只读引用

| 文件 | 审计用途 |
|---|---|
| `backend/spring-service/src/main/java/cn/codesentinel/review/ReviewHistoryFilter.java` | 复用过滤语义 |
| `backend/spring-service/src/main/java/cn/codesentinel/review/ReviewHistoryQueryService.java` | 既有列表语义与分页上限 |
| `backend/spring-service/src/main/java/cn/codesentinel/security/DashboardLocalAccessFilter.java` | `/api/dashboard/**` loopback 边界 |
| `backend/spring-service/src/main/java/cn/codesentinel/task/ReviewReport.java` | 报告实体与列映射 |
| `backend/spring-service/src/main/java/cn/codesentinel/task/ReviewFinding.java` | Finding 实体与列映射 |
| `backend/spring-service/src/main/java/cn/codesentinel/task/ReviewComment.java` | Comment 实体与列映射 |
| `backend/spring-service/src/main/java/cn/codesentinel/task/ReviewTask.java` | 任务实体与状态 |
| `backend/spring-service/src/main/java/cn/codesentinel/review/ReviewPageResponse.java` | 分页响应契约 |
| `backend/spring-service/src/main/java/cn/codesentinel/review/ReviewHistoryError.java` | 错误响应契约 |
| `backend/spring-service/src/main/java/cn/codesentinel/task/PublishStatus.java` | 已知发布状态 |
| `backend/spring-service/src/main/java/cn/codesentinel/task/TaskStatus.java` | 已知任务状态 |
| `backend/spring-service/src/main/resources/db/review_history.sql` | Phase 10.1 已批准 DDL |
| `backend/spring-service/src/main/resources/application.yml` | 数据源、时区相关配置、forwarded headers |
| `backend/spring-service/pom.xml` | `mysql-it` profile、测试依赖 |

### 2.5 不在本次范围

- B2 前端 Insights 页面、`frontend/` 任何改动。
- Python AI Service、LangGraph、Prompt、Finding 生成逻辑。
- GitHub Webhook、GitHub API、评论发布。
- 生产 / 验收数据库任何写操作。
- 任何 DDL 变更、索引新增、数据回填。
- 任何 Git 写操作。
- 任何对 `docs/DEVELOPMENT_STATUS.md` 的修改。

---

## 3. 逐项审计结果

### A. 统计口径

| # | 检查项 | 证据 | 结果 |
|---|---|---|---|
| A-01 | 统计根表是 `review_report`，不以 `review_task` 或无报告任务为根 | `ReviewStatisticsRepository.java:47-48`；两个查询均从 `review_report r` 出发；A 报告 §4.1 规则 8 | 通过 |
| A-02 | 报告级指标覆盖范围内全部报告 | `ReviewStatisticsService.java:257-325` 中 `reviewCount`、publish/AI 分布、`summaryCommentIdPresentCount` 均使用 `snapshot.reports()` | 通过 |
| A-03 | Finding 指标只统计实际行数等于 `finding_count` 的报告 | `ReviewStatisticsService.java:259-261, 564-567`；`findingsConsistent` 比较实际 `review_finding` 行数与声明值 | 通过 |
| A-04 | Comment 指标只统计实际行数等于 `published_comment_count` 的报告 | `ReviewStatisticsService.java:262-264, 569-572`；`review_comment` 仅表示已成功创建的内联评论 | 通过 |
| A-05 | Finding 闸门与 Comment 闸门相互独立 | 两个独立的 `filter`；验收测试 `shouldExcludeReport2003FromFindingsAndReport2005FromComments` 覆盖 | 通过 |
| A-06 | 不完整报告仍保留在报告级指标与 `/reviews` 行中 | 报告级聚合使用全部 `reports`；`/reviews` 的 `toReviewItem` 始终输出声明/实际/一致性标记 | 通过 |
| A-07 | 零分母比率返回 `null`，不返回 NaN / Infinity | `ReviewStatisticsService.java:578-581`；`ratio` 在分母为 0 时返回 `null` | 通过 |
| A-08 | 中位数包含 0 Finding 报告；偶数个取中间两值平均 | `ReviewStatisticsService.java:306-308, 583-594`；测试 `shouldComputeEvenMedianIncludingZeroFindingReports` | 通过 |
| A-09 | `maxFindingsInReview` 无 Finding 报告时为 `null`，否则取最大值 | `ReviewStatisticsService.java:309-311, 596-598` | 通过 |
| A-10 | `highSeverityFindingCount` = CRITICAL + HIGH，且只来自 Finding 一致报告 | `ReviewStatisticsService.java:291-292, 348-359`；SQL 条件聚合 | 通过 |
| A-11 | category / severity 分布固定顺序且包含 `UNKNOWN` | `ReviewStatisticsService.java:57-60, 273-276, 327-361, 600-621`；`ReviewStatisticsCount` 使用有序数组 | 通过 |
| A-12 | publish / ai 状态分布覆盖全部报告，未知值不丢失 | `ReviewStatisticsService.java:278-286, 434-455`；已知值精确计数，其余进入 `UNKNOWN` | 通过 |
| A-13 | 趋势中的 `reviewCount` 覆盖全部报告，Finding 数只覆盖一致报告 | `ReviewStatisticsService.java:389-407`；`reviewCount++` 无条件，Finding 计数前判断 `findingsConsistent` | 通过 |
| A-14 | 趋势无数据时 `points=[]`、`hasData=false`；有数据时零填充完整范围 | `ReviewStatisticsService.java:363-418`；`snapshot.reports().isEmpty()` 提前返回空趋势 | 通过 |
| A-15 | `/reviews` 同时返回声明值、实际值、一致性标记和逐报告分布 | `ReviewStatisticsReviewItem.java:15-43`；`ReviewStatisticsService.java:458-497` | 通过 |
| A-16 | 排序白名单 + 稳定 tie-breaker | `ReviewStatisticsService.java:109-129, 512-554`；默认 `createdAt DESC, reportId DESC` | 通过（tie-breaker 与 A 有 P3 差异，见 F-01） |
| A-17 | 分页边界正确，越界页返回空 items，`hasNext` 一致 | `ReviewStatisticsService.java:131-145, 556-562`；测试 `shouldPaginateAndSortDeterministically` | 通过 |
| A-18 | `dataQuality` 明确披露排除数与未知枚举数 | `ReviewStatisticsService.java:420-456`；`ReviewStatisticsDataQuality.java:10-19` | 通过（publish UNKNOWN 为契约扩展，见 F-07） |
| A-19 | `summaryCommentIdPresentCount` 只表示“有可用 ID”，不宣称摘要评论发布成功 | `ReviewStatisticsRepository.java:45-46`；`ReviewStatisticsService.java:296-299`；A 报告 §4.2 第 5 条 | 通过 |
| A-20 | 报告缺少对应 task 时失败关闭，而不是伪造 UNKNOWN | `ReviewStatisticsService.java:190-203`；`ReviewStatisticsMySqlIT.shouldFailClosedForAnOrphanReport` | 通过 |

### B. SQL 与数据完整性

| # | 检查项 | 证据 | 结果 |
|---|---|---|---|
| B-01 | Repository 只读，无 save / delete / update 方法 | `ReviewStatisticsRepository.java:24-25` 继承 Spring Data `Repository`，仅声明两个 `@Query` 方法 | 通过 |
| B-02 | 不读取 `review_result_delivery`，不解析 `review_finding.references_json` | Repository 两个 SQL 均只涉及 `review_report`、`review_task`、`review_finding`、`review_comment`；无 `references_json` | 通过 |
| B-03 | 所有用户输入使用命名参数，无字符串拼接 | `ReviewStatisticsRepository.java:49-56, 105-112`；sort/direction 只用于 Java 内存排序 | 通过 |
| B-04 | 报告查询与 Finding 聚合查询使用完全相同的过滤块 | `ReviewStatisticsRepository.java:49-56` 与 `105-112` 逐项一致 | 通过 |
| B-05 | 实际 Finding / Comment 数来自真实行，不依赖声明值 | `ReviewStatisticsRepository.java:40-44` 的 `COUNT(*)` 子查询；声明值仅用于一致性比较 | 通过 |
| B-06 | 两套 Finding 行数互相校验，防止聚合与主查询不一致 | `ReviewStatisticsService.java:240-253`；`actual` 与 `aggregated` 不等即抛 `ReviewHistoryDataIntegrityException` | 通过 |
| B-07 | 重复聚合 / 多余聚合 / 聚合缺失均失败关闭 | `ReviewStatisticsService.java:220-239`；测试 `shouldFailClosedWhenFindingAggregateIsMissing`、`shouldFailClosedWhenFindingAggregatesDisagree` | 通过 |
| B-08 | 一次请求在同一只读事务中读取，使用 `REPEATABLE_READ` | `ReviewStatisticsService.java:87-105`；`@Transactional(readOnly=true, isolation=REPEATABLE_READ)` | 通过 |
| B-09 | `LEFT JOIN review_task` 允许检测孤儿报告 | `ReviewStatisticsRepository.java:48`；Service 在 `taskId/owner/repo/...` 为 null 时抛异常 | 通过 |
| B-10 | 未知 category / severity 不丢失、不抛异常 | SQL 条件聚合 + `UNKNOWN` 桶；`ReviewStatisticsMySqlIT.shouldRetainUnknownStoredStatusesWithoutFailing` | 通过（NULL 边界见 F-03） |
| B-11 | 测试 schema 与生产 DDL 的差异有显式处理 | MySQL IT 使用 Hibernate `create-drop`，并在 fixture 前将 `publish_status` 改为 `VARCHAR(20)`；只作用于 Testcontainers 临时库 | 通过（生产 DDL 未被修改） |
| B-12 | `published_comment_count` 只对应 inline `review_comment`，不含 summary comment | `review_history.sql:19-20, 50-62`；`ReviewStatisticsService.java:269-271` | 通过 |
| B-13 | 未知 publish / ai status 原值保留在 `/reviews` item 中 | `ReviewStatisticsReviewItem.aiStatus/publishStatus` 为 String；MySQL IT 断言 `WEIRD` / `MYSTERY` 原值 | 通过 |
| B-14 | SQL 注入文本只作为字面值过滤 | 全部命名参数；`ReviewStatisticsMySqlIT.shouldTreatSqlInjectionTextAsALiteralFilterValue`，注入字符串返回 0 行 | 通过 |
| B-15 | `created_at` 无索引的已知性能限制 | A 报告 §7.5 已记录；B1 未改 DDL；当前数据量小，验收查询可接受 | 观察（非 B1 缺陷，见 §4.5） |

### C. 时间语义

| # | 检查项 | 证据 | 结果 |
|---|---|---|---|
| C-01 | 时间基准是 `review_report.created_at` | `ReviewStatisticsRepository.java:55-56, 111-112`；A 报告 §4.1 规则 2 | 通过 |
| C-02 | 时间范围左闭右闭 | SQL 使用 `>= :createdFrom` 与 `<= :createdTo` | 通过 |
| C-03 | 默认最近 30 个自然日（含今天） | `ReviewStatisticsService.java:50, 153-155`；`today.minusDays(29)` 到 `today` 结束 | 通过 |
| C-04 | 单边提供时的默认边界正确 | `ReviewStatisticsService.java:156-162`；只给 `createdFrom` 时 `to=今天结束`，只给 `createdTo` 时 `from=createdTo-29天` 开始 | 通过 |
| C-05 | 最大 366 个自然日，恰好 366 天允许 | `ReviewStatisticsService.java:168-174`；测试 `shouldAcceptExactlyThreeHundredSixtySixCalendarDays`、`shouldRejectRangeLongerThanThreeHundredSixtySixDays` | 通过 |
| C-06 | `createdFrom > createdTo` 拒绝 | `ReviewHistoryFilter.java:53-57`；Service 再次校验 `ReviewStatisticsService.java:164-167` | 通过 |
| C-07 | 使用应用本地时区 / Clock，不使用数据库时区 | `ReviewStatisticsService.java:74-85, 148-155`；`ZoneId.systemDefault()` + `Clock.system(...)` | 通过 |
| C-08 | SQL 不使用 `NOW()` / `CURDATE()` / `CURRENT_TIMESTAMP` | Repository 两个 SQL 无时间函数，只比较参数 | 通过 |
| C-09 | `DATETIME(6)` 与 `LocalDateTime` 语义一致 | DDL `review_history.sql:23-24, 45, 58`；DTO 与查询参数均为 `LocalDateTime` | 通过 |
| C-10 | DAY 桶为应用本地自然日 | `ReviewStatisticsService.java:373-377`；每个日期一个桶 | 通过 |
| C-11 | WEEK 桶为 ISO-8601 周，周一开始 | `ReviewStatisticsService.java:378-386, 391-394`；`previousOrSame(MONDAY)`；测试 `shouldUseIsoWeeksStartingOnMonday` | 通过 |
| C-12 | 趋势零填充；首尾周可超出请求边界 | `ReviewStatisticsService.java:370-387`；A 报告 §4.4 说明 | 通过 |
| C-13 | `range` 返回生效范围，`zoneId` / `generatedAt` 使用应用本地时间 | `ReviewStatisticsService.java:94-100`；`ReviewStatisticsRange.java:10-14` | 通过 |
| C-14 | 未来 `createdFrom` 的拒绝行为与 A 的语义一致 | 只提供未来 `createdFrom` 时，默认 `createdTo=今天结束`，因此 `from > to` 被拒绝；测试 `shouldRejectOnlyFromInTheFuture` | 通过（A 未要求单独的未来校验，行为由范围校验自然产生） |

### D. 安全与异常

| # | 检查项 | 证据 | 结果 |
|---|---|---|---|
| D-01 | 两个端点都位于 `/api/dashboard/**`，受 loopback 过滤器保护 | Controller `DashboardStatisticsController.java:64, 85`；`DashboardLocalAccessFilter.java:57-63, 73-90` | 通过 |
| D-02 | 不信任 Forwarded / X-Forwarded-For | `application.yml:16-18` 设置 `forward-headers-strategy: none`；Controller 测试 `shouldNotTrustForwardedHeaders` | 通过 |
| D-03 | 不读取、不回显 `REVIEW_HISTORY_INTERNAL_TOKEN` | Controller 无 token 参数 / header；测试 `shouldNotRequireOrEchoTheInternalToken` | 通过 |
| D-04 | 统计接口不调用 GitHub / Python / LLM | Controller 只调用 `ReviewStatisticsService`；Service 只调用 Repository | 通过 |
| D-05 | 400 错误映射稳定 | `DashboardStatisticsController.java:111-157`；`invalid_pagination`、`invalid_filter`、`invalid_granularity`、`invalid_sort`、`invalid_range` | 通过 |
| D-06 | 500 响应不泄漏 SQL / 表名 / 绑定值 / 凭据 | `DashboardStatisticsController.java:159-180`；响应固定 `{"error":"internal_error"}`；测试 `shouldReturnSafeInternalErrorForIntegrityFailure`、`shouldNotLeakUnexpectedExceptionDetails` | 通过 |
| D-07 | 日志不记录 Secret / SQL / 绑定值 | `handleUnexpected` 只记录异常类名；`handleDataIntegrity` 记录内部完整性消息（报告 ID 与计数，无 SQL/凭据） | 通过（与报告措辞有 P3 差异，见 F-05） |
| D-08 | SQL 注入防护 | 命名参数；注入文本测试通过 | 通过 |
| D-09 | 统计只读，不写数据库 | Repository 无写方法；Service 只读事务；验收 IT 记录前后行数不变 | 通过 |
| D-10 | 错误响应字段与项目实际契约一致 | `ReviewHistoryError.java:7` 使用 `error`；Controller 所有错误体均使用该字段 | 通过（A 文档示例为 `code`，见 F-09） |
| D-11 | 未预期异常不会把异常消息返回给客户端 | `handleUnexpected` 固定 `internal_error`；测试验证不包含 `super-secret` / `SQL` | 通过 |
| D-12 | 验收库测试有数据库名保护 | `ReviewStatisticsAcceptanceDbIT.java:83-93` 要求 URL 最后一段为 `codesentinel_accept_1123b` | 通过（未锁定 host/port，见 F-04） |
| D-13 | Loopback 是个人使用边界，不等同于认证 | `DashboardLocalAccessFilter.java:45-48` 明确说明；A 报告同样将 Dashboard 定位为本地个人使用 | 通过（边界声明清晰） |
| D-14 | Controller 与 Service 的分页校验重复 | Controller `DashboardStatisticsController.java:182-188`；Service `ReviewStatisticsService.java:556-562` | 通过（防御性重复，无副作用） |

### E. 测试可信度

| # | 检查项 | 证据 | 结果 |
|---|---|---|---|
| E-01 | `ReviewStatisticsServiceTest` 19/19 通过 | `target/surefire-reports/TEST-cn.codesentinel.statistics.ReviewStatisticsServiceTest.xml`：tests=19, failures=0, errors=0, skipped=0 | 通过 |
| E-02 | `DashboardStatisticsControllerTest` 15/15 通过 | `target/surefire-reports/TEST-cn.codesentinel.controller.DashboardStatisticsControllerTest.xml`：tests=15, failures=0, errors=0, skipped=0 | 通过 |
| E-03 | `ReviewStatisticsMySqlIT` 9/9 通过 | `target/failsafe-reports/TEST-cn.codesentinel.statistics.ReviewStatisticsMySqlIT.xml`：tests=9, failures=0, errors=0, skipped=0（59.738s） | 通过 |
| E-04 | `ReviewStatisticsAcceptanceDbIT` 12/12 通过 | `target/failsafe-reports/TEST-cn.codesentinel.statistics.ReviewStatisticsAcceptanceDbIT.xml`：tests=12, failures=0, errors=0, skipped=0（10.329s） | 通过 |
| E-05 | 后端完整单元测试通过 | 当前 47 个 surefire suite，合计 541 tests，0 failures / 0 errors / 0 skipped | 通过（报告写 536，见 F-06） |
| E-06 | 完整 MySQL IT 通过 | 当前 10 个 failsafe suite，合计 76 tests，0 failures / 0 errors / 0 skipped，其中包含 12 个验收测试 | 通过（报告写“76 运行、12 跳过”，见 F-06） |
| E-07 | B1 测试覆盖核心风险 | 服务测试覆盖范围、粒度、分页、排序、空值、中位数、趋势、未知枚举、一致性、失败关闭、过滤参数；Controller 测试覆盖绑定、默认值、错误映射、loopback、编码路径、Forwarded Header、Token、500 安全；MySQL IT 覆盖真实 SQL、过滤边界、空库、未知枚举、孤儿报告、注入文本、并发读；验收 IT 覆盖验收库数字、6 份报告、一致性标记、趋势、分页排序、时间边界 | 通过 |
| E-08 | `CodeSentinelApplicationTests` 的 B1 改动正确 | `git diff` 仅新增 `ReviewStatisticsRepository` 的 `@MockBean`；上下文测试 1/1 通过 | 通过 |
| E-09 | 测试产物晚于源码修改时间 | 主要 B1 源码修改于 21:22–21:29，MySqlIT 测试源码 21:55:22；对应 XML 产物时间为 21:55:53–21:57:07，验收 IT 产物 21:47:28，均晚于对应源码 | 通过（证据与当前代码对应） |
| E-10 | 测试环境限制已识别 | MySQL IT 使用 Hibernate `create-drop`；验收 IT 默认禁用；单元 / Controller 测试使用 mock；并发测试使用静态数据 | 观察（见 §6.4） |

### F. Git 工作区边界

| # | 检查项 | 证据 | 结果 |
|---|---|---|---|
| F-01 | 当前分支与 HEAD 正确 | `git rev-parse --abbrev-ref HEAD` = `phase11/dashboard`；HEAD = `27e3a41161cfa86ee2956ba0b3626a2bcc71eec7` | 通过 |
| F-02 | 暂存区为空 | `git diff --cached --name-only` 无输出 | 通过 |
| F-03 | B1 新增文件符合报告清单 | 新增 `DashboardStatisticsController.java`、`statistics/` 14 个类、4 个测试类、B1 实施报告 | 通过 |
| F-04 | B1 只修改一个既有 tracked 文件 | `CodeSentinelApplicationTests.java` 仅新增 import 与 `@MockBean` | 通过 |
| F-05 | 既有用户改动未被 B1 覆盖 | `.gitignore`、`ReviewHistoryQueryService.java`、`ReviewReportRepository.java`、`application.yml`、`docs/DEVELOPMENT_STATUS.md`、`frontend/.gitkeep` 等为 B1 之前已有的 Phase 11.x 工作；diff 内容与 B1 无关 | 通过 |
| F-06 | B1 未修改 DDL / pom / application.yml | `git diff` 显示这些文件的改动属于既有 Dashboard 工作；B1 报告也声明未修改 | 通过 |
| F-07 | 未执行 Git 写操作 | 审计期间只执行 `git status` / `git diff` / `git rev-parse` / `git log` 等只读命令 | 通过 |
| F-08 | 未清理工作区 | 未执行 `git clean`、`reset`、`checkout`、`stash` | 通过 |
| F-09 | 审计输出是唯一新增文件 | 本报告为 `docs/reports/Phase11_2_4_B1_Code_Audit_Report.md`，此前不存在 | 通过 |
| F-10 | 未进入 B2 | 未修改任何前端文件，未启动前端开发 | 通过 |

---

## 4. 审计发现

### 4.1 P0

无。

### 4.2 P1

无。

### 4.3 P2

无。

### 4.4 P3

#### F-01 [P3] 默认排序 tie-breaker 使用 `report_id DESC`，A 设计写的是 `task_id DESC`

- **证据**：`ReviewStatisticsService.java:125-126` 对所有排序追加 `Comparator.comparingLong(ReviewWithReport::reportId).reversed()`；A 报告 §6.2 第 620 行写明默认排序为 `createdAt DESC, taskId DESC`。B1 实施报告第 232 行明确记录实际使用 `report_id DESC`，并说明与既有 Review History 的 `id DESC` 保持一致。
- **影响**：`review_report.id` 与 `review_task.id` 都是唯一值，分页稳定性不受影响；差异只体现在 `created_at` 相同的多条记录之间的相对顺序。由于 `review_report.task_id` 有唯一键，二者在正常写入下近似同序，但并非数据库层面保证。
- **判定**：非功能性偏差，不阻断 B1。若后续要求与 A 文档严格一致，可在 B2 前统一 tie-breaker 或修订 A 文档；本次审计不修改代码。

#### F-02 [P3] `/reviews` 的 `commitSha` 取自 `t.commit_sha`，A 的 SQL 示例使用 `r.commit_sha`

- **证据**：`ReviewStatisticsRepository.java:34` 为 `t.commit_sha AS commitSha`；A 报告 §7.3 的 SQL 示例第 877 行为 `r.commit_sha AS commit_sha`。B1 实施报告第 460 行与实际代码一致。
- **影响**：正常写入路径下两者相等：`ReviewResultService.java:111` 要求 delivery 的 `commitSha` 等于 task 的 `commitSha`；`ReviewHistoryService.java:283-285` 用 delivery 的 `commitSha` 写入 report；报告创建后 task 的 `commitSha` 不可变。若 task 行缺失，Service 会失败关闭（`ReviewStatisticsService.java:190-203`），不会返回伪造值。只有在绕过应用直接改库、使 report 与 task 的 commit 不一致时，接口才会显示 task 的 commit 而非 report 的 commit。
- **判定**：低风险差异。建议后续明确“统计展示以 task commit 为准”或改为 `r.commit_sha`；本次不修改。

#### F-03 [P3] `NOT IN` 对 NULL 的 SQL 语义可能导致未知 category / severity 漏计

- **证据**：`ReviewStatisticsRepository.java:88-90` 与 `99-101` 使用 `f.severity NOT IN (...)`、`f.category NOT IN (...)`。SQL 中 `NULL NOT IN (...)` 结果为 `NULL`，`COUNT(CASE WHEN ... THEN 1 END)` 不会计数。当前 DDL `review_history.sql:33-34` 将 `category`、`severity` 声明为 `NOT NULL`，实体也按非空映射，因此正常数据不会触发。
- **影响**：只有绕过 DDL / 约束写入 NULL 时，`UNKNOWN` 分布与 `dataQuality.unknownCategoryFindingCount` / `unknownSeverityFindingCount` 会少计，且分布合计可能小于实际 Finding 行数。
- **判定**：潜在数据完整性边界，非当前缺陷。若未来允许 NULL 或导入外部数据，应改为 `IS NULL OR ... NOT IN (...)` 或在 Service 层显式校验；本次不修改。

#### F-04 [P3] 验收库 URL 校验只校验数据库名，未锁定 host / port

- **证据**：`ReviewStatisticsAcceptanceDbIT.java:83-93` 取 URL 最后一个 `/` 后的路径并去掉 query，只比较是否等于 `codesentinel_accept_1123b`；未校验 host、port 或 JDBC 协议。B1 实施报告第 773 行表述为“URL 必须精确指向 `codesentinel_accept_1123b`”。
- **影响**：开发者显式开启 `-Dcodesentinel.acceptance.db=true` 并提供凭据时，理论上可以把测试指向任意主机上同名数据库。测试本身是 `@Transactional(readOnly=true)`、Hikari `read-only=true`，且不含写操作，风险有限；但它不是“精确 URL”级别的保护。
- **判定**：测试安全加固项。建议后续增加 host/port 允许列表或要求显式 `acceptance.host`；本次不修改。

#### F-05 [P3] `handleDataIntegrity` 记录异常消息，报告“只记录报告 ID”的表述略强于实现

- **证据**：`DashboardStatisticsController.java:159-166` 使用 `log.error("Dashboard statistics history is unreadable: {}", error.getMessage())`；完整性异常消息包含报告 ID 以及 `actual` / `aggregated` 计数（如 `ReviewStatisticsService.java:246-252`）。B1 实施报告第 308 行称“只记录可定位的报告 ID；未记录 SQL 或敏感数据”。
- **影响**：日志中会出现报告 ID 和计数值，但不会出现 SQL、绑定值、Token 或凭据；不构成敏感信息泄漏。该差异属于报告措辞精度问题。
- **判定**：文档措辞问题。若需要严格只记录 ID，可调整异常消息或日志字段；本次不修改。

#### F-06 [P3] B1 实施报告的全量测试计数与当前测试产物不一致

- **证据**：B1 实施报告第 623、753 行写“后端完整 `mvn test` 536/536 通过”；当前 `target/surefire-reports` 为 47 个 suite、541 tests、0 failures / 0 errors / 0 skipped。报告第 624、754 行写“完整 MySQL IT 76 运行，0 失败，12 跳过”；当前 `target/failsafe-reports` 为 10 个 suite、76 tests、0 failures / 0 errors / 0 skipped（其中 `ReviewStatisticsAcceptanceDbIT` 12 个测试实际执行并通过）。
- **影响**：不影响代码正确性，但使报告中的测试证据无法按字面复现。当前 XML 证据显示 B1 相关 19 + 15 + 9 + 12 全部通过。
- **判定**：报告准确性问题。建议后续以一次干净的全量运行结果统一更新报告；本次不修改文档。

#### F-07 [P3] publish status 分布与 `dataQuality` 增加了 A 示例中没有的 `UNKNOWN` 契约

- **证据**：`ReviewStatisticsService.java:61-66, 278-286` 为 `publishStatusCounts` 增加 `UNKNOWN` 桶；`ReviewStatisticsService.java:438-455` 增加 `unknownPublishStatusReportCount`；`ReviewStatisticsDataQuality.java:10-19` 包含该字段。A 报告第 438-442 行的 publish 状态顺序只列到 `PENDING`，第 689-698 行的 `dataQuality` 示例没有 `unknownPublishStatusReportCount`。B1 实施报告第 202-203 行明确说明这是有意的扩展。
- **影响**：这是向后兼容的加法扩展，能避免未知存储值被静默丢弃；但 B2 前端类型与展示必须接受多出的 `UNKNOWN` 桶和字段，不能假设响应与 A 示例完全一致。
- **判定**：已文档化的契约扩展，不是缺陷。B2 开始前应把该扩展写入前端契约；本次不修改。

#### F-08 [P3] SQL 枚举比较与 Java 状态判断在大小写敏感性上不一致，属于潜在数据异常边界

- **证据**：MySQL 默认 `utf8mb4` 排序规则下，`f.severity = 'CRITICAL'`、`f.severity NOT IN (...)` 等比较通常大小写不敏感；而 Java 的 `KNOWN_AI_STATUSES.contains(...)` / `KNOWN_PUBLISH_STATUSES.contains(...)`（`ReviewStatisticsService.java:65-68, 434-441`）是大小写敏感的。正常写入使用枚举大写名称，因此当前数据不会触发。
- **影响**：如果通过外部导入写入小写 `critical` 或 `published`，SQL 可能将其计入已知分布，而 Java 的未知状态计数会将其计为 `UNKNOWN`，造成同一份响应中不同指标的口径不一致。
- **判定**：潜在数据异常边界，不是当前缺陷。若未来支持外部数据导入，应统一大小写规范化或在 SQL/Java 两侧使用同一判定规则；本次不修改。

#### F-09 [P3] A 报告的错误响应示例使用 `code`，实际项目契约使用 `error`

- **证据**：A 报告第 783 行示例为 `{ "code": "invalid_filter" }`；实际 `ReviewHistoryError.java:7` 的字段是 `error`，Controller 所有错误响应均使用 `{"error":"..."}`。B1 实施报告第 290-293、840 行已明确说明以实际契约为准。
- **影响**：实现是正确的，问题在于 A 报告示例可能误导后续前端或调用方。B2 前端必须以 `error` 字段解析错误。
- **判定**：文档差异，非代码缺陷。建议后续修订 A 报告示例或在前端契约中明确；本次不修改。

### 4.5 已知限制（非 P3 缺陷）

| 编号 | 限制 | 说明 |
|---|---|---|
| L-01 | `review_report.created_at` 没有索引 | A 报告 §7.5 已实测并记录；B1 未改 DDL。当前数据量下可接受，数据增长后需评估索引或下推查询。 |
| L-02 | `/reviews` 在 Java 内存中排序、分页 | A 报告明确接受当前数据规模下的内存方案；若单次范围报告数达到数万，应改为 SQL 分页并保持白名单和稳定 tie-breaker。 |
| L-03 | MySQL IT 使用 Hibernate `create-drop` | 测试 schema 与生产 DDL 不完全相同；已通过临时 `ALTER` 对齐 `publish_status`，并由验收 IT 覆盖真实 DDL 的关键路径。 |
| L-04 | 验收 IT 默认禁用 | `@EnabledIfSystemProperty(named = "codesentinel.acceptance.db", matches = "true")`；普通 CI 不会自动连接验收库。 |
| L-05 | 并发读测试使用静态数据 | `shouldReturnTheSameSnapshotToConcurrentReaders` 验证 16 个读者得到相同结果，但不模拟并发写入；不能替代完整的隔离级别压力测试。 |
| L-06 | 本次审计未重新运行 Maven | 测试证据来自现有 `target/surefire-reports` 与 `target/failsafe-reports`；产物时间晚于对应源码修改时间，但严格意义上不是审计期间的独立重跑。 |

---

## 5. 报告与代码 / A 设计的差异

### 5.1 B1 实施报告与当前代码

| 项目 | B1 报告 | 当前代码 | 判定 |
|---|---|---|---|
| 排序 tie-breaker | 报告第 232 行写 `report_id DESC` | `ReviewStatisticsService.java:125-126` 使用 `reportId DESC` | 一致 |
| `commitSha` 来源 | 报告第 460 行 SQL 使用 `t.commit_sha` | `ReviewStatisticsRepository.java:34` 使用 `t.commit_sha` | 一致 |
| 未知 publish status | 报告第 202-203 行说明增加 `UNKNOWN` 桶与计数 | `ReviewStatisticsService.java:61-66, 278-286, 438-455` | 一致 |
| 错误字段 | 报告第 290-293 行写 `{"error":"..."}` | `ReviewHistoryError.java:7` | 一致 |
| 全量单元测试数 | 报告第 623、753 行写 536 | 当前 surefire XML 合计 541 | 不一致（F-06） |
| 完整 MySQL IT | 报告第 624、754 行写 76 运行、12 跳过 | 当前 failsafe XML 76 tests、0 skipped（12 个验收测试实际执行） | 不一致（F-06） |
| 完整性日志 | 报告第 308 行写只记录报告 ID | Controller 记录异常消息，含 ID 与计数 | 表述略强（F-05） |
| 验收 URL 保护 | 报告第 773 行写“URL 必须精确指向验收库” | 只校验数据库名，不校验 host/port | 表述略强（F-04） |

### 5.2 A 设计与 B1 实现

| 项目 | A 设计 | B1 实现 | 判定 |
|---|---|---|---|
| 默认排序 tie-breaker | `createdAt DESC, taskId DESC`（A 第 620 行） | `createdAt DESC, reportId DESC` | P3 偏差（F-01） |
| `commitSha` 来源 | `r.commit_sha`（A 第 877 行） | `t.commit_sha`（Repository 第 34 行） | P3 偏差（F-02） |
| publish status 分布 | 固定顺序到 `PENDING`，示例无 `UNKNOWN`（A 第 438-442 行） | 增加 `UNKNOWN` 桶与 `unknownPublishStatusReportCount` | 已文档化扩展（F-07） |
| 错误响应示例 | `{"code":"..."}`（A 第 783 行） | `{"error":"..."}`（实际项目契约） | A 文档示例过期（F-09） |

> 结论：B1 实施报告对自身的实现描述基本准确；与 A 的差异主要是 A 的示例性 SQL / 响应契约，以及 B1 有意的数据质量扩展。除测试计数与日志措辞外，没有发现“报告声称但代码未实现”的功能性缺口。

---

## 6. 测试证据与限制

### 6.1 XML 证据

| 测试套件 | tests | failures | errors | skipped | time | 证据文件 |
|---|---:|---:|---:|---:|---:|---|
| `ReviewStatisticsServiceTest` | 19 | 0 | 0 | 0 | 0.430s | `target/surefire-reports/TEST-cn.codesentinel.statistics.ReviewStatisticsServiceTest.xml` |
| `DashboardStatisticsControllerTest` | 15 | 0 | 0 | 0 | 0.681s | `target/surefire-reports/TEST-cn.codesentinel.controller.DashboardStatisticsControllerTest.xml` |
| `ReviewStatisticsMySqlIT` | 9 | 0 | 0 | 0 | 59.738s | `target/failsafe-reports/TEST-cn.codesentinel.statistics.ReviewStatisticsMySqlIT.xml` |
| `ReviewStatisticsAcceptanceDbIT` | 12 | 0 | 0 | 0 | 10.329s | `target/failsafe-reports/TEST-cn.codesentinel.statistics.ReviewStatisticsAcceptanceDbIT.xml` |
| `CodeSentinelApplicationTests` | 1 | 0 | 0 | 0 | 11.665s | `target/surefire-reports/TEST-cn.codesentinel.CodeSentinelApplicationTests.xml` |
| **Surefire 合计** | **541** | **0** | **0** | **0** | — | 47 个 `TEST-*.xml` |
| **Failsafe 合计** | **76** | **0** | **0** | **0** | — | 10 个 `TEST-*.xml`，含 12 个验收测试 |

### 6.2 产物新鲜度

- 主要 B1 源码修改时间：`ReviewStatisticsService.java` 21:24:37、`ReviewStatisticsRepository.java` 21:22:36、`DashboardStatisticsController.java` 21:26:03。
- 主要 B1 测试源码修改时间：`ReviewStatisticsServiceTest.java` 21:28:17、`DashboardStatisticsControllerTest.java` 21:29:21、`ReviewStatisticsAcceptanceDbIT.java` 21:46:25、`ReviewStatisticsMySqlIT.java` 21:55:22。
- 对应测试产物时间：surefire 21:55:53–21:57:07；acceptance IT 21:47:28；MySqlIT 21:57:07。产物均晚于对应源码修改时间，可作为当前代码的测试证据。

### 6.3 测试可信度评估

**强项：**

1. 服务层单元测试覆盖了统计口径的关键分支：默认范围、单边范围、366 天上限、DAY/WEEK 桶、偶数中位数、零分母、未知枚举、失败关闭、过滤参数传递、分页排序。
2. Controller 测试覆盖了参数绑定、默认值、错误码、loopback、IPv6 loopback、编码路径/矩阵参数、Forwarded Header、内部 Token 不回显、500 不泄漏。
3. MySQL IT 使用真实 MySQL 8.0.46，覆盖实际 SQL、过滤边界、空库/空范围、未知枚举、孤儿报告、注入文本、并发读，能发现纯 mock 测试无法发现的 SQL 问题。
4. 验收 IT 覆盖 `codesentinel_accept_1123b` 的 6 份报告、50 条 Finding、26 条评论、7 个任务，验证了报告 2003 的 Finding 排除、2005 的 Comment 排除、2006 的未知枚举、1008 的无报告任务、2004 的损坏 `references_json` 不影响统计。
5. `CodeSentinelApplicationTests` 的 `@MockBean` 改动是必要的上下文兼容处理，且未改变既有测试语义。

**限制：**

1. `ReviewStatisticsServiceTest` 使用 mock Repository，不能证明 SQL 在真实 MySQL 上的行为；该部分由 MySQL IT 和验收 IT 补足。
2. `DashboardStatisticsControllerTest` 使用 mock Service，验证的是 Web 层契约，不是端到端数据正确性。
3. MySQL IT 使用 Hibernate `create-drop`，与生产 DDL 的索引、约束、列类型不完全相同；`publish_status` 通过临时 `ALTER` 对齐，其他列仍可能存在差异。
4. 验收 IT 默认禁用；本次 XML 显示它实际执行并通过，但普通 CI 可能跳过，不能把“本地通过”误认为“每次 CI 都会验证”。
5. 并发测试使用静态 fixture，主要验证读者之间的一致性，不验证并发写入下的隔离行为。
6. 本次审计未重新运行 Maven；测试计数和结果来自现有产物。报告中的 536 / “12 跳过”与当前产物不一致，已在 F-06 记录。

---

## 7. Git 工作区边界检查

### 7.1 当前状态

```text
branch: phase11/dashboard
HEAD:   27e3a41161cfa86ee2956ba0b3626a2bcc71eec7
staged: none
```

### 7.2 B1 新增文件

```text
backend/spring-service/src/main/java/cn/codesentinel/controller/DashboardStatisticsController.java
backend/spring-service/src/main/java/cn/codesentinel/statistics/  (14 个类)
backend/spring-service/src/test/java/cn/codesentinel/controller/DashboardStatisticsControllerTest.java
backend/spring-service/src/test/java/cn/codesentinel/statistics/ReviewStatisticsServiceTest.java
backend/spring-service/src/test/java/cn/codesentinel/statistics/ReviewStatisticsMySqlIT.java
backend/spring-service/src/test/java/cn/codesentinel/statistics/ReviewStatisticsAcceptanceDbIT.java
docs/reports/Phase11_2_4_B1_Implementation_Report.md
```

### 7.3 B1 修改的既有 tracked 文件

```text
backend/spring-service/src/test/java/cn/codesentinel/CodeSentinelApplicationTests.java
```

改动内容仅为：

```java
import cn.codesentinel.statistics.ReviewStatisticsRepository;
...
@MockBean
private ReviewStatisticsRepository reviewStatisticsRepository;
```

### 7.4 未被 B1 修改的既有工作区内容

以下修改/未跟踪文件在 B1 之前已存在，属于 Phase 10/11 既有工作，B1 未覆盖、未删除、未回滚：

```text
.gitignore
backend/spring-service/src/main/java/cn/codesentinel/review/ReviewHistoryQueryService.java
backend/spring-service/src/main/java/cn/codesentinel/task/ReviewReportRepository.java
backend/spring-service/src/main/resources/application.yml
docs/DEVELOPMENT_STATUS.md
frontend/.gitkeep (deleted)
frontend/ 下的 Phase 11 Dashboard 前端文件
backend/spring-service/src/main/java/cn/codesentinel/controller/DashboardReviewController.java
backend/spring-service/src/main/java/cn/codesentinel/controller/DashboardReviewDetailController.java
backend/spring-service/src/main/java/cn/codesentinel/security/DashboardLocalAccessFilter.java
backend/spring-service/src/main/java/cn/codesentinel/review/ReviewHistoryFilter.java
... 等既有 Phase 11.x 文件
```

### 7.5 边界结论

- 未执行 `git add`、`git commit`、`git push`、`git merge`、`git rebase`、`git reset`、`git clean`、`git checkout`。
- 未修改 `docs/DEVELOPMENT_STATUS.md`。
- 未修改 DDL、`pom.xml`、`application.yml`。
- 未修改任何 B2 前端文件。
- 本审计报告是本次唯一新增文件。

---

## 8. 最终判定

### 8.1 判定

**PASS WITH WARNINGS**

### 8.2 判定理由

1. **核心统计口径通过**：报告为根、报告级全量、Finding/Comment 独立一致性闸门、未知枚举保留、零分母 null、趋势与汇总口径均与 A 的核心设计一致。
2. **SQL 与数据完整性通过**：只读 Repository、命名参数、同一过滤块、真实行数校验、失败关闭、只读事务均正确。
3. **时间语义通过**：使用 `review_report.created_at`、应用本地时区、左闭右闭、30 天默认、366 天上限、DAY/WEEK 桶均正确。
4. **安全与异常通过**：`/api/dashboard/**` loopback 边界、Forwarded Header 不信任、Token 不读取、错误体不泄漏、SQL 注入防护均正确。
5. **测试通过**：B1 的 19 + 15 + 9 + 12 个测试全部通过；全量 XML 541 / 76 均 0 失败、0 错误、0 跳过。
6. **Git 边界通过**：B1 只修改 `CodeSentinelApplicationTests.java`，既有用户改动未被覆盖，未执行 Git 写操作。

### 8.3 警告与后续建议

- 9 项 P3 均不阻断 B1，但应在 B2 开始前或 B2 初期统一处理：
  - F-01 / F-02：统一或明确 A 与 B1 的排序 tie-breaker、`commitSha` 来源。
  - F-03 / F-08：若未来允许外部数据导入，补 NULL 与大小写规范化。
  - F-04：验收 IT 增加 host/port 保护。
  - F-05 / F-06 / F-09：统一文档措辞、测试计数和错误字段示例。
  - F-07：把 `UNKNOWN` publish 桶与 `unknownPublishStatusReportCount` 写入 B2 前端契约。
- 本次审计不修复任何问题。任何修复都必须另开任务，重新运行相关测试，并更新对应报告。
- **不进入 B2，不实现前端页面，不修改 `docs/DEVELOPMENT_STATUS.md`。**

---

## 9. 审计动作记录

本次审计执行的全部操作均为只读：

```text
读取 A 报告、B1 实施报告、全部 B1 源码与测试
读取 ReviewHistoryFilter / ReviewHistoryQueryService / DashboardLocalAccessFilter
读取 ReviewReport / ReviewFinding / ReviewComment / ReviewTask
读取 review_history.sql / application.yml / pom.xml
解析 target/surefire-reports 与 target/failsafe-reports XML
git status / git diff / git diff --cached / git rev-parse / git log
```

未执行：

```text
mvn test / mvn verify / mvn clean
任何数据库连接或 SQL
任何 Git 写操作
任何文件修改（除本报告）
```

---

*报告结束。*
