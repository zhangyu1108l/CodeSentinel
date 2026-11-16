# Phase 11.2.4-B1 实施报告 — Dashboard 只读统计后端

> 执行日期：2026-11-13  
> 分支：`phase11/dashboard`  
> HEAD：`27e3a41161cfa86ee2956ba0b3626a2bcc71eec7`  
> 阶段：Phase 11.2.4-B1（后端只读统计 API）  
> 范围：只实现 `GET /api/dashboard/statistics/overview` 与 `GET /api/dashboard/statistics/reviews`，不进入 B2 前端页面。  
> 结论：**B1 已完成。两个接口可用，统计口径以 `review_report` 为根、以实际 `review_finding` / `review_comment` 行数做一致性闸门；验收库 `codesentinel_accept_1123b` 的数字全部对齐，后端测试全部通过。未修改生产数据库、未修改既有 DDL、未新增依赖、未执行任何 Git 写操作。**

---

## 1. 本阶段完成内容

### 1.1 已实现

- `GET /api/dashboard/statistics/overview`
  - 默认最近 30 个自然日（含今天），最大 366 个自然日；
  - 报告级汇总、Finding 级汇总、分布、趋势、数据质量；
  - 支持 owner / repo / prNumber / taskStatus / publishStatus / aiStatus / createdFrom / createdTo / granularity 参数。
- `GET /api/dashboard/statistics/reviews`
  - 与 `/overview` 完全相同的筛选语义；
  - 报告元数据、声明/实际 Finding 数、声明/实际评论数、一致性标记；
  - 分页、白名单排序、稳定 tie-breaker。
- 新增 `ReviewStatisticsRepository`、`ReviewStatisticsService`、DTO records、异常、`DashboardStatisticsController`。
- 新增单元测试、Controller 测试、Testcontainers MySQL IT、只读验收库 IT。
- 在 `CodeSentinelApplicationTests` 中补充一个 `@MockBean`，使既有“排除 JPA 自动配置”的上下文测试仍可启动。

### 1.2 明确未做

- 未实现 Vue Insights 页面、首页卡片、筛选栏、趋势图、CSV 导出。
- 未修改 `frontend/`。
- 未修改 `review_report` / `review_finding` / `review_comment` / `review_task` 的 DDL。
- 未新增索引、数据库迁移、依赖或缓存。
- 未读取 `review_result_delivery`，未解析 `review_finding.references_json`。
- 未调用 GitHub API、Python AI Service 或 LLM。
- 未修改 Phase 10 的既有 API，未修改 `docs/DEVELOPMENT_STATUS.md`，未修改 Phase 11.2.4-A 调查报告。
- 未做数据回填（backfill）。
- 未进入 Phase 12。

---

## 2. 修改文件

### 2.1 新增文件

| 文件 | 说明 |
|---|---|
| `backend/spring-service/src/main/java/cn/codesentinel/controller/DashboardStatisticsController.java` | 两个统计接口、参数绑定、错误映射 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsRepository.java` | 只读原生 SQL、报告投影、Finding 聚合投影 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsService.java` | 范围解析、聚合、一致性、趋势、排序、分页 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/StatisticsGranularity.java` | `DAY` / `WEEK` 粒度 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsOverviewResponse.java` | `/overview` 响应 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsRange.java` | 生效范围 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsSummary.java` | 汇总与分布 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsTrend.java` | 趋势容器 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsTrendPoint.java` | 趋势桶 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsDataQuality.java` | 一致性排除与未知枚举披露 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsReviewItem.java` | `/reviews` 单行 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsCount.java` | 有序分布项 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/InvalidStatisticsGranularityException.java` | 非法粒度 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/InvalidStatisticsRangeException.java` | 范围超过 366 天 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/InvalidStatisticsSortException.java` | 非法排序 |
| `backend/spring-service/src/test/java/cn/codesentinel/statistics/ReviewStatisticsServiceTest.java` | 19 个服务层单元测试 |
| `backend/spring-service/src/test/java/cn/codesentinel/controller/DashboardStatisticsControllerTest.java` | 15 个 Controller / 安全边界测试 |
| `backend/spring-service/src/test/java/cn/codesentinel/statistics/ReviewStatisticsMySqlIT.java` | 9 个 Testcontainers MySQL IT |
| `backend/spring-service/src/test/java/cn/codesentinel/statistics/ReviewStatisticsAcceptanceDbIT.java` | 12 个只读验收库 IT |

### 2.2 修改的既有文件

| 文件 | 修改内容 |
|---|---|
| `backend/spring-service/src/test/java/cn/codesentinel/CodeSentinelApplicationTests.java` | 增加 `@MockBean ReviewStatisticsRepository`。该测试显式排除 `JpaRepositoriesAutoConfiguration`，原有做法是逐个 mock repository；新增统计服务后必须同步 mock，否则上下文测试启动失败。 |

### 2.3 未修改

- `backend/spring-service/pom.xml`
- `backend/spring-service/src/main/resources/application.yml`
- `backend/spring-service/src/main/resources/db/review_history.sql`
- `backend/spring-service/src/main/java/cn/codesentinel/review/ReviewHistoryFilter.java`
- `backend/spring-service/src/main/java/cn/codesentinel/security/DashboardLocalAccessFilter.java`
- 任何既有 Controller / Service / Repository / Entity
- `frontend/`
- `docs/DEVELOPMENT_STATUS.md`
- `docs/reports/Phase11_2_4_A_Investigation_Report.md`

---

## 3. API 契约

### 3.1 `GET /api/dashboard/statistics/overview`

#### 查询参数

