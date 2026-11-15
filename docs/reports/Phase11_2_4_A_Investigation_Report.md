# Phase 11.2.4-A 调查报告 — Dashboard Finding 统计与趋势分析

> 执行日期：2026-11-13  
> 分支：`phase11/dashboard`  
> HEAD：`27e3a41161cfa86ee2956ba0b3626a2bcc71eec7`  
> 阶段：Phase 11.2.4-A（只读调查与实施计划）  
> 性质：本阶段不修改源码、配置、依赖、数据库或既有文档，只新增本报告。  
> 结论：**可以进入 Phase 11.2.4-B。但统计必须建立在可验证的 `review_report` / `review_finding` / `review_comment` 行上，并把“报告计数是否完整”和“时间属于哪个时区”作为一等约束；不得为了页面效果引入无法从现有数据证明的指标。**

---

## 1. 调查结论

### 1.1 总体结论

Phase 11.2.4 可以在**不修改 Python AI Service、不修改数据库结构、不新增前端依赖**的前提下完成：

```text
Vue Insights 页面
  ↓
GET /api/dashboard/statistics/overview
GET /api/dashboard/statistics/reviews
  ↓
DashboardStatisticsController
  ↓
ReviewStatisticsService（只读事务）
  ↓
ReviewStatisticsRepository（原生 SQL / 投影）
  ↓
review_report
  ├─ review_finding
  └─ review_comment
  +
review_task（owner / repo / pr_number / task_status）
```

统计页面应当是**只读观察面板**，不是新的审查能力，也不是质量评分系统。它只回答：

- 选定的时间范围内，保存了多少份 Review 报告？
- 这些报告产生了多少 Finding？
- Finding 的 category / severity 分布如何？
- 每天 / 每周的 Review 数和 Finding 数如何变化？
- 哪些 Review 的 Finding 数明显偏离其他 Review？
- 哪些报告的数据不完整，因而不能进入 Finding 或 Comment 统计？

它**不回答**：

- 修复率、误报率、漏报率；
- 唯一缺陷数、跨 Review 去重后的缺陷数；
- 代码质量分数；
- 按 PR 大小归一化后的缺陷密度；
- Agent / 模型 / Token 成本对比；
- 审查耗时。

这些指标缺少数据基础，详见第 5 节。

### 1.2 关键判断

| 问题 | 结论 |
|---|---|
| 是否需要 Python AI Service 改动 | **不需要** |
| 是否需要新增数据库表或字段 | **不需要** |
| 是否需要执行数据库迁移 | **不需要**；索引优化建议延后，见 7.5 |
| 是否需要读取 `review_result_delivery` | **不读取**；它是接收/重放数据，不是结构化审查结果 |
| 是否需要调用 GitHub API | **不需要** |
| 是否需要调用 LLM | **不需要** |
| 是否新增前端依赖 | **不需要**；原生 SVG + CSS 足够 |
| 是否引入 Pinia | **不需要**；页面级状态 + composable 足够 |
| 是否引入 ECharts / Chart.js | **不需要**；当前数据形态用 SVG 折线图 + CSS 分布条即可 |
| 是否可计算唯一缺陷数 | **不可靠，不提供** |
| 是否可计算误报率 / 修复率 | **不可能，不提供** |
| 是否可做跨 Review 质量评分 | **不推荐，不提供** |
| 当前生产库是否有统计数据 | **没有**：`review_report` 为 0 行，页面真实状态是 Empty |
| 验收库是否可用于验收 | **可以**：`codesentinel_accept_1123b` 有 6 份报告、50 条 Finding、26 条评论，且包含刻意构造的异常 |
| 推荐页面入口 | **`/insights` 独立页面**，不塞进现有 `/` |
| 推荐 API 前缀 | **`/api/dashboard/statistics/**`**，自动受现有 loopback 边界保护 |
| 是否可以进入 11.2.4-B | **可以** |

### 1.3 推荐实现路径

```text
/insights
  ├─ 时间范围 / 仓库 / PR / 状态筛选（复用 ReviewHistoryFilter 语义）
  ├─ Summary Cards
  │    ├─ Review 数
  │    ├─ Finding 数
  │    ├─ High + Critical 数
  │    └─ 有 Inline Comment 的 Review 数
  ├─ Category / Severity 分布
  ├─ Day / Week 趋势（SVG）
  ├─ 数据完整性提示
  └─ 逐 Review 对比表（分页）
        ↓
GET /api/dashboard/statistics/overview
GET /api/dashboard/statistics/reviews
        ↓
DashboardStatisticsController
        ↓
ReviewStatisticsService
        ↓
ReviewStatisticsRepository
        ↓
MySQL（只读，REPEATABLE_READ）
```

前端首次进入时并行请求 `overview` 与 `reviews`。`overview` 在一个只读事务中返回 summary、trend、dataQuality；`reviews` 返回分页后的逐 Review 对比。筛选条件变化时同时刷新两者，分页只刷新 `reviews`。

### 1.4 本阶段明确不做的事

- 不实现 Phase 12 的自定义规则、RAG、Milvus、Dashboard 扩展。
- 不增加自动修复、自动评论、自动合并。
- 不增加新的数据库表、字段、迁移脚本或索引。
- 不解析 `review_result_delivery.findings_json` 来“补出”统计。
- 不对生产库做 backfill。
- 不修改 `ReviewHistoryFilter`、`ReviewHistoryQueryService`、`DashboardLocalAccessFilter` 的既有语义。
- 不修改 `docs/DEVELOPMENT_STATUS.md` 或既有 Phase 10 / 11.2.3 报告。
- 不执行 Git 写操作。

---

## 2. 实际状态核查

本节所有结论来自当前工作区代码、实际 MySQL 容器和实际数据，不依赖设计文档推断。

### 2.1 数据库实测

数据库：`codesentinel`（生产/开发库）

| 表 | 行数 | 说明 |
|---|---:|---|
| `review_task` | 8 | 8 条任务全部为 `COMPLETED` |
| `review_result_delivery` | 3 | 接收/重放数据，统计不使用 |
| `review_report` | 0 | **统计页面的真实生产状态是空** |
| `review_finding` | 0 | 无 Finding |
| `review_comment` | 0 | 无评论 |

关键事实：

1. 生产库有 8 条 `review_task`，但只有 3 条 `review_result_delivery`，且 `review_report` 为 0。  
   说明这些历史任务没有写入结构化 Review 历史，或者写入链路没有覆盖它们。统计页面不能根据任务数量“推测”Finding 数量。

2. 任务创建时间为 2026-10-06 至 2026-10-08。即使按任务时间统计，默认 30 天窗口（以 2026-11-13 为今天）也不会包含它们。  
   这不是统计 bug，而是数据现状。

3. 当前生产库没有任何 `review_report`，因此：
   - Summary 全部为 0；
   - Trend 无数据点；
   - 逐 Review 表为空；
   - 页面必须显示明确的 Empty 状态，而不是画一条全 0 的“下降趋势”。

### 2.2 验收库实测

数据库：`codesentinel_accept_1123b`（Phase 11.2.3-B 验收数据，**不是生产数据**）

| 表 | 行数 |
|---|---:|
| `review_task` | 7 |
| `review_report` | 6 |
| `review_finding` | 50 |
| `review_comment` | 26 |

逐报告核对：

| report_id | task_id | ai_status | publish_status | 声明 Finding | 实际 Finding | 声明 Comment | 实际 Comment | created_at |
|---:|---:|---|---|---:|---:|---:|---:|---|
| 2001 | 1001 | DEGRADED | PARTIAL | 45 | 45 | 25 | 25 | 2026-11-01 10:00:00 |
| 2002 | 1002 | COMPLETED | FAILED | 0 | 0 | 0 | 0 | 2026-10-31 09:00:00 |
| 2003 | 1003 | COMPLETED | PUBLISHED | 3 | **2** | 0 | 0 | 2026-10-30 08:00:00 |
| 2004 | 1004 | COMPLETED | PUBLISHED | 1 | 1 | 0 | 0 | 2026-10-29 07:00:00 |
| 2005 | 1005 | COMPLETED | PARTIAL | 1 | 1 | 2 | **1** | 2026-10-28 06:00:00 |
| 2006 | 1006 | **UNKNOWN** | PUBLISHED | 1 | 1 | 0 | 0 | 2026-10-27 05:00:00 |

另有 `review_task` 1008（`COMPLETED`，2026-10-26 04:00:00）没有对应 `review_report`。它不会出现在以 `review_report` 为根的统计中。

Finding 全量分布（50 条）：

| category | 数量 |
|---|---:|
| BUG | 13 |
| SECURITY | 13 |
| PERFORMANCE | 11 |
| QUALITY | 12 |
| **MYSTERY** | **1** |

| severity | 数量 |
|---|---:|
| CRITICAL | 10 |
| HIGH | 10 |
| MEDIUM | 10 |
| LOW | 10 |
| INFO | 9 |
| **UNKNOWN** | **1** |

刻意构造的异常：

1. **报告 2003**：声明 3 条 Finding，实际 2 条。  
   现有详情 API 会返回 409（`ReviewHistoryIncompleteException`），因为详情页拒绝展示不完整历史。统计也不能把这 2 条当作完整的 3 条。
2. **报告 2005**：声明 2 条已发布 Inline Comment，实际 1 条。  
   评论统计必须识别这个不一致。
3. **报告 2006**：`ai_status=UNKNOWN`，Finding 的 category 为 `MYSTERY`，severity 为 `UNKNOWN`。  
   统计必须把它们放进 `UNKNOWN` 桶，不能丢弃，也不能让页面崩溃。
4. **报告 2004**：`references_json` 损坏。  
   统计不读取 `references_json`，因此不影响计数；但它会影响详情 API。统计报告不应把“引用解析失败”误报成“Finding 不完整”。
5. **任务 1008 没有报告**。  
   说明 `review_task` 与 `review_report` 不是一一覆盖关系；统计以报告为根是正确的，但 UI 必须说明口径。

验收库中真正可用于 Finding 统计的报告是 5 份：2001、2002、2004、2005、2006；2003 因 Finding 数不一致被排除。可用于 Comment 统计的也是 5 份：2001、2002、2003、2004、2006；2005 因 Comment 数不一致被排除。

> 计算示例（仅用于验收，不是生产数据）：  
> Finding 总数 = 48；Finding 统计报告数 = 5；平均 = 9.6；中位数 = 1；最大值 = 45。  
> High + Critical = 19；占 48 条的 39.6%。  
> 发布状态：PUBLISHED 3、PARTIAL 2、FAILED 1、PENDING 0。  
> AI 状态：COMPLETED 4、DEGRADED 1、UNKNOWN 1。  
> 这些数字必须在 11.2.4-C 验收时与 SQL 逐项对齐。

### 2.3 后端代码现状

