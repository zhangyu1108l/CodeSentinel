# Phase 11.2.3-B 验收报告 — Dashboard Review Detail

> 验收日期：2026-11-13  
> 分支：`phase11/dashboard`  
> HEAD：`27e3a41161cfa86ee2956ba0b3626a2bcc71eec7`  
> 验收对象：Review Detail BFF、前端详情页、真实 MySQL 数据、真实浏览器端到端流程与安全边界  
> 最终结论：**PASS WITH WARNINGS（通过，附 2 项非阻塞警告）**

---

## 1. 验收结论

### 1.1 总体判定

**PASS WITH WARNINGS。**

Phase 11.2.3-B 的 Review Detail 功能已完整实现并通过验收：

- 三个 Dashboard BFF 端点（report / findings / comments）在真实 MySQL 数据上行为正确。
- 前端详情页的正常、空数据、404、409、400、500、数据库故障与后端不可用场景均按契约展示。
- 分页、独立区块加载、刷新、快速切页、路由切换取消请求均通过真实浏览器验证。
- 安全边界、错误体脱敏、日志敏感值扫描、XSS 转义均通过。
- 未发现阻塞性功能缺陷，未发现高风险安全问题。

存在 2 项非阻塞观察项，均不影响本阶段验收通过：

1. 后端完全不可用时，经 Vite 开发代理表现为 HTTP 502，页面显示通用错误文案 `The server returned an invalid response.`，未区分“服务不可用”和“响应格式异常”；Retry 与恢复流程正常。
2. 数据库表故障时，Hibernate 默认日志会输出 `SQL Error: 1146, SQLState: 42S02` 及表名；未包含密码、Token 或用户数据，但生产环境应通过日志级别与异常映射进一步收敛。

### 1.2 验收维度汇总

| 维度 | 结果 | 关键证据 |
|---|---|---|
| 后端全量单元测试 | **PASS** | 45 个测试集，507 个测试，0 失败 / 0 错误 / 0 跳过 |
| MySQL 集成测试 | **PASS** | 8 个 IT 类，55 个测试，0 失败 / 0 错误 / 0 跳过 |
| 前端静态检查 | **PASS** | `type-check`、`lint:check` 均退出码 0 |
| 前端单元测试 | **PASS** | 9 个测试文件，77 个测试全部通过 |
| 前端生产构建 | **PASS** | `vite build` 成功，生成 ReviewDetailView 独立 chunk |
| BFF API 正常与错误矩阵 | **PASS** | 38 个 API 场景，覆盖 200 / 400 / 404 / 409 / 500 |
| 分页与空数据 | **PASS** | findings 45 条、comments 25 条的边界页码逐一核对 |
| 安全边界 | **PASS** | Token、伪造转发头、编码/矩阵/反斜杠路径、错误体与日志扫描 |
| 数据库故障 | **PASS** | 临时重命名表后返回固定 500，恢复后服务正常 |
| 真实浏览器 E2E | **PASS** | Chrome 156 + CDP，51 项检查全部通过 |
| 后端不可用与恢复 | **PASS** | 502 → 错误页 → Retry → 后端恢复后 3 个请求均 200 |
| 变更边界 | **PASS** | 未修改源代码，仅新增本报告；未执行任何 Git 写操作 |

---

## 2. 验收范围、环境与方法

### 2.1 验收范围

本轮验收覆盖：

```text
Review History 列表
  → 点击 taskId
  → /reviews/:taskId
  → Review Detail 页面
  → GET /api/dashboard/reviews/{taskId}
  → GET /api/dashboard/reviews/{taskId}/findings
  → GET /api/dashboard/reviews/{taskId}/comments
  → DashboardReviewDetailController
  → ReviewHistoryQueryService
  → 真实 MySQL 8
```

同时覆盖：

- 页面状态：Loading、Invalid ID、404、409、通用 Error、Ready。
- 区块状态：findings 与 comments 独立加载、独立失败、独立重试、独立分页。
- 异常数据：空数据、null 字段、未知枚举、损坏 JSON、计数不一致、任务存在但无 report。
- 安全边界：无 Token、伪造 Token、伪造 `X-Forwarded-For`、非回环访问、编码/双重编码/矩阵/反斜杠路径。
- 故障恢复：数据库表不可用、后端进程停止、恢复后 Retry。

不覆盖、也未提前实现：

- Phase 11.2.4 的任何功能。
- RAG、Milvus、Dashboard 新页面、自动修复、GitHub 写操作。
- 生产数据库或生产环境的任何数据。

### 2.2 验收环境