| 参数 | 类型 | 必填 | 默认 | 语义 |
|---|---|---:|---|---|
| `owner` | string | 否 | 无 | `review_task.owner` 精确匹配，trim 后空值视为未提供 |
| `repo` | string | 否 | 无 | `review_task.repo` 精确匹配，trim 后空值视为未提供 |
| `prNumber` | integer | 否 | 无 | `review_task.pr_number` 精确匹配，必须 `> 0` |
| `taskStatus` | enum | 否 | 无 | `PENDING` / `RUNNING` / `COMPLETED` / `FAILED` |
| `publishStatus` | enum | 否 | 无 | `PENDING` / `PUBLISHED` / `PARTIAL` / `FAILED` |
| `aiStatus` | string | 否 | 无 | `COMPLETED` / `DEGRADED`（沿用 `ReviewHistoryFilter` 白名单） |
| `createdFrom` | ISO date-time | 否 | 今天 - 29 天 00:00:00 | 包含；应用本地 wall-clock |
| `createdTo` | ISO date-time | 否 | 今天 23:59:59.999999 | 包含；应用本地 wall-clock |
| `granularity` | enum | 否 | `DAY` | `DAY` / `WEEK`，大小写不敏感 |

范围补全规则：

```text
from、to 都为空   → [今天 - 29 天 00:00:00, 今天 23:59:59.999999]
仅 from 为空      → [to 所在日期 - 29 天 00:00:00, to]
仅 to 为空        → [from, 今天 23:59:59.999999]
from > to         → 400 invalid_filter
自然日跨度 > 366  → 400 invalid_range
```

#### 响应

```json
{
  "range": {
    "createdFrom": "2026-10-15T00:00:00",
    "createdTo": "2026-11-13T23:59:59.999999",
    "zoneId": "Asia/Shanghai",
    "granularity": "DAY"
  },
  "generatedAt": "2026-11-13T20:00:00",
  "summary": {
    "reviewCount": 6,
    "findingStatsReviewCount": 5,
    "findingCount": 48,
    "averageFindingsPerReview": 9.6,
    "medianFindingsPerReview": 1.0,
    "maxFindingsInReview": 45,
    "reviewsWithFindings": 4,
    "reviewsWithFindingsRatio": 0.8,
    "highSeverityFindingCount": 19,
    "highSeverityRatio": 0.3958333333333333,
    "commentStatsReviewCount": 5,
    "publishedInlineCommentCount": 25,
    "reviewsWithInlineComments": 1,
    "reviewsWithInlineCommentsRatio": 0.2,
    "summaryCommentIdPresentCount": 3,
    "categoryCounts": [
      { "key": "BUG", "count": 12 },
      { "key": "SECURITY", "count": 12 },
      { "key": "PERFORMANCE", "count": 11 },
      { "key": "QUALITY", "count": 12 },
      { "key": "UNKNOWN", "count": 1 }
    ],
    "severityCounts": [
      { "key": "CRITICAL", "count": 10 },
      { "key": "HIGH", "count": 9 },
      { "key": "MEDIUM", "count": 9 },
      { "key": "LOW", "count": 10 },
      { "key": "INFO", "count": 9 },
      { "key": "UNKNOWN", "count": 1 }
    ],
    "publishStatusCounts": [
      { "key": "PUBLISHED", "count": 3 },
      { "key": "PARTIAL", "count": 2 },
      { "key": "FAILED", "count": 1 },
      { "key": "PENDING", "count": 0 },
      { "key": "UNKNOWN", "count": 0 }
    ],
    "aiStatusCounts": [
      { "key": "COMPLETED", "count": 4 },
      { "key": "DEGRADED", "count": 1 },
      { "key": "UNKNOWN", "count": 1 }
    ]
  },
  "trend": {
    "granularity": "DAY",
    "hasData": true,
    "points": [
      {
        "bucketStart": "2026-10-15",
        "bucketEnd": "2026-10-15",
        "reviewCount": 0,
        "findingCount": 0,
        "highSeverityFindingCount": 0
      }
    ]
  },
  "dataQuality": {
    "totalReportCount": 6,
    "findingsConsistentReportCount": 5,
    "commentsConsistentReportCount": 5,
    "reportsExcludedFromFindingStats": 1,
    "reportsExcludedFromCommentStats": 1,
    "unknownCategoryFindingCount": 1,
    "unknownSeverityFindingCount": 1,
    "unknownAiStatusReportCount": 1,
    "unknownPublishStatusReportCount": 0
  }
}
```

> 示例中的数字来自 `codesentinel_accept_1123b`，用于说明响应结构；实际接口实时计算。`trend.points` 示例只展示第一个零填充桶，实际响应包含完整 30 个日桶或 5 个周桶。

与 Phase 11.2.4-A 计划相比的两处**向后兼容新增**：

1. `publishStatusCounts` 增加固定的 `UNKNOWN` 桶，避免存储层出现未知 `publish_status` 时计数丢失。
2. `dataQuality` 增加 `unknownPublishStatusReportCount`，与 `unknownAiStatusReportCount` 对称。

A 报告示例中的 `dataQuality` 只有 8 个字段；当前实现为 9 个字段。

### 3.2 `GET /api/dashboard/statistics/reviews`

#### 查询参数

| 参数 | 类型 | 必填 | 默认 | 语义 |
|---|---|---:|---|---|
| `page` | integer | 否 | 1 | `>= 1` |
| `size` | integer | 否 | 20 | `1..100` |
| `sort` | string | 否 | `createdAt` | `createdAt` / `actualFindingCount` / `highSeverityFindingCount` / `actualCommentCount` |
| `direction` | string | 否 | `desc` | `asc` / `desc` |
| `owner` | string | 否 | 无 | 同 `/overview` |
| `repo` | string | 否 | 无 | 同 `/overview` |
| `prNumber` | integer | 否 | 无 | 同 `/overview` |
| `taskStatus` | enum | 否 | 无 | 同 `/overview` |
| `publishStatus` | enum | 否 | 无 | 同 `/overview` |
| `aiStatus` | string | 否 | 无 | 同 `/overview` |
| `createdFrom` | ISO date-time | 否 | 同 `/overview` | 包含 |
| `createdTo` | ISO date-time | 否 | 同 `/overview` | 包含 |