| 组件 | 现状 | 对统计的影响 |
|---|---|---|
| `ReviewReport` | 扁平实体，字段包含 `taskId`、`commitSha`、`aiStatus`、`publishStatus`、`findingCount`、`publishedCommentCount`、`summaryCommentId`、`publishedAt`、`createdAt`、`updatedAt` | 报告级统计的主数据源 |
| `ReviewFinding` | 扁平实体，`category` / `severity` 为 `String`，`referencesJson` 为 TEXT，唯一键 `(report_id, ordinal)` | Finding 分布的数据源；DB 不校验枚举值 |
| `ReviewComment` | 扁平实体，保存已确认发布的 Inline Comment 定位，唯一键 `(report_id, finding_ordinal)` 与 `github_comment_id` | 评论统计的数据源；不包含失败/跳过项 |
| `ReviewTask` | 扁平实体，保存 owner / repo / prNumber / commitSha / status | 过滤与逐 Review 展示的数据源 |
| `ReviewHistoryQueryService` | 只读、`REPEATABLE_READ`；用声明计数做一致性闸门；不一致抛异常 | 统计应复用同样的“声明 vs 实际”判断，但不能直接复用其 409 行为 |
| `ReviewHistoryListService` | 以 `review_report` 为根，`exists` 子查询过滤 `review_task`，固定排序 `createdAt DESC, id DESC` | 统计筛选语义可复用 |
| `ReviewHistoryFilter` | owner / repo / prNumber / taskStatus / publishStatus / aiStatus / createdFrom / createdTo；全部精确匹配；时间边界包含 | 统计应复用，避免两套过滤语义 |
| `DashboardReviewController` | `/api/dashboard/reviews`；错误码 `invalid_pagination`、`invalid_filter`、`internal_error` | 统计 Controller 应沿用同样的错误风格 |
| `DashboardReviewDetailController` | `/api/dashboard/reviews/{taskId}/...`；409 表示历史不完整 | 统计不应复制 409；应显式返回数据质量信息 |
| `DashboardLocalAccessFilter` | `/api/dashboard/**` 仅允许 loopback；不信任转发头 | 新统计路径自动受保护，无需修改 |

`ReviewHistoryService.ensureHistory` 的关键行为：

- `review_report` 先插入，`review_finding` 逐条插入；
- 方法本身没有单一事务包住全部写入；
- 中断后可能留下“报告已存在、Finding 不完整”的中间状态；
- 后续 `ensureHistory` 会补写缺失的 Finding，但不会删除或回滚。

这解释了验收库中 2003、2005 的声明/实际不一致。统计必须把这种状态当作**可以存在的数据状态**处理，而不是假设数据库永远一致。

### 2.4 前端代码现状

- Vue 3 + Vue Router + Element Plus + Axios + Vitest。
- 没有 Pinia，没有 ECharts，没有 Chart.js，没有任何图表库。
- 现有路由：
  - `/` → `DashboardView`
  - `/reviews` → `ReviewHistoryView`
  - `/reviews/:taskId(\d+)` → `ReviewDetailView`
  - catch-all → `NotFoundView`
- 现有类型 `frontend/src/types/api.ts` 已定义 `ReviewHistoryItem`、`ReviewPage<T>`、`FindingCategory`、`FindingSeverity` 等。
- 现有 API 客户端按功能拆分：`api/review-history.ts`、`api/review-detail.ts`、`api/client.ts`。
- 现有列表页已经具备筛选、分页、Loading / Empty / Error / Retry、请求竞态控制的模式，可作为统计页的参考。
- 侧边栏当前只有 Dashboard 与 Review History，UI 文案为英文。

结论：统计页不需要引入全局状态管理；页面级 `ref` + `composable` 足够。图表使用原生 SVG 和 CSS，既避免新依赖，也便于单元测试和无障碍回退。

### 2.5 时间语义

这是本阶段最容易出错的点。

实测：

| 项 | 值 |
|---|---|
| `review_report.created_at` 类型 | `DATETIME(6)`，无时区 |
| Java 写入方式 | `LocalDateTime.now()`，使用 JVM 默认时区 |
| 当前 JVM 所在系统 | Windows `China Standard Time`，UTC+8 |
| MySQL 容器 `@@global.time_zone` | `SYSTEM` |
| MySQL 容器 `@@session.time_zone` | `SYSTEM` |
| MySQL `NOW()` | UTC 时间（与 JVM 本地时间相差 8 小时） |
| 存储内容 | Java 传入的本地墙钟字面值，例如 `2026-11-01 10:00:00`；不保存 offset |

因此：

1. `review_report.created_at` 的语义是**应用本地时间**，不是 UTC。
2. 不能在 SQL 中使用 `NOW()`、`CURDATE()`、`CURRENT_TIMESTAMP` 来推算“今天”或默认范围；数据库时区是 UTC，会错 8 小时。
3. 可以在 SQL 中使用 `DATE(created_at)` 做按天分组，因为 `DATETIME` 没有时区转换，`DATE()` 只是截断存储的字面值；它得到的日期与应用本地日期一致。
4. 统计响应必须显式返回 `zoneId`（例如 `Asia/Shanghai`），前端必须标注“应用本地时间”，不能把无 offset 的字符串当浏览器本地时间再转换。
5. 如果未来把写入改为 UTC，现有 `DATE(created_at)` 语义会失效。必须在写入语义变更时同步修改统计，并写测试。

建议：

- `ReviewStatisticsService` 注入 `ZoneId`（生产取 `ZoneId.systemDefault()`，测试可固定为 `Asia/Shanghai`）。
- 默认时间范围用 `LocalDate.now(zoneId)` 计算，再转换为 `LocalDateTime` 边界。
- 不使用 `java.time.Instant` 解释 `created_at`，除非未来数据库改为 `TIMESTAMP` 或增加 offset 字段。

---

## 3. 指标数据来源

### 3.1 允许的数据源

| 数据源 | 用途 | 备注 |
|---|---|---|
| `review_report` | Review 计数、时间范围、AI 状态、发布状态、声明计数、`summary_comment_id`、`published_at` | 统计的根表 |
| `review_finding` | Finding 总数、category / severity 分布、逐 Review 计数 | 只统计行，不解析 `references_json` |
| `review_comment` | 已发布 Inline Comment 计数、有评论的 Review 数 | 不包含摘要评论正文，也不包含失败/跳过项 |
| `review_task` | owner / repo / prNumber / taskStatus / commitSha 过滤与展示 | 与报告逻辑关联，无物理外键 |

### 3.2 明确禁止的数据源

| 数据源 | 禁止原因 |
|---|---|
| `review_result_delivery` | 接收/重放缓冲，不是结构化历史；读取它会绕过 Phase 10 的一致性契约 |
| `review_result_delivery.findings_json` | 不能为了补统计而临时解析；这会产生第二套 Finding 语义 |
| GitHub API | 统计是本地历史查询，不应触发外部调用、Rate Limit 或权限问题 |
| Python AI Service | 统计不需要重新分析；调用会增加延迟、成本和不确定性 |
| 日志文件 | 日志不是业务数据源；不能从日志推算 Finding |
| 前端本地缓存 | 不能作为统计事实来源；刷新后必须与服务端一致 |

### 3.3 逐指标来源矩阵

| 指标 | 来源 | 是否可计算 | 说明 |
|---|---|---:|---|
| Review 报告数 | `COUNT(review_report)` | 是 | 以报告为根，不含无报告的任务 |
| Finding 总数 | `COUNT(review_finding)` | 是 | 仅统计 Finding 计数一致的报告 |
| Category 分布 | `review_finding.category` | 是 | 未知值归入 `UNKNOWN` |
| Severity 分布 | `review_finding.severity` | 是 | 未知值归入 `UNKNOWN` |
| High + Critical 数 | `review_finding.severity` | 是 | 明确列出两个枚举值 |
| 每 Review 平均 Finding | 报告级计数 | 是 | 分母是进入 Finding 统计的报告数 |
| 每 Review 中位 Finding | 报告级计数 | 是 | 比平均值更抗极端值 |
| 每日 / 每周 Review 数 | `review_report.created_at` | 是 | 应用本地时间 |
| 每日 / 每周 Finding 数 | `review_report.created_at` + `review_finding` | 是 | 仅统计一致的报告 |
| 发布状态分布 | `review_report.publish_status` | 是 | 报告级 |
| AI 状态分布 | `review_report.ai_status` | 是 | 包含 `UNKNOWN` |
| Inline Comment 数 | `COUNT(review_comment)` | 是 | 仅统计评论计数一致的报告 |
| 有 Inline Comment 的 Review 数 | `review_comment` 按报告分组 | 是 | 报告级布尔 |
| `summary_comment_id` 存在数 | `review_report.summary_comment_id IS NOT NULL` | 是 | 只能说明“有可用 ID”，不能反推摘要评论一定成功 |
| 平均置信度 | `review_finding.confidence` | 可计算但不可靠 | 自报值，未校准，不建议作为主指标 |
| Rule ID 分布 | `review_finding.rule_id` | 可计算但噪声大 | 可能为空、跨 Agent 不统一；MVP 不做 |
| 文件热点 | `review_finding.file_path` | 可计算但噪声大 | 路径可能变化、同一文件跨 PR 不可比；MVP 不做 |
| 审查耗时 | 无 `started_at` / `finished_at` | 否 | 不提供 |
| 唯一缺陷数 | 无跨 Review 标识 | 否 | 不提供 |
| 误报率 / 漏报率 | 无 ground truth | 否 | 不提供 |
| 修复率 / 采纳率 | 无开发者反馈 | 否 | 不提供 |
| 缺陷密度 | 无 LOC / diff size / changed files | 否 | 不提供 |
| Token / 成本 | 未持久化 | 否 | 不提供 |
| Agent 维度对比 | 未持久化 Agent 归属 | 否 | Finding 只有 category，没有 agent 字段 |

---

## 4. 指标口径与计算语义

### 4.1 范围与筛选

统计范围定义为：

```text
review_report.created_at ∈ [createdFrom, createdTo]
AND 逻辑关联的 review_task 满足 owner / repo / prNumber / taskStatus 精确匹配
AND review_report 满足 publishStatus / aiStatus 精确匹配
```

规则：

1. **左闭右闭**：`createdFrom <= created_at <= createdTo`，与 `ReviewHistoryFilter` 一致。
2. **时间基准**：`review_report.created_at`，不是 `review_task.created_at`，不是 `updated_at`，也不是 `review_finding.created_at`。  
   `review_finding.created_at` 是写入时间，可能因为补写而晚于报告创建时间；用它会把这批 Finding 记到错误的日期。  
   `review_report.created_at` 是**首次写入结构化历史的时间**，不是 GitHub PR 创建时间。如果未来对历史任务做 backfill，历史报告会按 backfill 日期进入趋势；因此本阶段不做 backfill。若未来必须 backfill，应为趋势增加独立的 `review_occurred_at` 字段，不能复用 `created_at`。
3. **筛选语义**：复用 `ReviewHistoryFilter` 的精确匹配、trim、空字符串视为未提供、`prNumber > 0`、`createdFrom <= createdTo`。
4. **默认范围**：未提供时，默认最近 30 个自然日（含今天）：
   - `createdTo = 今天 23:59:59.999999`
   - `createdFrom = (今天 - 29 天) 00:00:00`
5. **单边提供**：
   - 只提供 `createdFrom`：`createdTo` 默认今天结束；
   - 只提供 `createdTo`：`createdFrom` 默认 `createdTo - 29 天` 的开始。
6. **最大范围**：366 个自然日。超过时返回 `invalid_range`，避免无界扫描。
7. **时区**：上述“今天”按应用 `ZoneId` 计算，不按 MySQL 时区计算。
8. **根表**：`review_report`。没有报告的任务（PENDING / RUNNING / FAILED 或历史未写入）不进入统计。UI 必须说明这一点。

### 4.2 Review 与 Finding 计数

设：