| 项目 | 值 |
|---|---|
| 操作系统 | Windows 10/11（win32） |
| 分支 | `phase11/dashboard` |
| HEAD | `27e3a41161cfa86ee2956ba0b3626a2bcc71eec7` |
| Java | 21 |
| Spring Boot | 3.x（项目现有版本） |
| MySQL | 8，`localhost:3307` |
| Redis | 7，`localhost:6379` |
| 后端端口 | `8080` |
| 前端开发服务器 | Vite，`http://127.0.0.1:5173` |
| 浏览器 | Google Chrome `156.0.8078.81` |
| 浏览器自动化 | Chrome DevTools Protocol（CDP），未安装 Playwright |
| API 测试工具 | PowerShell `Invoke-WebRequest` / `curl.exe` |
| 隔离数据库 | `codesentinel_accept_1123b` |

说明：

- MySQL 与 Redis 使用项目现有本地容器端口，未连接生产数据。
- 后端通过 `MYSQL_DATABASE=codesentinel_accept_1123b` 指向隔离验收库。
- 前端通过 `DEV_PROXY_TARGET=http://127.0.0.1:8080` 访问本地后端。
- 所有测试数据、脚本、日志、截图均位于工作区外的临时目录：
  `%TEMP%\opencode\cs-accept-1123b`。

### 2.3 隔离验收数据

| taskId | 场景 | 关键数据 |
|---|---|---|
| 1001 | 正常完整数据 | 45 findings、25 comments、summaryCommentId=9001、publishedAt 非空 |
| 1002 | 空数据 / null | 0 findings、0 comments、summaryCommentId=null、publishedAt=null |
| 1003 | findings 计数不一致 | report 期望 3，实际 2 → 409 |
| 1004 | `references_json` 损坏 | `{bad` → findings 500 |
| 1005 | comments 计数不一致 | report 期望 2，实际 1 → comments 409 |
| 1006 | 未知枚举 | aiStatus=`UNKNOWN`、category=`MYSTERY`、severity=`UNKNOWN` |
| 1008 | 任务存在但无 report | → 404 |
| 999999 | 任务不存在 | → 404 |

种子数据文件：

```text
%TEMP%\opencode\cs-accept-1123b\seed.sql
```

### 2.4 验收方法

| 层级 | 方法 |
|---|---|
| 后端单元测试 | `mvn -q test`，读取 Surefire 报告核对总数 |
| MySQL 集成测试 | `mvn -q -Pmysql-it verify`，读取 Failsafe 报告核对总数 |
| 前端静态检查 | `npm run type-check`、`npm run lint:check` |
| 前端单元测试 | `npm run test:unit` |
| 前端构建 | `npm run build` |
| API 契约 | `Invoke-WebRequest -SkipHttpErrorCheck` 逐项请求并记录状态码/响应体 |
| 安全边界 | 本机与局域网地址、伪造转发头、编码路径、curl `--path-as-is` |
| 数据库故障 | 临时 `RENAME TABLE`，请求后立即恢复 |
| 浏览器 E2E | Chrome CDP 脚本真实点击、真实导航、NetWork 事件监听、截图 |
| 日志安全 | 对后端/前端日志扫描配置中的 Secret、Token、Authorization、Bearer |

---

## 3. Git 与变更边界

### 3.1 验收入口状态

```text
Branch: phase11/dashboard
HEAD:   27e3a41161cfa86ee2956ba0b3626a2bcc71eec7
```

验收开始时：

```text
git status --porcelain=v1 | Measure-Object → 47
```

这 47 项为进入本阶段前已存在的修改与未跟踪内容，包括 Phase 10、Phase 11.2.2、Phase 11.2.3-A 的既有工作区内容。本轮未清理、未回滚、未覆盖。

### 3.2 本轮变更

本轮验收**未修改任何源代码、配置、测试或既有文档**。

创建本报告后，工作区新增且仅新增：

```text
?? docs/reports/Phase11_2_3_B_Acceptance_Report.md
```

因此 `git status --porcelain=v1` 由 47 项变为 48 项；其余 47 项内容未发生变化。

### 3.3 明确未执行的操作

```text
git commit
git push
git merge
git rebase
git reset
git clean
git checkout
删除分支
```

未修改：

- `docs/DEVELOPMENT_STATUS.md`（本阶段开始前已存在的修改保持原样）。
- `docs/reports/Phase10_*.md`。
- `docs/reports/Phase11_2_3_A_Investigation_Report.md`。
- `docs/reports/Phase11_2_3_B_Implementation_Report.md`。

### 3.4 临时进程清理

验收结束后已停止本轮启动的临时服务：

| 端口 | 进程 | 状态 |
|---|---|---|
| 8080 | Java（Spring Boot） | 已停止 |
| 5173 | Node（Vite） | 已停止 |
| 9222 | Chrome（CDP） | 已停止 |

复核结果：上述端口均无监听进程。MySQL `3307` 与 Redis `6379` 为验收前既有基础设施，未停止。

---

## 4. 后端单元测试与构建

### 4.1 全量单元测试

执行命令：

```powershell
cd backend/spring-service
mvn -q test
```

结果：

```text
Report files: 45
Tests run: 507
Failures: 0
Errors: 0
Skipped: 0
```

Surefire 报告核对结果：

