# Phase 11.2.3-A 调查报告 — Review Detail 页面技术调查与实施计划

> 执行日期：2026-11-12  
> 分支：`phase11/dashboard`  
> HEAD：`27e3a41161cfa86ee2956ba0b3626a2bcc71eec7`  
> 阶段：Phase 11.2.3-A（只读调查与实施计划）  
> 性质：本阶段不修改源码、配置、依赖或数据库，只新增本报告。  
> 结论：**可以进入 Phase 11.2.3-B，未发现需要先修改 Phase 10 API、安全过滤器或数据库结构的阻塞问题。**

---

## 1. 调查结论

### 1.1 总体结论

Review Detail 页面可以通过现有 Spring Boot 服务端能力实现，但**浏览器不能直接调用 Phase 10 的详情 API**：

```text
GET /api/reviews/{taskId}
GET /api/reviews/{taskId}/findings
GET /api/reviews/{taskId}/comments
```

这三个接口要求 `X-Internal-Token`，属于服务间只读 API。浏览器既不能获得该令牌，也不能把令牌存入 localStorage、sessionStorage、Cookie 或前端配置。

因此推荐新增一组同源、只读的 Dashboard BFF：

```text
GET /api/dashboard/reviews/{taskId}
GET /api/dashboard/reviews/{taskId}/findings
GET /api/dashboard/reviews/{taskId}/comments
```

BFF 直接复用 `ReviewHistoryQueryService` 和现有 DTO，不做 HTTP loopback 自调用，不复制查询逻辑，不修改 Phase 10 接口和安全边界。

### 1.2 关键判断

| 判断 | 结论 |
|---|---|
| 是否需要新的数据库字段 | **不需要** |
| 是否需要修改 Phase 10 API | **不需要** |
| 是否需要修改 `DashboardLocalAccessFilter` | **不需要**，`/api/dashboard/**` 已覆盖新路径 |
| 是否需要 Dashboard BFF | **需要**，否则浏览器无法安全取得详情 |
| 是否可以通过浏览器直连 Phase 10 API | **禁止** |
| 是否可以通过 Spring 自己 HTTP 调用自己 | **不采用**，直接注入 Service |
| 是否已有 AI 摘要正文与风险等级 | **没有持久化**，页面不得伪造 |
| 是否已有失败/跳过的 Inline Comment | **没有通过查询 API 暴露**，不得当作已发布评论展示 |
| 是否已有前端 Review Detail 页面 | **没有** |
| 是否需要新增前端依赖 | **不需要** |
| 是否可以进入 11.2.3-B | **可以** |

### 1.3 推荐实现路径

```text
ReviewHistoryView
  └─ 点击 taskId
       ↓
/reviews/:taskId(\d+)
       ↓
ReviewDetailView
  ├─ GET /api/dashboard/reviews/{taskId}
  ├─ GET /api/dashboard/reviews/{taskId}/findings?page=&size=
  └─ GET /api/dashboard/reviews/{taskId}/comments?page=&size=
       ↓
DashboardReviewDetailController
       ↓
ReviewHistoryQueryService
       ↓
review_report / review_finding / review_comment
```

页面先加载 report，成功后并行加载 findings 与 comments。三个区域各自具备 Loading、Empty、Error、Retry，页面级额外处理 404、409、无效 task ID 和通用服务错误。

### 1.4 已知但不能在 11.2.3-B 解决的问题

1. **没有 AI 摘要正文、风险等级、整体审查结论。**  
   Phase 10 的 `ReviewResultRequest` 明确不转发 Python 的自由格式 `report` 字典，`review_report` 只保存状态、计数、`summary_comment_id` 和时间。详情页必须显示“详细摘要未持久化”，不能编造摘要或风险等级。

2. **没有 Inline Comment 正文和逐项发布状态。**  
   `review_comment` 只保存成功发布的评论定位信息；失败与跳过项留在 `review_result_delivery.publish_outcome_json`，当前查询 API 不暴露。详情页只能展示“已成功发布的 Inline Comments”，不能展示失败/跳过项，也不能展示评论正文。

3. **没有 PR 标题、作者、分支、PR URL。**  
   当前结构化历史只保存 `owner`、`repo`、`prNumber`、`commitSha`。

这些是数据边界，不是前端实现缺陷。若确实需要，应另立阶段评估 Phase 10 契约或数据库变更，不能在 11.2.3-B 内擅自扩展。

---

## 2. 调查范围、依据与只读声明

### 2.1 已阅读文档

- `README.md`
- `docs/PROJECT_DESIGN.md`
- `docs/DEVELOPMENT_WORKFLOW.md`
- `docs/DEVELOPMENT_STATUS.md`
- `frontend/README.md`
- `docs/reports/Phase11_2_2_B_Report.md`
- `docs/reports/Phase11_2_2_B_1_Report.md`

### 2.2 已检查代码

后端：

- `controller/ReviewHistoryController.java`
- `controller/DashboardReviewController.java`
- `review/ReviewHistoryQueryService.java`
- `review/ReviewHistoryListService.java`
- `review/ReviewReportResponse.java`
- `review/ReviewFindingResponse.java`
- `review/ReviewCommentResponse.java`
- `review/ReviewPageResponse.java`
- `review/ReviewHistoryError.java`
- `review/ReviewHistoryFilter.java`
- `review/ReviewHistoryNotFoundException.java`
- `review/ReviewHistoryIncompleteException.java`
- `review/ReviewHistoryDataIntegrityException.java`
- `review/InvalidReviewHistoryPaginationException.java`
- `task/ReviewTask.java`
- `task/ReviewTaskService.java`
- `task/ReviewReport.java`
- `task/ReviewFinding.java`
- `task/ReviewComment.java`
- `task/ReviewResultRequest.java`
- `security/DashboardLocalAccessFilter.java`
- `security/InternalTokenMatcher.java`
- `resources/application.yml`
- `controller/DashboardReviewControllerTest.java`
- `controller/ReviewHistoryControllerTest.java`
- `review/ReviewHistoryQueryServiceTest.java`
- `review/ReviewHistoryListServiceTest.java`
- `security/DashboardLocalAccessFilterTest.java`
- `security/DashboardLocalAccessFilterTomcatTest.java`

前端：

- `src/router/index.ts`
- `src/api/client.ts`
- `src/api/review-history.ts`
- `src/api/index.ts`
- `src/types/api.ts`
- `src/utils/api-error.ts`
- `src/views/ReviewHistoryView.vue`
- `src/views/NotFoundView.vue`
- `src/layouts/DashboardLayout.vue`
- `src/components/SidebarNav.vue`
- `src/__tests__/router.spec.ts`
- `src/__tests__/review-history-api.spec.ts`
- `src/__tests__/ReviewHistoryView.spec.ts`
- `src/__tests__/App.spec.ts`
- `src/__tests__/DashboardLayout.spec.ts`
- `package.json`
- `vite.config.ts`
- `components.d.ts`
- `frontend/.env.example`