排序语义：

- `createdAt`：按报告 `created_at`；
- `actualFindingCount`：按实际 `review_finding` 行数；
- `highSeverityFindingCount`：按实际 `CRITICAL + HIGH` 行数；
- `actualCommentCount`：按实际 `review_comment` 行数；
- 所有排序都追加 `report_id DESC` 作为稳定 tie-breaker；
- 默认等价于 `createdAt DESC, report_id DESC`，与现有 Review History 的 `createdAt DESC, id DESC` 保持一致。

#### 响应

```json
{
  "items": [
    {
      "taskId": 1001,
      "owner": "acme",
      "repo": "sentinel-demo",
      "prNumber": 42,
      "commitSha": "1111111111111111111111111111111111111111",
      "createdAt": "2026-11-01T10:00:00",
      "taskStatus": "COMPLETED",
      "aiStatus": "DEGRADED",
      "publishStatus": "PARTIAL",
      "declaredFindingCount": 45,
      "actualFindingCount": 45,
      "findingsConsistent": true,
      "declaredCommentCount": 25,
      "actualCommentCount": 25,
      "commentsConsistent": true,
      "criticalCount": 9,
      "highCount": 9,
      "highSeverityFindingCount": 18,
      "mediumCount": 9,
      "lowCount": 9,
      "infoCount": 9,
      "unknownSeverityCount": 0,
      "bugCount": 12,
      "securityCount": 11,
      "performanceCount": 11,
      "qualityCount": 11,
      "unknownCategoryCount": 0
    }
  ],
  "page": 1,
  "size": 20,
  "totalItems": 6,
  "totalPages": 1,
  "hasNext": false
}
```

说明：

1. 不返回 `reportId`；对外使用 `taskId` 作为稳定业务标识。
2. `declaredFindingCount` / `actualFindingCount` 同时返回，便于前端显示“声明 / 实际”徽标。
3. `findingsConsistent` / `commentsConsistent` 由声明数与实际行数严格相等得出。
4. 即使 `findingsConsistent=false`，该行的实际 category / severity 分布仍然返回，便于定位数据问题；但这些行不进入 `/overview` 的 Finding 汇总。
5. 不返回 Finding 的 `title` / `description` / `file_path` / `rule_id` / `confidence`；统计页不需要这些字段。
6. `commitSha` 返回完整 40 位值。
7. 空结果时 `totalPages=0`、`hasNext=false`、`items=[]`。

### 3.3 错误契约

项目实际存在的 `ReviewHistoryError` 使用字段 `error`，不是 Phase 11.2.4-A 示例中的 `code`。B1 复用实际契约：

```json
{ "error": "invalid_filter" }
```

| HTTP | `error` | 触发条件 |
|---:|---|---|
| 400 | `invalid_filter` | owner/repo 超长、`prNumber <= 0`、非法枚举绑定、`createdFrom > createdTo`、非法日期格式 |
| 400 | `invalid_pagination` | `page < 1`、`size < 1`、`size > 100`、非数字 page/size |
| 400 | `invalid_granularity` | `granularity` 不是 `DAY` / `WEEK` |
| 400 | `invalid_sort` | `sort` 不在白名单，或 `direction` 不是 `asc` / `desc` |
| 400 | `invalid_range` | 生效范围超过 366 个自然日 |
| 500 | `internal_error` | 报告缺少 `review_task`、Finding 聚合不一致、数据库异常、其他未预期异常 |

安全约束：

- 500 响应只包含 `{"error":"internal_error"}`，不包含 SQL、表名、列名、绑定值、数据库地址或凭据。
- 数据完整性异常在服务端日志中只记录可定位的报告 ID；未记录 SQL 或敏感数据。
- 非 loopback 请求由既有 `DashboardLocalAccessFilter` 直接返回 403，响应体为空，不进入 Controller。

---

## 4. 统计口径

### 4.1 根表与人群

```text
review_report（根）
  ├─ LEFT JOIN review_task（owner / repo / pr_number / task_status）
  ├─ 子查询 review_finding（实际 Finding 行数）
  └─ 子查询 review_comment（实际评论行数）
```

- 报告级指标（`reviewCount`、发布状态分布、AI 状态分布、`summaryCommentIdPresentCount`）包含范围内**所有**报告。
- Finding 指标只包含 `actualFindingCount == finding_count` 的报告。
- Comment 指标只包含 `actualCommentCount == published_comment_count` 的报告。
- 没有 `review_report` 的 `review_task` 不进入任何统计。
- 有 `review_report` 但没有 `review_task` 的记录不会被静默丢弃；服务抛出 `ReviewHistoryDataIntegrityException`，接口返回 500。

### 4.2 Finding 一致性

```text
actualFindingCount
  = SELECT COUNT(*) FROM review_finding WHERE report_id = report.id
```

只有实际行数等于 `review_report.finding_count` 时，该报告的 Finding 才进入：

- `findingStatsReviewCount`
- `findingCount`
- `averageFindingsPerReview`
- `medianFindingsPerReview`
- `maxFindingsInReview`
- `reviewsWithFindings`
- `reviewsWithFindingsRatio`
- `highSeverityFindingCount`
- `highSeverityRatio`
- `categoryCounts`
- `severityCounts`
- `trend[].findingCount`
- `trend[].highSeverityFindingCount`