```text
surefire files=45 tests=507 failures=0 errors=0 skipped=0
latest=2026/11/13 20:06:44
```

**PASS。**

### 4.2 Review Detail BFF 定向测试

执行命令：

```powershell
mvn -q -Dtest=DashboardReviewDetailControllerTest test
```

结果：

```text
Tests run: 17, Failures: 0, Errors: 0, Skipped: 0
```

覆盖重点：

- 三个端点的字段映射与默认分页。
- 自定义分页参数传递。
- 内部标识不进入响应。
- 404（任务不存在 / 无 report）统一安全响应。
- findings / comments 计数不一致 → 409。
- 非法 taskId 与非法分页 → 400，且不调用 Service。
- 不要求 `X-Internal-Token`。
- 伪造 Token 不回显。
- 未预期异常 → 固定 `internal_error`。
- 数据不可读 → 固定 `internal_error`。

**PASS。**

### 4.3 相关回归

执行命令：

```powershell
mvn -q "-Dtest=ReviewHistoryQueryServiceTest,ReviewHistoryControllerTest,DashboardReviewControllerTest" test
```

| 测试类 | 结果 |
|---|---|
| `ReviewHistoryQueryServiceTest` | 20 / 0 / 0 |
| `ReviewHistoryControllerTest` | 12 / 0 / 0 |
| `DashboardReviewControllerTest` | 12 / 0 / 0 |

**PASS。**

### 4.4 构建

`mvn -q test` 与 `mvn -q -Pmysql-it verify` 均完成 `compile` / `test-compile`，未出现编译错误。测试输出中的异常堆栈均为测试预期场景（模拟数据库失败、重复结果、未预期异常等），不代表测试失败。

**PASS。**

---

## 5. MySQL 集成测试

### 5.1 执行命令

```powershell
cd backend/spring-service
mvn -q -Pmysql-it verify
```

### 5.2 汇总结果

```text
failsafe files=8
tests=55
failures=0
errors=0
skipped=0
latest=2026/11/13 20:08:18
```

### 5.3 分类结果

| IT 类 | 测试数 | 失败 | 错误 | 跳过 |
|---|---:|---:|---:|---:|
| `ReviewHistoryListMySqlIT` | 5 | 0 | 0 | 0 |
| `ReviewHistoryMySqlConcurrencyIT` | 3 | 0 | 0 | 0 |
| `ReviewHistoryMySqlConstraintIT` | 6 | 0 | 0 | 0 |
| `ReviewHistoryMySqlL1IT` | 4 | 0 | 0 | 0 |
| `ReviewHistoryMySqlMappingIT` | 7 | 0 | 0 | 0 |
| `ReviewHistoryMySqlQueryIT` | 12 | 0 | 0 | 0 |
| `ReviewHistoryMySqlWriteIT` | 17 | 0 | 0 | 0 |
| `ReviewResultDeliveryMySqlRaceIT` | 1 | 0 | 0 | 0 |
| **合计** | **55** | **0** | **0** | **0** |

### 5.4 数据隔离确认

- 集成测试与验收服务均连接 `codesentinel_accept_1123b`。
- 未连接、未修改现有 `codesentinel` 业务库。
- 未导入生产数据。
- 测试结束后未删除隔离库，便于复验；该库位于本地开发 MySQL。

**PASS。**

---

## 6. 前端静态检查、单元测试与构建

### 6.1 类型检查

```powershell
cd frontend
npm run type-check
```

结果：退出码 0，无类型错误。

**PASS。**

### 6.2 Lint

```powershell
npm run lint:check
```

内部执行：

```text
oxlint . && eslint .
```

结果：退出码 0，无 lint 错误。

**PASS。**

### 6.3 单元测试

```powershell
npm run test:unit
```

结果：

```text
Test Files  9 passed (9)
Tests       77 passed (77)
Duration    18.20s
```

测试文件：

```text
api-error.spec.ts
App.spec.ts
DashboardLayout.spec.ts
DashboardView.spec.ts
review-detail-api.spec.ts
review-history-api.spec.ts
ReviewDetailView.spec.ts
ReviewHistoryView.spec.ts
router.spec.ts
```

Review Detail 直接相关覆盖：

- `review-detail-api.spec.ts`：6 个 API 封装测试（同源端点、参数、AbortSignal、错误透传）。
- `ReviewDetailView.spec.ts`：21 个页面行为测试（加载顺序、404/409/Error、字段展示、AI 摘要说明、展开、引用过滤、独立分页、独立失败、过期响应、路由切换、刷新、卸载取消、非法 ID）。
- `router.spec.ts`、`App.spec.ts`、`ReviewHistoryView.spec.ts`：详情路由、侧边栏高亮、列表 taskId 链接。

说明：Vitest 统计的 77 个用例包含参数化展开用例，因此多于静态 `it(...)` 块数量。

**PASS。**

### 6.4 生产构建

```powershell
npm run build
```

结果：`vue-tsc --build` 与 `vite build` 均成功。