### 2.3 只读声明

本阶段：

- 未修改任何 `.java`、`.ts`、`.vue`、`.css`、`.yml`、`pom.xml`、`package.json` 或数据库脚本。
- 未安装或升级依赖。
- 未启动或修改 MySQL 数据。
- 未执行 Git commit、push、merge、rebase、reset、checkout。
- 未修改 `docs/DEVELOPMENT_STATUS.md`。
- 仅新增本报告文件。

---

## 3. 后端现状：Phase 10 详情 API 与可复用能力

### 3.1 Phase 10 详情 API

`ReviewHistoryController` 当前提供：

| 方法 | 路径 | 鉴权 | 参数 | 成功响应 |
|---|---|---|---|---|
| GET | `/api/reviews/{taskId}` | `X-Internal-Token` | `taskId` | `ReviewReportResponse` |
| GET | `/api/reviews/{taskId}/findings` | `X-Internal-Token` | `taskId`、`page`、`size` | `ReviewPageResponse<ReviewFindingResponse>` |
| GET | `/api/reviews/{taskId}/comments` | `X-Internal-Token` | `taskId`、`page`、`size` | `ReviewPageResponse<ReviewCommentResponse>` |

默认分页：

```text
page = 1
size = 20
MAX_PAGE_SIZE = 100
```

排序：

```text
findings: ordinal ASC
comments: findingOrdinal ASC
```

错误语义：

| 条件 | HTTP | Body |
|---|---|---|
| 缺失或错误 `X-Internal-Token` | 401 | 空 |
| 令牌配置为空 | 401 | 空，所有请求拒绝 |
| task 不存在 | 404 | 空 |
| report 不存在 | 404 | 空 |
| findings/comments 实际行数与 report 计数不一致 | 409 | `{"error":"review_history_incomplete"}` |
| `references_json` 无法安全解析 | 500 | 空 |
| `page < 1`、`size < 1`、`size > 100` | 400 | `{"error":"invalid_pagination"}` |

Phase 10 Controller 对 task 不存在和 report 不存在使用同一个空 404，避免泄露资源存在性。

### 3.2 `ReviewHistoryQueryService` 的复用价值

`ReviewHistoryQueryService` 是只读服务，所有查询在一个 `REPEATABLE_READ` 只读事务中完成：

| 方法 | 读取内容 | 一致性检查 |
|---|---|---|
| `getReport(taskId)` | task、report | 检查 findings 与 comments 两项实际计数 |
| `getFindings(taskId, page, size)` | task、report、findings 分页 | 检查 findings 实际计数 |
| `getComments(taskId, page, size)` | task、report、comments 分页 | 检查 comments 实际计数 |

一致性不满足时抛出 `ReviewHistoryIncompleteException`，不会返回部分数据。

该 Service 是 Dashboard BFF 的最佳复用点：

- 不依赖 HTTP。
- 不读取 `review_result_delivery`。
- 不写数据库。
- 不暴露内部 Entity ID。
- 已有完整的 404 / 409 / 500 异常类型。
- 已有 DTO 与分页 Envelope。

### 3.3 现有 Dashboard BFF 模式

`DashboardReviewController` 已实现：

```text
GET /api/dashboard/reviews
```

特点：

- 不读取 `review.history.internal-token`。
- 不接收、不转发 `X-Internal-Token`。
- 直接调用 `ReviewHistoryListService`。
- 复用 Phase 10 `ReviewReportResponse` 与 `ReviewPageResponse`。
- 使用 `ReviewHistoryError` 返回安全错误码。
- 处理非法分页、非法筛选、参数类型错误和数据损坏。

`DashboardLocalAccessFilter` 对所有 `/api/dashboard/**` 请求做 TCP 对端 loopback 限制，不使用转发头。

### 3.4 为什么不采用其他方案

| 方案 | 不采用原因 |
|---|---|
| 浏览器直连 `/api/reviews/**` | 必须暴露内部令牌，违反安全边界 |
| 前端持有 `X-Internal-Token` | 令牌会进入浏览器内存/存储/网络面板，禁止 |
| Spring 自己 HTTP 调用 `/api/reviews/**` | 无意义 loopback，增加超时、错误映射和令牌管理，直接注入 Service 更简单 |
| 前端读取数据库/直连 MySQL | 架构禁止，且不受 loopback 边界保护 |
| 修改 Phase 10 API 去掉令牌 | 破坏既有服务间安全契约，禁止 |
| 把 Phase 10 Controller 改成浏览器接口 | 混淆服务间 API 与 Dashboard BFF 边界，禁止 |

---

## 4. 数据契约与展示边界

### 4.1 Report DTO：`ReviewReportResponse`

这是详情页基础信息的唯一数据来源，也是列表页当前使用的 DTO。

| 字段 | 类型 | 可空 | 含义 | 详情页用途 |
|---|---|---|---|---|
| `taskId` | `long` | 否 | Review task ID | 页面标题、返回/刷新 |
| `owner` | `string` | 否 | 仓库 owner | 仓库信息 |
| `repo` | `string` | 否 | 仓库名 | 仓库信息 |
| `prNumber` | `int` | 否 | Pull Request 编号 | PR 信息 |
| `commitSha` | `string` | 否 | 被审查提交 SHA | 提交信息 |
| `taskStatus` | `string` | 否 | `PENDING` / `RUNNING` / `COMPLETED` / `FAILED` | Task 状态标签 |
| `aiStatus` | `string` | 否 | `COMPLETED` / `DEGRADED` | AI 状态标签 |
| `publishStatus` | `string` | 否 | `PENDING` / `PUBLISHED` / `PARTIAL` / `FAILED` | GitHub 发布状态标签 |
| `findingCount` | `int` | 否 | Finding 总数 | 计数、分页总数参考 |
| `publishedCommentCount` | `int` | 否 | 已成功发布的 Inline Comment 数 | 计数、分页总数参考 |
| `summaryCommentId` | `Long` | **是** | PR Summary 评论 ID | 展示 ID 或 “Not available” |
| `publishedAt` | `LocalDateTime` | **是** | 至少一项确认发布的时间 | 展示或 “—” |
| `createdAt` | `LocalDateTime` | 否 | Report 创建时间 | 展示 |
| `updatedAt` | `LocalDateTime` | 否 | Report 最近更新时间 | 标注为 “Last updated” |

注意：

- `updatedAt` **不是**审查完成时间，不能写成 “Completed at”。
- `publishedAt` 为 `null` 不代表 review 没运行，只代表没有已确认发布项。
- `summaryCommentId` 为 `null` 表示当前结构化历史没有可用的 Summary Comment ID，不能断言“一定没有生成 Summary”。
- 三个状态字段语义不同，不能合并成一个 “status”。