被排除的报告仍计入：

- `reviewCount`
- `publishStatusCounts`
- `aiStatusCounts`
- `summaryCommentIdPresentCount`
- `trend[].reviewCount`

### 4.3 Comment 一致性

```text
actualCommentCount
  = SELECT COUNT(*) FROM review_comment WHERE report_id = report.id
```

只有实际行数等于 `published_comment_count` 时，该报告的评论才进入：

- `commentStatsReviewCount`
- `publishedInlineCommentCount`
- `reviewsWithInlineComments`
- `reviewsWithInlineCommentsRatio`

`summary_comment_id` 不参与 `publishedInlineCommentCount`；`summaryCommentIdPresentCount` 单独统计所有报告中 `summary_comment_id IS NOT NULL` 的数量。

### 4.4 未知枚举

| 来源 | 处理 |
|---|---|
| `category` 不属于 `BUG` / `SECURITY` / `PERFORMANCE` / `QUALITY` | 计入 `UNKNOWN` category 桶 |
| `severity` 不属于 `CRITICAL` / `HIGH` / `MEDIUM` / `LOW` / `INFO` | 计入 `UNKNOWN` severity 桶 |
| `ai_status` 不属于 `COMPLETED` / `DEGRADED` | 在 `aiStatusCounts` 计入 `UNKNOWN`；原始值保留在 `/reviews` item 的 `aiStatus` |
| `publish_status` 不属于 `PENDING` / `PUBLISHED` / `PARTIAL` / `FAILED` | 在 `publishStatusCounts` 计入 `UNKNOWN`；原始值保留在 `/reviews` item 的 `publishStatus` |

- 未知值不会触发 `IllegalArgumentException` 或 500。
- `ReviewHistoryFilter.aiStatus` 仍只接受 `COMPLETED` / `DEGRADED`；这是既有筛选契约，不在 B1 修改。因此未知 `ai_status` 只能作为**已存储数据**出现在结果中，不能作为筛选值。
- `publishStatus` 的筛选参数仍为 Java 枚举，无法表达未知存储值；未知值同样只在结果中保留。

### 4.5 比率与零分母

| 指标 | 分母 | 零分母 |
|---|---|---|
| `averageFindingsPerReview` | `findingStatsReviewCount` | `null` |
| `reviewsWithFindingsRatio` | `findingStatsReviewCount` | `null` |
| `highSeverityRatio` | `findingCount` | `null` |
| `reviewsWithInlineCommentsRatio` | `commentStatsReviewCount` | `null` |
| `medianFindingsPerReview` | 无（空列表） | `null` |
| `maxFindingsInReview` | 无（空列表） | `null` |

所有可空值返回 JSON `null`，不会出现 `NaN` 或 `Infinity`。

### 4.6 中位数与最大值

- 中位数只使用 Finding 一致报告的实际 Finding 数，包括 0 Finding 的报告。
- 奇数个报告取中间值；偶数个报告取中间两数平均。
- `maxFindingsInReview` 返回 `Long`；无 Finding 一致报告时为 `null`。
- 验收数据 Finding 数列表为 `[45, 0, 1, 1, 1]`，排序后 `[0, 1, 1, 1, 45]`，中位数 `1.0`，最大值 `45`。

### 4.7 趋势

- `DAY`：每个应用本地自然日一个桶，`bucketStart == bucketEnd`。
- `WEEK`：ISO-8601 周，周一到周日；第一个/最后一个桶可以超出请求范围。
- 有报告时，零填充整个范围；无报告时 `hasData=false`、`points=[]`。
- `reviewCount` 包含所有报告；`findingCount` / `highSeverityFindingCount` 只包含 Finding 一致报告。
- 趋势桶使用 Java 时间计算，不使用 SQL `DATE()` / `WEEK()` / `NOW()`。

### 4.8 时间语义

- 所有时间都是**应用本地 wall-clock**，与既有 `DATETIME(6)` 存储约定一致。
- `review_report.created_at` 与 `review_task.created_at` 都按本地时间存储。
- `range.zoneId` 返回应用 `ZoneId`（当前 JVM 为 `Asia/Shanghai`）。
- `generatedAt` 使用 `LocalDateTime.now(clock)`，不带 offset。
- 不使用 SQL `NOW()` / `CURDATE()` / `CURRENT_TIMESTAMP`。
- 不把 `LocalDateTime` 当作 UTC。
- 边界是包含的：`created_at >= createdFrom AND created_at <= createdTo`。

---

## 5. SQL 设计

### 5.1 Repository

`ReviewStatisticsRepository` 继承 `Repository<ReviewReport, Long>`，不继承 `JpaRepository`，从接口层面避免暴露写方法。

两个原生查询共享完全相同的过滤块：

```sql
WHERE (:owner IS NULL OR t.owner = :owner)
  AND (:repo IS NULL OR t.repo = :repo)
  AND (:prNumber IS NULL OR t.pr_number = :prNumber)
  AND (:taskStatus IS NULL OR t.status = :taskStatus)
  AND (:publishStatus IS NULL OR r.publish_status = :publishStatus)
  AND (:aiStatus IS NULL OR r.ai_status = :aiStatus)
  AND r.created_at >= :createdFrom
  AND r.created_at <= :createdTo
```

所有用户输入都是命名参数，没有字符串拼接。MySQL 的 `:param` 会被绑定为位置参数，测试已验证 NULL 参数与多参数过滤行为。

### 5.2 报告查询