关键产物：

```text
dist/assets/ReviewDetailView-WyDITrTa.js   18.04 kB │ gzip: 5.24 kB
dist/assets/ReviewDetailView-DDK7Gu7E.css   6.71 kB │ gzip: 1.63 kB
```

构建耗时约 `721ms`，1730 个模块完成转换。

**PASS。**

### 6.5 未新增依赖

- 未安装 Playwright。
- 未新增任何 npm / Maven 依赖。
- 浏览器自动化使用系统已安装 Chrome 的 CDP，不写入 `package.json`。

**PASS。**

---

## 7. BFF API 正常与错误矩阵（真实 MySQL）

### 7.1 测试方式

使用 PowerShell `Invoke-WebRequest -SkipHttpErrorCheck` 对真实运行的后端逐项请求，记录 HTTP 状态码与响应体。错误响应体均按固定安全 JSON 校验。

### 7.2 主矩阵

| # | 场景 | 端点 | HTTP | 结果 / 响应 |
|---:|---|---|---:|---|
| 1 | 1001 正常 report | `GET /api/dashboard/reviews/1001` | **200** | 45 findings、25 comments、summaryCommentId=9001 |
| 2 | 1001 findings 默认分页 | `GET .../1001/findings` | **200** | 20 条，totalItems=45，totalPages=3，hasNext=true |
| 3 | 1001 comments 默认分页 | `GET .../1001/comments` | **200** | 20 条，totalItems=25，totalPages=2，hasNext=true |
| 4 | 1002 空/null report | `GET .../1002` | **200** | findingCount=0、publishedCommentCount=0、summaryCommentId=null、publishedAt=null |
| 5 | 1002 findings | `GET .../1002/findings` | **200** | `items=[]`、totalItems=0、totalPages=0、hasNext=false |
| 6 | 1002 comments | `GET .../1002/comments` | **200** | `items=[]`、totalItems=0、totalPages=0、hasNext=false |
| 7 | 1003 report 计数不一致 | `GET .../1003` | **409** | `{"error":"review_history_incomplete"}` |
| 8 | 1003 findings 计数不一致 | `GET .../1003/findings` | **409** | 固定安全错误体 |
| 9 | 1003 comments（0 条，一致） | `GET .../1003/comments` | **200** | 空页 |
| 10 | 1004 report | `GET .../1004` | **200** | report 本身可读 |
| 11 | 1004 findings 损坏 JSON | `GET .../1004/findings` | **500** | `{"error":"internal_error"}` |
| 12 | 1004 comments | `GET .../1004/comments` | **200** | 空页 |
| 13 | 1005 report 评论计数不一致 | `GET .../1005` | **409** | 固定安全错误体 |
| 14 | 1005 findings | `GET .../1005/findings` | **200** | 1 条 |
| 15 | 1005 comments 计数不一致 | `GET .../1005/comments` | **409** | 固定安全错误体 |
| 16 | 1006 未知枚举 report | `GET .../1006` | **200** | aiStatus=`UNKNOWN` 原样返回 |
| 17 | 1006 未知枚举 findings | `GET .../1006/findings` | **200** | category=`MYSTERY`、severity=`UNKNOWN` 原样返回 |
| 18 | 1008 无 report | `GET .../1008` | **404** | `{"error":"review_not_found"}` |
| 19 | 999999 不存在 | `GET .../999999` | **404** | 与无 report 相同的安全 404 |

**PASS。**

### 7.3 非法 taskId

逐项请求：

```text
0
-1
abc
1.5
999999999999999999999999999999999999
" 1"（URL 编码空格）
1001x
```

结果：

```text
全部 400
{"error":"invalid_task_id"}
```

校验发生在 Controller 进入 Service 之前；不会查询数据库，也不会返回框架默认错误页。

**PASS。**

### 7.4 非法分页

逐项请求：

```text
findings: page=0 / -1 / abc / 1.5 / 2147483648
findings: size=0 / -2 / 101 / abc / 9999999999
comments: page=0
comments: size=101
```

结果：

```text
全部 400
{"error":"invalid_pagination"}
```

未出现 500、框架默认错误体或参数回显。

**PASS。**

### 7.5 错误体安全

所有错误响应均为固定错误码：

```json
{"error":"invalid_task_id"}
{"error":"invalid_pagination"}
{"error":"review_not_found"}
{"error":"review_history_incomplete"}
{"error":"internal_error"}
```

响应中未出现：

- SQL 语句、表名、列名。
- Java 异常类名、堆栈、文件路径。
- `reportId`、`finding.id`、`comment.id` 等内部标识。
- Token、Secret、环境变量。
- 原始损坏数据（如 `{bad`、`references_json`）。

**PASS。**

### 7.6 状态码与业务语义一致性

- 404 对“任务不存在”和“任务存在但无 report”返回相同响应，避免枚举资源是否存在。
- 409 仅用于持久化计数与实际行数不一致，页面不展示部分历史。
- 500 仅用于数据不可读或未预期异常，响应体固定为 `internal_error`。
- 400 仅用于请求参数非法，不进入业务查询。