- `R_all` = 范围内所有 `review_report`；
- `R_findings` = `R_all` 中实际 Finding 行数等于 `review_report.finding_count` 的报告；
- `F` = `R_findings` 对应的 `review_finding` 行；
- `R_comments` = `R_all` 中实际 Comment 行数等于 `published_comment_count` 的报告；
- `C` = `R_comments` 对应的 `review_comment` 行。

定义：

| 字段 | 公式 | 空值规则 |
|---|---|---|
| `reviewCount` | `count(R_all)` | 0 |
| `findingStatsReviewCount` | `count(R_findings)` | 0 |
| `findingCount` | `count(F)` | 0 |
| `averageFindingsPerReview` | `count(F) / count(R_findings)` | 分母为 0 时返回 `null` |
| `medianFindingsPerReview` | `median({每份报告的 Finding 数})`，偶数取中间两数平均 | 分母为 0 时返回 `null` |
| `maxFindingsInReview` | `max({每份报告的 Finding 数})` | 分母为 0 时返回 `null` |
| `reviewsWithFindings` | 满足 Finding 数 `> 0` 的 `R_findings` 数量 | 0 |
| `reviewsWithFindingsRatio` | `reviewsWithFindings / count(R_findings)` | 分母为 0 时返回 `null` |
| `highSeverityFindingCount` | `severity ∈ {CRITICAL, HIGH}` 的 `F` 数量 | 0 |
| `highSeverityRatio` | `highSeverityFindingCount / count(F)` | 分母为 0 时返回 `null` |
| `commentStatsReviewCount` | `count(R_comments)` | 0 |
| `publishedInlineCommentCount` | `count(C)` | 0 |
| `reviewsWithInlineComments` | 满足 Comment 数 `> 0` 的 `R_comments` 数量 | 0 |
| `reviewsWithInlineCommentsRatio` | `reviewsWithInlineComments / count(R_comments)` | 分母为 0 时返回 `null` |
| `summaryCommentIdPresentCount` | `summary_comment_id IS NOT NULL` 的 `R_all` 数量 | 0 |

关键约定：

1. **分母为 0 返回 `null`，不返回 0。**  
   0/0 显示为 `0%` 会误导用户以为“比例为零”，实际是“没有样本”。前端显示 `—`。
2. **`reviewCount` 可以大于 `findingStatsReviewCount`。**  
   差额来自 Finding 计数不一致的报告。UI 必须同时显示两者，或在数据质量提示中解释。
3. **平均值和中位数都保留。**  
   验收库中 2001 有 45 条 Finding，其他报告 0–1 条；只看平均值 9.6 会严重高估典型情况，中位数 1 更诚实。两者都不是“质量分数”。
4. **`maxFindingsInReview` 只用于发现异常大报告，不用于排名“最差代码”。**  
   Finding 多不等于代码差，可能只是 PR 更大。
5. **`summaryCommentIdPresentCount` 不能命名为“摘要评论成功数”。**  
   DDL 明确说明 `NULL = no usable summary id`，非空只代表“有可用 ID”。真正的摘要发布结果没有单独的结构化字段。

### 4.3 分布口径

Category 固定顺序：

```text
BUG → SECURITY → PERFORMANCE → QUALITY → UNKNOWN
```

Severity 固定顺序：

```text
CRITICAL → HIGH → MEDIUM → LOW → INFO → UNKNOWN
```

规则：

1. 已知值按上述顺序返回；未知值统一归入 `UNKNOWN`，保留数量。
2. 不因未知值抛异常，不丢弃未知值，不把它们偷偷并入其他分类。
3. 分布计数使用实际 `review_finding` 行，不使用 `review_report.finding_count` 声明值。
4. 分布只覆盖 `R_findings`；不完整报告的 Finding 不进入分布。
5. 响应使用有序数组 `[{key, count}]`，不使用 JSON object。原因：
   - 保留展示顺序；
   - 允许出现 `UNKNOWN` 而不破坏 `FindingCategory` 联合类型；
   - 前端不需要依赖对象 key 的遍历顺序。

发布状态固定顺序：

```text
PUBLISHED → PARTIAL → FAILED → PENDING
```

AI 状态固定顺序：

```text
COMPLETED → DEGRADED → UNKNOWN
```

### 4.4 趋势口径

趋势按 `review_report.created_at` 分桶：

| 粒度 | 桶定义 | 说明 |
|---|---|---|
| `DAY` | 应用本地自然日 `00:00:00` 至 `23:59:59.999999` | MVP 默认 |
| `WEEK` | ISO-8601 周，周一开始 | MVP 可选 |

每个桶返回：

```json
{
  "bucketStart": "2026-11-01",
  "bucketEnd": "2026-11-01",
  "reviewCount": 1,
  "findingCount": 45,
  "highSeverityFindingCount": 18
}
```

规则：

1. `reviewCount` 统计该桶内所有报告。
2. `findingCount` / `highSeverityFindingCount` 只统计 `R_findings`。
3. 如果范围内一份报告都没有：`points = []`，`hasData = false`，不返回一整屏 0。
4. 如果范围内有报告：对请求范围内的每个桶零填充，缺失桶返回 0。这样“没有 Review 的日期”与“有 Review 但 0 Finding 的日期”在视觉上可区分（前者 reviewCount=0，后者 reviewCount>0、findingCount=0）。
5. `WEEK` 桶按日历周切分；范围首尾可能是部分周。计数只包含筛选范围内的数据，UI 应标注“首尾周可能不完整”。
6. 不在 SQL 中使用 `NOW()` / `CURDATE()` 计算桶边界；桶边界由 Java 用 `ZoneId` 计算，SQL 只负责按 `DATE(created_at)` 聚合或由 Java 分桶。
7. 趋势只展示计数，不展示“平均 Finding 趋势”。平均值在样本量为 1 的桶里波动极大，容易误导。

### 4.5 发布与评论口径

1. `publishedInlineCommentCount` 是 `review_comment` 的实际行数，不是 `review_report.published_comment_count` 声明值。
2. `review_comment` 只包含**已确认发布成功**的 Inline Comment；失败、跳过、摘要评论都不在其中。
3. `publishStatus=PARTIAL` 可能表示：
   - 部分 Inline Comment 发布失败；
   - 摘要评论失败；
   - 其他发布阶段失败。
   仅凭 `published_comment_count=0` 不能断言“没有评论”或“发布完全失败”。
4. `publishStatus=FAILED` 的报告仍可能有 Finding；Finding 统计应包含它，除非 Finding 本身不一致。
5. `summary_comment_id` 只表示“有可用 ID”，不表示摘要正文存在、摘要发布成功或摘要内容质量。
6. 不计算“评论发布成功率”，因为：
   - 分母不明确（全部 Finding？尝试发布的 Finding？）；
   - 失败/跳过项没有结构化记录；
   - 低严重度 Finding 可能本来就不发布评论。
   
   只提供“已发布 Inline Comment 数”和“有 Inline Comment 的 Review 数”，并在 UI 中称为“Inline Comment 覆盖”，不称为“成功率”。

### 4.6 数据完整性口径

`dataQuality` 是统计响应的一等字段，不是可选调试信息。

| 字段 | 含义 |
|---|---|
| `totalReportCount` | 范围内报告总数 |
| `findingsConsistentReportCount` | 实际 Finding 数 = 声明 Finding 数的报告数 |
| `commentsConsistentReportCount` | 实际 Comment 数 = 声明 Comment 数的报告数 |
| `reportsExcludedFromFindingStats` | `totalReportCount - findingsConsistentReportCount` |
| `reportsExcludedFromCommentStats` | `totalReportCount - commentsConsistentReportCount` |
| `unknownCategoryFindingCount` | `R_findings` 中 category 不在允许枚举内的数量 |
| `unknownSeverityFindingCount` | `R_findings` 中 severity 不在允许枚举内的数量 |
| `unknownAiStatusReportCount` | `R_all` 中 `ai_status` 不在 `COMPLETED/DEGRADED` 内的数量 |

策略建议：

1. **报告级指标**（Review 数、AI 状态、发布状态、`summary_comment_id` 存在数）使用 `R_all`。
2. **Finding 指标**使用 `R_findings`；不完整报告的 Finding 不进入总数、分布、平均值、中位数、趋势。
3. **Comment 指标**使用 `R_comments`；不完整报告的 Comment 不进入总数和覆盖率。
4. **不把不一致报告“修正”为声明值。** 声明值只是快照声明，实际行才是数据库事实。
5. **不把不一致报告静默丢弃。** 必须在 `dataQuality` 和 UI 警告中显示数量。
6. **详情链接**：逐 Review 表中，Finding 或 Comment 不一致的报告应显示“数据不完整”徽标，并禁用详情链接（详情 API 会 409）。这不是新增后端行为，只是避免用户点击后看到错误页。

### 4.7 明确不计算的指标

以下指标即使“看起来可以算”，也不进入 MVP：

| 指标 | 不计算的原因 |
|---|---|
| 唯一缺陷数 | 没有跨 Review 的稳定 Finding 标识；`rule_id` 可为空，行号会漂移 |
| 跨 Review 去重率 | 同上 |
| 缺陷复发率 | 同上 |
| 误报率 | 没有人工标注的 ground truth |
| 漏报率 | 没有完整缺陷集合 |
| 修复率 / 采纳率 | 没有开发者反馈或后续 commit 关联 |
| 缺陷密度（每 KLOC / 每文件） | 没有 LOC、diff size、changed files 持久化 |
| 质量分数 | 权重主观，无法验证；会制造虚假精确感 |
| 审查耗时 | 没有 started_at / finished_at |
| 发布延迟 | `published_at` 只对已确认发布的报告非空，不能代表审查耗时，样本有偏 |
| Token / 成本 | 没有持久化 |
| Agent 维度对比 | Finding 没有 agent 归属字段 |
| 模型版本对比 | 没有模型版本字段 |
| PR 大小归一化 | 没有 PR 大小数据 |
| 严重度加权分数 | 权重主观，且会掩盖原始分布 |

---

## 5. 不可靠指标清单

| 指标 | 为什么不可靠 | 处理决定 |
|---|---|---|
| 唯一缺陷数 | 无跨 Review 稳定 ID；`rule_id` 可空；同一问题在不同 commit 行号变化 | **不提供** |
| 去重后的 Finding 数 | 同上 | **不提供** |
| 误报率 | 无人工标注 | **不提供** |
| 修复率 | 无后续 commit / 评论解决状态 | **不提供** |
| 缺陷密度 | 无 PR 大小 / LOC | **不提供** |
| 质量分数 | 权重无依据 | **不提供** |
| 平均置信度 | LLM 自报，未校准；不同模型/提示不可比 | **不作为主指标**；如未来展示，必须标注“自报、未校准” |
| Rule ID Top N | 可能为空、命名不统一、跨 Agent 不一致 | **MVP 不做**；后续需要先统一规则库 |
| 文件热点 | 路径随重构变化；同一文件跨 PR 不可比 | **MVP 不做** |
| 每日平均 Finding | 单日样本可能为 1，波动极大 | **不做趋势线**；只做总数 |
| 评论发布成功率 | 分母和失败项不明确 | **不做**；只做已发布计数 |
| 摘要评论成功数 | `summary_comment_id` 为 NULL 不等于没有摘要 | **只做 ID 存在数**，并明确命名 |
| 跨仓库对比 | 仓库规模、语言、规则不同 | **不做排名**；只做筛选后的计数 |
| Agent 效果对比 | 无 agent 归属 | **不提供** |