```sql
SELECT
    r.id AS reportId,
    r.task_id AS taskId,
    t.owner AS owner,
    t.repo AS repo,
    t.pr_number AS prNumber,
    t.commit_sha AS commitSha,
    t.status AS taskStatus,
    r.ai_status AS aiStatus,
    r.publish_status AS publishStatus,
    r.created_at AS createdAt,
    r.finding_count AS declaredFindingCount,
    (SELECT COUNT(*) FROM review_finding f
      WHERE f.report_id = r.id) AS actualFindingCount,
    r.published_comment_count AS declaredCommentCount,
    (SELECT COUNT(*) FROM review_comment c
      WHERE c.report_id = r.id) AS actualCommentCount,
    CASE WHEN r.summary_comment_id IS NULL THEN 0 ELSE 1 END
        AS summaryCommentIdPresent
FROM review_report r
LEFT JOIN review_task t ON t.id = r.task_id
WHERE ...
```

- `LEFT JOIN` 用于发现孤儿报告，而不是静默丢弃。
- 相关子查询使用 `review_finding(report_id, ordinal)` 与 `review_comment(report_id, finding_ordinal)` 的联合索引前缀，能够走覆盖索引。
- 不读取 `review_result_delivery`。
- 不读取 `review_finding.references_json`。

### 5.3 Finding 聚合查询

```sql
SELECT
    f.report_id AS reportId,
    COUNT(*) AS actualFindingCount,
    COUNT(CASE WHEN f.severity = 'CRITICAL' THEN 1 END) AS criticalCount,
    COUNT(CASE WHEN f.severity = 'HIGH' THEN 1 END) AS highCount,
    COUNT(CASE WHEN f.severity = 'MEDIUM' THEN 1 END) AS mediumCount,
    COUNT(CASE WHEN f.severity = 'LOW' THEN 1 END) AS lowCount,
    COUNT(CASE WHEN f.severity = 'INFO' THEN 1 END) AS infoCount,
    COUNT(CASE WHEN f.severity NOT IN
        ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO') THEN 1 END)
        AS unknownSeverityCount,
    COUNT(CASE WHEN f.category = 'BUG' THEN 1 END) AS bugCount,
    COUNT(CASE WHEN f.category = 'SECURITY' THEN 1 END) AS securityCount,
    COUNT(CASE WHEN f.category = 'PERFORMANCE' THEN 1 END)
        AS performanceCount,
    COUNT(CASE WHEN f.category = 'QUALITY' THEN 1 END) AS qualityCount,
    COUNT(CASE WHEN f.category NOT IN
        ('BUG', 'SECURITY', 'PERFORMANCE', 'QUALITY') THEN 1 END)
        AS unknownCategoryCount
FROM review_finding f
JOIN review_report r ON r.id = f.report_id
LEFT JOIN review_task t ON t.id = r.task_id
WHERE ...
GROUP BY f.report_id
```

- 一个报告一行；没有 Finding 的报告不会出现在结果中，Java 侧按 0 处理。
- 不读取任何 Finding 文本、文件路径或 JSON。
- 投影接口 `FindingAggregateRow` 与 `ReportStatisticsRow` 把原始 SQL 结果隔离在 Repository 层。

### 5.4 事务与一致性

`ReviewStatisticsService.overview` 与 `reviews` 都使用：

```java
@Transactional(readOnly = true, isolation = Isolation.REPEATABLE_READ)
```

两次查询在同一个只读事务中执行，MySQL 在 REPEATABLE READ 下提供一致性快照。服务还会校验：

- 每个报告必须能关联到任务；
- Finding 聚合行不能重复；
- Finding 聚合不能引用不存在的报告；
- 报告子查询的实际 Finding 数必须等于聚合查询的总数。

任一校验失败都返回 500 `internal_error`，不返回部分统计。

### 5.5 EXPLAIN 基线（验收库）

报告查询：

| 表 | type | key | rows | Extra |
|---|---|---|---:|---|
| `review_report r` | `ALL` | `NULL` | 6 | `Using where` |
| `review_task t` | `eq_ref` | `PRIMARY` | 1 | — |
| `review_finding f`（子查询） | `ref` | `uk_review_finding_report_ordinal` | 10 | `Using index` |
| `review_comment c`（子查询） | `ref` | `uk_review_comment_report_finding` | 13 | `Using index` |

Finding 聚合查询：

| 表 | type | key | rows | Extra |
|---|---|---|---:|---|
| `review_report r` | `ALL` | `NULL` | 6 | `Using where; Using temporary` |
| `review_task t` | `eq_ref` | `PRIMARY` | 1 | — |
| `review_finding f` | `ref` | `uk_review_finding_report_ordinal` | 10 | — |

`review_report` 当前索引：

```text
PRIMARY(id)
UNIQUE uk_review_report_task(task_id)
```

没有 `created_at` 索引。B1 按 A 报告约定**不新增索引**；当前验收库 6 行，全表扫描成本可忽略。后续当报告数 > 10,000 或 P95 > 200 ms 时，再评估 `review_report(created_at, id)`。

---

## 6. 一致性与异常数据处理

### 6.1 `dataQuality` 字段

| 字段 | 含义 |
|---|---|
| `totalReportCount` | 范围内报告总数 |
| `findingsConsistentReportCount` | 实际 Finding 行数 = 声明数的报告数 |
| `commentsConsistentReportCount` | 实际评论行数 = 声明数的报告数 |
| `reportsExcludedFromFindingStats` | `totalReportCount - findingsConsistentReportCount` |
| `reportsExcludedFromCommentStats` | `totalReportCount - commentsConsistentReportCount` |
| `unknownCategoryFindingCount` | Finding 一致报告中未知 category 的行数 |
| `unknownSeverityFindingCount` | Finding 一致报告中未知 severity 的行数 |
| `unknownAiStatusReportCount` | `ai_status` 不在 `COMPLETED` / `DEGRADED` 的报告数 |
| `unknownPublishStatusReportCount` | `publish_status` 不在四个已知状态的报告数 |