### 4.2 Finding DTO：`ReviewFindingResponse`

| 字段 | 类型 | 可空 | 说明 |
|---|---|---|---|
| `ordinal` | `int` | 否 | 0-based 稳定序号 |
| `category` | `string` | 否 | 模型值：`BUG` / `SECURITY` / `PERFORMANCE` / `QUALITY` |
| `severity` | `string` | 否 | 模型值：`CRITICAL` / `HIGH` / `MEDIUM` / `LOW` / `INFO` |
| `confidence` | `Double` | 否 | 0.0 ~ 1.0 |
| `ruleId` | `string` | 否 | 规则 ID，可能为空字符串 |
| `title` | `string` | 否 | Finding 标题 |
| `filePath` | `string` | 否 | 文件路径 |
| `startLine` | `int` | 否 | 起始行 |
| `endLine` | `int` | 否 | 结束行 |
| `description` | `string` | 否 | 问题描述 |
| `reason` | `string` | 否 | 判断原因/证据 |
| `suggestion` | `string` | 否 | 修复建议 |
| `references` | `string[]` | 元素可空 | 引用列表，可能包含 `null` 元素 |

展示规则：

- `ordinal` 是 0-based；UI 若显示 “Finding #” 应使用 `ordinal + 1`，并在测试中固定这一映射。
- `references` 必须先过滤 `null`、空白元素再渲染；不能把 `null` 显示成字符串。
- `category` / `severity` 遇到未知值必须回退为普通标签并显示原值，不能崩溃。
- `confidence` 显示为百分比时使用安全格式化；不能产生 `NaN%`。
- 所有文本使用 Vue 插值或文本节点，禁止 `v-html`。

### 4.3 Comment DTO：`ReviewCommentResponse`

| 字段 | 类型 | 可空 | 说明 |
|---|---|---|---|
| `findingOrdinal` | `int` | 否 | 对应 Finding 的 0-based ordinal |
| `githubCommentId` | `Long` | **是** | GitHub comment ID；仅防御性“已发布但无 ID”场景为空 |
| `filePath` | `string` | 否 | 评论定位文件 |
| `startLine` | `int` | 否 | 起始行 |
| `endLine` | `int` | 否 | 结束行 |

关键边界：

- `review_comment` 只保存**成功发布**的 Inline Comment。
- Summary Comment 不在此列表中。
- 失败/跳过项不在 `review_comment` 中，当前 API 不提供。
- 没有评论正文、发布时间、逐项发布状态。
- `githubCommentId` 为 `null` 时显示 “ID unavailable”，不能显示成发布失败。

### 4.4 分页 Envelope

`ReviewPageResponse<T>`：

```json
{
  "items": [],
  "page": 1,
  "size": 20,
  "totalItems": 0,
  "totalPages": 0,
  "hasNext": false
}
```

前端不得依赖 Spring Data `Page` 的内部结构。分页参数由服务端处理，默认 `1 / 20`，最大 `100`。

### 4.5 当前不可用的数据

| 期望内容 | 是否存在 | 说明 |
|---|---|---|
| AI 摘要正文 | **否** | Python `report` 字典未进入 Java 持久化契约 |
| 风险等级 / 总体结论 | **否** | 未存储 |
| PR 标题、作者、分支、URL | **否** | 只保存 owner/repo/PR 编号/commit SHA |
| Inline Comment 正文 | **否** | `review_comment` 没有正文列 |
| 评论发布时间 | **否** | DTO 未暴露 |
| 失败/跳过的评论项 | **否** | 仅存在于 `publish_outcome_json`，查询 API 不暴露 |
| Finding 创建时间 | **否（DTO 未暴露）** | Entity 有 `created_at`，但 `ReviewFindingResponse` 不包含 |
| 按 severity/category 的聚合统计 | **否** | 只能通过拉取所有 Findings 推导，不能在大数据集上安全实现 |
| GitHub Summary/Comment URL | **否** | 未存储 URL |

因此 11.2.3-B **不得**：

- 生成或猜测摘要正文。
- 生成风险等级。
- 把 Summary Comment 的 ID 渲染成完整评论内容。
- 把失败/跳过评论补进 “Published comments”。
- 为了“数据更丰富”而修改 Phase 10 Schema。

---

## 5. Dashboard BFF 推荐方案

### 5.1 新增 Controller

推荐新增：

```text
backend/spring-service/src/main/java/cn/codesentinel/controller/DashboardReviewDetailController.java
```

不修改：

- `ReviewHistoryController`
- `DashboardReviewController`
- `ReviewHistoryQueryService`
- `ReviewHistoryListService`
- `DashboardLocalAccessFilter`
- `application.yml`
- 数据库脚本

Controller 直接构造器注入 `ReviewHistoryQueryService`。

### 5.2 Endpoint 映射

| 方法 | 路径 | Service 调用 | 成功响应 |
|---|---|---|---|
| GET | `/api/dashboard/reviews/{taskId}` | `getReport(taskId)` | `ReviewReportResponse` |
| GET | `/api/dashboard/reviews/{taskId}/findings` | `getFindings(taskId, page, size)` | `ReviewPageResponse<ReviewFindingResponse>` |
| GET | `/api/dashboard/reviews/{taskId}/comments` | `getComments(taskId, page, size)` | `ReviewPageResponse<ReviewCommentResponse>` |

默认参数：

```text
page = 1
size = 20
```

### 5.3 task ID 校验

路径变量建议使用 `String` 接收后显式解析，避免直接依赖 Spring 类型转换的错误语义：

```text
必须匹配数字
必须能解析为 long
必须 > 0
必须能由 long 表示
```

不合法时返回：

```text
HTTP 400
{"error":"invalid_task_id"}
```

实现上可以使用 Controller 内部的私有异常与 `@ExceptionHandler`，不新增公共异常类型。合法 task ID 再交给 `ReviewHistoryQueryService`。

### 5.4 分页校验

在调用 Service 前校验：

```text
page >= 1
1 <= size <= ReviewHistoryQueryService.MAX_PAGE_SIZE
```

不合法时返回：

```text
HTTP 400
{"error":"invalid_pagination"}
```

同时处理 `page=abc`、`size=abc`、整数溢出等 Spring 参数绑定错误，统一映射为 `invalid_pagination`。不得把 `IllegalArgumentException` 直接暴露成 500。

### 5.5 错误语义