---

## 6. API 设计

### 6.1 路径与职责

沿用现有 Dashboard BFF 风格，新增：

```text
GET /api/dashboard/statistics/overview
GET /api/dashboard/statistics/reviews
```

| 接口 | 职责 | 事务 |
|---|---|---|
| `/overview` | summary + trend + dataQuality，一次请求返回同一快照 | 只读，`REPEATABLE_READ` |
| `/reviews` | 逐 Review 对比表，分页、排序 | 只读，`REPEATABLE_READ` |

为什么拆成两个：

1. Summary + Trend 必须来自同一数据库快照，否则可能出现“总数 6、趋势合计 5”的矛盾。放在一个 Service 方法、一个事务中返回。
2. 逐 Review 表需要分页和排序，独立请求避免每次翻页都重算 summary/trend。
3. 两个接口都只读，前端可以并行加载；任一失败可以独立重试，不会拖垮整个页面。

### 6.2 查询参数

两个接口共用筛选参数，语义与 `ReviewHistoryFilter` 完全一致：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `owner` | string | 否 | 精确匹配，trim，最大 255 |
| `repo` | string | 否 | 精确匹配，trim，最大 255 |
| `prNumber` | integer | 否 | 必须 > 0 |
| `taskStatus` | enum | 否 | `PENDING` / `RUNNING` / `COMPLETED` / `FAILED` |
| `publishStatus` | enum | 否 | `PENDING` / `PUBLISHED` / `PARTIAL` / `FAILED` |
| `aiStatus` | string | 否 | `COMPLETED` / `DEGRADED` |
| `createdFrom` | ISO date-time | 否 | 包含；应用本地时间 |
| `createdTo` | ISO date-time | 否 | 包含；应用本地时间 |

`/overview` 额外参数：

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `granularity` | enum | `DAY` | `DAY` / `WEEK` |

`/reviews` 额外参数：

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `page` | integer | 1 | >= 1 |
| `size` | integer | 20 | 1–100 |
| `sort` | string | `createdAt` | 白名单：`createdAt` / `actualFindingCount` / `highSeverityFindingCount` / `actualCommentCount` |
| `direction` | string | `desc` | `asc` / `desc` |

排序必须使用白名单映射，禁止把用户输入直接拼进 `ORDER BY`。默认排序 `createdAt DESC, taskId DESC`，保证分页稳定。

### 6.3 `/overview` 响应

```json
{
  "range": {
    "createdFrom": "2026-10-15T00:00:00",
    "createdTo": "2026-11-13T23:59:59.999999",
    "zoneId": "Asia/Shanghai",
    "granularity": "DAY"
  },
  "generatedAt": "2026-11-13T20:30:00",
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
    "highSeverityRatio": 0.3958,
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
      { "key": "PENDING", "count": 0 }
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
        "bucketStart": "2026-10-27",
        "bucketEnd": "2026-10-27",
        "reviewCount": 1,
        "findingCount": 1,
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
    "unknownAiStatusReportCount": 1
  }
}
```

> 上述数字来自 `codesentinel_accept_1123b` 的验收数据，仅用于说明响应结构，不是生产数据。实际接口必须从数据库实时计算。  
> `trend.points` 示例只展示了一个点；实际响应会零填充完整时间范围。

注意事项：

1. `range` 返回**生效后的**范围，而不是原始参数。前端据此显示“当前统计区间”。
2. `zoneId` 必须返回，前端据此标注时间语义。
3. `generatedAt` 使用应用本地时间，不带 offset；前端不要用 `Date` 做时区转换。
4. `averageFindingsPerReview` / `medianFindingsPerReview` 可以为 `null`；前端显示 `—`。
5. `categoryCounts` / `severityCounts` 始终返回完整的有序列表（包括 0 值），前端不需要自己补空桶。
6. `publishStatusCounts` / `aiStatusCounts` 同理。
7. `trend.points` 在无数据时为空数组，`hasData=false`；有数据时零填充完整范围。

### 6.4 `/reviews` 响应

复用现有 `ReviewPage<T>` 结构：