### 6.2 验收数据逐项核对

验收库：`codesentinel_accept_1123b`，6 份报告、50 条 Finding、26 条评论、7 个任务。

| 报告 | 任务 | 场景 | 关键结果 |
|---:|---:|---|---|
| 2001 | 1001 | 正常大报告 | 45/45 Finding、25/25 评论、summary id 存在、18 条 CRITICAL+HIGH |
| 2002 | 1002 | 空报告 | 0/0 Finding、0/0 评论，一致 |
| 2003 | 1003 | Finding 声明 3 / 实际 2 | `findingsConsistent=false`；报告仍计入 `reviewCount`；Finding 全部排除；趋势中 `reviewCount=1`、`findingCount=0` |
| 2004 | 1004 | `references_json={bad` | 统计不读取该列；Finding 1/1、评论 0/0，正常计入 |
| 2005 | 1005 | 评论声明 2 / 实际 1 | `commentsConsistent=false`；报告仍计入 `reviewCount`；Finding 1/1 正常计入；评论全部排除 |
| 2006 | 1006 | 未知枚举 | `ai_status=UNKNOWN`、`category=MYSTERY`、`severity=UNKNOWN`；未知 category/severity 各 1，AI UNKNOWN 报告 1 |
| 1008 | — | 有任务无报告 | 不进入统计；按 owner `eta` 查询返回 0 条 |

### 6.3 未知 publish status

验收库没有未知 `publish_status`，因此 MySQL IT 在隔离测试库中额外插入 `publish_status=MYSTERY`：

- `/reviews` item 原样返回 `"MYSTERY"`；
- `publishStatusCounts` 的 `UNKNOWN` 桶 +1；
- `dataQuality.unknownPublishStatusReportCount` +1；
- 不抛异常，不丢计数。

### 6.4 失败关闭

以下情况返回 500，而不是返回不完整数据：

- `review_report.task_id` 找不到 `review_task`；
- Finding 聚合行重复；
- Finding 聚合引用了不存在的报告；
- 报告子查询实际 Finding 数与聚合查询总数不一致。

---

## 7. 测试与验证

### 7.1 测试套件

| 测试 | 数量 | 结果 | 说明 |
|---|---:|---|---|
| `ReviewStatisticsServiceTest` | 19 | 通过 | Mock Repository；范围、粒度、分页、排序、空值、中位数、趋势、未知枚举、一致性、失败关闭、过滤参数传递 |
| `DashboardStatisticsControllerTest` | 15 | 通过 | `@WebMvcTest`；参数绑定、默认值、错误映射、loopback/编码路径/Forwarded Header、Token 不读取、500 不泄漏 |
| `ReviewStatisticsMySqlIT` | 9 | 通过 | Testcontainers `mysql:8.0.46`；验收 fixture、过滤边界、空库/空范围、未知枚举、孤儿报告、SQL 注入文本、并发读一致性 |
| `ReviewStatisticsAcceptanceDbIT` | 12 | 通过 | 只读连接 `codesentinel_accept_1123b`；固定时钟 `2026-11-13T12:00:00Z` / `Asia/Shanghai`；验收数字、6 份报告、2003/2004/2005/2006/1008、趋势、分页排序、时间边界、并发读 |
| 后端完整 `mvn test` | 536 | 通过 | 0 failures、0 errors、0 skipped |
| 完整 MySQL IT（`mysql-it` profile） | 76 | 通过 | 0 failures、0 errors；无验收库凭据时 12 个验收测试按设计跳过 |
| 验收库定向执行 | 12 | 通过 | 0 failures、0 errors、0 skipped |

### 7.2 验收库数字

| 指标 | 期望 | 实际 |
|---|---:|---:|
| 报告总数 | 6 | 6 |
| 原始 Finding 行数 | 50 | 50 |
| 原始评论行数 | 26 | 26 |
| 任务数 | 7 | 7 |
| `reviewCount` | 6 | 6 |
| `findingStatsReviewCount` | 5 | 5 |
| `findingCount` | 48 | 48 |
| `averageFindingsPerReview` | 9.6 | 9.6 |
| `medianFindingsPerReview` | 1.0 | 1.0 |
| `maxFindingsInReview` | 45 | 45 |
| `reviewsWithFindings` | 4 | 4 |
| `reviewsWithFindingsRatio` | 0.8 | 0.8 |
| `highSeverityFindingCount` | 19 | 19 |
| `highSeverityRatio` | 19/48 ≈ 0.3958 | 19/48 |
| `commentStatsReviewCount` | 5 | 5 |
| `publishedInlineCommentCount` | 25 | 25 |
| `reviewsWithInlineComments` | 1 | 1 |
| `reviewsWithInlineCommentsRatio` | 0.2 | 0.2 |
| `summaryCommentIdPresentCount` | 3 | 3 |
| `reportsExcludedFromFindingStats` | 1 | 1 |
| `reportsExcludedFromCommentStats` | 1 | 1 |
| `unknownCategoryFindingCount` | 1 | 1 |
| `unknownSeverityFindingCount` | 1 | 1 |
| `unknownAiStatusReportCount` | 1 | 1 |
| `unknownPublishStatusReportCount` | 0 | 0 |

分布：

```text
BUG 12, SECURITY 12, PERFORMANCE 11, QUALITY 12, UNKNOWN 1   = 48
CRITICAL 10, HIGH 9, MEDIUM 9, LOW 10, INFO 9, UNKNOWN 1      = 48
PUBLISHED 3, PARTIAL 2, FAILED 1, PENDING 0, UNKNOWN 0        = 6
COMPLETED 4, DEGRADED 1, UNKNOWN 1                            = 6
```