| 条件 | HTTP | Body | 说明 |
|---|---|---|---|
| 非 loopback 请求 | 403 | 空 | 由 `DashboardLocalAccessFilter` 在 Controller 前拒绝 |
| task ID 非数字/非正数/溢出 | 400 | `{"error":"invalid_task_id"}` | 不进入 Service |
| 分页非法或参数类型错误 | 400 | `{"error":"invalid_pagination"}` | 不进入 Service |
| task 不存在 | 404 | `{"error":"review_not_found"}` | 与 report 缺失共用 |
| report 不存在 | 404 | `{"error":"review_not_found"}` | 不泄露具体缺失层级 |
| 历史计数不一致 | 409 | `{"error":"review_history_incomplete"}` | 不返回部分数据 |
| `references_json` 不可读等数据损坏 | 500 | `{"error":"internal_error"}` | 记录安全日志 |
| 其他未预期异常 | 500 | `{"error":"internal_error"}` | Controller 级兜底处理；不返回堆栈或内部消息 |

错误响应复用现有 `ReviewHistoryError`：

```java
public record ReviewHistoryError(String error) {
}
```

建议为 Controller 增加一个 `@ExceptionHandler(Exception.class)` 兜底，返回固定的 `internal_error`；更具体的异常处理器优先级更高。兜底处理器只记录安全日志，不把异常 message 写入响应。

不输出异常 message，不输出 SQL、Entity、令牌或内部路径。

### 5.6 不修改 Phase 10 与安全过滤器

- Phase 10 `/api/reviews/**` 保持原路径、令牌、状态码和空 404 语义。
- 新 BFF 不读取 `review.history.internal-token`。
- 新 BFF 不接收、不转发 `X-Internal-Token`。
- `DashboardLocalAccessFilter` 的 `DASHBOARD_NAMESPACE = /api/dashboard/**` 已覆盖全部新路径，无需改代码或测试。
- 不需要修改 `application.yml` 的 `forward-headers-strategy`。

### 5.7 为什么新增独立 Controller

- 列表 BFF 与详情 BFF 职责不同，独立文件更符合单一职责。
- 不需要为了三个详情接口改动已验收的列表 Controller。
- 共用同一个 loopback 过滤器与 URL 命名空间。
- 后续如果详情增加缓存、聚合或不同错误策略，不会污染列表接口。

---

## 6. 前端现状与复用方案

### 6.1 现有 Review History 页面

`frontend/src/views/ReviewHistoryView.vue` 已实现：

- 调用 `GET /api/dashboard/reviews`。
- 全部 8 个筛选条件。
- 服务端分页：`10 / 20 / 50 / 100`。
- 首次 Loading 骨架屏。
- 刷新/翻页时保留当前列表并显示 updating。
- 空状态、错误状态、Retry、Refresh。
- `AbortController` + `requestSequence` 防止竞态。
- `onBeforeUnmount` 取消未完成请求。
- 状态标签、日期格式化、null 占位。
- 表格 `row-key="taskId"`。

当前 task ID 只是文本：

```vue
<span class="task-id">#{{ row.taskId }}</span>
```

11.2.3-B 应改为指向详情页的 `RouterLink`，不改变行数据或其他列。

### 6.2 现有路由

`frontend/src/router/index.ts` 当前只有：

```text
/
/reviews
/:pathMatch(.*)*  -> not-found
```

尚未存在 Review Detail 路由。

已用当前 `vue-router@5.4.0` 验证：

```text
/reviews                         -> review-history
/reviews/7                       -> 可匹配数字详情路由
/reviews/missing-entry           -> not-found（保持现有行为）
/reviews/999999999999999999999   -> 可匹配数字路由，但超出安全整数，由页面拒绝
```

因此采用：

```ts
{
  path: 'reviews/:taskId(\\d+)',
  name: 'review-detail',
  component: () => import('@/views/ReviewDetailView.vue'),
  meta: { title: 'Review Detail' },
}
```

数字正则放在静态 `/reviews` 之后、catch-all 之前。这样：

- `/reviews/missing-entry` 仍然走 `not-found`。
- 现有 `App.spec.ts` 中的 not-found 断言无需改变语义。
- 不会把任意子路径误当成详情页。

### 6.3 导航高亮

`SidebarNav.vue` 当前只在 `route.name === 'review-history'` 时高亮 `/reviews`。

需要改为：

```text
route.name === 'review-history' || route.name === 'review-detail'
  -> '/reviews'
```

详情页仍属于 “Review History” 工作区，侧边栏保持高亮。

### 6.4 可复用的前端能力

| 能力 | 复用方式 |
|---|---|
| Axios 同源客户端 | 复用 `apiGet` / `http` |
| 错误归一化 | 复用 `ApiError`、`toApiError`、`getErrorMessage` |
| 分页 Envelope | 新增泛型 `ReviewPage<T>`，与现有 `ReviewHistoryPage` 兼容 |
| 状态标签颜色 | 提取共享展示 helper，列表与详情共用 |
| 日期/计数/null 占位 | 提取共享展示 helper |
| 布局 | 继续使用 `DashboardLayout` 与 `.page` / `.panel` 样式 |
| Loading/Empty/Error | 复用 Element Plus `el-skeleton`、`el-empty`、`el-button`、`el-tag` |
| 表格 | 复用 `el-table` / `el-table-column` |
| 分页 | 复用 `el-pagination` |

### 6.5 推荐新增/修改的前端类型

在 `src/types/api.ts` 中增加：

```ts
export type FindingCategory =
  | 'BUG'
  | 'SECURITY'
  | 'PERFORMANCE'
  | 'QUALITY'

export type FindingSeverity =
  | 'CRITICAL'
  | 'HIGH'
  | 'MEDIUM'
  | 'LOW'
  | 'INFO'

export interface ReviewFinding {
  ordinal: number
  category: FindingCategory
  severity: FindingSeverity
  confidence: number
  ruleId: string
  title: string
  filePath: string
  startLine: number
  endLine: number
  description: string
  reason: string
  suggestion: string
  references: Array<string | null>
}

export interface ReviewComment {
  findingOrdinal: number
  githubCommentId: number | null
  filePath: string
  startLine: number
  endLine: number
}

export interface ReviewPage<T> {
  items: T[]
  page: number
  size: number
  totalItems: number
  totalPages: number
  hasNext: boolean
}

export type ReviewHistoryPage = ReviewPage<ReviewHistoryItem>
export type ReviewDetailReport = ReviewHistoryItem
export type ReviewFindingPage = ReviewPage<ReviewFinding>
export type ReviewCommentPage = ReviewPage<ReviewComment>
```

说明：

- `category` / `severity` 按项目文档的模型值定义为 union；运行期仍需保留 `default` 回退，避免历史数据或未知值导致界面崩溃。
- `ReviewHistoryPage` 改为泛型别名，不改变运行时结构，不改变现有 API 响应。
- `ReviewDetailReport` 直接复用列表的 report 字段，避免复制 DTO。

### 6.6 推荐新增 API 模块

`frontend/src/api/review-detail.ts`：