**PASS。**

---

## 8. 分页、空数据与边界语义

### 8.1 findings 分页（1001，共 45 条）

| 请求 | 条数 | totalItems | totalPages | hasNext | 序号范围 |
|---|---:|---:|---:|---|---|
| `page=2&size=10` | 10 | 45 | 5 | true | #10–#19 |
| `page=5&size=10` | 5 | 45 | 5 | false | #40–#44 |
| `page=6&size=10` | 0 | 45 | 5 | false | 空页 |
| `page=1&size=100` | 45 | 45 | 1 | false | #0–#44 |

### 8.2 comments 分页（1001，共 25 条）

| 请求 | 条数 | totalItems | totalPages | hasNext | findingOrdinal 范围 |
|---|---:|---:|---:|---|---|
| `page=2&size=10` | 10 | 25 | 3 | true | 10–19 |
| `page=3&size=10` | 5 | 25 | 3 | false | 20–24 |
| `page=4&size=10` | 0 | 25 | 3 | false | 空页 |

### 8.3 空数据与 null 字段

1002 验证结果：

| 字段 | 返回值 | 页面展示 |
|---|---|---|
| `findingCount` | 0 | `0` |
| `publishedCommentCount` | 0 | `0` |
| `summaryCommentId` | `null` | `Not available` |
| `publishedAt` | `null` | `—` |
| findings | 空数组 | `No findings stored for this review` |
| comments | 空数组 | `No published inline comments stored for this review` |

1001 边界：

- 第 25 条 comment 的 `githubCommentId=null`，页面显示 `ID unavailable`。
- finding 的 `references` 包含 `null`、空白字符串时，页面过滤后仅展示有效引用。
- `references` 为空数组或 `null` 时，页面显示 `No references`。

### 8.4 独立分页语义

真实浏览器验证：

- findings 翻到第 2 页时，comments 仍保持第 1 页。
- comments 翻到第 2 页时，findings 仍保持第 2 页。
- findings 翻到第 3 页（最后 5 条）时，comments 仍保持第 2 页。
- 当前页为空但 `totalItems > 0` 时，分页组件保留，并显示空页提示。

**PASS。**

---

## 9. 安全边界验收

### 9.1 访问控制与 Token

| 场景 | 结果 | 证据 |
|---|---|---|
| 无 `X-Internal-Token` 访问 BFF | **200** | `no-token status=200` |
| 伪造 `X-Internal-Token: forged-value` | **200**，响应不含该值 | `echoedToken=False` |
| 空 `X-Internal-Token` | **200** | `empty-token status=200` |
| 浏览器请求携带 `X-Internal-Token` | **0 次** | CDP 全量请求头检查 |
| 浏览器请求携带 `Authorization` | **0 次** | CDP 全量请求头检查 |
| 前端读取/写入 Token | **0 处** | 静态扫描无 `localStorage` / `sessionStorage` / Cookie Token |

### 9.2 非回环访问

使用局域网地址访问：

```text
http://172.20.10.5:8080/api/dashboard/reviews/1001
```

并同时伪造：

```text
X-Forwarded-For: 127.0.0.1
X-Real-IP: 127.0.0.1
Forwarded: for=127.0.0.1
```

结果：

```text
HTTP 403，响应体为空
```

证明 `DashboardLocalAccessFilter` 基于真实 remote peer 判定，不信任转发头。

### 9.3 路径绕过矩阵

使用 `curl.exe --path-as-is` 并携带伪造转发头访问局域网地址：

| 路径 | 结果 |
|---|---:|
| `/api/dashboard/reviews/1001` | **403** |
| `/api/%64ashboard/reviews/1001` | **403** |
| `/api/%2564ashboard/reviews/1001` | **403** |
| `/api/dashboard;x/reviews/1001` | **403** |
| `/api/dashboard/reviews;x/1001` | **403** |
| `/api/dashboard/reviews/1001;x` | **403** |
| `/api/dashboard%3Bx/reviews/1001` | **403** |
| `/api/dashboard%2Freviews%2F1001` | **400**（Tomcat 拒绝，未进入业务） |
| `/api%2Fdashboard%2Freviews%2F1001` | **400**（Tomcat 拒绝，未进入业务） |
| `/api/dashboard\reviews\1001` | **400**（Tomcat 拒绝，未进入业务） |
| `/api/dashboard%5Creviews%5C1001` | **400**（Tomcat 拒绝，未进入业务） |
| `/api//dashboard//reviews//1001` | **403** |
| `/api/./dashboard/reviews/1001` | **403** |
| `/api/%2e/dashboard/reviews/1001` | **403** |
| `/api/dashboard/reviews/1001/findings?page=1&size=20` | **403** |

未出现路径规范化后绕过过滤器进入业务的情况。