验收 SQL（只读）：

```sql
-- 原始行数
SELECT COUNT(*) FROM codesentinel_accept_1123b.review_report;
SELECT COUNT(*) FROM codesentinel_accept_1123b.review_finding;
SELECT COUNT(*) FROM codesentinel_accept_1123b.review_comment;
SELECT COUNT(*) FROM codesentinel_accept_1123b.review_task;

-- 每份报告的声明/实际行数
SELECT r.id, r.task_id, r.finding_count,
       (SELECT COUNT(*) FROM codesentinel_accept_1123b.review_finding f
         WHERE f.report_id = r.id) AS actual_findings,
       r.published_comment_count,
       (SELECT COUNT(*) FROM codesentinel_accept_1123b.review_comment c
         WHERE c.report_id = r.id) AS actual_comments
FROM codesentinel_accept_1123b.review_report r
ORDER BY r.id;

-- 排除 Finding 不一致报告（2003）后的分布
SELECT category, COUNT(*)
FROM codesentinel_accept_1123b.review_finding
WHERE report_id <> 2003
GROUP BY category;

SELECT severity, COUNT(*)
FROM codesentinel_accept_1123b.review_finding
WHERE report_id <> 2003
GROUP BY severity;
```

趋势：

- DAY：30 个桶（2026-10-15 至 2026-11-13），10-27 至 11-01 每天 1 份报告；
- 10-30（报告 2003）`reviewCount=1`、`findingCount=0`；
- 11-01（报告 2001）`reviewCount=1`、`findingCount=45`、`highSeverityFindingCount=18`；
- 全部 Finding 一致报告合计 48 条 Finding、19 条高严重度 Finding；
- WEEK：5 个桶，第一桶从 2026-10-12（周一）开始，最后桶从 2026-11-09 开始；10-26 周包含 6 份报告、48 条 Finding、19 条高严重度 Finding。

### 7.3 时间与时区验证

- 默认范围：`2026-10-15T00:00:00` 至 `2026-11-13T23:59:59.999999`；
- `zoneId` 返回 `Asia/Shanghai`；
- `generatedAt` 固定时钟下为 `2026-11-13T20:00:00`；
- 报告 2001 的 `created_at=2026-11-01 10:00:00`，`createdFrom=createdTo=该时刻` 时命中 1 条；
- `createdFrom = createdAt + 1µs` 时不再命中报告 2001；
- `createdTo = createdAt - 1µs` 时不再命中报告 2001；
- 单日范围 `2026-11-01 00:00:00` 至 `2026-11-01 23:59:59.999999` 命中 1 份报告、45 条 Finding，趋势恰好 1 个日桶；
- 周桶按周一至周日切分，首尾周允许超出请求范围；
- 未使用 SQL 时间函数，未把 `LocalDateTime` 当 UTC。

### 7.4 安全测试

| 场景 | 结果 |
|---|---|
| 非 loopback IPv4 请求 `/api/dashboard/statistics/overview` | 403，空响应体，Service 不被调用 |
| 编码路径 `/api/%64ashboard/...` | 403 |
| Matrix 参数 `/api/dashboard;x/...` | 403 |
| 双重编码 `%2564ashboard` | 403 |
| `X-Forwarded-For: 127.0.0.1` + 非 loopback peer | 403，不信任转发头 |
| IPv6 loopback `0:0:0:0:0:0:0:1` | 200 |
| 不携带 `X-Internal-Token` | 200；统计接口不要求内部 Token |
| 携带 `X-Internal-Token` | 200；响应不回显 Token |
| 数据完整性异常消息包含 SQL 文本 | 500 只返回 `internal_error`，不包含 SQL |
| 未预期异常消息包含密码/Secret | 500 只返回 `internal_error`，不包含密码/Secret |
| SQL 注入文本作为 owner 值 | 按字面值过滤，返回 0 条，不改变 SQL 结构 |

### 7.5 实际执行命令

```text
mvn -q -f backend/spring-service/pom.xml -DskipTests compile
mvn -q -f backend/spring-service/pom.xml -DskipTests test-compile
mvn -q -f backend/spring-service/pom.xml -Dtest=ReviewStatisticsServiceTest test
mvn -q -f backend/spring-service/pom.xml -Dtest=DashboardStatisticsControllerTest test
mvn -f backend/spring-service/pom.xml -Pmysql-it "-Dit.test=ReviewStatisticsMySqlIT" "-Dsurefire.skip=true" verify
mvn -f backend/spring-service/pom.xml -Pmysql-it "-Dit.test=ReviewStatisticsAcceptanceDbIT" "-Dsurefire.skip=true" "-Dcodesentinel.acceptance.db=true" "-Dcodesentinel.acceptance.db.url=jdbc:mysql://localhost:3307/codesentinel_accept_1123b" "-Dcodesentinel.acceptance.db.username=codesentinel" "-Dcodesentinel.acceptance.db.password=<local-dev-password>" verify
mvn -f backend/spring-service/pom.xml test
mvn -f backend/spring-service/pom.xml -Pmysql-it "-Dsurefire.skip=true" verify
```

结果：

```text
ReviewStatisticsServiceTest:        19/19 通过
DashboardStatisticsControllerTest:  15/15 通过
ReviewStatisticsMySqlIT:             9/9  通过
ReviewStatisticsAcceptanceDbIT:     12/12 通过
后端完整 mvn test:                 536/536 通过
完整 MySQL IT:                      76 运行，0 失败，12 跳过（验收库测试默认禁用）
```

### 7.6 只读验证

验收库测试执行前后：