```text
GET_REVIEW_DETAIL_ENDPOINT = '/api/dashboard/reviews'
getReviewDetail(taskId, signal)
getReviewFindings(taskId, { page, size }, signal)
getReviewComments(taskId, { page, size }, signal)
```

要求：

- 全部使用 `apiGet`。
- 全部接受 `AbortSignal`。
- 只使用同源相对路径。
- 不设置 `X-Internal-Token`。
- 不读取浏览器存储。
- 不在 API 层伪造分页默认值之外的字段。
- 在 `src/api/index.ts` 导出。

### 6.7 推荐共享展示 helper

新增：

```text
frontend/src/utils/review-display.ts
```

建议包含：

```text
TagType
formatDateTime
formatCount
formatSummaryComment
taskStatusType
aiStatusType
publishStatusType
severityType
categoryType
formatConfidence
formatLineRange
```

`ReviewHistoryView.vue` 改为导入已有同名的格式化/标签函数，删除本地重复实现；行为必须保持不变。

不提取分页状态 composable。findings 与 comments 是独立分页区块，强行抽象成一个通用 composable 会增加状态耦合和测试复杂度。

---

## 7. Review Detail 页面与交互设计

### 7.1 页面结构

```text
Back to review history                         Refresh
Review #123                                    [Task status]
owner/repo · PR #42 · Commit abc123...

┌─ Review information ──────────────┐ ┌─ AI review summary ─────────────┐
│ Repository                         │ │ AI status: COMPLETED / DEGRADED │
│ Pull request                       │ │ Stored findings: N              │
│ Commit SHA                         │ │ Publish status                  │
│ Task status / AI / Publish         │ │ Summary comment ID              │
│ Findings / Published comments      │ │ Narrative summary not stored    │
│ Published / Created / Last updated │ │                                 │
└────────────────────────────────────┘ └─────────────────────────────────┘

┌─ Findings ──────────────────────────────────────────────────────────────┐
│ Finding #1  [HIGH] [SECURITY]  Title                    Confidence 94% │
│ file/path.java L52–58                                                   │
│ [expand] Description / Reason / Suggestion / References                 │
│ ...                                                                     │
│ Pagination                                                              │
└─────────────────────────────────────────────────────────────────────────┘

┌─ Published inline comments ─────────────────────────────────────────────┐
│ Only comments confirmed published to GitHub are stored and shown.       │
│ Finding #1  file/path.java L52–58  GitHub comment ID 123456             │
│ ...                                                                     │
│ Pagination                                                              │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.2 基础信息展示

只展示真实存在的 DTO 字段：

| UI 项 | 来源 | null/特殊处理 |
|---|---|---|
| Review task | `taskId` | 无 |
| Repository | `owner/repo` | 显示完整值，CSS 截断时加 `title` |
| Pull request | `prNumber` | `PR #42` |
| Commit SHA | `commitSha` | `<code>` + `title`，允许换行/截断 |
| Task status | `taskStatus` | 状态标签 |
| AI status | `aiStatus` | 状态标签 |
| Publish status | `publishStatus` | 状态标签 |
| Findings | `findingCount` | 数字 |
| Published comments | `publishedCommentCount` | 数字 |
| Summary comment | `summaryCommentId` | `null` 显示 “Not available” |
| Published at | `publishedAt` | `null` 显示 “—” |
| Created at | `createdAt` | 日期格式化 |
| Last updated | `updatedAt` | **不得写成 Completed** |

### 7.3 AI Summary 区域

由于没有持久化摘要正文，区域必须采用“状态 + 明确不可用说明”的设计，而不是空着或编造文本。

建议内容：

```text
AI review summary
AI status: DEGRADED
Stored findings: 12
Publication: PARTIAL
Summary comment: #900 / Not available

Narrative summary and risk level are not stored in the structured review
history and are not shown here. Detailed findings are listed below.
```

这样可以：

- 满足详情页必须有 AI 摘要区域的产品要求。
- 不伪造任何审查结论。
- 让用户知道可以去 Findings 或 GitHub Summary 查看真实内容。

不得显示：

```text
"Overall risk: HIGH"          // 无数据
"Review passed"                // 无数据
"AI found 3 critical issues"   // 除非从真实 findingCount 推导，且不能声称 severity 分布
```

### 7.4 Findings 区域

使用 `el-table`，建议列：

- Finding 序号：`ordinal + 1`。
- Severity：`el-tag`，颜色映射：
  - CRITICAL / HIGH -> danger
  - MEDIUM -> warning
  - LOW / INFO -> info
  - 未知 -> info + 原值
- Category：`el-tag`，未知值回退。
- Finding：标题 + `ruleId`（若为空则不显示空括号）。
- Location：`filePath` + `formatLineRange(startLine, endLine)`。
- Confidence：百分比，例如 `94%`；异常值显示 “—”。
- Expand：展开后显示：
  - Description
  - Reason
  - Suggestion
  - References（过滤 null 与空白后逐条显示；无引用时显示 “No references”）

重要约束：

- 长文本只用文本插值。
- 不执行 finding 中任何内容。
- 不把 `ruleId` 当作 HTML。
- 不自动跳转外部引用 URL；当前只保存字符串，不保证是安全 URL。
- `references` 中的 `null` 必须被过滤。

### 7.5 Published Inline Comments 区域

必须与 Findings 明确分开，不能把 Comment 合并进 Findings 列表，也不能把 Finding 当作“已发布评论”。

建议标题：

```text
Published inline comments
```

副标题：

```text
Only comments confirmed published to GitHub are stored and shown.
Failed or skipped comments are not listed.
```

表格列：

- Finding：`findingOrdinal + 1`，与 Findings 的显示序号一致。
- Location：`filePath` + 行号范围。
- GitHub comment ID：`githubCommentId`，`null` 显示 “ID unavailable”。

不要添加：

- “Comment body” 列，因为数据不存在。
- “Failed/Skipped” 行，因为 API 不返回。
- “Published at” 列，因为 DTO 不返回。
- 伪造的 GitHub 链接，因为未保存 URL，且不应在前端拼接不可靠地址。

### 7.6 页面状态

页面级状态优先级：

```text
无效 task ID
  > 首次加载 Loading
  > 404 Not Found
  > 409 Incomplete
  > 通用 Error
  > Ready
```

#### 首次加载

- 显示页面级骨架屏。
- 先请求 report。
- report 成功后再并行请求 findings 与 comments。
- report 失败时不发子请求。

#### Invalid task ID

路由只匹配数字，但数字可能：

- 为 0。
- 超出 `Number.MAX_SAFE_INTEGER`。
- 无法安全解析。

页面显示 “Review not found”，不发送 API 请求，提供返回 Review History 的按钮。

#### 404

BFF 返回 `review_not_found`：

