# Phase 11.2.3-B 实施报告 — Review Detail 页面

> 实施日期：2026-11-13  
> 分支：`phase11/dashboard`  
> HEAD：`27e3a41161cfa86ee2956ba0b3626a2bcc71eec7`  
> 阶段：Phase 11.2.3-B（Dashboard Review Detail）  
> 状态：**实现与验证完成，等待人工验收；未进入 Phase 11.2.4。**

---

## 1. 实施概要

本阶段按照 `docs/reports/Phase11_2_3_A_Investigation_Report.md` 确定的数据契约，实现 Review Detail 页面所需的全部内容：

```text
Review History 列表
  ↓ 点击 taskId
/reviews/:taskId(\d+)
  ↓
ReviewDetailView
  ↓ 先加载 report
GET /api/dashboard/reviews/{taskId}
  ↓ 成功后并行加载
GET /api/dashboard/reviews/{taskId}/findings?page=&size=
GET /api/dashboard/reviews/{taskId}/comments?page=&size=
  ↓
DashboardReviewDetailController
  ↓
ReviewHistoryQueryService（直接复用，无 HTTP loopback）
  ↓
review_report / review_finding / review_comment
```

关键实现点：

1. 新增只读 Dashboard BFF `DashboardReviewDetailController`，直接注入并复用 `ReviewHistoryQueryService`，不读取、不转发 `X-Internal-Token`。
2. 浏览器只访问同源 `/api/dashboard/reviews/**`，不接触 Phase 10 内部 API，不把内部 Token 写入任何前端位置。
3. 前端新增 Review Detail 路由、类型、API 封装、展示工具和页面组件。
4. Review History 列表的 taskId 改为 `RouterLink`，详情页仍高亮侧边栏 Review History。
5. 页面严格区分 Loading、Invalid ID、404、409、通用 Error、Ready 状态；findings 与 comments 各自拥有独立加载、错误、重试和分页状态。
6. AI 摘要区域只展示实际持久化的状态与计数，并明确说明叙述性摘要和风险等级未持久化。
7. 已发布评论区域只展示持久化的已发布 Inline Comment 元数据，并明确说明评论正文、发布时间、GitHub URL 未存储。

本阶段未修改 Phase 10 的 Controller / Service / DTO / Repository / 数据库 Schema / `application.yml` / `DashboardLocalAccessFilter`，未新增依赖，未引入 Pinia、ECharts、图表、`v-html`、浏览器存储或轮询。

---

## 2. 修改文件清单

### 2.1 新增文件

| 文件 | 说明 |
|---|---|
| `backend/spring-service/src/main/java/cn/codesentinel/controller/DashboardReviewDetailController.java` | Dashboard Review Detail BFF，三个只读端点与固定安全错误体 |
| `backend/spring-service/src/test/java/cn/codesentinel/controller/DashboardReviewDetailControllerTest.java` | BFF 契约、安全边界、错误映射测试（17 个） |
| `frontend/src/api/review-detail.ts` | `getReviewDetail` / `getReviewFindings` / `getReviewComments` |
| `frontend/src/utils/review-display.ts` | 列表与详情共享的日期、计数、置信度、行号、标签类型等展示函数 |
| `frontend/src/views/ReviewDetailView.vue` | Review Detail 页面 |
| `frontend/src/__tests__/review-detail-api.spec.ts` | 详情 API 封装测试（6 个） |
| `frontend/src/__tests__/ReviewDetailView.spec.ts` | 详情页行为测试（21 个） |
| `docs/reports/Phase11_2_3_B_Implementation_Report.md` | 本报告 |

### 2.2 修改文件