```text
review_report  6 → 6
review_finding 50 → 50
review_comment 26 → 26
review_task     7 → 7
```

验收测试使用：

- 仅只读 Service 查询；
- Hikari `read-only=true`；
- 测试级 `@Transactional(readOnly = true)`；
- URL 必须精确指向 `codesentinel_accept_1123b`，否则测试拒绝启动；
- 未执行任何 INSERT / UPDATE / DELETE / DDL。

Testcontainers MySQL IT 使用独立临时数据库，允许建表、插入 fixture 和 `ALTER` 测试列类型；这些操作不触及验收库或生产库。

---

## 8. Git 状态

### 8.1 当前状态

- 分支：`phase11/dashboard`
- HEAD：`27e3a41161cfa86ee2956ba0b3626a2bcc71eec7`
- 本阶段未执行 commit、push、merge、rebase、reset、clean、checkout。

### 8.2 本阶段新增 / 修改

新增：

```text
backend/spring-service/src/main/java/cn/codesentinel/controller/DashboardStatisticsController.java
backend/spring-service/src/main/java/cn/codesentinel/statistics/
backend/spring-service/src/test/java/cn/codesentinel/controller/DashboardStatisticsControllerTest.java
backend/spring-service/src/test/java/cn/codesentinel/statistics/
docs/reports/Phase11_2_4_B1_Implementation_Report.md
```

修改：

```text
backend/spring-service/src/test/java/cn/codesentinel/CodeSentinelApplicationTests.java
```

`CodeSentinelApplicationTests` 的改动仅为新增 `ReviewStatisticsRepository` 的 `@MockBean`，用于维持既有上下文测试策略（该测试显式排除 JPA Repository 自动配置）。

### 8.3 未触碰的既有工作区改动

工作区在 B1 开始前已存在多份用户改动/未跟踪文件，本阶段未覆盖、未删除、未回滚，包括但不限于：

```text
.gitignore
backend/spring-service/src/main/java/cn/codesentinel/review/ReviewHistoryQueryService.java
backend/spring-service/src/main/java/cn/codesentinel/task/ReviewReportRepository.java
backend/spring-service/src/main/resources/application.yml
docs/DEVELOPMENT_STATUS.md
frontend/
docs/reports/Phase10_*.md
docs/reports/Phase11_2_2_*.md
docs/reports/Phase11_2_3_*.md
docs/reports/Phase11_2_4_A_Investigation_Report.md
```

---

## 9. 已知限制

1. **无 `created_at` 索引**：`review_report` 目前全表扫描；验收库 6 行无影响。A 报告约定 B1 不加索引，后续按数据量与 P95 再评估。
2. **内存排序与分页**：`/reviews` 先加载范围内全部报告，再在 Java 中排序、分页。当前数据量小；若未来单次范围报告数很大，应改为 SQL 分页/排序，但必须保持白名单和稳定 tie-breaker。
3. **最大范围 366 天**：限制单次扫描量，但 366 天日趋势最多 366 个桶；前端渲染需注意。
4. **筛选无法表达未知枚举**：`aiStatus` / `publishStatus` 参数仍使用既有白名单/Java 枚举，未知存储值只能在结果中保留，不能作为筛选条件。
5. **一致性只校验行数**：`finding_count` / `published_comment_count` 与实际行数的比较不能证明 Finding 内容正确，也不能证明评论与 Finding 的语义对应关系。
6. **`summaryCommentIdPresentCount` 是存在性指标**：只判断 `summary_comment_id IS NOT NULL`，不验证该 GitHub 评论是否仍然存在或可读。
7. **无缓存**：每次请求都读数据库；这是 B1 的有意选择，避免缓存失效导致统计与历史记录不一致。
8. **无前端**：B2 的 Vue Insights 页面、筛选栏、趋势图、表格均未实现。
9. **无回填**：历史缺失的 `review_report` / `review_finding` / `review_comment` 不会被补造；统计只反映已持久化数据。
10. **测试 schema 差异**：Testcontainers IT 使用 Hibernate `create-drop`；`publish_status` 在实体中是 Java 枚举，Hibernate 在 MySQL 上会生成 `enum` 列，因此测试在 fixture 前把该列 `ALTER` 为 `VARCHAR(20)`，以匹配生产 DDL。`ai_status` 本来就是 String，无需调整。生产 DDL 未被修改；该 `ALTER` 只作用于临时测试库。
11. **验收测试默认禁用**：`ReviewStatisticsAcceptanceDbIT` 需要显式系统属性与验收库凭据；未配置时按设计跳过，不会在普通 CI 中误连生产库。
12. **错误字段名**：实际项目契约是 `{"error":"..."}`，与 A 报告早期示例的 `{"code":"..."}` 不同；B1 以实际契约为准。
13. **未知 publish status 的额外字段**：`publishStatusCounts` 增加 `UNKNOWN` 桶、`dataQuality` 增加 `unknownPublishStatusReportCount`，属于向后兼容新增，前端 B2 需要按新字段渲染。
14. **生产库当前无数据**：本报告所有数字来自验收库 `codesentinel_accept_1123b`，不代表生产库；生产库首次接入后指标会变化。

---

## 10. 结论与下一步

Phase 11.2.4-B1 的后端只读统计能力已完成：

- 两个接口已实现并可用；
- 统计以 `review_report` 为根，Finding / Comment 一致性闸门明确；
- 验收库所有预期数字对齐；
- 单元、Controller、MySQL、验收库测试全部通过；
- 安全边界复用既有 `DashboardLocalAccessFilter`，无 Token/错误泄漏；
- 未修改 DDL、依赖、生产库或前端。

**下一步：Phase 11.2.4-B2（Vue Insights 页面）尚未开始。**