- 显示专用 Not Found 状态。
- 说明该 task 没有可用的结构化历史。
- 提供 “Back to review history”。
- 不显示 Retry 作为主要操作（重复请求无意义），可保留返回。

#### 409

BFF 返回 `review_history_incomplete`：

- 显示 “Review history is incomplete”。
- 说明存储计数与子记录不一致，当前不会展示部分数据。
- 提供 Retry。
- 不显示任何半成品 Findings/Comments。

#### 通用 Error

- 显示安全错误信息 + Retry。
- 不用 Axios 原始错误、堆栈或响应体。
- 网络错误、500、超时均走此状态。

#### 区块级状态

Findings 与 Comments 各自独立：

| 状态 | 表现 |
|---|---|
| Loading | 骨架屏或 updating 提示；首次加载不显示空表 |
| Empty | 该区块 Empty + 说明 |
| Error | 区块内错误 + Retry，只重试该区块 |
| 409 | 区块内 “history incomplete” + Retry |
| Ready | 表格 + 分页 |

一个区块失败不得清空另一个区块。

### 7.7 刷新、翻页与竞态

- 点击 Refresh：
  - 取消所有进行中的请求。
  - 重新请求 report。
  - report 成功后重新请求当前 findings/comments 页。
  - 请求期间保留已有内容，并显示 updating 状态。
- Findings 翻页只影响 findings。
- Comments 翻页只影响 comments。
- 改变某个区块的 page size 时，该区块页码重置为 1，另一个区块不受影响。
- 每个请求使用独立 `AbortController` 与 sequence；旧请求即使晚返回也不能覆盖新状态。
- `onBeforeUnmount` 取消所有请求。
- 路由从 `/reviews/7` 切到 `/reviews/8` 时，必须重置页面状态并重新加载；不能复用旧 review 数据。
- 不实现轮询、自动重试或无限重试。

### 7.8 空页处理

服务端可能返回：

```text
items = []
totalItems > 0
```

此时不能显示“完全没有数据”，应显示：

```text
No findings on this page
```

并保留分页，让用户返回有效页。Comments 同理。

### 7.9 响应式与可访问性

- 基础信息与 AI Summary 在宽屏双列，窄屏单列。
- 表格允许横向滚动，不强行压缩列宽。
- 长仓库名、commit SHA、文件路径加 `title`。
- Loading 区域使用 `role="status"`，错误使用 `role="alert"`。
- 表格外层在有请求时设置 `aria-busy`。
- 所有按钮有明确文本，不依赖纯图标。
- 只使用键盘可操作的 Element Plus 表格展开按钮。

---

## 8. 安全边界分析

### 8.1 浏览器可见面

11.2.3-B 后浏览器只新增访问：

```text
/api/dashboard/reviews/{taskId}
/api/dashboard/reviews/{taskId}/findings
/api/dashboard/reviews/{taskId}/comments
```

这些路径：

- 同源。
- 只读 GET。
- 由 `DashboardLocalAccessFilter` 限制为 loopback。
- 不需要、不接受、不返回内部令牌。

### 8.2 内部令牌

- `REVIEW_HISTORY_INTERNAL_TOKEN` 继续只用于服务间 `/api/reviews/**`。
- 新 BFF 不读取该配置。
- 前端不新增任何 `VITE_*` 令牌变量。
- 前端不写 localStorage / sessionStorage / Cookie。
- 浏览器 Network 面板中不会出现 `X-Internal-Token`。
- 若客户端恶意发送 `X-Internal-Token`，BFF 忽略该头，且不得在响应/日志中回显。

### 8.3 Loopback 边界

`DashboardLocalAccessFilter`：

- 使用 `request.getRemoteAddr()`。
- 忽略 `X-Forwarded-For`、`Forwarded`。
- `application.yml` 已设置 `server.forward-headers-strategy: none`。
- `/api/dashboard/**` 全部覆盖新路径。
- 非 loopback 请求在 Controller 前返回 403，Service 不会被调用。

已知边界：

- 这是个人本地 Dashboard 的应用层边界，**不是用户级身份认证**。
- 同主机反向代理也会表现为 loopback；如果未来暴露到公网，必须在代理层增加认证。
- 11.2.3-B 不改变这一点。

### 8.4 输入与输出安全

- task ID 显式校验，防止负数、0、溢出和类型转换异常。
- 分页显式校验，防止深层分页或非法 page size。
- 不拼接 SQL；全部通过现有 Repository。
- 错误响应不包含异常 message、SQL、Entity、堆栈、令牌或文件系统路径。
- 日志只记录安全标识（task ID、错误类别），不记录 token、代码正文或评论正文。
- 页面不使用 `v-html`。
- 不执行 PR 代码、不调用 GitHub API、不下载额外内容。
- 不把 `references` 当作可点击 URL，避免不可信 scheme。

### 8.5 边界不变式

11.2.3-B 完成后必须仍然满足：

```text
Phase 10 /api/reviews/** 的请求与响应契约不变
DashboardLocalAccessFilter 的代码与测试不变
浏览器不持有内部令牌
Dashboard BFF 不调用 GitHub
Dashboard BFF 不写数据库
Dashboard BFF 不执行用户代码
```

---

## 9. 可执行实施计划

### 9.1 文件清单

#### 后端新增

| 文件 | 内容 |
|---|---|
| `backend/spring-service/src/main/java/cn/codesentinel/controller/DashboardReviewDetailController.java` | 三个 BFF endpoint、task ID/分页校验、错误映射 |
| `backend/spring-service/src/test/java/cn/codesentinel/controller/DashboardReviewDetailControllerTest.java` | BFF 契约、错误、安全和 loopback 测试 |

#### 后端不修改

- `ReviewHistoryController.java`
- `DashboardReviewController.java`
- `ReviewHistoryQueryService.java`
- `ReviewHistoryListService.java`
- `ReviewHistoryError.java`
- 所有 Entity / Repository / DTO
- `DashboardLocalAccessFilter.java`
- `application.yml`
- `pom.xml`
- 数据库脚本

#### 前端新增

| 文件 | 内容 |
|---|---|
| `frontend/src/api/review-detail.ts` | 三个详情 API 调用 |
| `frontend/src/utils/review-display.ts` | 共享日期/状态/严重度/行号/置信度格式化 |
| `frontend/src/views/ReviewDetailView.vue` | 详情页面 |
| `frontend/src/__tests__/review-detail-api.spec.ts` | API 模块测试 |
| `frontend/src/__tests__/ReviewDetailView.spec.ts` | 页面状态、表格、分页、竞态测试 |

#### 前端修改