| 文件 | 说明 |
|---|---|
| `frontend/src/types/api.ts` | 新增 `FindingCategory`、`FindingSeverity`、`ReviewPage<T>`、`ReviewDetailReport`、`ReviewFinding`、`ReviewComment`、`ReviewFindingPage`、`ReviewCommentPage`；`ReviewHistoryPage` 改为 `ReviewPage<ReviewHistoryItem>` 别名 |
| `frontend/src/api/index.ts` | 导出详情 API 与端点常量 |
| `frontend/src/router/index.ts` | 新增 `/reviews/:taskId(\d+)` 路由；`/reviews/missing-entry` 仍落到 not-found |
| `frontend/src/components/SidebarNav.vue` | `review-detail` 路由同样高亮 Review History |
| `frontend/src/views/ReviewHistoryView.vue` | taskId 改为指向详情页的 `RouterLink`；展示函数改为引用共享工具 |
| `frontend/src/__tests__/router.spec.ts` | 新增详情路由、非数字子路径、not-found 测试 |
| `frontend/src/__tests__/App.spec.ts` | 新增详情路由集成测试；mock 详情 API；验证侧边栏高亮 |
| `frontend/src/__tests__/ReviewHistoryView.spec.ts` | 适配 `RouterLinkStub`；新增 taskId 链接测试 |

### 2.3 明确未修改

- Phase 10 的 Controller / Service / DTO / Repository。
- `DashboardLocalAccessFilter`。
- 数据库 Schema、迁移脚本、实体字段。
- `application.yml`、`review.history.internal-token` 配置语义。
- `docs/DEVELOPMENT_STATUS.md`（工作区中的既有修改未触碰）。

工作区在本次阶段开始前已存在其他修改与未跟踪文件（见第 7 节），本阶段未删除、未回滚、未覆盖这些内容。

---

## 3. API 契约

三个端点均为只读，路径前缀 `/api/dashboard/reviews`，不要求 `X-Internal-Token`。

### 3.1 `GET /api/dashboard/reviews/{taskId}`

成功：`200 OK`，返回 `ReviewReportResponse`：

```json
{
  "taskId": 7,
  "owner": "owner",
  "repo": "repo",
  "prNumber": 42,
  "commitSha": "abc123",
  "taskStatus": "COMPLETED",
  "aiStatus": "DEGRADED",
  "publishStatus": "PARTIAL",
  "findingCount": 2,
  "publishedCommentCount": 1,
  "summaryCommentId": 900,
  "publishedAt": "2026-01-02T03:04:05",
  "createdAt": "2026-01-02T03:00:00",
  "updatedAt": "2026-01-02T03:04:00"
}
```

`summaryCommentId` 与 `publishedAt` 可以为 `null`。响应不包含 `reportId`、`id` 等内部标识。

### 3.2 `GET /api/dashboard/reviews/{taskId}/findings`

查询参数：

| 参数 | 默认值 | 约束 |
|---|---|---|
| `page` | `1` | 必须 ≥ 1 |
| `size` | `20` | 1 ≤ size ≤ 100 |

成功：`200 OK`：

```json
{
  "items": [
    {
      "ordinal": 0,
      "category": "SECURITY",
      "severity": "HIGH",
      "confidence": 0.94,
      "ruleId": "CWE-89",
      "title": "SQL injection",
      "filePath": "src/UserRepository.java",
      "startLine": 52,
      "endLine": 58,
      "description": "Externally controlled SQL.",
      "reason": "Input is concatenated.",
      "suggestion": "Use parameters.",
      "references": ["CWE-89", null, " ", "OWASP"]
    }
  ],
  "page": 1,
  "size": 20,
  "totalItems": 1,
  "totalPages": 1,
  "hasNext": false
}
```

`references` 允许包含 `null`，前端展示时过滤 `null` 与空白项。

### 3.3 `GET /api/dashboard/reviews/{taskId}/comments`

查询参数与分页约束同 findings。成功：`200 OK`：

```json
{
  "items": [
    {
      "findingOrdinal": 0,
      "githubCommentId": null,
      "filePath": "src/UserRepository.java",
      "startLine": 52,
      "endLine": 58
    }
  ],
  "page": 1,
  "size": 20,
  "totalItems": 1,
  "totalPages": 1,
  "hasNext": false
}
```

仅包含已确认发布到 GitHub 的 Inline Comment；评论正文、发布时间、GitHub URL 不在契约内。

### 3.4 错误契约

所有错误响应均为固定安全 JSON，不包含异常消息、SQL、路径、堆栈或内部字段：