### 9.4 浏览器网络边界

CDP 捕获的全部浏览器 API 请求：

- 仅访问 `/api/dashboard/reviews/**`。
- 未访问 Phase 10 内部 API（`/api/reviews`、`/api/tasks`、`/api/github`、`/api/internal`）。
- 未访问跨域地址。
- 未携带 `X-Internal-Token` 或 `Authorization`。

### 9.5 XSS 与 DOM 安全

1001 的 finding 文本包含真实恶意载荷：

```html
<img src=x onerror="window.__xss=1">
<script>window.__xss=2</script>
<svg onload="window.__xss=3">
<b>Use parameterized queries.</b>
```

真实浏览器验证：

| 检查 | 结果 |
|---|---|
| `window.__xss` | `undefined` |
| 展开区域危险节点（script/img/svg/iframe/object/embed/b） | 0 |
| finding 标题 DOM | 文本以 `&lt;img` 转义 |
| Description 文本 | 原样作为文本显示，不执行 |
| 页面 `[v-html]` 节点 | 0 |

静态扫描：

```text
v-html / innerHTML= / insertAdjacentHTML / outerHTML= → 0 处
```

### 9.6 其他安全确认

- 未执行任何来自 PR/仓库的不可信代码。
- 未调用 GitHub API 写操作。
- 未把 Secret、Token、密码写入报告或日志。
- 未引入 `v-html`、浏览器存储、Cookie Token、轮询。
- 未新增依赖。

**PASS。**

---

## 10. 数据库故障与日志安全

### 10.1 数据库表故障注入

将隔离库中的 `review_finding` 临时重命名：

```sql
USE codesentinel_accept_1123b;
RENAME TABLE review_finding TO review_finding_accept_tmp;
```

请求结果：

```text
GET /api/dashboard/reviews/1001/findings
→ 500 {"error":"internal_error"}

GET /api/dashboard/reviews/1001
→ 500 {"error":"internal_error"}
```

恢复：

```sql
RENAME TABLE review_finding_accept_tmp TO review_finding;
```

恢复后：

```text
GET /api/dashboard/reviews/1001/findings
→ 200
```

确认：

- 故障期间未返回 SQL、表名、堆栈或驱动异常。
- 表已恢复，服务无需重启即可继续工作。
- 未对现有业务库执行该操作。

**PASS。**

### 10.2 日志敏感值扫描

扫描文件：

```text
backend.out.log
backend.err.log
frontend.out.log
frontend.err.log
```

对本地 `.env` 中 7 个敏感配置逐项统计出现次数：

| 配置键 | 出现次数 |
|---|---:|
| `MYSQL_PASSWORD` | **0** |
| `MYSQL_ROOT_PASSWORD` | **0** |
| `DEEPSEEK_API_KEY` | **0** |
| `GITHUB_WEBHOOK_SECRET` | **0** |
| `GITHUB_PRIVATE_KEY` | **0** |
| `REVIEW_RESULT_INTERNAL_TOKEN` | **0** |
| `REVIEW_HISTORY_INTERNAL_TOKEN` | **0** |

同时扫描：

```text
X-Internal-Token
Authorization
Bearer
```

结果：**0 处**。

### 10.3 日志中的业务标识

数据库故障期间，Hibernate 默认日志出现：

```text
SQL Error: 1146, SQLState: 42S02
Table 'codesentinel_accept_1123b.review_finding' doesn't exist
```

评估：

- 未包含数据库密码、Token、用户数据或源码内容。
- 包含 SQLState、错误码与隔离库表名。
- 属于 Hibernate 默认 SQL 异常日志，不是 BFF 主动输出。
- 不影响本阶段功能验收，但生产环境应通过日志级别与异常映射收敛。

**记为非阻塞警告 W-2。**

### 10.4 应用日志

应用层日志仅记录：

```text
WARN  Dashboard review history is incomplete: Incomplete findings history for task id=1003...
ERROR Dashboard review history is unreadable: Unreadable references_json...
```

未记录完整响应体、Token 或敏感配置。

**PASS（附 W-2 警告）。**

---

## 11. 真实浏览器端到端验收

### 11.1 方法与限制

- 使用系统 Chrome `156.0.8078.81` 的 headless 模式。
- 通过 CDP `Page.navigate`、`Runtime.evaluate`、`Network.enable`、`Fetch.enable`、`Emulation.setDeviceMetricsOverride` 完成真实导航、点击、请求监听、故障注入与截图。
- **未安装 Playwright**，未新增依赖。
- E2E 脚本位于工作区外：

```text
%TEMP%\opencode\cs-accept-1123b\cdp-e2e.mjs
```

执行命令：

```powershell
node $env:TEMP\opencode\cs-accept-1123b\cdp-e2e.mjs
```

结果：**51 项检查全部通过。**

### 11.2 列表入口与详情基础信息