| 文件 | 内容 |
|---|---|
| `frontend/src/types/api.ts` | Finding/Comment/泛型分页/详情类型 |
| `frontend/src/api/index.ts` | 导出详情 API |
| `frontend/src/router/index.ts` | 数字详情路由 |
| `frontend/src/components/SidebarNav.vue` | 详情路由保持 Review History 高亮 |
| `frontend/src/views/ReviewHistoryView.vue` | task ID 改为 RouterLink；改用共享展示 helper |
| `frontend/src/__tests__/router.spec.ts` | 详情路由与 not-found 回归 |
| `frontend/src/__tests__/ReviewHistoryView.spec.ts` | taskId 链接断言 |
| `frontend/src/__tests__/App.spec.ts` | 详情路由与侧边栏集成断言（如采用） |

#### 明确不修改

- `frontend/components.d.ts`：计划只使用已有 `ElButton`、`ElTag`、`ElTable`、`ElTableColumn`、`ElPagination`、`ElSkeleton`、`ElEmpty`、`ElIcon`，不需要新增全局组件。
- `frontend/package.json` / `package-lock.json`：不新增依赖。
- 不引入 Pinia、ECharts、图表或 Phase 12 功能。
- `docs/DEVELOPMENT_STATUS.md`：不修改。
- `DashboardLayout.vue` 的 Phase 11.1 标签：不属于本阶段。

### 9.2 实施顺序

#### Step 1：后端 BFF

1. 新建 `DashboardReviewDetailController`。
2. 注入 `ReviewHistoryQueryService`。
3. 实现三个 GET 方法。
4. 实现 task ID 校验、分页校验、404/409/400/500 错误映射。
5. 新建 `DashboardReviewDetailControllerTest`。
6. 运行定向测试。

完成标准：

- 默认分页与自定义分页参数正确传递。
- 所有 DTO 字段原样返回。
- task/report 缺失 404 `review_not_found`。
- 计数不一致 409 `review_history_incomplete`。
- 非法 task ID 400 `invalid_task_id`。
- 非法分页 400 `invalid_pagination`。
- 数据损坏 500 `internal_error`。
- 未预期异常 500 `internal_error`，不泄露异常信息。
- 非 loopback 403 且 Service 零调用。
- 不需要 `X-Internal-Token`。
- 不泄露令牌或异常消息。

#### Step 2：前端类型与 API

1. 扩展 `types/api.ts`。
2. 新建 `api/review-detail.ts`。
3. 更新 `api/index.ts`。
4. 新建 `review-detail-api.spec.ts`。
5. 运行 API 定向测试与 type-check。

完成标准：

- 三个 URL 精确匹配 BFF。
- `page` / `size` 始终传递。
- `AbortSignal` 透传。
- 错误继续由统一 API client 归一化。
- 不引入任何令牌或存储逻辑。

#### Step 3：路由、导航与列表入口

1. 添加 `reviews/:taskId(\\d+)` 路由。
2. `SidebarNav` 对 `review-detail` 保持 `/reviews` 高亮。
3. `ReviewHistoryView` 的 task ID 改为 `RouterLink`。
4. 更新 router / list / App 测试。

完成标准：

- `/reviews/7` 解析到 `review-detail`。
- `/reviews/missing-entry` 仍是 `not-found`。
- 列表 task ID 可点击进入详情。
- 详情页侧边栏仍高亮 Review History。
- 返回列表可用。

#### Step 4：Review Detail 页面

1. 实现 task ID 解析与无效 ID 状态。
2. 实现 report-first 加载。
3. 实现 Findings/Comments 并行加载与独立状态。
4. 实现基础信息与 AI Summary 不可用说明。
5. 实现 Findings 表格、展开详情、引用过滤。
6. 实现 Published Comments 表格与 ID 缺失占位。
7. 实现独立分页、刷新、Retry、竞态取消。
8. 实现 404 / 409 / 通用 Error / Empty / Loading。
9. 编写 `ReviewDetailView.spec.ts`。

完成标准：

- 页面只展示真实数据。
- 不伪造 AI 摘要或风险等级。
- 失败/跳过评论不出现在 Published Comments。
- 三个请求互不覆盖。
- 路由切换和卸载会取消旧请求。
- 所有空态、错误态可重试（404 除外）。

#### Step 5：完整验证

后端：

```powershell
cd backend/spring-service
mvn -Dtest=DashboardReviewDetailControllerTest test
mvn -Dtest=ReviewHistoryQueryServiceTest,ReviewHistoryControllerTest,DashboardReviewControllerTest test
mvn test
```

说明：

- 本阶段只改 Controller 和测试，不改 Service/Entity/Repository/DDL，不强制要求新增 MySQL IT。
- 如果时间允许，可额外运行 `mvn -Pmysql-it verify` 作为回归，但不作为本阶段阻塞项。
- 必须确认 Phase 10 Controller 测试和 Dashboard 列表测试仍然通过。

前端：

```powershell
cd frontend
npm run type-check
npm run lint:check
npm run test:unit
npm run build
```

最后：

```powershell
cd <workspace-root>
git diff --check
git status --porcelain=v1
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
```

### 9.3 测试矩阵

#### 后端 Controller

| 用例 | 预期 |
|---|---|
| GET report 默认参数 | 200，全部字段映射 |
| GET findings 默认参数 | Service 收到 `1, 20` |
| GET comments 自定义 `page/size` | Service 收到对应值 |
| report 字段 JSON | 不包含 `reportId` 等内部字段 |
| task 不存在 | 404 `review_not_found` |
| report 不存在 | 404 `review_not_found` |
| findings 计数不一致 | 409 `review_history_incomplete` |
| comments 计数不一致 | 409 `review_history_incomplete` |
| `page=0` | 400 `invalid_pagination` |
| `size=101` | 400 `invalid_pagination` |
| `page=abc` | 400 `invalid_pagination` |
| taskId=`abc` | 400 `invalid_task_id` |
| taskId=`0` | 400 `invalid_task_id` |
| taskId 超出 long | 400 `invalid_task_id` |
| 无内部令牌 | 200，不要求鉴权 |
| 携带伪造内部令牌 | 200，响应不回显 |
| 非 loopback | 403，Service 零调用 |
| 编码/matrix dashboard 路径 + 非 loopback | 403 |
| 数据损坏 | 500 `internal_error` |
| 未预期运行时异常 | 500 `internal_error`，无异常 message |
| 异常 message 泄露 | 响应中不存在 |

#### 前端 API

| 用例 | 预期 |
|---|---|
| `getReviewDetail(7)` | `/api/dashboard/reviews/7` |
| findings 查询 | `/api/dashboard/reviews/7/findings` + `page/size` |
| comments 查询 | `/api/dashboard/reviews/7/comments` + `page/size` |
| AbortSignal | 透传给 `apiGet` |
| API 错误 | 保持 `ApiError` |

#### 前端页面