| HTTP | 响应体 | 触发条件 |
|---|---|---|
| 400 | `{"error":"invalid_task_id"}` | taskId 非数字、为 0、为负数、为小数、超出 `long` 范围 |
| 400 | `{"error":"invalid_pagination"}` | `page < 1`、`size < 1`、`size > 100`；`page`/`size` 非数字或整数溢出 |
| 404 | `{"error":"review_not_found"}` | 任务不存在，或任务存在但没有结构化 Review Report |
| 409 | `{"error":"review_history_incomplete"}` | 持久化计数与实际 findings/comments 不一致 |
| 500 | `{"error":"internal_error"}` | 历史数据不可读、其他未预期异常 |

实现细节：

- `taskId` 以 `String` 接收，先经 `^\d+$` 校验，再 `Long.parseLong`，最后要求 `> 0`；避免 `long` 路径变量在框架层产生不可控错误。
- `MethodArgumentTypeMismatchException` 仅当字段为 `page`/`size` 时映射为 `invalid_pagination`，其他类型不匹配映射为 `internal_error`。
- 兜底 `@ExceptionHandler(Exception.class)` 只记录异常类型名，不记录异常消息。

---

## 4. 安全验证

| 验证项 | 结果 |
|---|---|
| 浏览器是否需要内部 Token | 不需要；三个 BFF 端点均不读取 `X-Internal-Token` |
| 是否转发内部 Token | 不转发；Controller 直接调用 Service |
| 伪造 `X-Internal-Token` 是否回显 | 测试确认响应不包含该 Token |
| 是否信任 `X-Forwarded-For` / `Forwarded` | 不信任；远程 peer 即使携带转发头仍返回 403 |
| 非本机访问 `/api/dashboard/**` | 由既有 `DashboardLocalAccessFilter` 拦截，返回 403 且响应体为空 |
| 编码路径 / 矩阵参数绕过 | 测试覆盖 `/api/%64ashboard/...`、`/api/dashboard;x/...`、`.../findings;x` 等，远程 peer 均 403 |
| 错误信息泄漏 | 固定错误码；异常消息、SQL、表名、异常类名均不出现在响应中 |
| 日志泄漏 | 兜底异常只记录异常类型；未记录 Token、Secret、代码内容或用户敏感数据 |
| 前端是否持有内部凭据 | 否；无 localStorage / sessionStorage / Cookie / 硬编码 Token |
| 是否执行 PR 代码 | 否；仅读取已持久化的审查历史 |
| XSS 风险 | 不使用 `v-html`；所有文本经 Vue 插值转义 |

后端测试显式覆盖：

- 无 Token 可正常访问。
- 携带伪造 Token 不回显。
- 远程地址访问返回 403，且不调用 Service。
- 编码路径与矩阵参数访问返回 403。
- 转发头不能伪造本机身份。
- IPv6 回环地址可访问。
- 未预期异常与数据完整性异常均返回安全 `internal_error`。

---

## 5. 前端实现

### 5.1 路由与导航

```text
/reviews                  → Review History
/reviews/:taskId(\d+)     → Review Detail
/reviews/missing-entry    → not-found（非数字不匹配详情路由）
```

- Review History 的 task ID 使用 `RouterLink` 指向 `/reviews/{taskId}`。
- Review Detail 路由下侧边栏仍高亮 Review History。
- 路由参数变化时详情页重新初始化；离开页面时取消全部请求。

### 5.2 页面状态

| 状态 | 展示 |
|---|---|
| Loading | 页面级骨架屏 |
| Invalid ID | “Review not found”，说明 URL 中不是有效正整数 ID，未发送请求 |
| 404 | “Review not found”，说明没有结构化历史或结果尚未接收；提供返回列表链接 |
| 409 | “Review history is incomplete”，说明计数不一致且不展示部分数据；提供重试 |
| Error | “Unable to load review detail” + 安全错误消息；提供重试 |
| Ready | 展示 Review 信息、AI 摘要说明、Findings、Published Inline Comments |

报告加载失败时不会发起 findings/comments 请求。

### 5.3 Review 信息

展示字段：