| 检查 | 结果 | 证据 |
|---|---|---|
| Review History 列表加载 6 条存储报告 | **PASS** | rows=6，链接 `#1001`–`#1006` |
| 列表侧边栏选中 Review History | **PASS** | active=`Review History` |
| 点击 taskId 进入 `/reviews/1001` | **PASS** | path=`/reviews/1001`，h1=`Review #1001` |
| 详情页侧边栏保持 Review History | **PASS** | active=`Review History` |
| Review information 展示完整元数据 | **PASS** | repository、PR #42、40 位 SHA、三种状态、45/25、#9001 |
| AI Summary 仅展示持久化状态与计数 | **PASS** | 含 DEGRADED / 45 / PARTIAL，并提示叙述摘要与风险等级未存储 |
| findings 默认第 1 页 20 条 | **PASS** | rows=20，badge=`45 findings`，分页 Total 45 |
| comments 默认第 1 页 20 条 | **PASS** | rows=20，badge=`25 comments`，分页 Total 25 |
| 三个请求分别发出 | **PASS** | report、findings、comments 均 200 |
| 1440px 无横向溢出 | **PASS** | `scrollWidth - innerWidth = -10` |

### 11.3 Finding 展开与 XSS

| 检查 | 结果 |
|---|---|
| 展开行展示 Description / Reason / Suggestion / References | **PASS** |
| References 过滤 null/空白后保留 2 项 | **PASS** |
| 恶意 HTML 作为文本显示 | **PASS** |
| `window.__xss` 未定义 | **PASS** |
| 危险 DOM 节点 0 个 | **PASS** |
| 页面无 `v-html` 节点 | **PASS** |

### 11.4 独立分页与刷新

| 检查 | 结果 | 证据 |
|---|---|---|
| findings 第 2 页显示 #21–#40 | **PASS** | rows=20，active=2 |
| findings 翻页不影响 comments | **PASS** | comments rows=20，active=1 |
| comments 第 2 页显示最后 5 条 | **PASS** | rows=5，含 #21–#25，不含 #26 |
| comments 翻页不影响 findings | **PASS** | findings rows=20，active=2 |
| findings 第 3 页显示最后 5 条 | **PASS** | rows=5，含 #41–#45 |
| null GitHub comment ID 显示 `ID unavailable` | **PASS** | 第 25 条 comment |
| Refresh 重载 report、findings 当前页、comments 当前页 | **PASS** | findings p3、comments p2 均保留，3 个请求成功 |

### 11.5 并发与取消

| 场景 | 结果 | 证据 |
|---|---|---|
| 快速连续切换 findings 页码 | **PASS** | 最终停留在最后一次选择的第 1 页 |
| 过期 findings 请求被取消 | **PASS** | 2 个 `net::ERR_ABORTED` |
| 路由切换离开详情页 | **PASS** | 1 个在途请求 `net::ERR_ABORTED` |
| 返回列表后列表仍可用 | **PASS** | rows=6 |
| 过期响应不覆盖最后一次选择 | **PASS** | 页面数据与最后一次请求一致 |

### 11.6 页面状态

| 场景 | 结果 | 证据 |
|---|---|---|
| 404 `/reviews/999999` | **PASS** | `Review not found`，仅请求 report，响应 404 |
| 409 `/reviews/1003` | **PASS** | `Review history is incomplete`，不展示部分 findings |
| 400（CDP 故障注入） | **PASS** | `Unable to load review detail` + 通用文案，不泄漏 `invalid_task_id` |
| 400 后 Retry 恢复 | **PASS** | 恢复真实 1006 数据 |
| 500 findings（1004 损坏 JSON） | **PASS** | findings 区块显示安全错误，comments 区块与页面其余部分正常 |
| 500 响应不泄漏内部信息 | **PASS** | 页面无 `invalid_json`、`references_json`、`SQLException`、`internal_error` |
| 1002 空数据 | **PASS** | 两个区块显示空状态，计数为 0 |
| 1002 null 字段 | **PASS** | `summaryCommentId` → `Not available`，`publishedAt` → `—` |
| 1006 未知枚举 | **PASS** | AI 状态显示 `UNKNOWN`，finding 显示 `MYSTERY` / `UNKNOWN`，不崩溃 |

关于 400：正常正整数路由不会自然产生非法 taskId，因此使用 CDP `Fetch.fulfillRequest` 将 1006 的 report 请求替换为固定 400 响应，仅验证前端错误映射，不修改后端或数据库。

### 11.7 无效前端路由

| 路径 | 结果 | API 请求数 |
|---|---|---:|
| `/reviews/0` | `Invalid review id`，说明不会发送请求 | **0** |
| `/reviews/999999999999999999999` | `Invalid review id`，说明不会发送请求 | **0** |
| `/reviews/not-a-number` | `Page not found` | **0** |

说明：非法数字 ID 由前端在发请求前拦截；非数字子路径不匹配详情路由，进入 not-found。

### 11.8 后端不可用与恢复

步骤：