| 用例 | 预期 |
|---|---|
| 首次加载 | report 请求先发；成功后 findings/comments 并行 |
| report 失败 | 不发送子请求 |
| 404 | 专用 Not Found，不发子请求 |
| 409 | Incomplete 状态 + Retry |
| 通用错误 | Error + Retry |
| 基础信息 | 全部真实字段显示 |
| null 时间/Summary ID | 显示占位，不出现 `null` |
| AI Summary | 显示状态与不可用说明，不出现伪造风险等级 |
| Findings | 全部字段、严重度/类别标签、行号、置信度 |
| Findings 展开 | Description/Reason/Suggestion/References |
| references 含 null | 过滤后显示 |
| Comments | 只显示已发布元数据；`githubCommentId=null` 显示 ID unavailable |
| 失败/跳过 | 页面无对应行、无对应状态 |
| 独立分页 | 只请求对应区块，参数正确 |
| page size 变化 | 该区块页码重置为 1 |
| 空页但 totalItems>0 | 显示 “No ... on this page” 且保留分页 |
| 区块错误 | 另一区块仍正常显示 |
| 旧请求晚返回 | 不覆盖新请求数据 |
| 路由 7 -> 8 | 重新加载，不显示旧数据 |
| 卸载 | Abort 所有请求 |
| 非法数字 ID | 不发请求，显示 Not Found |
| 侧边栏 | 详情页仍高亮 Review History |
| 列表入口 | taskId 是详情链接 |

#### 回归

| 用例 | 预期 |
|---|---|
| `/reviews` | 列表行为不变 |
| `/reviews/missing-entry` | 仍为 Page not found |
| 列表筛选/分页/空页 | 全部既有测试通过 |
| `App.spec.ts` | 现有 not-found 断言不改变 |
| `components.d.ts` | 构建后无新增组件 |

### 9.4 Definition of Done

- [ ] 后端 BFF 三个 endpoint 可用。
- [ ] 只复用 Service，不通过 HTTP 回调自己。
- [ ] Phase 10 API 未修改。
- [ ] `DashboardLocalAccessFilter` 未修改。
- [ ] 浏览器不使用内部令牌。
- [ ] 页面展示真实 report、findings、published comments。
- [ ] 不伪造 AI 摘要、风险等级或审查结论。
- [ ] 失败/跳过评论不出现在 Published Comments。
- [ ] 404 / 409 / 400 / 500 / 空态 / 加载态 / 重试全部有测试。
- [ ] 三个请求具备取消与竞态保护。
- [ ] 无新增依赖。
- [ ] 无 `v-html`。
- [ ] Java 定向测试与完整单元测试通过。
- [ ] 前端 type-check、lint、test、build 通过。
- [ ] `git diff --check` 无新增 whitespace error。
- [ ] 未修改 `DEVELOPMENT_STATUS.md`。
- [ ] 未提交、未 push、未 merge。
- [ ] 输出 Phase 11.2.3-B 实施报告。

---

## 10. 风险、限制、验收与工作区状态

### 10.1 风险与限制

| 风险/限制 | 影响 | 应对 |
|---|---|---|
| 没有 AI 摘要正文与风险等级 | 无法展示完整“AI Summary” | 显示真实状态 + 明确不可用说明；不编造 |
| 没有评论正文 | 只能展示已发布评论元数据 | 明确说明；后续阶段再评估是否扩展契约 |
| 失败/跳过评论不可见 | 用户可能误以为所有评论都成功 | 文案明确 “Only comments confirmed published”；发布状态单独展示 |
| `summaryCommentId` 可为 null | 无法区分“没生成”还是“ID 未保存” | 使用中性的 “Not available” |
| `publishedAt` 可为 null | 没有确认发布时间 | 显示 “—”，不推导时间 |
| `updatedAt` 语义 | 容易被误写成完成时间 | 固定标注 “Last updated” |
| 没有 PR 标题/作者/URL | 基础信息不完整 | 只展示真实字段，不做猜测 |
| 不能按 severity/category 聚合 | 无法展示分布图/统计 | 不在本阶段实现；避免拉取全部 findings |
| 409 可能由瞬时状态触发 | 页面无法展示部分数据 | 专用 Incomplete 状态 + Retry，不展示半成品 |
| report 与子区块是独立只读事务 | 极端情况下可能看到不同瞬间的版本 | 各区块独立 409/错误处理；不合并部分数据 |
| Loopback 边界不是身份认证 | 同主机代理可绕过 | 保持现状，不在本阶段扩大安全范围 |
| 无真实浏览器 E2E | 视觉/响应式未自动验证 | 人工验收 |
| 大数据量表格性能 | 单页最多 100 行 | 使用服务端分页；不一次拉取全部 |
| `DashboardLayout` 仍显示 Phase 11.1 标签 | 文案陈旧 | 已知既有问题，不属于本阶段 |

### 10.2 人工验收清单

1. 启动 MySQL、Spring Boot、前端开发服务器。
2. 打开 `/reviews`，确认列表正常。
3. 点击 task ID，进入 `/reviews/{taskId}`。
4. 确认基础信息与列表数据一致。
5. 确认 AI Summary 区域只显示真实状态，不显示伪造摘要/风险。
6. 确认 Findings 分页、展开、引用过滤、置信度显示。
7. 确认 Published inline comments 只显示成功发布项。
8. 确认 `summaryCommentId=null`、`publishedAt=null`、`githubCommentId=null` 的占位。
9. 访问不存在的数字 ID，确认 Not Found。
10. 访问 `/reviews/missing-entry`，确认仍是 Page not found。
11. 在浏览器 Network / Application 中确认没有 `X-Internal-Token`、没有令牌存储。
12. 窄屏下确认布局不溢出、表格可横向滚动。
13. 刷新详情页，确认深链接可直接打开。

### 10.3 当前工作区状态

本报告创建前已确认：

```text
branch: phase11/dashboard
HEAD:   27e3a41161cfa86ee2956ba0b3626a2bcc71eec7
```

工作区已有修改/未跟踪内容必须继续保留，包括：

- `.gitignore` 修改
- Phase 11.2.2-A 后端修改与新增 Controller/Service/异常/测试
- `application.yml` 修改
- `docs/DEVELOPMENT_STATUS.md` 既有修改
- `frontend/.gitkeep` 删除状态
- `frontend/` 未跟踪文件
- 既有报告文件

本阶段新增：

```text
?? docs/reports/Phase11_2_3_A_Investigation_Report.md
```

本阶段未执行：

```text
git commit
git push
git merge
git rebase
git reset
git checkout
```

### 10.4 验收状态

Phase 11.2.3-A 调查完成，推荐方案具备可执行性，未发现阻塞项。

**等待人工验收。验收通过前不进入 Phase 11.2.3-B，不创建 Review Detail 源码，不修改任何现有文件。**