- Task ID
- Repository（`owner/repo`）
- Pull Request 编号
- Commit SHA
- Task status / AI status / Publish status
- Finding count / Published comment count
- Summary comment ID（无则 `Not available`）
- Published at / Created at / Last updated（时间为 `null` 时显示 `—`）

页面明确标注 `updatedAt` 为 “Last updated”，不虚构 “Completed at”。

### 5.4 AI 摘要

只展示实际持久化的 AI 状态、finding 计数、发布状态、summary comment ID，并显示固定说明：

> Narrative summary and risk level are not stored in the structured review history and are not shown here.

不推断综述文本、总体风险等级或“审查通过”等结论。

### 5.5 Findings

- 表格展示序号、严重程度、类别、标题、规则 ID、文件路径、行号范围、置信度。
- 行号格式为 `L52` 或 `L52–58`；非法行号显示 `—`。
- 置信度显示为百分比；非法值显示 `—`。
- 未知 severity/category 使用中性标签，不抛异常。
- 展开行显示 Description、Reason、Suggestion、References。
- References 过滤 `null`、空白项；为空时显示 “No references”。
- 分页与每页条数独立于 comments；修改 size 时该区块回到第 1 页。
- 当前页为空但 `totalItems > 0` 时仍保留分页组件，显示 “No findings on this page”。
- 区块独立 Loading / Error / Incomplete / Retry，不影响 comments 区块。

### 5.6 Published Inline Comments

- 表格展示 finding 序号、文件路径、行号范围、GitHub comment ID。
- `githubCommentId` 为 `null` 时显示 “ID unavailable”。
- 明确说明仅展示已确认发布的评论；失败/跳过评论不展示；评论正文、发布时间、GitHub URL 未存储。
- 独立分页、独立 Loading / Error / Retry；空页但总数大于 0 时保留分页。

### 5.7 请求生命周期

```text
进入页面 / taskId 变化
  ↓
取消旧请求，重置状态
  ↓
加载 report
  ├─ 失败 → 404 / 409 / Error，不请求子区块
  └─ 成功 → findings 与 comments 并行加载
```

- 所有请求使用 `AbortController`。
- 每个区块维护递增 sequence，过期响应不写入状态。
- Refresh 取消在途请求，重新加载 report，再并行重载当前 findings/comments 页码。
- 卸载时取消全部在途请求。
- 无轮询、无自动重试；Retry 均由用户触发。
- 分页请求失败时保留已有列表内容（仅重试场景），不伪造数据。

### 5.8 共享展示工具

`frontend/src/utils/review-display.ts` 提供：

```text
TagType
formatDateTime
formatCount
formatSummaryComment
formatSummaryCommentId
formatText
formatConfidence
formatLineRange
taskStatusType
aiStatusType
publishStatusType
severityType
categoryType
```

Review History 与 Review Detail 均使用这些函数，避免两套状态映射漂移。

---

## 6. 测试结果

### 6.1 后端定向测试

```powershell
mvn -q -Dtest=DashboardReviewDetailControllerTest test
```

结果：`Tests run: 17, Failures: 0, Errors: 0, Skipped: 0`。

### 6.2 后端相关回归

```powershell
mvn -q "-Dtest=ReviewHistoryQueryServiceTest,ReviewHistoryControllerTest,DashboardReviewControllerTest" test
```

| 测试类 | 结果 |
|---|---|
| `ReviewHistoryQueryServiceTest` | 20 / 0 / 0 |
| `ReviewHistoryControllerTest` | 12 / 0 / 0 |
| `DashboardReviewControllerTest` | 12 / 0 / 0 |

### 6.3 后端全量测试

```powershell
mvn -q test
```

结果：

```text
Report files: 45
Tests run: 507, Failures: 0, Errors: 0, Skipped: 0
No failing test sets.
```

输出中的测试异常日志均为测试预期场景（如模拟数据库失败、重复结果、未预期异常等），不代表测试失败。

### 6.4 前端验证

| 命令 | 结果 |
|---|---|
| `npm run type-check` | 通过 |
| `npm run lint:check` | 通过（oxlint + eslint） |
| `npm run test:unit` | 9 个测试文件，77 个测试全部通过 |
| `npm run build` | 通过；生成 `ReviewDetailView-*.js`、`review-display-*.js` 等路由/共享 chunk |