1. 停止 8080 端口的 Spring Boot 进程。
2. 浏览器访问 `/reviews/1001`。
3. Vite 代理返回 **502**（`text/plain`）。
4. 页面显示：

```text
Unable to load review detail
The server returned an invalid response.
Retry
```

5. 在后端仍不可用时点击 Retry，页面保持安全错误状态。
6. 重启后端。
7. 点击 Retry。

恢复结果：

```text
GET /api/dashboard/reviews/1001                    → 200
GET /api/dashboard/reviews/1001/findings?page=1&size=20  → 200
GET /api/dashboard/reviews/1001/comments?page=1&size=20  → 200
```

页面恢复：

- h1=`Review #1001`
- findings rows=20
- comments rows=20
- error state=0
- JS exceptions=0

**PASS。**

### 11.9 浏览器运行质量

| 指标 | 结果 |
|---|---|
| 未捕获 JS 异常 | **0** |
| 应用 console error | **0** |
| 预期网络错误日志 | 主 E2E 中 4 条，对应主动构造的 400 / 404 / 409 / 500；后端不可用的 502 在独立故障脚本中验证 |
| 非预期 API 状态码 | 0 |
| 浏览器 API 请求总数 | 28+，全部位于 `/api/dashboard/reviews` |

### 11.10 响应式布局与截图

| 视口 | 结果 | 截图 |
|---|---|---|
| 1440px 桌面 | 无横向溢出；`scrollWidth - innerWidth = -10` | `review-detail-1440.png`（1430×4021） |
| 390px 移动 | 无横向溢出；侧边栏隐藏；菜单按钮 `Open navigation` | `review-detail-390.png`（390×4849） |
| 后端不可用 | 错误状态与 Retry 正常 | `review-detail-backend-down.png`（1418×1002） |

截图路径：

```text
%TEMP%\opencode\cs-accept-1123b\review-detail-1440.png
%TEMP%\opencode\cs-accept-1123b\review-detail-390.png
%TEMP%\opencode\cs-accept-1123b\review-detail-backend-down.png
```

**PASS。**

---

## 12. 已知限制、警告与最终判定

### 12.1 非阻塞警告

| 编号 | 警告 | 影响 | 建议 |
|---|---|---|---|
| **W-1** | 后端不可用时，经 Vite 代理表现为 HTTP 502，页面显示 `The server returned an invalid response.` | 用户无法区分“服务未启动”和“响应格式异常”；Retry 可恢复 | 后续可增加网络错误/服务不可用专用文案；本阶段不阻塞 |
| **W-2** | 数据库表故障时，Hibernate 默认日志输出 `SQL Error: 1146, SQLState: 42S02` 与表名 | 日志包含隔离库表名；无密码、Token、用户数据 | 生产环境应收紧 SQL 异常日志级别，并在 BFF 层保持固定错误体 |

两项均不影响 Review Detail 的功能正确性、安全边界或数据一致性。

### 12.2 继承的已知限制

以下限制来自 Phase 10 持久化契约，本阶段未改变：

1. **没有 AI 叙述性摘要与总体风险等级。** 页面只展示持久化的 AI 状态、计数、发布状态与 summary comment ID，并明确说明未存储。
2. **没有评论正文、发布时间、GitHub URL。** `review_comment` 仅保存已成功发布的定位信息。
3. **不展示发布失败或跳过的评论。** 这些信息未通过查询 API 暴露。
4. **GitHub comment ID 可能为空。** 页面显示 `ID unavailable`，不推断为发布失败。
5. **BFF 仅限本机访问。** 现有 `DashboardLocalAccessFilter` 只接受回环地址；远程部署或反向代理需要后续单独设计认证边界。
6. **详情页不提供跳转 GitHub 的链接。** 当前契约没有仓库 HTML URL 或 PR URL。
7. **无自动刷新与轮询。** 运行中的审查任务需要用户手动 Refresh。

### 12.3 明确未做

- 未实现 Phase 11.2.4。
- 未修改数据库 Schema。
- 未修改 Phase 10 Controller / Service / DTO / Repository。
- 未修改 `DashboardLocalAccessFilter`。
- 未新增依赖。
- 未安装 Playwright。
- 未执行任何 Git 提交、推送、合并、变基、重置、清理、检出或删除分支。
- 未修改 `docs/DEVELOPMENT_STATUS.md`、Phase 10 报告、Phase 11.2.3-A 报告。
- 未把真实 Token、密码、Secret 写入报告或日志。

### 12.4 最终判定

**PASS WITH WARNINGS。**

Phase 11.2.3-B 已满足验收要求：

- 核心 Review Detail 闭环可用。
- 正常、空数据、404、409、400、500、数据库故障、后端不可用均有可核查证据。
- 分页、独立区块、刷新、取消、恢复行为正确。
- 安全边界与错误脱敏通过。
- 自动化测试与真实浏览器 E2E 全部通过。

本阶段到此停止，等待人工确认；**未进入 Phase 11.2.4**。