```json
{
  "items": [
    {
      "taskId": 1001,
      "owner": "owner",
      "repo": "repo",
      "prNumber": 42,
      "commitSha": "0123456789abcdef0123456789abcdef01234567",
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

1. `declaredFindingCount` / `actualFindingCount` 同时返回，前端显示徽标；不要只返回一个“修正后”的数字。
2. `criticalCount` 等来自实际 Finding 行。即使 `findingsConsistent=false`，也返回已存在的行数，但 UI 必须标记“不完整”，且这些行不进入汇总。
3. `taskStatus` 来自 `review_task`；如果报告没有对应任务，按现有列表服务的行为返回 500，而不是伪造 `UNKNOWN`。
4. 不返回 Finding 的 title / description / file_path / rule_id / confidence。统计页不需要这些敏感或高噪声字段；详情页已有专门接口。
5. `commitSha` 返回完整值，前端可截断显示。
6. `owner` / `repo` / `prNumber` 是筛选和导航所需的最小信息。

### 6.5 错误码

| HTTP | code | 触发条件 |
|---:|---|---|
| 400 | `invalid_filter` | `owner` / `repo` 超长、`prNumber <= 0`、`createdFrom > createdTo`、非法枚举绑定 |
| 400 | `invalid_pagination` | `page < 1`、`size < 1`、`size > 100` |
| 400 | `invalid_granularity` | `granularity` 不是 `DAY` / `WEEK` |
| 400 | `invalid_sort` | `sort` 不在白名单，或 `direction` 不是 `asc` / `desc` |
| 400 | `invalid_range` | 范围超过 366 个自然日 |
| 500 | `internal_error` | 数据库异常、报告缺少对应任务、其他未预期错误 |

错误响应沿用现有 `ReviewHistoryError` 风格：

```json
{ "code": "invalid_filter" }
```

不要在响应中放 SQL、表名、堆栈或 owner/repo 之外的敏感信息。

### 6.6 命名约定

建议使用以下字段名，避免歧义：

| 不推荐 | 推荐 | 原因 |
|---|---|---|
| `totalReviews` | `reviewCount` | 明确是报告数，不是任务数 |
| `totalFindings` | `findingCount` | 与现有 DTO 风格一致 |
| `avgFindings` | `averageFindingsPerReview` | 明确分母 |
| `successRate` | `reviewsWithInlineCommentsRatio` | 不是发布成功率 |
| `summaryComments` | `summaryCommentIdPresentCount` | 只代表有可用 ID |
| `excludedReports` | `reportsExcludedFromFindingStats` | 区分 Finding / Comment 两种排除 |
| `unknownCount` | `unknownCategoryFindingCount` | 明确维度和单位 |

---

## 7. Repository / SQL 设计

### 7.1 推荐的分层

```text
controller/DashboardStatisticsController.java
statistics/ReviewStatisticsService.java
statistics/ReviewStatisticsRepository.java
statistics/dto/*.java
```

- Controller 只负责参数绑定、调用 Service、映射错误。
- Service 负责默认范围、粒度、数据质量策略、聚合与 DTO 组装。
- Repository 负责参数化 SQL 和投影，不包含业务判断。
- DTO 使用 record，字段与 API 契约一一对应。
- 复用 `ReviewHistoryFilter`、`ReviewHistoryError`、`InvalidReviewHistoryFilterException`、`InvalidReviewHistoryPaginationException`，避免复制过滤语义。

如果希望保持包内聚，也可以把 Service / Repository / DTO 放在现有 `cn.codesentinel.review` 下；但不建议把统计逻辑塞进 `ReviewHistoryQueryService`。统计与详情查询是不同用例，混在一起会让 409 一致性闸门和统计的“部分数据可展示”策略相互纠缠。

### 7.2 数据访问方式

现有项目只使用 Spring Data JPA，没有 `JdbcTemplate` / `EntityManager` 原生查询的使用先例。推荐：

- **Spring Data JPA + `@Query(nativeQuery = true)` + interface projection**；
- 不引入新依赖（`spring-boot-starter-data-jpa` 已包含所需能力）；
- 不使用字符串拼接 SQL；
- 所有用户输入通过命名参数绑定；
- 排序字段通过 Service 白名单映射，不直接绑定用户输入。

原生 SQL 的两个实现注意点：

1. **可空时间参数**：`(:createdFrom IS NULL OR ...)` 在 Hibernate 6 + MySQL 下通常可用，但必须在 MySQL IT 中同时覆盖 null 与非 null；如果出现参数类型推断问题，Service 可用固定的最小/最大时间哨兵值代替 null（不改变语义）。
2. **枚举参数**：`publish_status` / `status` 在数据库中存的是字符串；原生查询应传 `enum.name()` 或显式转成字符串，避免 Hibernate 把枚举当序号。

选择原生 SQL 的原因：

1. `review_report` 与 `review_task` 没有 JPA 关联，JPQL 无法自然 `JOIN`；
2. 需要 `GROUP BY`、条件聚合、`HAVING`、分页排序；
3. 需要精确控制 MySQL 的 `DATE(created_at)` 语义；
4. 现有实体是扁平结构，强行加关联会破坏 Phase 10 的映射约定。

### 7.3 查询拆分

建议一个 `overview` 事务内执行 4 组查询：

#### A. 报告级聚合

返回每份报告的：

```text
report_id, task_id, owner, repo, pr_number, commit_sha,
ai_status, publish_status, created_at,
declared_finding_count, actual_finding_count,
declared_comment_count, actual_comment_count,
summary_comment_id_present
```

用途：

- `reviewCount`、AI/发布状态分布、`summaryCommentIdPresentCount`；
- `dataQuality` 的一致性计数；
- 逐报告平均值 / 中位数 / 最大值；
- 趋势的 `reviewCount`。

建议 SQL 形态：

```sql
SELECT
    r.id AS report_id,
    r.task_id AS task_id,
    t.owner AS owner,
    t.repo AS repo,
    t.pr_number AS pr_number,
    r.commit_sha AS commit_sha,
    r.ai_status AS ai_status,
    r.publish_status AS publish_status,
    r.created_at AS created_at,
    r.finding_count AS declared_finding_count,
    (SELECT COUNT(*) FROM review_finding f WHERE f.report_id = r.id) AS actual_finding_count,
    r.published_comment_count AS declared_comment_count,
    (SELECT COUNT(*) FROM review_comment c WHERE c.report_id = r.id) AS actual_comment_count,
    (r.summary_comment_id IS NOT NULL) AS summary_comment_id_present
FROM review_report r
LEFT JOIN review_task t ON t.id = r.task_id
WHERE (:owner IS NULL OR t.owner = :owner)
  AND (:repo IS NULL OR t.repo = :repo)
  AND (:prNumber IS NULL OR t.pr_number = :prNumber)
  AND (:taskStatus IS NULL OR t.status = :taskStatus)
  AND (:publishStatus IS NULL OR r.publish_status = :publishStatus)
  AND (:aiStatus IS NULL OR r.ai_status = :aiStatus)
  AND (:createdFrom IS NULL OR r.created_at >= :createdFrom)
  AND (:createdTo IS NULL OR r.created_at <= :createdTo)
```

说明：

- `review_finding(report_id, ordinal)` 与 `review_comment(report_id, finding_ordinal)` 的唯一索引可以覆盖 `COUNT(*) WHERE report_id = ?`，是索引覆盖扫描。
- 这份结果集在内存中按报告聚合，避免多次扫描同一批报告。
- 当前数据量很小；即使未来到几千份报告，这个结果集仍然可控。若达到数万份，再考虑把 summary/trend 下推到 SQL（见 7.6）。
- **孤儿报告不能静默丢弃**：使用 `LEFT JOIN` 后，如果某行的 `task_id` 为空，Service 必须抛出 `ReviewHistoryDataIntegrityException`（映射为 500 `internal_error`），与现有 `ReviewHistoryListService` 的 fail-closed 行为一致。若使用 `INNER JOIN`，孤儿报告会被静默少计，这是不可接受的。
- 带 owner/repo 筛选时，孤儿报告本来就不属于该筛选结果；但无筛选统计必须先做上述检查。建议先执行 A 查询并检查孤儿，再执行 B/C/E，确保同一事务内不会返回“少计”的结果。

#### B. Category 分布

```sql
SELECT f.category AS key, COUNT(*) AS count
FROM review_finding f
JOIN review_report r ON r.id = f.report_id
JOIN review_task t ON t.id = r.task_id
WHERE <与 A 相同的筛选条件>
  AND (SELECT COUNT(*) FROM review_finding x WHERE x.report_id = r.id) = r.finding_count
GROUP BY f.category
```

#### C. Severity 分布

与 B 相同，只替换 `f.category` 为 `f.severity`。

#### D. 趋势

可以：

- 在 SQL 中按 `DATE(r.created_at)` 聚合 `reviewCount` / `findingCount`；或
- 复用 A 的报告级结果，在 Java 中按 `ZoneId` 分桶。

推荐 **Java 分桶**（复用 A）：

- 避免 SQL 时区/日期函数差异；
- 便于对“Finding 不一致报告”做条件计数；
- 便于零填充和 ISO 周计算；
- 报告级结果已经加载，不需要再扫一遍。

如果未来报告数量很大，再把趋势下推到 SQL：

```sql
SELECT DATE(r.created_at) AS bucket,
       COUNT(DISTINCT r.id) AS review_count,
       SUM(CASE WHEN <findings_consistent> THEN <actual_finding_count> ELSE 0 END) AS finding_count
FROM ...
GROUP BY DATE(r.created_at)
ORDER BY bucket
```

注意：`SUM(CASE WHEN ... THEN actual_finding_count ELSE 0 END)` 需要先按报告聚合，否则会被 JOIN 放大。不要在明细 JOIN 上直接 `SUM`。

### 7.4 逐 Review 表查询

复用报告级聚合结果，增加按报告分组的 category / severity 计数。两种实现：

**方案 1（推荐）**：A + E 两份聚合查询，Service 在内存中按 `report_id` 合并、排序、分页。  
适合当前数据量（0–几千份报告），实现简单，排序和一致性标记容易测试。

**方案 2**：SQL 分页 + 独立 count 查询。  
适合大数据量，但需要处理：

- `ORDER BY` 白名单与别名；
- `COUNT(*)` 与 `GROUP BY` 的分页 count；
- 多查询之间的一致性；
- native count query 的维护成本。

MVP 推荐方案 1；在 7.6 给出何时切换到方案 2 的阈值。

逐 Review 行的 category / severity 计数可以在 SQL 中用条件聚合：

```sql
SUM(CASE WHEN f.severity = 'CRITICAL' THEN 1 ELSE 0 END) AS critical_count,
SUM(CASE WHEN f.severity = 'HIGH' THEN 1 ELSE 0 END) AS high_count,
...
SUM(CASE WHEN f.category = 'BUG' THEN 1 ELSE 0 END) AS bug_count,
...
```

但这样会把 A 的“报告级”查询变成“报告 × Finding”明细聚合，行数放大。更清晰的做法是：

- A 查询报告级基础信息；
- E 查询按 `report_id` 分组的 category / severity 计数；
- Service 按 `report_id` 合并。

E 查询：

```sql
SELECT
    f.report_id AS report_id,
    SUM(CASE WHEN f.severity = 'CRITICAL' THEN 1 ELSE 0 END) AS critical_count,
    SUM(CASE WHEN f.severity = 'HIGH' THEN 1 ELSE 0 END) AS high_count,
    ...
    SUM(CASE WHEN f.category = 'BUG' THEN 1 ELSE 0 END) AS bug_count,
    ...
    SUM(CASE WHEN f.category NOT IN ('BUG','SECURITY','PERFORMANCE','QUALITY') THEN 1 ELSE 0 END) AS unknown_category_count,
    SUM(CASE WHEN f.severity NOT IN ('CRITICAL','HIGH','MEDIUM','LOW','INFO') THEN 1 ELSE 0 END) AS unknown_severity_count
FROM review_finding f
JOIN review_report r ON r.id = f.report_id
JOIN review_task t ON t.id = r.task_id
WHERE <筛选条件>
GROUP BY f.report_id
```

这份查询覆盖所有报告（包括不一致报告），用于逐 Review 展示；汇总只使用 `findingsConsistent=true` 的行。

### 7.5 索引现状与建议

实测索引：

| 表 | 索引 | 列 |
|---|---|---|
| `review_report` | PRIMARY | `id` |
| `review_report` | `uk_review_report_task` | `task_id` |
| `review_finding` | PRIMARY | `id` |
| `review_finding` | `uk_review_finding_report_ordinal` | `report_id, ordinal` |
| `review_comment` | PRIMARY | `id` |
| `review_comment` | `uk_review_comment_report_finding` | `report_id, finding_ordinal` |
| `review_comment` | `uk_review_comment_github_id` | `github_comment_id` |
| `review_task` | PRIMARY | `id` |

实测 `EXPLAIN`（验收库，按 `created_at` 范围 + 排序）：

```text
review_report: type=ALL, key=NULL, rows=6, Extra=Using where; Using filesort
review_task:   type=eq_ref, key=PRIMARY, rows=1
```

结论：

1. `review_report.created_at` 没有索引，范围查询是全表扫描 + 文件排序。
2. 当前数据量（生产 0 行，验收 6 行）下完全没有性能问题。
3. `review_finding` / `review_comment` 的 `report_id` 前缀唯一索引可以覆盖按报告计数。
4. `review_task.owner/repo/pr_number/status` 没有索引；带这些筛选时会对 `review_task` 做全表扫描。当前 7–8 行，无影响。

建议：

- **本阶段不新增索引。** 没有迁移工具，且当前数据量不需要；擅自改 DDL 会违反“最小修改”原则。
- 在 11.2.4-C 记录 `EXPLAIN` 结果，作为后续优化基线。
- 当生产报告数超过约 10,000 行，或统计接口 P95 超过 200 ms 时，再评估：
  - `review_report(created_at, id)`；
  - `review_task(owner, repo, pr_number)`。
- 加索引必须单独走数据库变更流程，不与前端/后端功能 PR 混合。

### 7.6 规模阈值与降级策略

| 报告数（范围内） | 策略 |
|---:|---|
| 0–5,000 | 内存聚合，单次加载报告级结果；当前推荐 |
| 5,000–50,000 | 保留内存聚合但增加响应时间日志；考虑把 summary/trend 下推 SQL |
| > 50,000 | 必须改为 SQL 聚合 + 分页查询；增加索引；评估缓存 |

不在 MVP 实现缓存。原因：

- 数据量小；
- Review 完成后统计应立即变化，缓存会制造“刚审查完但数字没变”的困惑；
- 个人 Dashboard 没有高并发需求。

如果未来加缓存，必须：
- 以筛选条件 + 时间范围 + 数据版本为 key；
- 设置短 TTL（例如 30 秒）；
- 在 Review 完成事件后主动失效，或接受短暂不一致并明确标注。

---

## 8. 前端设计

### 8.1 页面位置

推荐新增独立页面：

```text
/insights
```

理由：

1. 统计页有自己的时间范围、粒度、筛选和分页状态，塞进 `/` 会让首页职责过载。
2. 独立 URL 可刷新、可收藏、可从侧边栏直接进入。
3. 现有 `/` 的 DashboardView 可以保持不变，避免影响 Phase 11.1 的布局与测试。
4. 后续如果要在首页放“最近 7 天摘要”，可以作为独立小卡片复用 `/overview`，不需要现在重构首页。

侧边栏新增：

```text
Dashboard
Review History
Review Insights   ← 新增
```

图标可使用 `@element-plus/icons-vue` 中已有的 `TrendCharts`，不新增依赖。路由名建议 `insights`，标题 `Review Insights`。

### 8.2 页面结构

```text
InsightsView
├─ Page header
│   ├─ 标题
│   ├─ 说明：统计基于已保存的 Review 报告
│   └─ 刷新按钮
├─ Filter bar
│   ├─ 时间范围（el-date-picker，daterange）
│   ├─ owner / repo / prNumber
│   ├─ taskStatus / publishStatus / aiStatus
│   ├─ granularity（DAY / WEEK）
│   ├─ Apply / Reset
│   └─ 当前时区说明
├─ Data quality alert（有排除时显示）
├─ Summary cards（4–6 个）
├─ Distribution section
│   ├─ Category bars
│   └─ Severity bars
├─ Trend section
│   ├─ Review / Finding 切换或双线
│   └─ SVG 折线图 + 数据表 fallback
├─ Review comparison table
│   ├─ 分页
│   ├─ 排序
│   └─ 数据完整性徽标
└─ Empty / Error / Loading states
```

### 8.3 组件拆分

建议：

| 组件 | 职责 |
|---|---|
| `views/InsightsView.vue` | 页面编排、筛选状态、两个接口的加载协调 |
| `components/insights/InsightsFilterBar.vue` | 筛选表单，emit `apply` / `reset` |
| `components/insights/StatCard.vue` | 单个指标卡，支持 `value` / `suffix` / `hint` / `loading` |
| `components/insights/DistributionBars.vue` | 通用横向分布条，接收 `items` 和颜色映射 |
| `components/insights/TrendChart.vue` | 原生 SVG 折线图，接收 points 和 series 配置 |
| `components/insights/ReviewComparisonTable.vue` | Element Plus 表格、分页、排序、完整性徽标 |
| `composables/useStatisticsOverview.ts` | `/overview` 请求、竞态控制、错误映射 |
| `composables/useReviewStatistics.ts` | `/reviews` 请求、分页、排序、竞态控制 |
| `utils/statistics-format.ts` | 百分比、平均值、中位数、日期、空值格式化 |
| `utils/trend-geometry.ts` | SVG 坐标、路径、刻度计算，纯函数，便于单测 |

不引入 Pinia：筛选条件在 `InsightsView` 中持有，通过 props / emit 传递；两个 composable 各自管理请求状态。页面刷新后重新请求，不需要全局缓存。

### 8.4 请求与竞态

参考现有列表页的模式：

```text
用户点击 Apply
  ↓
取消上一次未完成请求（AbortController）
  ↓
并行请求 overview + reviews(page=1)
  ↓
Promise.allSettled
  ↓
任一成功先渲染；失败区域单独显示错误与 Retry
```

要点：

1. 筛选变化时 `page` 重置为 1。
2. 翻页只请求 `/reviews`，不重新请求 `/overview`。
3. 组件卸载时 abort 未完成请求。
4. 不要在 `watch` 中对每个输入字符立即发请求；使用 Apply 按钮，或 300 ms debounce。
5. 错误信息使用现有 `toApiError` / `getErrorMessage`，不要把后端错误码直接展示给用户。
6. 对 400 错误显示“筛选条件不合法”，对 500 显示“统计加载失败，请重试”，并保留 Retry。

### 8.5 无依赖图表方案

#### 趋势图

使用 `<svg viewBox="0 0 720 240">`：

- x 轴：桶索引，`x = padding + i * (width - 2*padding) / (n - 1)`；
- y 轴：计数，`y = height - padding - (value / maxValue) * (height - 2*padding)`；
- `n=1` 时把点放在中间，避免除零；
- `maxValue=0` 时画基线，不画除零路径；
- 网格线 4 条，刻度标签显示 0 / 25% / 50% / 75% / 100% 或取整后的计数；
- x 轴标签按间隔抽样，避免 30 天标签重叠；
- 每个点带 `<title>`，hover 显示日期与数值；
- 折线使用 `stroke`，可选半透明面积 `path`；
- 空数据不渲染图表，显示 `el-empty`。

#### 分布条

使用 CSS：

```text
label | bar track (flex) | count | percentage
```

- 宽度按 `count / total * 100%`；
- `total=0` 时显示空轨道，不显示 0% 标签；
- `UNKNOWN` 使用中性灰色；
- 颜色不是唯一编码：每行都有文字标签和数字。

#### 可访问性

- SVG `role="img"` + `aria-label` 概述，例如“2026-10-27 至 2026-11-13 的每日 Review 数”；
- `<title>` / `<desc>` 提供可读描述；
- 图表下方提供可折叠的数据表，作为屏幕阅读器和无 SVG 环境的回退；
- 不用红绿作为唯一区分；
- 所有交互控件有 label。

### 8.6 文案与空值

| 场景 | 文案 |
|---|---|
| 无报告 | “当前时间范围内没有已保存的 Review 报告。统计只包含已写入结构化历史的 Review。” |
| 有报告但 0 Finding | “这些 Review 没有产生 Finding。” |
| 比例分母为 0 | 显示 `—`，tooltip “没有样本” |
| Finding 数据不完整 | “有 N 份报告的 Finding 明细与声明计数不一致，已从 Finding 统计中排除；Review 计数仍包含它们。” |
| Comment 数据不完整 | “有 N 份报告的评论明细与声明计数不一致，已从评论统计中排除。” |
| 未知枚举 | “未知（MYSTERY）” / “未知（UNKNOWN）”，灰色 |
| 生产库为空 | 不要显示“0% 下降”；显示 Empty 状态与口径说明 |

### 8.7 时间显示

- 后端返回的 `createdAt` 是应用本地墙钟字符串，没有 offset。
- 前端**不要**用 `new Date(str)` 再按浏览器时区转换；否则用户在另一个时区打开页面时，时间会漂移。
- 使用字符串截取 / 正则解析 `YYYY-MM-DDTHH:mm:ss`，直接显示 `YYYY-MM-DD HH:mm`。
- 页面筛选栏或页脚标注：“时间口径：应用本地时间（Asia/Shanghai）”，其中时区来自响应 `range.zoneId`。
- 日期选择器发送 `YYYY-MM-DDT00:00:00` 和 `YYYY-MM-DDT23:59:59.999999`，不要发送 `YYYY-MM-DD` 让后端猜。

### 8.8 表格列建议

| 列 | 内容 | 备注 |
|---|---|---|
| Created | `YYYY-MM-DD HH:mm` | 默认降序 |
| Repository | `owner/repo` | 可筛选 |
| PR | `#123` | 链接到 GitHub？MVP 不做外部链接，避免新窗口/权限问题 |
| Task | `taskId` | 可链接到 `/reviews/{taskId}`，但不一致报告禁用 |
| AI / Publish | 两个小徽标 | DEGRADED / PARTIAL 等 |
| Findings | `actual / declared` | 不一致时橙色/红色徽标 |
| High+Critical | 数字 | 来自实际行 |
| Comments | `actual / declared` | 不一致时徽标 |
| Data | `完整` / `不完整` | 文字，不仅靠颜色 |

分页默认 20，最大 100，与后端一致。

### 8.9 前端测试

| 测试 | 内容 |
|---|---|
| `statistics-format.spec.ts` | 百分比、平均值、中位数、null → `—`、未知枚举标签 |
| `trend-geometry.spec.ts` | n=0 / n=1 / max=0 / 正常序列 / 坐标边界 |
| `InsightsView.spec.ts` | 加载、成功、空数据、错误、部分数据警告、筛选重置 |
| `ReviewComparisonTable.spec.ts` | 分页、排序、完整性徽标、详情链接禁用 |
| `api/statistics.spec.ts` | 查询参数序列化、错误映射、AbortSignal |
| `TrendChart.spec.ts` | SVG 渲染、aria-label、空数据不渲染 |

不写只看快照的测试；断言用户可见文本、数值和交互结果。

---

## 9. 安全边界

### 9.1 访问控制

- 新接口位于 `/api/dashboard/statistics/**`，已被 `DashboardLocalAccessFilter` 的 `/api/dashboard/**` 规则覆盖。
- 该过滤器使用 TCP peer 地址，不信任 `X-Forwarded-For` / `Forwarded`，且 `server.forward-headers-strategy=none`。
- 不新增 token、Cookie、Session 或登录流程。
- 不接受 `X-Internal-Token`；不要复用 Phase 10 的服务间 token。
- 非 loopback 请求应返回 403，且不进入 Controller。
- 如果未来通过反向代理暴露 Dashboard，代理必须自己做认证；这是现有边界已知限制，统计页不改变它。

### 9.2 数据暴露

统计页暴露：

- owner / repo / PR 编号 / commit SHA / taskId；
- 聚合计数、状态、时间。

统计页**不暴露**：

- Finding 的 title / description / reason / suggestion；
- 文件路径与行号；
- 代码片段；
- GitHub token、Webhook secret、内部 token；
- 评论正文。

这些最小暴露原则与现有 Review History 列表一致。

### 9.3 SQL 注入与参数

- 所有筛选值使用命名参数绑定。
- `sort` / `direction` / `granularity` 使用白名单枚举映射，不拼接用户输入。
- 不把 `owner` / `repo` 直接插入 SQL 字符串。
- 如果采用 SQL 分页，使用 `LIMIT` / `OFFSET` 绑定参数，并限制 `size <= 100`；MVP 的内存分页只在已加载的聚合行上切片，不拼接 SQL。
- 原生 SQL 集中在 Repository，不散落在 Controller / Service。

### 9.4 日志

- 记录 `invalid_filter` / `invalid_range` 时只记录错误码和字段名，不记录完整 owner/repo（可选）。
- 记录 `internal_error` 时记录 taskId / reportId（如有）和异常摘要，不记录 SQL 参数全量。
- 不记录任何 token、secret、代码内容。
- 不在日志中输出完整 SQL，避免泄露数据分布。

### 9.5 只读保证

- Service 使用 `@Transactional(readOnly = true, isolation = Isolation.REPEATABLE_READ)`。
- 不调用任何写 Repository 方法。
- 不触发 `ensureHistory`、不触发 `review_result_delivery` 重放。
- 不调用 GitHub / LLM / Python 服务。
- 不修改 `updated_at`。

---

## 10. 性能

### 10.1 当前成本

| 项 | 实测 / 估算 |
|---|---|
| 生产报告数 | 0 |
| 验收报告数 | 6 |
| 验收 Finding 数 | 50 |
| 验收 Comment 数 | 26 |
| `review_report` 范围查询 | 全表扫描 + filesort（无 `created_at` 索引） |
| `review_finding` 按报告计数 | 唯一索引 `(report_id, ordinal)` 覆盖 |
| `review_comment` 按报告计数 | 唯一索引 `(report_id, finding_ordinal)` 覆盖 |
| 预期接口耗时 | 当前数据量下 < 20 ms（本地 MySQL） |

当前数据量下，性能不是风险。真正的风险是“未来数据增长后仍然全表扫描”。

### 10.2 查询次数

`/overview` 建议 3–4 次查询：

1. 报告级聚合（A）；
2. Category 分布（B）；
3. Severity 分布（C）；
4. 可选：Comment 按报告计数（如果 A 不包含）。

`/reviews` 建议 2 次查询：

1. 报告级聚合（A）；
2. Category / Severity 按报告分组（E）。

所有查询在同一个只读事务中执行。不要 N+1 查询每份报告的 Finding / Comment。

### 10.3 响应大小

- `/overview`：summary 约 1 KB，trend 30–366 个点约 5–40 KB，dataQuality 约 0.5 KB。
- `/reviews`：20 行 × 约 15 字段，约 10 KB。
- 限制 `size <= 100`，避免一次拉取过多行。
- 趋势最大 366 个 DAY 点；WEEK 最多 53 个点。超过 366 天直接拒绝。

### 10.4 超时与降级

- 统计查询不应调用外部服务，超时风险低。
- 如果数据库慢，返回 500 `internal_error`，前端显示 Retry；不要返回部分伪造数据。
- 不建议为统计接口设置比全局更短的超时；按现有 Spring 配置。
- 如果未来加入缓存，必须明确缓存失效策略，不能让用户看到过期统计而不知情。

### 10.5 索引决策

本阶段不新增索引。理由：

1. 生产 0 行、验收 6 行，加索引没有收益；
2. 项目没有迁移工具，手工 DDL 容易与文档/环境不一致；
3. 索引属于数据库变更，应与功能 PR 分开评审；
4. 先用 `EXPLAIN` 建立基线，再按真实数据量决策。

记录以下基线到 11.2.4-C：

```text
review_report: ALL, rows=6, Using where; Using filesort
review_task:   eq_ref PRIMARY, rows=1
```

当报告数 > 10,000 或 P95 > 200 ms 时，再评估 `review_report(created_at, id)`。

---

## 11. 测试方案

### 11.1 后端单元测试

`ReviewStatisticsServiceTest`（Mock Repository）：

1. 默认范围：
   - 未提供 from/to → 最近 30 个自然日，含今天；
   - 只提供 from → to 为今天结束；
   - 只提供 to → from 为 to - 29 天开始。
2. 范围校验：
   - from > to → `invalid_filter`；
   - 超过 366 天 → `invalid_range`。
3. 粒度：
   - `DAY` / `WEEK` 正常；
   - 非法值 → `invalid_granularity`。
4. 一致性：
   - 报告声明 3、实际 2 → 从 Finding 汇总排除；
   - 评论声明 2、实际 1 → 从 Comment 汇总排除；
   - `dataQuality` 计数正确。
5. 空值：
   - 0 报告 → `average` / `median` / `max` 为 `null`；
   - 0 Finding → `highSeverityRatio` 为 `null`；
   - 0 Comment → `reviewsWithInlineCommentsRatio` 为 `null`。
6. 中位数：
   - 奇数个报告；
   - 偶数个报告（中间两数平均）；
   - 含 0 Finding 的报告。
7. 未知枚举：
   - `MYSTERY` → `UNKNOWN` category；
   - `UNKNOWN` severity → `UNKNOWN`；
   - 未知 `ai_status` → `UNKNOWN`；
   - 不抛异常，不丢计数。
8. 趋势：
   - 无数据 → `points=[]`、`hasData=false`；
   - 有数据 → 零填充完整范围；
   - DAY 桶边界；
   - WEEK 周一开始；
   - 首尾部分周；
   - Finding 不一致报告只影响 findingCount，不影响 reviewCount。

### 11.2 后端 Controller 测试

`DashboardStatisticsControllerTest`（`@WebMvcTest` + Mock Service）：

1. `/overview` 参数绑定：owner / repo / prNumber / statuses / createdFrom / createdTo / granularity。
2. `/reviews` 参数绑定：page / size / sort / direction。
3. 错误映射：
   - 非法分页 → 400 `invalid_pagination`；
   - 非法筛选 → 400 `invalid_filter`；
   - 非法粒度 → 400 `invalid_granularity`；
   - 非法排序 → 400 `invalid_sort`；
   - 超范围 → 400 `invalid_range`；
   - 数据完整性异常 → 500 `internal_error`。
4. 不读取 `X-Internal-Token`，不要求内部 token。
5. 默认值：page=1、size=20、granularity=DAY。

### 11.3 后端 MySQL 集成测试

使用现有 Testcontainers 模式（`mysql-it` profile，`@Tag("mysql-it")`）。

注意：现有 `ReviewHistoryMySqlTestBase` **故意不创建 `review_task`**，并 mock 了 `ReviewTaskService`。统计 SQL 需要 `JOIN review_task`，因此需要新的测试基类：

```text
ReviewStatisticsMySqlTestBase
├─ 创建 review_task 表（测试专用 DDL）
├─ 创建 review_report / review_finding / review_comment
├─ 不创建 review_result_delivery（统计不读取）
└─ 使用真实 Repository + Service
```

测试数据至少覆盖：

1. 正常报告：1 报告 / 2 Finding / 1 Comment。
2. 零 Finding 报告。
3. Finding 数不一致报告：声明 3、实际 2。
4. Comment 数不一致报告：声明 2、实际 1。
5. 未知 category / severity。
6. 未知 `ai_status`。
7. 多份报告跨多个日期（趋势分桶）。
8. 无报告的任务（确保不被统计）。
9. 边界时间：`createdFrom` 当天 00:00:00、`createdTo` 当天 23:59:59.999999。
10. 筛选组合：owner + repo + prNumber + status + 时间段。

断言：

- summary 每个计数；
- category / severity 顺序与 `UNKNOWN` 桶；
- trend 桶数与零填充；
- dataQuality 排除数；
- 逐 Review 表的 actual/declared 与一致性标记；
- 排序白名单。

### 11.4 安全测试

1. 非 loopback 请求 `/api/dashboard/statistics/overview` → 403。
2. `X-Forwarded-For: 127.0.0.1` 不能绕过。
3. 编码路径（例如 `%2F`、matrix parameter）仍被识别为 Dashboard 请求；现有 `DashboardLocalAccessFilterTest` 已覆盖机制，新增路径只需确认匹配。
4. 响应不包含 token / SQL / 堆栈。
5. SQL 注入字符串作为 owner/repo → 按字面值查询，不改变 SQL 结构。

### 11.5 前端测试

见 8.9。额外要求：

- 空数据：不渲染趋势 SVG，显示 Empty。
- 部分数据：显示 Warning，数字与 `dataQuality` 一致。
- 未知枚举：显示“未知”，不崩溃。
- 比例 null：显示 `—`，不显示 `0%`。
- 请求竞态：快速切换筛选，旧响应不覆盖新响应。
- 分页：切换筛选后回到第 1 页。
- 时区：显示应用时区说明，不按浏览器时区转换。

### 11.6 验收测试

使用 `codesentinel_accept_1123b`：

1. 启动后端并指向验收库（通过环境变量，不修改 `application.yml`）。
2. 请求 `/api/dashboard/statistics/overview`，逐项核对：
   - `reviewCount=6`；
   - `findingStatsReviewCount=5`；
   - `findingCount=48`；
   - `averageFindingsPerReview=9.6`；
   - `medianFindingsPerReview=1.0`；
   - `maxFindingsInReview=45`；
   - `highSeverityFindingCount=19`；
   - `highSeverityRatio≈0.3958`；
   - `commentStatsReviewCount=5`；
   - `reviewsWithFindings=4`；
   - `reviewsWithFindingsRatio=0.8`；
   - `publishedInlineCommentCount=25`；
   - `reviewsWithInlineComments=1`；
   - `reviewsWithInlineCommentsRatio=0.2`；
   - `summaryCommentIdPresentCount=3`；
   - 发布状态 / AI 状态分布；
   - `dataQuality` 排除数与 `unknownCategoryFindingCount=1`、`unknownSeverityFindingCount=1`、`unknownAiStatusReportCount=1`。
3. 请求 `/reviews`，核对 2003 的 `3/2`、2005 的 `2/1` 徽标。
4. 验证 2006 的 `MYSTERY` / `UNKNOWN` 进入 UNKNOWN 桶。
5. 验证 2004 的损坏 `references_json` 不影响统计（统计不读取它）。
6. 验证 1008 无报告不出现在统计中。
7. 验证空范围（例如 2020 年）→ 200、0 计数、空趋势、Empty 页面。
8. 验证非法参数 → 400 对应错误码。
9. 验证非 loopback → 403。
10. 跑前端 `type-check`、`test:unit`、`lint:check`、`build`。
11. 跑后端 `mvn test` 与 `mvn -Pmysql-it verify`（如环境可用）。

### 11.7 不属于本阶段测试的内容

- 不测试 GitHub API（统计不调用）。
- 不测试 Python Agent（统计不调用）。
- 不测试自动修复 / 自动评论（不属于本阶段）。
- 不做大规模压测；当前数据量不足以支撑有意义的基准。记录 `EXPLAIN` 即可。

---

## 12. 子阶段拆分

### 11.2.4-A：调查（本报告）

产出：

- 本报告；
- 明确的数据口径、不可靠指标、API/Repository/前端方案；
- 未决问题清单。

完成标准：

- 不修改任何既有文件；
- 所有结论有代码/数据库证据；
- 用户确认关键口径。

### 11.2.4-B1：后端只读统计 API

范围：

- `ReviewStatisticsRepository`
- `ReviewStatisticsService`
- DTO records
- `DashboardStatisticsController`
- 错误码与异常
- 单元测试 + Controller 测试 + MySQL IT

不包含：

- 前端页面；
- 数据库索引/DDL；
- Python / GitHub / LLM 改动；
- 缓存。

完成标准：

- 两个接口可用；
- 验收库数字与 SQL 对齐；
- 空数据、非法参数、非 loopback、未知枚举、部分数据均有测试；
- `mvn test` 通过；
- `mvn -Pmysql-it verify` 通过（如环境允许）。

### 11.2.4-B2：前端 Insights 页面

范围：

- `/insights` 路由与侧边栏；
- 筛选栏、Summary cards、分布条、SVG 趋势图、逐 Review 表；
- Loading / Empty / Error / Partial data 状态；
- 前端 API client、类型、格式化工具；
- Vitest 测试。

不包含：

- 新依赖（Pinia / ECharts / Chart.js）；
- 首页重构；
- CSV 导出；
- 自动刷新 / WebSocket；
- 详情页改动（除必要的链接禁用逻辑）。

完成标准：

- `type-check`、`test:unit`、`lint:check`、`build` 通过；
- 空数据与部分数据状态正确；
- 无新依赖；
- 页面在窄屏可用；
- 不按浏览器时区错误转换时间。

### 11.2.4-C：验收与文档

范围：

- 使用 `codesentinel_accept_1123b` 做端到端验收；
- 记录实际数字、`EXPLAIN`、错误码、截图（如需要）；
- 更新 `docs/DEVELOPMENT_STATUS.md`（仅在用户批准后）；
- 输出验收报告。

完成标准：

- 第 11.6 节全部通过；
- 已知限制与未决问题记录完整；
- 生产空库状态被明确说明；
- 不把验收数据当成生产数据。

---

## 13. 风险

| 风险 | 影响 | 概率 | 缓解 |
|---|---|---|---|
| 把声明计数当真，统计出“完整”的假象 | 高 | 中 | 一致性闸门；`dataQuality`；排除不完整报告；测试 2003/2005 |
| 时区处理错误，趋势整体偏移 8 小时 | 高 | 中 | 应用本地时间语义；不使用 SQL `NOW()`；响应返回 `zoneId`；固定时区测试 |
| 未知枚举导致 500 或数据丢失 | 中 | 中 | `UNKNOWN` 桶；不抛异常；测试 `MYSTERY` / `UNKNOWN` |
| 报告缺少 `review_task` 导致整页 500 | 中 | 低 | 与现有列表一致，fail closed + 日志；验收库确认无孤儿报告 |
| 大范围查询全表扫描 | 中 | 低（当前） | 默认 30 天；最大 366 天；记录 EXPLAIN；后续按阈值加索引 |
| 原生 SQL 与 MySQL 方言绑定，测试不足 | 高 | 中 | Testcontainers MySQL IT；参数绑定；不拼 SQL |
| 前端把 Finding 数当“代码质量”排名 | 高 | 高 | 文案明确“计数不是质量”；不提供质量分数；不提供仓库排名 |
| 验收数据被误认为生产趋势 | 中 | 高 | 报告和 UI 明确标注数据源；生产库 0 报告 |
| 详情链接对不完整报告返回 409 | 低 | 中 | 表格显示“不完整”并禁用详情链接 |
| 统计页范围蔓延到 RAG / 自定义规则 / 导出 | 中 | 中 | 本阶段明确不做；子阶段边界 |
| 新增依赖导致构建/维护成本 | 中 | 低 | 不引入 Pinia/ECharts；原生 SVG/CSS |
| 缓存导致“刚审查完数字没变” | 中 | 低 | MVP 不做缓存 |
| 生产历史任务永远不出现在统计中 | 中 | 高 | UI 说明口径；如用户要求，单独做 backfill，不在统计阶段偷解析 delivery |

---

## 14. 未决问题

以下问题需要用户确认后再进入 11.2.4-B。每项都给出推荐方案。

### Q1. 页面放在哪里？

- **推荐**：新增 `/insights` 独立页面，侧边栏新增 “Review Insights”。
- 备选：嵌入现有 `/`，在 DashboardView 下方加统计区。
- 不建议：替换现有 `/`。

理由：统计页有独立筛选、时间范围、分页和空状态；独立路由更清晰，也不影响 Phase 11.1 首页。

### Q2. 不完整报告如何处理？

- **推荐**：报告级指标包含；Finding 指标排除 Finding 不一致的报告；Comment 指标排除 Comment 不一致的报告；`dataQuality` 明确显示排除数，UI 显示警告。
- 备选：全部包含，用声明值补齐（**不推荐**，会伪造数据）。
- 备选：整页 409 / 500（**不推荐**，一份坏报告会让整个统计不可用）。

### Q3. 默认时间范围和最大范围？

- **推荐**：默认最近 30 个自然日（含今天）；最大 366 个自然日；超过返回 `invalid_range`。
- 备选：默认全部历史（**不推荐**，无界扫描，且生产库为空时没有意义）。
- 备选：默认 7 天（可能样本太少）。

### Q4. 是否默认包含 DEGRADED / FAILED 报告？

- **推荐**：包含。DEGRADED 表示 AI 结果降级，FAILED 表示发布失败，但 Finding 仍然可能存在；排除会低估 Finding。UI 显示 AI / 发布状态分布，用户可筛选。
- 备选：默认只含 COMPLETED + PUBLISHED（**不推荐**，会隐藏真实数据）。
- 需要确认：产品上是否希望“只看成功审查”。

### Q5. 是否展示置信度、Rule ID、文件热点？

- **推荐**：MVP 不展示。置信度自报未校准；Rule ID 可空且不统一；文件路径高噪声且涉及代码结构暴露。
- 备选：后续作为“高级指标”单独设计，并明确不可比。
- 需要确认：是否有实际使用场景。

### Q6. 未知枚举如何展示？

- **推荐**：`UNKNOWN` 桶，灰色，文案“未知（原值）”；不丢弃，不抛错。
- 备选：过滤掉未知值（**不推荐**，会少报）。
- 备选：整页报错（**不推荐**，验收库 2006 会直接打挂页面）。

### Q7. 时间显示用应用本地时间还是 UTC？

- **推荐**：应用本地时间（当前 `Asia/Shanghai`），响应返回 `zoneId`，UI 标注。理由：数据库存的就是应用本地墙钟，转换为 UTC 会改变历史语义。
- 备选：统一 UTC（需要改写入语义 + 数据迁移，超出本阶段）。

### Q8. 是否需要为生产历史任务做 backfill？

- **推荐**：本阶段不做。统计页真实状态就是空；先让新 Review 走通历史写入。
- 如果用户要求历史数据：单独开一个 backfill 任务，复用 `ReviewHistoryService.ensureHistory`，从 `review_result_delivery` 幂等补写；不要在统计 Repository 里临时解析 `findings_json`。
- 需要确认：是否接受“上线初期统计为空”。

### Q9. 是否需要 CSV 导出 / 定时报表？

- **推荐**：不做。属于后续 Dashboard 功能，不是 Finding 统计闭环的一部分。
- 需要确认：是否有离线分析需求。

### Q10. 是否需要在首页放摘要卡片？

- **推荐**：B2 先做 `/insights`；首页摘要卡片作为后续可选增强，复用 `/overview`。
- 备选：B2 同时在首页放 4 个卡片（会增加首页改动和测试范围）。

---

## 15. 实施建议

### 15.1 推荐的最小可行范围

如果用户确认 Q1–Q4、Q6、Q7，建议按以下顺序实施：

```text
11.2.4-B1  后端
  1. DTO records
  2. ReviewStatisticsRepository（原生 SQL + 投影）
  3. ReviewStatisticsService（范围、粒度、一致性、聚合）
  4. DashboardStatisticsController（两个 GET）
  5. 单元 / Controller / MySQL IT
  6. 用验收库手工核对数字

11.2.4-B2  前端
  1. types/statistics.ts + api/statistics.ts
  2. 格式化工具 + SVG 几何工具 + 单测
  3. StatCard / DistributionBars / TrendChart
  4. ReviewComparisonTable
  5. InsightsView + 路由 + 侧边栏
  6. 状态与竞态测试

11.2.4-C  验收
  1. 验收库端到端
  2. 空库 / 空范围 / 非法参数 / 403
  3. EXPLAIN 基线
  4. 文档与验收报告
```

### 15.2 推荐的文件清单

后端（新增）：

```text
backend/spring-service/src/main/java/cn/codesentinel/statistics/
├── ReviewStatisticsRepository.java
├── ReviewStatisticsService.java
└── dto/
    ├── ReviewStatisticsOverviewResponse.java
    ├── ReviewStatisticsSummary.java
    ├── ReviewStatisticsTrend.java
    ├── ReviewStatisticsTrendPoint.java
    ├── ReviewStatisticsDataQuality.java
    ├── ReviewStatisticsItem.java
    └── ReviewStatisticsRange.java

backend/spring-service/src/main/java/cn/codesentinel/controller/
└── DashboardStatisticsController.java
```

测试（新增）：

```text
backend/spring-service/src/test/java/cn/codesentinel/statistics/
├── ReviewStatisticsServiceTest.java
├── ReviewStatisticsMySqlTestBase.java
└── ReviewStatisticsMySqlIT.java

backend/spring-service/src/test/java/cn/codesentinel/controller/
└── DashboardStatisticsControllerTest.java
```

前端（新增）：

```text
frontend/src/views/InsightsView.vue
frontend/src/components/insights/InsightsFilterBar.vue
frontend/src/components/insights/StatCard.vue
frontend/src/components/insights/DistributionBars.vue
frontend/src/components/insights/TrendChart.vue
frontend/src/components/insights/ReviewComparisonTable.vue
frontend/src/composables/useStatisticsOverview.ts
frontend/src/composables/useReviewStatistics.ts
frontend/src/utils/statistics-format.ts
frontend/src/utils/trend-geometry.ts
frontend/src/api/statistics.ts
frontend/src/types/statistics.ts
```

需要修改的既有文件（最小）：

```text
frontend/src/router/index.ts          // 新增 /insights 路由
frontend/src/components/SidebarNav.vue // 新增菜单项与 activePath 分支
frontend/src/api/index.ts             // 导出 statistics API
```

不修改：

```text
docs/DEVELOPMENT_STATUS.md
docs/reports/Phase10_*.md
docs/reports/Phase11_2_3_*.md
backend/.../review/ReviewHistoryQueryService.java
backend/.../review/ReviewHistoryFilter.java
backend/.../security/DashboardLocalAccessFilter.java
backend/spring-service/src/main/resources/db/*.sql
frontend/package.json
```

### 15.3 验收闸门

进入 11.2.4-B2 前：

- [ ] B1 接口在验收库返回正确数字；
- [ ] 2003 / 2005 被正确排除并计入 dataQuality；
- [ ] 2006 的未知枚举进入 UNKNOWN；
- [ ] 空范围返回 200 + 空趋势；
- [ ] 非法参数返回正确 400；
- [ ] 非 loopback 返回 403；
- [ ] `mvn test` 通过；
- [ ] `mvn -Pmysql-it verify` 通过（如环境允许）。

进入 11.2.4-C 前：

- [ ] 前端 `type-check`、`test:unit`、`lint:check`、`build` 通过；
- [ ] 空数据 / 部分数据 / 错误 / 加载状态均有测试；
- [ ] 无新依赖；
- [ ] 窄屏可用；
- [ ] 时间语义标注正确；
- [ ] 运行 `git status`，确认改动范围符合预期。

### 15.4 本报告没有做的事

- 没有修改任何源码、配置、依赖或数据库；
- 没有执行 DDL/DML；
- 没有执行 Git 写操作；
- 没有创建 11.2.4-B 的任何实现；
- 没有修改 `docs/DEVELOPMENT_STATUS.md`；
- 没有把验收库数据写入生产库。

---

## 附录 A：验收库数据核对 SQL

以下 SQL 仅用于验收核对，不写入任何数据。

```sql
-- 报告声明 vs 实际
SELECT
    r.id,
    r.task_id,
    r.ai_status,
    r.publish_status,
    r.finding_count AS declared_findings,
    (SELECT COUNT(*) FROM review_finding f WHERE f.report_id = r.id) AS actual_findings,
    r.published_comment_count AS declared_comments,
    (SELECT COUNT(*) FROM review_comment c WHERE c.report_id = r.id) AS actual_comments,
    r.created_at
FROM review_report r
ORDER BY r.id;

-- Finding 分布
SELECT category, COUNT(*) FROM review_finding GROUP BY category;
SELECT severity, COUNT(*) FROM review_finding GROUP BY severity;

-- 发布状态 / AI 状态
SELECT publish_status, COUNT(*) FROM review_report GROUP BY publish_status;
SELECT ai_status, COUNT(*) FROM review_report GROUP BY ai_status;

-- 评论分布
SELECT report_id, COUNT(*) FROM review_comment GROUP BY report_id;

-- 无报告的任务
SELECT t.id, t.status, t.created_at
FROM review_task t
LEFT JOIN review_report r ON r.task_id = t.id
WHERE r.id IS NULL;

-- 时间范围查询计划
EXPLAIN SELECT r.id
FROM review_report r
JOIN review_task t ON t.id = r.task_id
WHERE r.created_at >= '2026-10-01 00:00:00'
  AND r.created_at <= '2026-11-30 23:59:59'
ORDER BY r.created_at DESC, r.id DESC;
```

当前预期结果（2026-11-13 实测）：

```text
report 2001: 45/45, 25/25
report 2002: 0/0, 0/0
report 2003: 3/2, 0/0
report 2004: 1/1, 0/0
report 2005: 1/1, 2/1
report 2006: 1/1, 0/0
task 1008: 无报告
```

## 附录 B：证据文件

| 文件 | 用途 |
|---|---|
| `backend/spring-service/src/main/resources/db/review_history.sql` | `review_report` / `review_finding` / `review_comment` 的批准 DDL |
| `backend/spring-service/src/main/java/cn/codesentinel/task/ReviewReport.java` | 报告字段、生命周期、发布结果更新 |
| `backend/spring-service/src/main/java/cn/codesentinel/task/ReviewFinding.java` | Finding 字段、`(report_id, ordinal)` 唯一键、`category` / `severity` 为 String |
| `backend/spring-service/src/main/java/cn/codesentinel/task/ReviewComment.java` | 已发布 Inline Comment 元数据 |
| `backend/spring-service/src/main/java/cn/codesentinel/task/ReviewTask.java` | owner / repo / PR / status / commit |
| `backend/spring-service/src/main/java/cn/codesentinel/task/ReviewHistoryService.java` | 报告与 Finding 非单事务写入、幂等补写 |
| `backend/spring-service/src/main/java/cn/codesentinel/review/ReviewHistoryQueryService.java` | 声明计数一致性闸门、409 语义 |
| `backend/spring-service/src/main/java/cn/codesentinel/review/ReviewHistoryListService.java` | 报告为根、`review_task` 过滤、固定排序 |
| `backend/spring-service/src/main/java/cn/codesentinel/review/ReviewHistoryFilter.java` | 复用筛选语义 |
| `backend/spring-service/src/main/java/cn/codesentinel/task/ReviewReportRepository.java` | 现有 `searchHistory` 查询 |
| `backend/spring-service/src/main/java/cn/codesentinel/controller/DashboardReviewController.java` | BFF 错误码与参数风格 |
| `backend/spring-service/src/main/java/cn/codesentinel/controller/DashboardReviewDetailController.java` | 详情 BFF 与 409 |
| `backend/spring-service/src/main/java/cn/codesentinel/security/DashboardLocalAccessFilter.java` | loopback 边界 |
| `backend/spring-service/src/main/resources/application.yml` | 无时区配置、无 forwarded headers |
| `backend/spring-service/pom.xml` | 无 JdbcTemplate 先例、Testcontainers 测试依赖 |
| `frontend/src/router/index.ts` | 现有路由 |
| `frontend/src/components/SidebarNav.vue` | 现有导航 |
| `frontend/src/types/api.ts` | 现有类型与 `ReviewPage<T>` |
| `frontend/src/api/index.ts` | 现有 API 导出 |
| `frontend/package.json` | 无 Pinia / ECharts / 图表库 |

---

## 附录 C：本报告的调查边界声明

1. 本报告没有从设计文档推断数据库结构；所有表、列、索引、行数均来自实际 MySQL 容器。
2. 本报告没有把验收库数据当作生产数据；所有示例数字均明确标注来源。
3. 本报告没有把 `review_result_delivery` 的 JSON 作为统计事实来源。
4. 本报告没有建议执行 PR 代码、调用 GitHub API 或调用 LLM。
5. 本报告没有修改任何既有文件；唯一新增文件是本报告。
6. 报告中的 API、DTO、SQL 形态是设计建议，不是已实现代码；11.2.4-B 开始前仍需用户确认第 14 节的关键问题。