新增前端测试：

| 文件 | 测试数 | 覆盖重点 |
|---|---|---|
| `review-detail-api.spec.ts` | 6 | 同源端点、参数、AbortSignal、ApiError 透传 |
| `ReviewDetailView.spec.ts` | 21 | 加载顺序、404/409/Error、字段展示、AI 摘要说明、展开、分页、独立失败、过期响应、路由切换、刷新、卸载取消、非法 ID |
| `router.spec.ts` | +3 | 详情路由、非数字子路径、not-found |
| `App.spec.ts` | +1 | 详情路由渲染与侧边栏高亮 |
| `ReviewHistoryView.spec.ts` | +1 | taskId 链接目标 |

### 6.5 静态与差异检查

```powershell
git diff --check
```

退出码 0。仅出现 `.gitignore` 的 LF→CRLF 提示（该文件为工作区既有修改，不是本阶段改动）。

---

## 7. Git 状态

```text
Branch: phase11/dashboard
HEAD:   27e3a41161cfa86ee2956ba0b3626a2bcc71eec7
```

`git status --porcelain=v1` 中与本阶段直接相关的新增文件：

```text
?? backend/spring-service/src/main/java/cn/codesentinel/controller/DashboardReviewDetailController.java
?? backend/spring-service/src/test/java/cn/codesentinel/controller/DashboardReviewDetailControllerTest.java
?? frontend/src/api/review-detail.ts
?? frontend/src/utils/review-display.ts
?? frontend/src/views/ReviewDetailView.vue
?? frontend/src/__tests__/review-detail-api.spec.ts
?? frontend/src/__tests__/ReviewDetailView.spec.ts
?? docs/reports/Phase11_2_3_B_Implementation_Report.md
```

本阶段修改的已跟踪文件：

```text
M frontend/src/types/api.ts
M frontend/src/api/index.ts
M frontend/src/router/index.ts
M frontend/src/components/SidebarNav.vue
M frontend/src/views/ReviewHistoryView.vue
M frontend/src/__tests__/router.spec.ts
M frontend/src/__tests__/App.spec.ts
M frontend/src/__tests__/ReviewHistoryView.spec.ts
```

说明：

- 工作区中还有 Phase 10 / Phase 11.2.2 / Phase 11.2.3-A 遗留的已修改和未跟踪文件，本阶段未删除、未回滚、未覆盖。
- `docs/DEVELOPMENT_STATUS.md` 为进入本阶段前已存在的修改，本阶段未改动。
- 本阶段未执行 `git add`、`git commit`、`git push`、`git merge`、`git rebase`、`git reset`、`git checkout`。
- HEAD 仍为任务要求的基线提交。

---

## 8. 已知限制

1. **没有 AI 叙述性摘要与风险等级。** Phase 10 的持久化结构不保存 Python 报告中的叙述性文本和总体风险等级，页面只能展示状态与计数，并明确提示未存储。
2. **没有评论正文、发布时间和 GitHub URL。** `review_comment` 仅保存已成功发布的定位信息，页面不展示、也不伪造这些字段。
3. **不展示发布失败或跳过的评论。** 这些信息在 `review_result_delivery.publish_outcome_json` 中，未通过查询 API 暴露。
4. **GitHub comment ID 可能为空。** 历史数据允许 `github_comment_id` 为 `null`，页面以 “ID unavailable” 呈现。
5. **BFF 仅限本机访问。** 现有 `DashboardLocalAccessFilter` 只接受回环地址；远程部署或反向代理场景需要后续单独设计认证边界，本阶段未改动。
6. **详情页不提供跳转 GitHub 的链接。** 当前契约没有仓库 HTML URL 或 PR URL 字段，未在浏览器端拼装不可靠链接。
7. **无自动刷新与轮询。** 运行中的审查任务需要用户手动 Refresh 才能看到新结果，避免额外请求与状态竞争。

---

## 9. 人工验收步骤

### 9.1 准备

1. 按现有项目说明启动 MySQL、Redis、Spring Boot 与前端开发服务器。
2. 确认数据库中至少存在一条包含 findings 和已发布 comments 的 Review 历史记录，并记录其 `task_id`。
3. 确认后端与前端均使用本阶段代码，浏览器访问前端同源地址（默认 `http://localhost:5173`）。

### 9.2 列表入口

1. 打开 `/reviews`。
2. 确认 task ID 显示为链接，悬停有下划线/主题色反馈。
3. 点击某条 task ID，确认进入 `/reviews/{taskId}`。
4. 确认侧边栏仍高亮 “Review History”。

### 9.3 详情内容

1. 确认页面标题为 `Review #<taskId>`，副标题包含 `owner/repo`、`PR #`、commit SHA。
2. 核对 Review information 中全部字段与数据库/接口一致。
3. 确认 `summaryCommentId` 为空时显示 `Not available`，`publishedAt` 为空时显示 `—`。
4. 确认 AI 摘要区域明确提示叙述性摘要与风险等级未持久化。
5. 展开 findings 行，确认 Description / Reason / Suggestion / References 正确，且 `null`/空白引用不显示。
6. 确认行号、置信度格式正确。
7. 确认 Published inline comments 仅展示已发布评论，空 GitHub ID 显示 “ID unavailable”。

### 9.4 分页与刷新

1. 将 findings 每页条数改为 50，确认回到第 1 页且 comments 页码不受影响。
2. 分别翻动 findings 与 comments，确认两者互不影响。
3. 点击 Refresh，确认 report 重新加载，findings/comments 保持当前页码并重新请求。
4. 在请求进行中快速切换页码，确认最终展示最后一次选择的数据。

### 9.5 异常状态

1. 访问 `/reviews/999999999`，确认显示 404 “Review not found”，且不请求 findings/comments。
2. 访问 `/reviews/0`、`/reviews/abc`、`/reviews/missing-entry`，确认不会进入详情页或显示无效 ID 状态。
3. 临时停止后端后点击 Retry，确认显示安全错误信息，不出现堆栈、SQL 或内部路径。
4. 若可构造 409 数据，确认页面显示 “Review history is incomplete”，不展示部分数据。

### 9.6 安全抽查

```powershell
# 缺少内部 Token 仍可访问（仅本机）
curl.exe -i http://localhost:8080/api/dashboard/reviews/7

# 非法 task id
curl.exe -i http://localhost:8080/api/dashboard/reviews/0
curl.exe -i http://localhost:8080/api/dashboard/reviews/abc

# 非法分页
curl.exe -i "http://localhost:8080/api/dashboard/reviews/7/findings?page=0"
curl.exe -i "http://localhost:8080/api/dashboard/reviews/7/comments?size=101"

# 伪造 Token 不应出现在响应中
curl.exe -i -H "X-Internal-Token: test-token" http://localhost:8080/api/dashboard/reviews/7
```

确认错误响应体仅为固定错误码，且响应中不出现 `test-token`、异常消息、表名或文件路径。

### 9.7 复验命令

```powershell
# 后端
cd backend/spring-service
mvn -q -Dtest=DashboardReviewDetailControllerTest test
mvn -q test

# 前端
cd frontend
npm run type-check
npm run lint:check
npm run test:unit
npm run build
```

---

## 10. 结论

Phase 11.2.3-B 已按既定契约完成：

- Review Detail 三个 BFF 端点可用，错误契约固定且安全。
- 前端详情页具备完整页面状态、独立区块状态、分页、刷新、请求取消与过期响应保护。
- 列表入口、路由、侧边栏高亮、共享展示工具均已落地。
- 后端定向测试、相关回归、全量测试，以及前端类型检查、Lint、单元测试、生产构建全部通过。
- 未修改 Phase 10 核心代码、数据库 Schema、`application.yml` 或 `DashboardLocalAccessFilter`。
- 未新增依赖，未引入 Pinia、ECharts、图表、`v-html`、内部 Token、浏览器存储或轮询。

**本阶段到此停止，等待人工验收；未进入 Phase 11.2.4。**
