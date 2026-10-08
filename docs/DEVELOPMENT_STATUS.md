# CodeSentinel Development Status

> 本文件用于记录 CodeSentinel 的**实际开发进度**。  
> 与 `AGENTS.md`、`docs/PROJECT_DESIGN.md` 配合使用。
>
> - `AGENTS.md`：项目开发规则与约束
> - `PROJECT_DESIGN.md`：项目方案、架构与技术路线
> - `DEVELOPMENT_STATUS.md`：当前实际做到哪里

---

# 1. 当前项目状态

## 项目名称

**CodeSentinel**

中文名称：**代码哨兵——AI 智能代码审查系统**

## 当前阶段

**Phase 6：Code Context — ✅ 完成（6.1~6.7.6 全部完成；真实 PR E2E 验收通过）**

## 当前任务

Phase 6.7.6（真实 PR E2E 联调）已完成并通过验收（PR #3，task 3~7；含受控 degraded 演练；Python 1052 / Java 202）。下一步：Phase 7（Static Analysis）。

## 当前总体进度

```text
Phase 1  基础工程                 ✅ 已完成
Phase 2  GitHub App + Webhook     ✅ 已完成
Phase 3  GitHub API               ✅ 已完成
Phase 4  Review Task + Redis      ✅ 已完成
Phase 5  Python AI Service        ✅ 已完成
Phase 6  Code Context             ✅ 已完成（6.1~6.7.6，真实 PR E2E 验收通过）
Phase 7  Static Analysis          ⬜ 未开始
Phase 8  LangGraph Multi-Agent    ⬜ 未开始
Phase 9  GitHub 评论              ⬜ 未开始
Phase 10 MySQL 历史记录           ⬜ 未开始
```

---

# 2. 已确定的项目决策

以下内容已经确定，除非用户明确要求，否则不要擅自修改。

| 方向 | 当前决策 |
|---|---|
| 产品入口 | GitHub Pull Request 自动审查 |
| 支持语言 | Java + Python |
| 检测方向 | Bug + Security + Performance + Quality |
| 后端 | Spring Boot 3 |
| 后端语言 | Java 21 |
| AI 服务 | Python + FastAPI |
| Agent | LangChain + LangGraph |
| LLM | DeepSeek API |
| GitHub | GitHub App + Webhook + GitHub API |
| 数据库 | MySQL 8 |
| 异步任务 | Redis |
| MVP RAG | 不做 |
| MVP Milvus | 不做 |
| GitHub 输出 | PR Summary + Inline Comment |
| Dashboard | 第二阶段 |
| VS Code | 后续阶段 |
| GitHub Action | 后续阶段 |
| 用户代码执行 | MVP 不执行 |
| 自动修复 | 后续阶段 |
| GitHub Review 状态 | MVP 只使用 COMMENT，不自动 APPROVE / REQUEST_CHANGES |

---

# 3. 总体开发路线

```text
Phase 1
基础工程
    ↓
Phase 2
GitHub App + Webhook
    ↓
Phase 3
GitHub API
    ↓
Phase 4
Review Task + Redis
    ↓
Phase 5
Python AI Service + DeepSeek
    ↓
Phase 6
Code Context
    ↓
Phase 7
Static Analysis
    ↓
Phase 8
LangGraph Multi-Agent
    ↓
Phase 9
GitHub Summary + Inline Comment
    ↓
Phase 10
MySQL 历史记录
    ↓
MVP 完成
```

后续扩展：

```text
Phase 11 Dashboard
    ↓
Phase 12 Custom Rules
    ↓
Phase 13 RAG / Milvus
    ↓
Phase 14 GitHub Action
    ↓
Phase 15 VS Code
    ↓
Phase 16 Sandbox + Auto Fix
```

---

# 4. Phase 1：基础工程

## 目标

建立最小可运行的项目骨架。

### Spring Boot

```text
backend/
└── spring-service/
```

目标：

- Spring Boot 3
- Java 21
- 基础 REST API
- 基础配置管理
- 基础日志
- 基础异常处理
- 基础测试

### Python

```text
agent/
```

目标：

- Python 3.12+
- FastAPI
- 基础配置
- 基础日志
- `/health`
- 基础测试
- LLM Service 骨架

### 基础设施

```text
infra/
└── docker-compose.yml
```

目标：

- MySQL 8
- Redis
- Spring Boot / Python 服务的基础容器配置

## Phase 1 状态

**✅ 已完成**

## 已完成

- [x] 创建 Monorepo
- [x] 创建 Spring Boot 项目
- [x] 创建 Python 项目
- [x] 创建 Docker Compose
- [x] 配置 MySQL
- [x] 配置 Redis
- [x] 基础测试通过

## 当前任务

Phase 1 基础工程全部完成。下一步：Phase 2（GitHub App + Webhook）。

## 阻塞问题

暂无。

---

# 5. Phase 2：GitHub App + Webhook

## 目标

实现 GitHub → Spring Boot 的自动事件触发链路。

目标流程：

```text
GitHub PR
   ↓
GitHub App
   ↓
Webhook
   ↓
Spring Boot
   ↓
验证签名
   ↓
解析事件
```

## 子任务

- [x] 创建 GitHub App
- [x] 配置 App ID
- [x] 配置 Private Key (PEM 文件路径方式)
- [x] 配置 Webhook Secret (待用户填写 .env)
- [x] 配置 Repository 权限
- [x] Webhook Controller
- [x] `X-Hub-Signature-256` 验证
- [x] `pull_request` Event 解析
- [x] 支持 `opened`
- [x] 支持 `synchronize`
- [x] 支持 `reopened`
- [x] 真实 GitHub Webhook 联调（Smee + Spring Boot）

## Phase 2 状态

**✅ 已完成**

Webhook 全链路已打通：

```text
GitHub PR → GitHub App → Smee → Spring Boot /api/github/webhook
                                ↓
                         X-Hub-Signature-256 验证通过
                                ↓
                         pull_request 事件解析成功
                                ↓
                         返回 200 OK
```

Webhook 幂等设计依赖后续 Task 系统（Phase 4），届时再统一实现。

## 当前任务

Phase 2 已完成。下一步：Phase 3（GitHub API）。

## 阻塞问题

暂无。

---

# 6. Phase 3：GitHub API

## 目标

让 Spring Boot 能够获取 PR 审查所需的全部代码信息。

## 子任务

- [x] Installation Token 获取
- [x] Repository API
- [x] Pull Request API
- [x] Commit API
- [x] Changed Files / Diff 获取
- [x] 文件内容获取
- [x] GitHub API 错误处理
- [ ] Token 缓存 / 刷新（Phase 3.x 后续）
- [ ] Rate Limit 处理基础机制（Phase 3.x 后续）

## 关键输出

系统已经能够获得：

```text
Repository
PR
Commit
Diff
Changed Files
File Content
```

## Phase 3 状态

**✅ 已完成**

完整数据获取链路：

```text
Webhook (Phase 2)
    ↓
GithubPullRequestClient.getPullRequest(owner, repo, prNumber)
    ↓ PullRequest { number, title, state, head: { sha, ref }, base: { ref } }
    ↓
GithubCommitClient.getCommit(owner, repo, head.sha)
    ↓ Commit { sha, message, files: [{ filename, status, patch }] }
    ↓
GithubFileContentClient.getFileContent(owner, repo, file.filename, head.sha)
    ↓ FileContent { path, content }
    ↓
AI Review (Phase 5+)
```

## Phase 3 子阶段

### Phase 3.1：GitHub App JWT + Installation Token

- [x] `GithubJwtService` — RS256 JWT 生成（纯 Java 标准库，零额外依赖）
- [x] `GithubAuthService` — App JWT → Installation Access Token
- [x] `InstallationToken` record — token + expires_at
- [x] `GithubApiException` — 统一异常，含 HTTP statusCode
- [x] 测试：GithubJwtServiceTest（20 tests）+ GithubAuthServiceTest（13 tests）

### Phase 3.2：GitHub API Client 基础设施

- [x] `GithubApiClient` — 共享 RestClient（baseUrl + Accept header + 错误处理）
- [x] 非 2xx 响应 → `GithubApiException(statusCode, body)`
- [x] 测试：GithubApiClientTest（10 tests）

### Phase 3.3：Repository API

- [x] `GithubRepositoryClient` — GET /repos/{owner}/{repo}
- [x] `Repository` record — id, full_name, name
- [x] 测试：GithubRepositoryClientTest（8 tests）

### Phase 3.4：Pull Request API

- [x] `GithubPullRequestClient` — GET /repos/{owner}/{repo}/pulls/{number}
- [x] `PullRequest` record — number, title, state, head{sha, ref}, base{ref}
- [x] 测试：GithubPullRequestClientTest（10 tests）

### Phase 3.5：Commit / Diff / Changed Files API

- [x] `GithubCommitClient` — GET /repos/{owner}/{repo}/commits/{sha}
- [x] `Commit` record — sha, message, files[{ filename, status, patch }]
- [x] 测试：GithubCommitClientTest（11 tests）

### Phase 3.6：File Content API

- [x] `GithubFileContentClient` — GET /repos/{owner}/{repo}/contents/{path}?ref={sha}
- [x] `FileContent` record — path, content（Base64 解码后）
- [x] 测试：GithubFileContentClientTest（11 tests）

## 当前测试

全量测试：**104/104** 通过，BUILD SUCCESS。

## 当前任务

Phase 3 已完成。下一步：Phase 4（Review Task + Redis）。

## 阻塞问题

暂无。

---

# 7. Phase 4：Review Task + Redis

## 目标

实现 GitHub Webhook 和 AI Review 的异步解耦。

目标流程：

```text
Webhook
   ↓
ReviewTask
   ↓
MySQL / Redis
   ↓
Python Worker
```

## 子任务

- [x] ReviewTask Entity
- [x] ReviewTask Repository
- [x] ReviewTask Service
- [x] Task Status (PENDING / RUNNING / COMPLETED / FAILED)
- [x] Redis Task Producer
- [x] Python Worker (BLPOP consumer)
- [x] Task 消费
- [x] 基础失败处理
- [x] retry_count
- [x] 幂等控制 (owner + repo + prNumber + commitSha)

## Phase 4 子阶段

- [x] Phase 4.1：ReviewTask Entity + TaskStatus
- [x] Phase 4.2：ReviewTaskRepository + ReviewTaskService
- [x] Phase 4.3：Webhook → ReviewTaskService.createTask
- [x] Phase 4.4：Redis Producer (RPUSH to codesentinel:review:tasks)
- [x] Phase 4.5：Python Worker (BLPOP + TaskHandler)
- [x] Phase 4.6：Retry + Idempotency

## Phase 4 完成链路

```text
GitHub Webhook
    ↓
WebhookController
    ↓
ReviewTaskService.createTask()  ← 幂等 (owner+repo+pr+sha)
    ↓
ReviewTask(PENDING) → MySQL
    ↓
ReviewTaskProducer.publish() → Redis RPUSH
    ↓
Redis List "codesentinel:review:tasks"
    ↓
Python Worker BLPOP → TaskHandler
    ↓
Java 状态 API (Running / Complete / Failure)
    ↓
成功 → COMPLETED
失败 → retryCount < 3 → PENDING → Redis 重入队
         retryCount >= 3 → FAILED
```

## Retry 配置

- MAX_RETRY_COUNT: 3（环境变量 REVIEW_TASK_MAX_RETRIES）
- retryCount 由 Java / MySQL 作为唯一数据源
- Python Worker 不自己计算 retryCount

## Java 内部 API

| 端点 | 说明 |
|---|---|
| POST /api/tasks/{taskId}/running | 标记 RUNNING |
| POST /api/tasks/{taskId}/complete | 标记 COMPLETED |
| POST /api/tasks/{taskId}/failure | 返回 {"retry":bool, "taskId":int, "retryCount":int, "status":"PENDING"/"FAILED"} |

## 测试结果

| 服务 | 总数 | 通过 | 状态 |
|---|---|---|---|
| Java (Spring Boot) | 152 | 152 | ✅ BUILD SUCCESS |
| Python (agent) | 25 | 25 | ✅ 全部通过 |

> 注：test_health.py 在 Windows 临时端口耗尽时偶发 WinError 10055 失败，属于系统环境问题（已通过 `netsh int ipv4 set dynamicport tcp start=10000 num=55535` 解决），非 Phase 4 代码问题。

## Phase 4 状态

**✅ 已完成**

## 当前任务

Phase 4 全部完成。下一步：Phase 5（Python AI Service + DeepSeek）。

## 阻塞问题

暂无。

---

# 8. Phase 5：Python AI Service + DeepSeek

## 目标

先完成最小 AI Review 链路，不急着实现完整 Multi-Agent。

目标：

```text
Spring Boot
   ↓
Python AI Service
   ↓
DeepSeek
   ↓
Structured Finding
   ↓
Spring Boot
```

## 子任务

- [x] LLM Service（LLMService：调用 + JSON 解析 + Pydantic 校验）
- [x] DeepSeek 配置（DEEPSEEK_API_KEY / MODEL / BASE_URL / TIMEOUT / TEMPERATURE）
- [x] Timeout（DeepSeek 调用 60s；Worker → AI Service 120s，AI_SERVICE_TIMEOUT）
- [x] Retry（复用 Phase 4 外层 task retry：LLM 失败 → FastAPI 500 → Worker → failure/retry 链路；LLM 内部 retry/repair 未实现，属后续优化）
- [x] Pydantic Schema（ReviewTaskRequest / ReviewTaskResult / ReviewFinding / LlmReviewOutput）
- [x] Structured Output（DeepSeek json_object → json.loads → LlmReviewOutput.model_validate）
- [x] 基础 Review Prompt（agent/app/prompts/review.py，system + user）
- [ ] Java Review（依赖 Phase 6 Code Context 提供代码内容）
- [ ] Python Review（依赖 Phase 6 Code Context 提供代码内容）
- [x] Service-to-Service API（POST /api/reviews，Phase 5.1）

## Phase 5 子阶段

- [x] Phase 5.1：Python AI Service HTTP 边界（Review DTO / Mock ReviewService / Worker 接线）— commit `d9fa710`
- [x] Phase 5.2：DeepSeek LLM 真实调用（LLMService / DeepSeekClient / Prompt / 结构化输出）

## Phase 5 完成链路

```text
Redis BLPOP "codesentinel:review:tasks"
    ↓
Python Worker (TaskHandler)
    ↓ HTTP POST /api/reviews (timeout=AI_SERVICE_TIMEOUT, 默认 120s)
FastAPI ReviewService (async)
    ↓ prompts.build_messages (system + user)
LLMService
    ↓ DeepSeekClient (httpx.AsyncClient, json_object 模式)
DeepSeek API POST {DEEPSEEK_BASE_URL}/chat/completions
    ↓ choices[0].message.content (JSON 字符串)
json.loads → LlmReviewOutput.model_validate → ReviewFinding[]
    ↓
ReviewTaskResult (status=COMPLETED, report 统计)
    ↓
Worker → Java POST /api/tasks/{id}/complete
    ↓
MySQL: COMPLETED
```

异常传播（复用 Phase 4 机制，零新增 retry）：

```text
LLMConfigError / LLMException / LLMResponseError
    ↓
FastAPI 500 → AiServiceClient raise_for_status
    ↓
handler._process 抛出 → consumer._handle_task_failure
    ↓
Java report_failure → retry 判定 → RPUSH 重入队 / FAILED
```

## 关键设计

- DeepSeek 使用 httpx.AsyncClient 直连 OpenAI-compatible API，未引入 OpenAI SDK / LangChain / LangGraph
- API 层 → ReviewService → LLMService → DeepSeekClient 四层职责分离；Prompt 独立在 app/prompts/
- LLM 只产出 findings；task_id / status / report 由 ReviewService 组装
- 当前 files=[]（无代码内容），LLM 正确返回 findings=[]，属预期行为
- test_deepseek_live.py 在 DEEPSEEK_API_KEY 未配置时自动 skip，默认 pytest 不依赖真实 API

## 测试结果

| 服务 | 总数 | 通过 | 状态 |
|---|---|---|---|
| Java (Spring Boot) | 152 | 152 | ✅ |
| Python (agent) | 79 | 79 | ✅（含 2 个真实 DeepSeek live 测试） |

真实 DeepSeek 联调（Phase 5.2 收尾时执行）：
- live 单测：files=[] / files=[路径] 均返回 findings=[]，2 passed
- 全链路：Redis → Worker → FastAPI → DeepSeek（HTTP 200，content_length=16 即 `{"findings": []}`）→ Java → MySQL COMPLETED（5 秒内）

## 已知问题 / 技术债

- DEEPSEEK_API_KEY 当前来自系统环境变量，agent/.env 未持久化（建议统一到 agent/.env）
- 本机 redis-server 与 Docker Redis 均监听 6379，localhost 解析到本机实例（手工验证时消息需投递本机 Redis）
- 环境实装 redis-py 8.1.0，requirements.txt 声明 redis>=5.0,<6.0 不符
- MySQL review_task 表由手动 DDL 创建（JPA ddl-auto 默认 none）
- LLM 内部 retry / repair / JSON 自动修复未实现（按 Phase 5.2 边界，走外层 task retry）

## Phase 5 状态

**✅ 已完成**

核心目标"先证明 Spring Boot → Python → DeepSeek → Structured Finding → Spring Boot 链路是通的"已达成。Java/Python 代码的真实分析能力在 Phase 6 提供 Code Context 后自然生效。

## 当前任务

Phase 5 已完成。下一步：Phase 6（Code Context）。

## 阻塞问题

暂无。

---

# 9. Phase 6：Code Context

## 目标

避免只把 Git Diff 直接交给 LLM。

目标：

```text
Diff
 ↓
Changed File
 ↓
Changed Method
 ↓
Class
 ↓
Imports
 ↓
Related Code
 ↓
Code Context
```

## 第一阶段优先技术

- AST
- Tree-sitter
- JavaParser
- ripgrep
- 简单依赖分析

暂不使用：

- Milvus
- RAG

**实际采用（6.1~6.5）**：统一 diff 行号语义 + 正则识别 + 行扫描 + 字符串/注释掩码 + Java 大括号深度 + Python 缩进。**未引入任何第三方解析依赖，未使用 AST / Tree-sitter / JavaParser / ripgrep**；所有定位结果标记 `source=HEURISTIC` 并携带 `confidence`，后续若精度不足可在不改契约的前提下替换实现（`SymbolSource.AST` 已预留）。

## 子任务

- [x] Diff Parser（Phase 6.1，commit `5c8c703`）
- [x] File Context（Phase 6.2，commit `f29190e`）
- [x] Method Context（Phase 6.3，commit `4cbdd6b`）
- [x] Class Context（Phase 6.4，commit `c6b5391`）
- [x] Related Code（Phase 6.5，commit `6c9bc48`）
- [x] Context Size Control（Phase 6.6.1 ~ 6.6.3，commits `ca97606` / `e3f0b3c` / `f4192dd`）
- [x] Token 控制（Phase 6.6.4，commit `d3ecb2f`）

## Phase 6 尚未完成的部分（重要，勿误判为已闭环）

6.1~6.6 完成的是**纯 Python、可离线测试的 Code Context 构建链与预算控制**；6.7.1 提供了 Java 侧 PR Context 只读接口。**Python 侧取码与装配尚未实现**：

- [x] Java 侧 PR Context 只读接口（Phase 6.7.1：`GET /api/tasks/{taskId}/pr-context`，含分页 / 内容保护 / 单 Token 复用；**尚未提交**）
- [x] Python 侧 `PrContext` DTO + `PrContextClient`（Phase 6.7.2：`schemas/pr_context.py` + `context/pr_context_client.py`；**尚未提交**）
- [x] `CodeContextBuilder`：`PrContext → CodeContext` 装配（Phase 6.7.3：`context/code_context_builder.py`；**尚未提交**）
- [x] `ReviewService` 接线（Phase 6.7.4：取码 → 装配 → 预算；取码失败降级 `degraded`，不触发 Phase 4 无限重试；**尚未提交**）
- [x] Prompt 渲染 Code Context + `file_path` / 行号硬约束（Phase 6.7.5：`prompts/code_context.py` + `build_messages(request, context, context_report)`；**尚未提交**）
- [x] 真实 PR 端到端联调（Phase 6.7.6：PR #3，webhook → Task → Redis → Worker → PR Context → CodeContext → Budget → Prompt → DeepSeek → Findings 全部通过；含受控 degraded 演练；**尚未提交**）

因此当前 `handler.py` 仍传 `files=[]`（仅影响 Prompt header 的文件列表显示，Context 按 task_id 获取）；`prompts/review.py` 已在 Context 可用时渲染真实代码（diff / changed methods / related code / 不可用原因 / 截断声明），仅在无 Context 配置时保留 Phase 5 的 "no file content" 声明。

## Phase 6 子阶段

### Phase 6.1：Diff Parser + Code Context 数据契约（commit `5c8c703`）

- [x] `agent/app/schemas/code_context.py`：Phase 6 全套内部契约（Language / FileStatus / DiffLine / Hunk / ChangedRange / SymbolRef / FileStructure / CodeSnippet / FileDiff / FileContext / CodeContext）
- [x] `agent/app/context/diff_parser.py`：`detect_language` / `parse_file_status` / `parse_hunks` / `merge_changed_ranges` / `parse_patch`
- [x] 行号一律 1-based 且以 **diff 新文件侧**为准（Phase 9 行级评论的前提）
- [x] 替换语义（`-` 紧跟 `+`）只报新增侧；纯删除锚定到最近的新侧行；整文件删除不产出区间（不伪造行号）
- [x] 按 hunk header 声明行数关闭 hunk，避免把下一个文件的 `--- a/x` 误读为删除行
- [x] `patch=None`（binary / 纯 rename / 超大 diff）、空 patch、畸形 header 全部降级为 `notes`，不抛异常
- [x] 测试 138 项（`test_diff_parser.py` 77 + `test_code_context_schemas.py` 61）

### Phase 6.2：File Context（commit `f29190e`）

- [x] `FileContent { path, revision, content, error }` 输入模型（命名对齐 Java `FileContent` record）
- [x] `FileContext` 追加 `content` / `line_count`（向后兼容，6.1 字段与语义未变）
- [x] `agent/app/context/file_context_builder.py`：`split_lines` / `count_lines` / `build_file_context` / `build_file_contexts`
- [x] 行号采用 **Git 行模型**：先归一 CRLF/CR，再 `split("\n")` 并只剥离末尾一个空元素；**不使用 `str.splitlines()`**（它会在 `\x0b`、`\x0c`、`\u2028` 处额外断行，导致与 diff 行号错位）
- [x] 关联键 = 新路径；`content.path != file_diff.path` 时拒绝使用（防止张冠李戴）
- [x] REMOVED 文件不要求 head 内容，传入的内容被忽略并记 note
- [x] 一致性检查：`revision` 不符、`changed_ranges` 超出文件长度、ADDED 文件行数少于新增行数 → 记 note，不修正事实数据
- [x] 测试 90 项（`test_file_context_builder.py` 76 + 契约 14）

### Phase 6.3：Method Context（commit `4cbdd6b`）

- [x] `MethodContext { name, start_line, end_line, kind, language, enclosing_class, signature, code, source, confidence, changed_ranges }`
- [x] `agent/app/context/method_context_builder.py`：`find_methods` / `match_methods` / `build_method_contexts` / `attach_method_contexts`
- [x] 共享扫描原语：字符串/字符字面量/行注释/块注释/Java 文本块/Python 三引号掩码（掩码与原行等长，列号可直接回用于切片）
- [x] Java：大括号深度 ≥ 1 + 签名正则 + 块关键字与前缀 token 双重排除 + 大括号配对求 body；接口/抽象的无 body 声明仅在 depth==1 接受（因此方法体内的 `foo(bar);` 不会被当方法）
- [x] Java 构造方法：无前缀候选需满足 depth==1 + 首字母大写 + **参数列表形状**（据此区分 `E(int v)` 构造方法与 `VALUE(1)` / `CODE("s")` 枚举常量）
- [x] Python：`def` / `async def` + 括号平衡 0 处的 `:` 求 header + 缩进求 block 尾；`kind` 由最近外层块头判定（class → METHOD，def/无 → FUNCTION，故嵌套函数是 FUNCTION）
- [x] 注解 / 装饰器计入 `start_line`（含跨行写法）
- [x] 关联采用 **overlap 而非 containment**：命中签名、命中注解行、一个区间跨多方法、多个区间落同一方法（合并为一个 MethodContext）均正确处理
- [x] 置信度：Java body 0.9 / 构造方法 0.7 / 无 body 声明 0.6 / Python 0.85
- [x] 真实代码自检：项目 28 个 Python 文件识别数与 `def` 行数全一致；Java main 69 个方法范围全部合法
- [x] 测试 120 项

### Phase 6.4：Class Context（commit `c6b5391`）

- [x] `TypeKind`（CLASS / INTERFACE / ENUM / RECORD / ANNOTATION_TYPE）+ `ClassContext { name, start_line, end_line, kind, language, depth, signature, code, source, confidence }`
- [x] `MethodContext.enclosing_class`、`FileContext.classes` 追加；6.1 就存在的 `FileContext.enclosing_class` 首次真正填充
- [x] `agent/app/context/class_context_builder.py`：`find_classes` / `find_anonymous_regions` / `innermost_scope` / `innermost_class` / `enclosing_class_name` / `build_class_contexts` / `attach_class_contexts`
- [x] 抽取 `agent/app/context/source_scanner.py`：6.3/6.4/6.5 共用掩码、大括号扫描、缩进块扫描、注解回溯、签名折叠与切片原语（避免多套解析器）
- [x] Java 支持 class / interface / enum / record / `@interface` / abstract class / static nested / inner / 多层嵌套 / 方法内 local class；`depth` = 同文件中包含它的类型个数（Java 与 Python 语义一致）
- [x] Python 支持 class / 多层 nested class / 装饰器；docstring 与字符串内的 `class X:` 被掩码忽略；顶格 docstring 内容不会截断块
- [x] **anonymous class 不生成 ClassContext**（无名可报，避免伪造），但其体区间作为"无名作用域"参与最近作用域竞争 → 匿名体内方法 `enclosing_class=None`，不会错误归属外层类；匿名体内的命名 local class 仍按最内层胜出
- [x] `FileContext.enclosing_class` 仅在无歧义时填充（变更方法的唯一 enclosing，或无方法时唯一的顶层类型），否则为 `None`
- [x] 真实代码自检：Java 48 个类型 / 246 个方法，0 处范围或切片错误；Python class 数量与独立统计 0 处不符
- [x] 测试 116 项 + 契约 14 项

### Phase 6.5：Related Code（commit `6c9bc48`）

- [x] `RelatedKind`（METHOD / CONSTRUCTOR / FIELD / NESTED_TYPE）+ `RelatedReason`（SIBLING_OF_CHANGED_METHOD / MEMBER_OF_CHANGED_CLASS）+ `RelatedCodeContext { path, name, start_line, end_line, reason, kind, owner_class, code, source, confidence }`；`FileContext.related_code` 追加
- [x] `agent/app/context/related_code_builder.py`：`build_related_code` / `attach_related_code`
- [x] 选择链路：`changed_ranges + changed methods → innermost_class 得 anchor → 取 anchor 的直接成员（同类方法 / 字段 / 构造方法 / 嵌套类型）→ 去重 → 稳定排序`
- [x] 排序优先级：同类方法 > 同类字段 > 构造方法 > 同类嵌套类型，同级按 `(start_line, name)`
- [x] 只取**结构证据**：`innermost_class == anchor`（方法/字段）、`depth == anchor.depth + 1` 且被包含（嵌套类型）；不做名称相似度、子串、语义或调用推断
- [x] 与 `changed_ranges` 重叠的候选一律丢弃 → 变更方法自身、被改字段、anchor 类型本身都不会重复出现，也不复制整个类源码
- [x] Java 字段：类体大括号深度 + `java_declaration_end` 遇 `;` 才算字段（正确排除方法、`static {}`、局部变量、`record = 1;`、枚举常量）；支持注解独立行、跨行初始化、数组、接口常量
- [x] Python 类属性：赋值与"仅注解"两种形态；按语句级游标消费，跨行初始化器的续行不会成为独立字段；多行 class header 的参数行不进入扫描；方法体内局部变量、模块级常量、嵌套类属性均不外泄
- [x] 跨文件搜索 / symbol index / call graph / imports / 继承解析 **一律未实现**（仅当前 FileContext）
- [x] 输入 FileContext 不可变（全部 `model_copy`），content 不可用 / REMOVED / 空文件 / OTHER / 畸形源码一律返回空列表
- [x] 真实代码自检：36 个文件跑完整 6.1→6.5，123 条 related code，切片与行号 0 问题、0 重复嵌套
- [x] 测试 89 项 + 契约 16 项

### Phase 6.6.1：Context 预算数据模型（commit `ca97606`）

- [x] `ContextBudget { max_item_chars=6000, max_related_chars=12000, max_file_chars=24000, max_total_chars=None, min_file_chars=4000, keep_changed_code=True, allow_nested_header_only=True }`（默认值来自真实测量）
- [x] `ContextStats { prompt_chars, prompt_chars_by_kind, estimated_tokens, related_total/kept/dropped, truncated_items, retained_source_chars }`
- [x] `Truncation { applied, reasons, dropped_items, trimmed_items, removed_chars }`
- [x] `RelatedCodeContext.truncated`、`MethodContext.truncated`、`ClassContext.header_end_line` 追加；`FileContext` / `CodeContext` 追加 `stats` / `truncation`（全部带默认值，向后兼容）
- [x] `agent/app/context/context_size_controller.py`：`estimate_tokens(text) = ceil(other_chars/3) + cjk_chars`（确定性、无 tokenizer、无网络）
- [x] 测试 30 项

### Phase 6.6.2：单文件 Context Size Control（commit `e3f0b3c`）

- [x] `measure_context(file_context) -> ContextStats`：只测不裁；`prompt_chars` 仅计 diff / changed methods / related / 元数据，`content` 与未变更 `classes[].code` 只进 `retained_source_chars`
- [x] `apply_context_budget(file_context, budget) -> FileContext`：related 按优先级整条删除；单条超限时 METHOD / CONSTRUCTOR / FIELD 整条删、NESTED_TYPE 可降级为声明头（依赖 `ClassContext.header_end_line`）；changed code 永不为 related 让路；diff 不裁
- [x] 优先级：reason（SIBLING > MEMBER）→ kind（METHOD > FIELD > CONSTRUCTOR > NESTED_TYPE）→ confidence → 与 changed_range 的行距 → start_line / name；保留条目**保持输入顺序**
- [x] `class_context_builder.py` 最小改动：填充 `header_end_line`（6.4 检测行为不变）
- [x] 输入不可变（`model_copy`）、幂等（已降级条目不二次收缩）；测试 61 项 + 契约 16 项

### Phase 6.6.3：多文件 Context Budget（commit `f4192dd`）

- [x] `plan_file_budgets(weights, budget)`：权重 = `1 + changed_method_count`；floor 优先、按权重分配、total 不足时按权重顺序确定性降级；输出顺序 = 输入顺序
- [x] `apply_context_budget_to_files(files, budget)`：逐文件复用 6.6.2，设置 `max_total_chars` 时进入全局二次削减（低重要度文件 → 同文件低优先级 related 先删；changed code 仍受保护；仍超则记录 `changed code exceeds total budget` 留给 Prompt 层）
- [x] `aggregate_stats(files)`：数值求和、`prompt_chars_by_kind` 首见序合并、`stats=None` 即时测量
- [x] 测试 40 项

### Phase 6.6.4：Token 控制（commit `d3ecb2f`）

- [x] `tokens_for_chars` / `chars_for_tokens`：与估算器同源（默认 3 字符/token，rate 下限 1；零/None/负数 → 0；精确往返）
- [x] `budget_from_tokens(...) -> ContextBudget`：把 token 限额换算为字符预算（单文件 / 多文件 / item / related / min-file），其余沿用 `base`（默认 `DEFAULT_BUDGET`），不修改 `base`
- [x] 未引入 tiktoken / tokenizers 等任何 Token SDK；未改 6.6.1~6.6.3 行为
- [x] 测试 49 项

### Phase 6.7.1：Java 侧 PR Context 读取（**尚未提交**）

- [x] `config/ReviewContextProperties`（`review.context.max-files=50` / `max-file-bytes=262144` / `max-fetch-pages=5` / `include-content-extensions=[java, py]`，含缺省值与扩展名归一化）；已登记到 `@EnableConfigurationProperties`，`application.yml` 同步
- [x] `github/GithubPullRequestFilesClient`：`GET /repos/{owner}/{repo}/pulls/{number}/files`，`per_page=100`，解析 `Link rel="next"` 分页；达到 `max-files` 立即停止后续请求；`max-fetch-pages` 安全上限；Link 缺失/畸形视为无下一页；保持 GitHub 返回顺序
- [x] `github/PullRequestFile`：`path / previousPath(previous_filename) / status / additions / deletions / changes / patch / blobUrl`
- [x] `prcontext/PrContextFile` / `PrContextResponse`：稳定 JSON 契约；空 `patch` 归一为 `null`；`content_available` / `content_truncated` / `content_reason`（蛇形字段，供 6.7.2 Python 侧对齐）
- [x] `prcontext/PrContextService`：从 ReviewTask 取 owner/repo/prNumber/commitSha → PR metadata → changed files → 逐文件内容决策；removed 与非 Java/Python 文件**在请求前**跳过；单文件 HTTP 失败仅降级该文件
- [x] `controller/PrContextController`：`GET /api/tasks/{taskId}/pr-context`；task 不存在 → 404（控制器内局部 `@ExceptionHandler(TaskNotFoundException)`）
- [x] `github/GithubFileContentClient` 修复：路径按段 `UriUtils` 编码（空格 / `#` / 中文安全）；`encoding != base64`、`type != file`、NUL 二进制、`size`/解码长度超限 → 明确标记 `content` 不可用且**不进入 JSON**；合法空文件（`size=0 + base64 + content=""`）仍返回空字符串
- [x] `github/GithubPullRequestClient` 追加 Token overload（原签名保留并委托，公共语义不变）
- [x] `github/FileContent` 追加 `contentReason` + `REASON_TOO_LARGE` / `REASON_BINARY`
- [x] Installation Token 单次复用：`PrContextService` 每次构建只取一次 Token 并贯穿 PR / files / contents 三个客户端（无全局缓存）
- [x] `content_reason` 取值：`removed` / `unsupported_language` / `too_large` / `binary` / `fetch_failed:<status>`（未知 HTTP 错误为 `fetch_failed:unknown`）
- [x] Java 测试 202/202（基线 152 + 新增 50：files client 14 / file content 9 / service 13 / controller 5 / properties 9）
- [x] `git diff --check` 通过；Python 本次零修改

**6.7.1 设计决策（已确认，不要再改）**

- `max-file-bytes` **无法**在 `GET /pulls/{n}/files` 阶段提前获知（该 API 不返回字节大小），因此采用 **contents 响应后的 `size` / 解码长度防护**；**不新增 Git Trees / Blobs API**（removed 与非 Java/Python 仍按规格在请求前跳过）
- `TaskNotFoundException` 在 `PrContextController` 内局部返回 404；其他 GitHub / Token 异常**沿用项目现有异常传播方式**（容器转 5xx），**不新增全局错误响应体系**
- `content_available` / `content_truncated` / `content_reason` 保持**蛇形字段名**，作为 6.7.2 Python 侧契约（其余字段沿用项目既有驼峰：taskId / owner / repo / prNumber / commitSha / previousPath / patch / blobUrl）

### Phase 6.7.2：Python PrContext DTO + PrContextClient（**尚未提交**）

- [x] `agent/app/schemas/pr_context.py`：`PrContext` + `PrContextFile`，严格对应 Java `GET /api/tasks/{taskId}/pr-context` 返回结构
  - Java 普通字段沿用项目既有 camelCase 映射（与 `TaskMessage` 一致：taskId / prNumber / commitSha / previousPath / blobUrl / baseRef / headRef）
  - `content_available` / `content_truncated` / `content_reason` 固定为**蛇形**（camelCase 变体不被接受，保持契约唯一）
  - `content` 允许 `null`；空字符串 `content=""` 仍表示**合法空文件**（`content_available=true`）
  - `content_reason` 原样保留 `removed` / `unsupported_language` / `too_large` / `binary` / `fetch_failed:*`
  - 必需字段：`path`、`status`（缺失 → ValidationError）；计数器与可选字段带容错默认值（0 / None / false）
- [x] `agent/app/context/pr_context_client.py`：`PrContextClient.fetch(task_id) -> PrContext`（async）
  - 使用既有 `httpx`（AsyncClient，与 DeepSeekClient 同风格），**未新增 HTTP 客户端依赖**
  - base URL 复用 `settings.JAVA_SERVICE_URL`，超时新增 `settings.PR_CONTEXT_TIMEOUT`（默认 30s，已同步 `.env.example`）
  - 非 2xx / 非 JSON / Schema 不符：记录日志后**原样抛出**（与 `AiServiceClient` / `JavaServiceClient` 约定一致），由调用方决定降级
  - 纯传输层：不做 Context 装配、不构建 Prompt、不做业务判断；日志不输出文件内容
- [x] 测试 44 项（`test_pr_context_schemas.py` 29 + `test_pr_context_client.py` 15）：完整解析 / 多文件顺序 / content=null 与 reason / 蛇形字段映射 / camelCase 变体拒绝 / 空文件保留 / 缺字段默认值 / 必需字段校验 / 404 / 5xx / 非 JSON / 空 files / 超时与 base URL 复用 / 传输层边界
- [x] Python 全量 948/948（基线 904 + 新增 44）

**6.7.2 设计决策**

- DTO 普通字段采用**与 `TaskMessage` 相同的 camelCase 字段名**（直接反序列化 Java JSON，无需 alias）；仅内容状态三字段使用蛇形，与 Java `@JsonProperty` 完全对齐
- 客户端为 **async**（未来消费者 `ReviewService` 也是 async；与 `DeepSeekClient` 风格一致），传输失败不包装成自定义异常，保持既有客户端约定
- 超时独立于 `AI_SERVICE_TIMEOUT`（上下文抓取涉及 Java 侧多次 GitHub 调用），但仍是同一套 `settings` 配置体系

### Phase 6.7.3：CodeContextBuilder（**尚未提交**）

- [x] `agent/app/context/code_context_builder.py`：`CodeContextBuilder.build(pr_context) -> CodeContext`（装配，无 IO、无预算、无 Prompt）
- [x] 复用 6.1~6.5 既有链路，不重复实现解析：`parse_patch → build_file_context → attach_method_contexts → attach_class_contexts → attach_related_code`
- [x] 字段映射：
  - `CodeContext.repository = "owner/repo"`、`pr_number`、`head_sha = commitSha`；**`base_sha` 保持 `None`**（Java 契约只提供 base 分支名而非 base SHA，不得把 ref 名当作 SHA 记录）
  - `PrContextFile.path/status/patch/previousPath` → `FileDiff`（patch=None → `patch_available=false` + note；renamed → `previous_path` 与新的 `path`）
  - `PrContextFile.content` → `FileContent { path, revision=commitSha, content, error=content_reason }` → `FileContext.content` / `line_count` / `content_available`
  - `content_reason` 保留在 `FileContext.content.error` 与 `notes` 中（removed / unsupported_language / too_large / binary / fetch_failed:*）
  - 文件顺序与 Java 返回顺序一致
- [x] 不可用内容安全语义：`content=null` 一律不伪造代码（methods/classes/changed_symbols/related_code 全为空、`line_count=0`、无 snippets/structure）；单个文件不可用不影响整体构建；REQUIRED 字段（如 removed 的 `skipped_reason`）与 note 保留原因
- [x] title / state / baseRef / headRef 不复制进 CodeContext（需要的调用方保留 PrContext；未为未来 Prompt 预设计字段）；未做任何 schema 结构调整
- [x] 未应用预算：`CodeContext.stats/truncation` 与各 `FileContext.stats/truncation` 保持 `None`（预算由 6.6.3 的 `apply_context_budget_to_files` 在接线阶段调用，留给 6.7.4）
- [x] 测试 30 项（`test_code_context_builder.py`）：正常映射 / 多文件顺序 / patch 保留 / patch=None / 可用内容与 6.1~6.5 联动（methods/classes/related）/ Python 文件 / 空文件 / renamed / removed / unsupported_language / too_large / binary / fetch_failed:* / 空 files / 不伪造不可用 content / 单个不可用不影响整体 / 输入不可变 / 确定性 / 预算未应用 / 无全局 note
- [x] Python 全量 978/978（基线 948 + 新增 30）；现有 6.1~6.6 测试零回归

**6.7.3 设计决策**

- `base_sha` 保持 `None`：Java `PrContextResponse` 只有 `baseRef`（分支名）没有 base SHA；**不新增字段**，也不把分支名写入 SHA 字段
- 不把 title/state/refs 复制进 `CodeContext`，避免为 Prompt 阶段提前扩 schema；6.7.4/6.7.5 可同时持有 `PrContext` 与 `CodeContext`
- 装配阶段不触发预算裁剪（保持 `stats/truncation=None`），预算作为显式步骤由调用方决定

### Phase 6.7.4：ReviewService 接线（**尚未提交**）

- [x] `agent/app/services/review_service.py`：`ReviewService` 新增可选注入 `pr_context_client` / `context_builder` / `context_budget`；`review()` 流程变为
  `_load_context(request) → build_messages(request) → llm_service.generate_findings(...)`
- [x] `agent/app/api/review_router.py`：生产注入 `PrContextClient`（新增 `get_pr_context_client` 依赖），正式接入取码
- [x] 正常路径：`PrContextClient.fetch(task_id)` → `CodeContextBuilder.build(pr_context)` → **Phase 6.6 预算**：`apply_context_budget_to_files(context.files, budget)`（默认 `DEFAULT_BUDGET`），并把 `aggregate_stats(files)` / `aggregate_truncation(files)` 回填到 `CodeContext.stats/truncation`
- [x] `agent/app/context/context_size_controller.py`：**最小追加** `aggregate_truncation(files) -> Truncation`（与既有 `aggregate_stats` 对称的汇总函数，未改 6.6 任何既有语义）
- [x] 失败降级（本阶段核心）：
  - `_load_context` 内 `fetch / build / budget` 的任何异常都被捕获 → **不向上抛出**（因此不会进入 Phase 4 的 `report_failure → retry` 链，避免对 404/契约不符/网络错误做无意义重试）
  - `ReviewTaskResult.status = "DEGRADED"`，`report.context = {available:false, degraded:true, reason:<短原因>}`，`report.summary` 明确写 "Review degraded ... PR context unavailable."
  - `reason` 只暴露失败类别：`http_error:<status>`（404/5xx）/ `ConnectError` / `ReadTimeout` / `ValidationError` / 其他类名；**不把异常 message 写进报告**（validator 消息可能回显代码内容）；完整堆栈仅 DEBUG 记录
  - `ReviewTask` 生命周期不受影响：worker 仍按原流程 `mark_completed`（degraded 不等于任务失败）
- [x] CodeContext **未接入 Prompt / LLM**：`build_messages(request)` 与 `llm_service.generate_findings(messages)` 与 Phase 5.2 完全一致（测试用 `messages == build_messages(request)` 静态证明）；CodeContext 仅被装配、预算并汇总进 `report.context`
- [x] Phase 4 重试策略**未改动**：LLM 失败（`LLMException` 等）仍照旧向上抛出触发既有 retry；只有 context 失败被本地降级
- [x] 未注入 `pr_context_client` 时保持 Phase 5 行为：`status=COMPLETED`、`report.context = {available:false, degraded:false, reason:"not_configured"}`
- [x] 测试 22 项（`test_review_service.py` 新增 17 + `test_context_size_controller.py` 新增 5）：正常装配与预算 / 多文件汇总 / prompt 未被改变 / 预算生效（related 被裁） / 404·5xx·网络异常·ValueError·ValidationError 全部 degraded / builder 异常 degraded / 不抛出 / not_configured 保持 Phase 5 / LLM 失败仍传播（含 degraded 情况下） / 请求不可变 / 确定性 / `aggregate_truncation` 汇总
- [x] Python 全量 1000/1000（基线 978 + 新增 22）；6.1~6.6 与 Phase 4/5 测试零回归

**6.7.4 设计决策**

- `status="DEGRADED"` 作为既有 `ReviewTaskResult.status` 的新取值表达降级；任务生命周期仍为 COMPLETED（degraded ≠ failed），不新增状态机
- 降级边界只包住 context 获取/装配/预算；**LLM 调用在边界之外**，因此真正的审查失败仍走 Phase 4 retry
- 预算始终执行（未显式传入时用 `DEFAULT_BUDGET`），装配与预算解耦但都由 `ReviewService` 显式调用
- 不在本阶段把 CodeContext 放进 Prompt（留 6.7.5）；`report.context` 只放摘要（数量/estimated_tokens/truncated），不放代码内容

### Phase 6.7.5：Prompt 接线（**尚未提交**）

- [x] `agent/app/prompts/code_context.py`（新）：`render_code_context(context)` / `render_context_unavailable(reason)`；纯渲染，无 IO、无预算逻辑、无 schema 变更
  - 渲染载荷与 6.6 预算度量同一口径（metadata / diff / changed methods / related code）+ 内容可用性 + stats / truncation 声明
  - `content` 全文与未变更 `classes[].code` 按 6.6 契约仍不发送（只进 `retained_source_chars`）；可用内容以 diff / changed method 切片 / related 切片呈现，Prompt 明示 "selection of the changed files, not the whole repository"
  - 行号只来自已有字段（hunk header、methods/classes/related 的 start-end、changed_ranges），不新算行号
- [x] `agent/app/prompts/review.py`：`build_messages(request, context=None, context_report=None)` 三态
  - 无 report（旧调用方）→ Phase 5.2 user message **逐字节不变**（回归测试锁定）
  - context 可用 → header + 渲染块；degraded → "PR context unavailable (reason: ...)"，不伪造代码
  - `SYSTEM_PROMPT` 追加硬约束：`file_path` 必须来自提供的上下文、行号必须存在于提供的 diff/代码、不得编造行号、截断/内容不可用不得当作"没有问题"的证据；既有 JSON schema 与规则全部保留
- [x] `agent/app/services/review_service.py`：`_load_context` 返回 `(context | None, report)`；`review()` 把两者交给 `build_messages`，并 DEBUG 记录 prompt 字符数（不记录内容）
- [x] 不可用内容：`content: unavailable (reason: ...)` 可区分 removed / unsupported_language / too_large / binary / fetch_failed:<status>；无代码围栏、无 "None" 文本
- [x] 截断声明：`Context truncation: THE CODE CONTEXT BELOW IS INCOMPLETE ...`（含 reasons / dropped / trimmed / removed_chars）；未截断时无任何截断声明
- [x] 测试 52 项（新 `test_code_context_prompt.py` 48 + `test_review_service.py` 净增 4：6.7.4 的 "prompt 不变" 静态断言被 context-in-prompt / 不可用 / 截断 / degraded / not_configured 取代）
- [x] Python 全量 1052/1052（1000 + 52）；6.1~6.7.4 与 Phase 4/5 零回归；`git diff --check` 通过

**6.7.5 设计决策**

- 渲染载荷严格对齐 6.6 预算口径（metadata + diff + changed methods + related）：full content 属 `retained_source_chars`（设计上不发送），Prompt 明确说明内容以切片呈现，避免"以下即完整仓库"的暗示
- classes / changed_symbols 只渲染定位性标签（名称 / 行号 / kind / source / confidence），不重复发送类体代码；字段变更由 related code 的 FIELD 项覆盖
- 可用性（reason）、截断（applied）、统计（stats）全部来自现有模型字段，Prompt 层不重新计算预算
- `build_messages` 保持向后兼容三态；只有 degraded 输出 unavailable 语句，`not_configured` 保持 Phase 5 行为
- 渲染文本含不可信源码，禁止写日志；ReviewService 只记录字符数

### Phase 6.7.6：真实 PR E2E 联调（**尚未提交**）

环境修复（均为本机配置/环境，未改业务代码）：
- [x] `.env` 陈旧项修复（gitignored，不入库）：私钥路径指向实际存在的 pem 文件；补充真实 `GITHUB_INSTALLATION_ID`（165170316，zhangyu1108l / app codesentinel-lab）
- [x] Docker Desktop 启动 + `docker compose up -d mysql`（3307，复用既有 volume）；未启动 compose Redis（6379 沿用本机实例）
- [x] `codesentinel.review_task` 表存在且列与实体一致（未新建/修改表）
- [x] Spring 以 `-Dspring-boot.run.workingDirectory=<repo root>` 启动（私钥路径按进程 CWD 解析，`spring-boot:run` 默认工作目录为模块目录——启动方式问题，非代码缺陷）
- [x] Python 侧从 `.env` 显式导出环境变量后启动 FastAPI / Worker（settings.py 按 CWD 读取 `.env` 的既有约定）
- [x] Smee 转发重建（GitHub App webhook URL → `http://localhost:8080/api/github/webhook`）

真实 PR 联调（PR #3，分支 `test/phase6-e2e`，经 GitHub API 创建，未合并）：
- [x] 测试内容：`e2e-fixtures/Phase6Sample.java`（added）、`e2e-fixtures/phase6_sample.py`（added）、`e2e-fixtures/notes.md`（added，unsupported）、`agent/app/worker/java_client.py`（modified，单方法注释变更）
- [x] **task 4**（synchronize，cf2f13fb）：webhook → Task → Redis → Worker → `/pr-context` 200（files=3, withContent=2）→ 预算（estimatedTokens=377, truncated=false）→ Prompt → DeepSeek 200 → **COMPLETED, findings=2**
- [x] **task 5**（modified 文件，9c5f4199）：files=4, withContent=3, estimatedTokens=1188, related_kept=2 → **COMPLETED, findings=2**
- [x] A：`/pr-context` 返回真实 path / status / additions / deletions / changes / patch；Java/Python 有 content；md = `unsupported_language` 无 content；文件顺序 = GitHub 顺序
- [x] B：`PrContextClient` 解析真实 Java JSON，snake_case 三字段映射正确；`CodeContextBuilder` 构造真实 CodeContext；输入顺序保留；不可用文件未伪造代码
- [x] C：真实上下文进入 6.6 预算；stats 与渲染载荷口径一致（prompt_chars=1126 / 3559，estimated_tokens=377 / 1188）；本 PR 未触发截断（整文件 added / 单行 modified），无虚假截断声明
- [x] D：录制最终 messages 验证：repository / PR / commit SHA / 文件路径 / diff / changed methods（真实代码切片）/ related code（task 5：`related_kept=2`）/ 不可用原因 / 硬约束全部存在；15 项检查全 OK
- [x] E：真实 DeepSeek findings 逐条核验：`file_path` ∈ 提供上下文；`start_line/end_line` 均落在该文件被提供的行区间内（Java 7-10 ⊂ 变更方法 7-10；Python 1-2 ⊂ 方法 1-2）
- [x] F（受控 degraded）：Spring 以坏私钥路径运行（仅上下文接口 500）→ task 6：`/pr-context` 500 → 日志 "PR context unavailable ... reason=http_error:500" → DeepSeek 仍被调用（Phase 5 流程保留）→ **status=DEGRADED, findings=0**；degraded Prompt 含 "PR context unavailable" 且无代码/围栏；**不进入 Phase 4 retry**（MySQL：COMPLETED、retry_count=0、无 error_message）
- [x] F 恢复：还原 Spring 后 task 7（69b0c3aa）：files=4, withContent=3, estimatedTokens=1203 → **COMPLETED, findings=1**（同 PR 仅 commit 变化 → 新 task，幂等正常）
- [x] G 回归：Python **1052/1052**；Java **202/202**（BUILD SUCCESS）；`git diff --check` 通过
- [x] 安全检查：Spring / Worker / AI 正常日志无 API Key、JWT、私钥、密码模式命中；未输出完整敏感源码

**6.7.6 结论**

- **真实 E2E PASS**：真实 PR 从 webhook → Task → Redis → Worker → PR Context → CodeContext → Budget → Prompt → DeepSeek → Findings 全链路成功（task 4 / 5 / 7）；受控 degraded 演练通过（task 6）
- **未发现 6.7.x 业务代码缺陷**（无需最小修复）；发现的问题均为环境/启动配置类（见 §已知问题）
- **Phase 6 正式完成**，下一阶段为 Phase 7（Static Analysis）

## Phase 6 当前链路（纯 Python，离线可测）

```text
GitHub patch / status / path / previous_path
    ↓ diff_parser.parse_patch
FileDiff { hunks, changed_ranges, additions, deletions, patch_available, notes }
    ↓ file_context_builder.build_file_context(+ FileContent)
FileContext { content, line_count, content_available, skipped_reason, notes }
    ↓ method_context_builder.attach_method_contexts
FileContext.methods[]  +  changed_symbols[]
    ↓ class_context_builder.attach_class_contexts
FileContext.classes[]  +  methods[].enclosing_class  +  FileContext.enclosing_class
    ↓ related_code_builder.attach_related_code
FileContext.related_code[]
    ↓ （6.7.3 已实现）CodeContextBuilder.build 装配为 CodeContext
    ↓ （6.7.4 已实现）apply_context_budget_to_files（6.6 预算）→ CodeContext.stats/truncation
    ↓ （6.7.5 已实现）render_code_context → build_messages user message（diff + methods + related + 声明）
    ↓ （6.7.6 已验收）真实 PR 端到端联调通过（PR #3：task 4/5/7 COMPLETED + task 6 DEGRADED 演练）
```

共享层：

```text
source_scanner.py     掩码 / 大括号深度 / 声明终止符 / 缩进块 / 注解回溯 / 签名折叠 / 切片
file_context_builder  split_lines / count_lines（Git 行模型）
```

## 关键设计

- 行号统一为 **1-based + diff 新文件侧**，Method / Class / Related 三级范围可直接与 `changed_ranges` 比较
- 所有降级都显式化：`notes` / `skipped_reason` / `patch_available` / `content_available` / `confidence`，禁止静默丢数据、禁止伪造行号或名称
- 全部为纯函数、无 IO、无第三方依赖；`build_*` 不抛异常，`attach_*` 一律返回 `model_copy`，输入不可变
- `source` + `confidence` 贯穿三级符号，为后续 Validator / 行级评论定位提供可信度依据
- 代码内容属不可信用户源码：**禁止写日志**，后续若要把 context 摘要写进 report 必须先剥离 `content` / `code`

## 测试结果

| 服务 | 总数 | 通过 | 状态 |
|---|---|---|---|
| Python (agent) | 1052 | 1052 | ✅（6.7.5 新增 52：1000 → 1052） |
| Java (Spring Boot) | 202 | 202 | ✅（6.7.1 新增 50：152 → 202） |

Phase 6 测试分布：

```text
test_diff_parser.py                   77
test_code_context_schemas.py         152
test_file_context_builder.py          76
test_method_context_builder.py       120
test_class_context_builder.py        131
test_related_code_builder.py          89
test_context_size_controller.py      185
test_pr_context_schemas.py            29
test_pr_context_client.py             15
test_code_context_builder.py          30
test_code_context_prompt.py           48（6.7.5 新增）
test_review_service.py                29（含 6.7.5 新增 4）
Phase 5 及更早（不含 review_service）   71
```

Java 6.7.1 新增分布：

```text
GithubPullRequestFilesClientTest      14
GithubFileContentClientTest           20（11 → 20）
PrContextServiceTest                  13
PrContextControllerTest                5
ReviewContextPropertiesTest            9
```

## 已知问题 / 技术债

- 6.7.1 ~ 6.7.6 全链路已就绪并完成真实 PR E2E 验收（PR #3，task 3~7）；**未发现 6.7.x 业务代码缺陷**
- 6.7.1 / 6.7.2 / 6.7.3 / 6.7.4 / 6.7.5 均尚未提交（工作区改动未 commit）；测试 PR #3 与分支 `test/phase6-e2e` 保留在远端（未合并），MySQL task 3~7 为联调记录
- 联调环境问题（非代码缺陷，已在本地处理，`.env` 不入库）：
  - Spring 私钥路径按进程 CWD 解析：`spring-boot:run` 默认工作目录为模块目录 → 需 `-Dspring-boot.run.workingDirectory=<repo root>` 或绝对路径；`.env` 中陈旧私钥文件名与缺失 `GITHUB_INSTALLATION_ID` 已修复
  - Docker Desktop 引擎需先启动（MySQL 走 compose 3307；本机 3306 为无关实例）；Redis 沿用本机 6379
- `handler.py` 仍传 `files=[]`：仅影响 Prompt header 的文件列表显示；Context 按 task_id 获取，不影响链路（观察项）
- Worker 日志每分钟出现 `Redis BLPOP error: Timeout reading from socket`：redis-py 8.1.0 与 requirements 声明不符的既有债务（超时抛异常而非返回 nil），不影响任务消费
- `max-file-bytes` 只能在 contents 响应后判定（`pulls/{n}/files` 无字节大小），超大文件仍会各发一次 contents 请求后才判为 `too_large`；严格"不请求"需要 Git Trees/Blobs size（已决策不引入）
- `content_truncated` 当前恒为 `false`：超限内容按不可用处理，不返回截断正文
- 单文件 contents 的**网络级异常**（非 `GithubApiException`）会终止整个 PR Context；仅 HTTP 4xx/5xx 按 `fetch_failed:<status>` 降级
- 降级语义已在 6.7.4 实现：context 失败 → `status=DEGRADED` + `report.context.reason`（`http_error:<status>` / 异常类名），不进入 Phase 4 retry；**LLM 失败仍照旧抛出触发既有 retry**（Phase 4 未改动）
- 预算已由 `ReviewService` 在 6.7.4 显式应用（默认 `DEFAULT_BUDGET`，可注入覆盖），`CodeContext.stats/truncation` 已回填（新增 `aggregate_truncation` 汇总，未改 6.6 既有语义）
- Prompt 渲染对齐 6.6 预算口径：**full content 不发送**（`retained_source_chars`），可用内容以 diff / changed-method / related 切片呈现；`estimated_tokens` 度量的是该切片载荷（含少量固定声明文本未计入）
- 状态可见性限制：degraded 目前只体现在 `ReviewTaskResult.status/report`，worker 仍 `mark_completed`（Java 侧 MySQL 为 COMPLETED）；若需要把 degraded 回传 Java，属后续阶段（不新增数据库结构）
- `_anchors` 对每个 `changed_range` 只探测首尾两行，单个区间跨越 3 个及以上类型时中间类型可能漏成 anchor（只影响完整性，不产生错误项）
- Python 多行字符串属性（`TEXT = """` 跨行）的 `end_line` 停在起始行，`code` 只含首行（不产生误报，其内部行由 `in_triple` 跳过）
- Java 已知漏识别：4 层以上嵌套泛型返回类型的方法、字段初始化含匿名类或双花括号初始化、嵌套在类内部的 interface / abstract 无 body 声明方法（depth ≥ 2）、行内注解含嵌套括号
- Java 多声明符字段 `private String a, b;` 只取首个名字
- Python 属性识别不跨反斜杠续行；`x += 1` 不算声明（有意排除）
- 启发式定位固有误差：全部 `source=HEURISTIC`，`confidence ≤ 0.9`

## Phase 6 状态

**✅ 已完成**

6.1~6.7.6 全部完成并通过真实 PR E2E 验收：构建链（Diff → File → Method → Class → Related）、大小 / Token 预算、Java PR Context 只读接口、Python `PrContext` DTO / Client、`CodeContextBuilder` 装配、`ReviewService` 接线（含取码失败降级）、Prompt 渲染（diff + changed methods + related code + 可用性/截断声明 + file_path/行号硬约束），以及真实 PR 全链路联调（PR #3：task 4/5/7 COMPLETED + task 6 受控 DEGRADED；Python 1052 / Java 202）。已知限制：Imports / namespace / package 分析未实现（不影响本阶段验收，留待后续按需）。

## 当前任务

Phase 7（Static Analysis）尚未开始。按开发流程，新 Phase 首个任务应先阅读文档 / 检查代码与 Git 状态 / 提出实现计划，暂不修改代码。

## 阻塞问题

暂无。

---

# 10. Phase 7：Static Analysis

## Java

计划使用：

```text
PMD
Checkstyle
Semgrep
```

后续可选：

```text
SpotBugs
```

## Python

计划使用：

```text
Ruff
Bandit
Semgrep
```

## 目标

统一转换为：

```text
StaticAnalysisResult
```

然后提供给 Agent：

```text
Static Analysis
      +
Code Context
      ↓
LLM Agent
```

## 子任务

- [ ] Java analyzer adapter
- [ ] Python analyzer adapter
- [ ] PMD
- [ ] Checkstyle
- [ ] Semgrep
- [ ] Ruff
- [ ] Bandit
- [ ] 统一结果 Schema
- [ ] Tool Error Handling

## Phase 7 状态

**⬜ 未开始**

## 当前任务

暂无。

## 阻塞问题

暂无。

---

# 11. Phase 8：LangGraph Multi-Agent

## 目标

构建完整 Agent 工作流。

目标：

```text
START
  ↓
Load Context
  ↓
Detect Language
  ↓
Static Analysis
  ↓
Planner
  ↓
┌──────────────┬──────────────┬──────────────┬──────────────┐
│              │              │              │
Bug Agent   Security Agent  Performance   Quality Agent
                             Agent
│              │              │              │
└──────────────┴──────────────┴──────────────┘
                       ↓
                Merge Findings
                       ↓
                  Deduplicate
                       ↓
                  Validator
                       ↓
              Severity / Confidence
                       ↓
                 Reporter
                       ↓
                      END
```

## Agent

- [ ] Planner Agent
- [ ] Bug Agent
- [ ] Security Agent
- [ ] Performance Agent
- [ ] Quality Agent
- [ ] Validator Agent
- [ ] Reporter Agent

## 重点原则

- Agent 职责单一
- 统一 Finding Schema
- 证据优先
- 不允许无依据推测
- Validator 是最终质量闸门

## Phase 8 状态

**⬜ 未开始**

## 当前任务

暂无。

## 阻塞问题

暂无。

---

# 12. Phase 9：GitHub Summary + Inline Comment

## 目标

把经过 Validator 确认的 Finding 反馈到 GitHub PR。

目标：

```text
Finding
   ↓
File
   ↓
Line
   ↓
Commit SHA
   ↓
GitHub Inline Comment
```

同时生成：

```text
PR Summary
```

## 子任务

- [ ] PR Summary Generator
- [ ] Inline Comment Builder
- [ ] Line Mapping
- [ ] Commit SHA 映射
- [ ] GitHub Comment API
- [ ] Comment 失败处理
- [ ] Comment 幂等
- [ ] 无法定位行时的降级策略

## MVP 输出

```text
COMMENT
```

暂不自动：

```text
APPROVE
REQUEST_CHANGES
```

## Phase 9 状态

**⬜ 未开始**

## 当前任务

暂无。

## 阻塞问题

暂无。

---

# 13. Phase 10：MySQL 历史记录

## 核心表

```text
github_installation
repository
pull_request
review_task
review_report
review_finding
review_comment
```

## 子任务

- [ ] 数据库 Schema
- [ ] Migration
- [ ] Entity / Model
- [ ] Repository
- [ ] Service
- [ ] Review Report 保存
- [ ] Finding 保存
- [ ] Comment 保存
- [ ] Review 查询 API
- [ ] 历史 Review 查询

## Phase 10 状态

**⬜ 未开始**

## 当前任务

暂无。

## 阻塞问题

暂无。

---

# 14. MVP 验收标准

以下全部完成后，MVP 才视为完成：

```text
[ ] 创建 GitHub PR
        ↓
[ ] GitHub Webhook 自动触发
        ↓
[ ] Spring Boot 正确接收并验证
        ↓
[ ] 创建 ReviewTask
        ↓
[ ] Redis 异步投递
        ↓
[ ] Python Worker 获取任务
        ↓
[ ] 获取 Diff / Code Context
        ↓
[ ] Java / Python 静态分析
        ↓
[ ] LangGraph Multi-Agent 分析
        ↓
[ ] Validator 验证 Finding
        ↓
[ ] Report Generator 输出结果
        ↓
[ ] Spring Boot 保存 MySQL
        ↓
[ ] GitHub PR Summary
        ↓
[ ] GitHub Inline Comments
```

---

# 15. AI 评测状态

## 测试集

计划建立：

```text
test-cases/
├── java/
│   ├── bug/
│   ├── security/
│   ├── performance/
│   └── quality/
└── python/
    ├── bug/
    ├── security/
    ├── performance/
    └── quality/
```

## 评测指标

- Precision
- Recall
- False Positive Rate
- Line Localization Accuracy

## 当前状态

**⬜ 测试集尚未建立**

---

# 16. 第二阶段计划

MVP 完成后：

## Dashboard

- [ ] Review History
- [ ] Finding Statistics
- [ ] Security Trend
- [ ] Bug Trend
- [ ] Performance Trend
- [ ] Quality Trend

## Custom Rules

- [ ] Project Rules
- [ ] Team Rules
- [ ] Custom Review Policy

---

# 17. 第三阶段计划

只有存在实际需求后再实施：

## RAG / Milvus

可能用于：

```text
企业规范
项目规范
安全规范
框架文档
历史 Review
```

## GitHub Action

```text
GitHub Action
    ↓
CodeSentinel
```

## VS Code

```text
VS Code
    ↓
CodeSentinel API
```

## Auto Fix

```text
Finding
 ↓
Fix Agent
 ↓
Patch
 ↓
Sandbox
 ↓
测试
 ↓
用户确认
```

---

# 18. 当前已知问题

Phase 6（Code Context）相关：

- [ ] Code Context 尚未接入真实 PR 数据
  - 影响：`handler.py` 仍传 `files=[]`，`prompts/review.py` 仍声明 "no file content or diff"，LLM 看不到真实代码；Phase 5 链路行为未变
  - 原因：Java 侧尚无 PR Context 只读接口，Python 侧尚无 `PrContextClient`，`CodeContextBuilder` 装配与 `ReviewService` 接线未实现
  - 临时方案：无（6.1~6.5 的构建链可离线验证，真实数据接入属 Phase 6 收尾）
  - 最终方案：Java `GET /pulls/{n}/files`（分页 + binary / 大小保护）→ Python client → `CodeContextBuilder` → `ReviewService`（取码失败降级 `degraded`，不得触发 Phase 4 无限重试）→ Prompt 渲染 → 真实 PR 联调

- [ ] 未实现 Context Size Control / Token 控制
  - 影响：成员很多的类会产出大量 related code（实测 `agent/app/config/settings.py` 单文件 18 条），嵌套类型的 `code` 为完整 body；接入 Prompt 后容易膨胀并挤占预算
  - 原因：按阶段边界刻意未实现（属 Phase 6.6）
  - 临时方案：无
  - 最终方案：在装配层加入文件数 / 单文件字节 / 总字符预算与截断记录（`truncation.applied` / `dropped_files`），且截断必须在 Prompt 中显式声明

- [ ] `_anchors` 只探测每个 changed range 的首尾两行
  - 影响：单个区间跨越 3 个及以上类型时，中间类型可能漏成 anchor，其成员不会进入 related code（只影响完整性，不产生错误项）
  - 原因：为控制实现复杂度，锚点探测只取区间端点
  - 临时方案：无
  - 最终方案：需要时对区间覆盖行抽样/逐行探测，或建立"行 → 类型"映射

Phase 5 及更早的遗留技术债见 §8「已知问题 / 技术债」。

格式：

```text
- [ ] 问题描述
  - 影响：
  - 原因：
  - 临时方案：
  - 最终方案：
```

---

# 19. 当前开发记录

## 记录规则

每完成一个任务，更新：

1. Current Phase
2. Current Task
3. Completed
4. Known Issues
5. Next Step

不要删除重要历史记录。

---

## 开发记录

### 2026-09-25

项目正式初始化。

已完成：

- [x] 确定项目名称：CodeSentinel
- [x] 确定 GitHub PR 自动审查
- [x] 确定 Java + Python
- [x] 确定 Bug / Security / Performance / Quality 四大检测方向
- [x] 确定 Spring Boot 3 + Python + LangChain + LangGraph
- [x] 确定 DeepSeek API
- [x] 确定 GitHub App + Webhook
- [x] 确定 MySQL + Redis
- [x] 确定 MVP 暂不使用 RAG / Milvus
- [x] 确定 GitHub PR Summary + Inline Comments
- [x] 确定 MVP 不执行用户 PR 代码
- [x] 创建项目级 `AGENTS.md`
- [x] 创建项目设计文档

当前状态：

```text
Phase 0：项目初始化
```

下一步：

```text
Phase 3：GitHub API
```

---

### 2026-09-27

Phase 2 最终验收：真实 GitHub Webhook 联调成功。

已完成：

- [x] 将 `feature/add-webhook-verification` 合并到 `webhook-test` 分支
- [x] 配置 Smee 代理（`https://smee.io/...` 转发到 `localhost:8080`）
- [x] 解决 Spring Boot 读取 `.env` 问题（`mvn spring-boot:run` 不自动加载 `.env`，需在启动前手动设置环境变量）
- [x] 修复 Webhook Secret 签名验证失败（Secret 值不一致导致 HMAC 不匹配）
- [x] 真实 Webhook 联调验证通过：
  - GitHub PR #1 `synchronize` 事件成功到达
  - Smee 转发 `POST /api/github/webhook` 返回 200
  - Spring Boot 日志输出：`Received pull_request event: action=synchronize, repo=zhangyu1108l/CodeSentinel, pr=1, sender=zhangyu1108l`
- [x] 全部 21 个测试通过（1 context + 9 controller + 11 verifier）

当前状态：

```text
Phase 2：GitHub App + Webhook ✅ 完成
```

已知问题：

- `.env` 不会被 `mvn spring-boot:run` 自动加载，后续可考虑引入 dotenv 依赖
- Webhook 幂等设计待 Phase 4 与 Task 系统一起实现

下一步：

```text
Phase 3：GitHub API

---

### 2026-09-25 (2)

Spring Boot 基础工程初始化。

已完成：

- [x] 创建 `.gitignore`（Java / Maven / Python / IntelliJ / VS Code / Windows / Docker / Secrets）
- [x] 创建 `backend/spring-service/` Maven 项目结构
- [x] Spring Boot 3.4.4 + Java 21
- [x] `spring-boot-starter-web`
- [x] `spring-boot-starter-actuator`（暴露 health, info 端点）
- [x] `pom.xml` 配置
- [x] `application.yml` 配置（应用名、端口、Actuator）
- [x] `CodeSentinelApplication.java` 启动类
- [x] `HealthController.java`（`GET /api/health` 返回服务状态）
- [x] `CodeSentinelApplicationTests.java`（Spring Context 启动测试）
- [x] Maven 编译通过
- [x] 测试通过（1/1, 0 failures）

当前状态：

```text
Phase 1：基础工程 🟡 进行中
Spring Boot ✅ / Python ⬜ / Docker Compose ⬜
```

下一步：

```text
Phase 3：GitHub API
```

### 2026-09-27 (Merge)

Phase 2 最终合并：PR #1 已合并到 `main`。

已完成：

- [x] PR #1 (`webhook-test` → `main`) 通过 GitHub CLI 合并
- [x] 合并无冲突，merge commit: `494ac5c`
- [x] `main` 分支已包含全部 Phase 2 Webhook 代码
- [x] `main` 分支运行 Maven 测试：21/21 通过，BUILD SUCCESS
- [x] 保留 `webhook-test` 和 `feature/add-webhook-verification` 分支供追溯
- [x] 更新 `DEVELOPMENT_STATUS.md` 至最终状态

当前状态：

```text
Phase 2：GitHub App + Webhook ✅ 完成（已合并至 main）
```

下一步：

```text
Phase 3：GitHub API

---

### 2026-09-25 (3)

Python FastAPI 基础工程初始化。

已完成：

- [x] 创建 `agent/` 目录结构（`app/`, `app/config/`, `tests/`）
- [x] Python 3.13 + FastAPI
- [x] `requirements.txt`（fastapi, uvicorn, pydantic-settings, httpx, pytest）
- [x] `app/config/settings.py`（Pydantic Settings，读取 .env）
- [x] `app/main.py`（FastAPI 入口，lifespan 事件，日志）
- [x] `GET /health` 接口（返回 `{"status":"UP","service":"codesentinel-ai"}`）
- [x] `.env.example`（环境变量示例，不含真实密钥）
- [x] `tests/test_health.py`（TestClient 测试 /health）
- [x] 测试通过（1/1, 0 failures）

当前状态：

```text
Phase 1：基础工程 🟡 进行中
Spring Boot ✅ / Python ✅ / Docker Compose ⬜
```

下一步：

```text
Docker Compose（MySQL 8 + Redis）
```

---

### 2026-09-25 (4)

Phase 1 基础设施建设完成：

- [x] 创建根目录 `.env.example`（13 项配置：MySQL / Redis / Spring Boot / FastAPI / DeepSeek / GitHub App）
- [x] 创建 `.env`（本地开发使用，Sensitive 留空，Git 已忽略）
- [x] 创建 `docker-compose.yml`（MySQL 8.0 + Redis 7-Alpine，volume 持久化 + healthcheck + 独立网络）
- [x] 更新 `application.yml`（MySQL/Redis 数据源配置使用环境变量引用）
- [x] 创建占位目录 `knowledge/`、`frontend/`、`action/`（含 `.gitkeep`）
- [x] MySQL 8.0.46 启动正常，`codesentinel` 数据库已创建
- [x] Redis 7 启动正常，`PING → PONG`
- [x] Spring Boot 测试：1/1 通过
- [x] FastAPI 测试：1/1 通过

MySQL 端口：3307（Docker），Redis 端口：6379

当前状态：

```text
Phase 1：基础工程 ✅ 完成
Spring Boot ✅ / Python ✅ / Docker Compose ✅
```

Git commit：`056c1de`，已推送至 `origin/main`。

下一步：

```text
Phase 2：GitHub App + Webhook
```

---

### 2026-09-26

Phase 2 第一小步：Webhook 接收 + 签名验证 + PR 事件解析。

已完成：

- [x] 新增 `GithubAppProperties` (`cn.codesentinel.config`) — `@ConfigurationProperties(prefix = "github.app")` record 类
- [x] 新增 `WebhookSignatureVerifier` (`cn.codesentinel.webhook`) — HMAC-SHA256 签名验证，使用 `MessageDigest.isEqual()` 常量时间比较
- [x] 新增 `WebhookController` (`cn.codesentinel.webhook`) — `POST /api/github/webhook`
- [x] 在 `application.yml` 中添加 `github.app.*` 配置（通过环境变量注入）
- [x] 在 `CodeSentinelApplication` 添加 `@EnableConfigurationProperties(GithubAppProperties.class)`
- [x] `WebhookSignatureVerifierTest`（11 个测试）
  - 合法签名接受、非法签名拒绝、空/null 签名处理、错误前缀、空 hex 值、非法 hex、篡改 payload、空 payload、未配置 secret
- [x] `WebhookControllerTest`（9 个测试，`@WebMvcTest` + `@TestPropertySource`）
  - 缺失签名 → 401、非法签名 → 401、缺失事件头 → 400
  - push 事件 → 200（忽略）、opened/synchronize/reopened → 200（记录日志）
  - closed 动作 → 200（忽略）、非法 JSON body → 400
- [x] Maven 编译 + 全部 21 个测试通过

Webhook 请求处理流程：

```text
POST /api/github/webhook
    ↓
1. 检查 X-Hub-Signature-256 header（缺失 → 401）
    ↓
2. HMAC-SHA256 验证原始 body（失败 → 401），使用 MessageDigest.isEqual 常量时间比较
    ↓
3. 检查 X-GitHub-Event header（缺失 → 400）
    ↓
4. 仅处理 pull_request 事件（其他 → 200 忽略）
    ↓
5. 解析 JSON payload，提取 action
    ↓
6. 仅处理 opened / synchronize / reopened（其他 → 200 忽略）
    ↓
7. 记录日志（repo、PR number、sender、action）
    ↓
8. 返回 200
```

当前状态：

```text
Phase 2：GitHub App + Webhook ✅ 已完成
Webhook 接收 ✅ / 签名验证 ✅ / PR 事件解析 ✅ / GitHub App 创建 ✅ / 真实联调 ✅
```

---

### 2026-09-28

Phase 3（GitHub API）全部 6 个子阶段完成。

已完成：

- [x] Phase 3.1：GithubJwtService（RS256 JWT）+ GithubAuthService（Installation Token）+ GithubApiException + InstallationToken
- [x] Phase 3.2：GithubApiClient（共享 RestClient，baseUrl + Accept + defaultStatusHandler → GithubApiException）
- [x] Phase 3.3：GithubRepositoryClient + Repository record（GET /repos/{owner}/{repo}）
- [x] Phase 3.4：GithubPullRequestClient + PullRequest record（GET /repos/{owner}/{repo}/pulls/{number}）
- [x] Phase 3.5：GithubCommitClient + Commit record（GET /repos/{owner}/{repo}/commits/{sha}，含 files + patch）
- [x] Phase 3.6：GithubFileContentClient + FileContent record（GET .../contents/{path}?ref={sha}，Base64 解码）
- [x] 新增 19 个文件（13 main + 6 test），约 2500 行代码
- [x] 全量测试：104/104 通过，BUILD SUCCESS
- [x] Git commit：`b379eba` — feat(github): complete phase 3 github api integration

Phase 3 实现了完整的 GitHub API 数据获取链路：

```text
Webhook → PR → Commit (files + patches) → File Content → AI Review
```

当前状态：

```text
Phase 3：GitHub API ✅ 完成
```

当前包结构：

```text
cn.codesentinel/
├── config/
│   └── GithubAppProperties.java        (6 字段配置)
├── github/
│   ├── GithubJwtService.java           (JWT 生成)
│   ├── GithubAuthService.java          (Token 获取)
│   ├── GithubApiClient.java            (共享 RestClient)
│   ├── GithubApiException.java         (统一异常)
│   ├── InstallationToken.java          (token 生命周期)
│   ├── Repository.java                 (仓库信息)
│   ├── PullRequest.java                (PR 元数据)
│   ├── Commit.java                     (提交 + 文件变更 + patch)
│   ├── FileContent.java                (文件完整内容)
│   ├── GithubRepositoryClient.java     (仓库 API)
│   ├── GithubPullRequestClient.java    (PR API)
│   ├── GithubCommitClient.java         (提交 API)
│   └── GithubFileContentClient.java    (文件内容 API)
├── webhook/
│   ├── WebhookController.java
│   └── WebhookSignatureVerifier.java
└── controller/
    └── HealthController.java
```

下一步：

```text
Phase 4：Review Task + Redis
```

---

### 2026-09-29

Phase 4（Review Task + Redis）全部 6 个子阶段完成。

已完成：

- [x] Phase 4.1：ReviewTask Entity + TaskStatus 枚举
- [x] Phase 4.2：ReviewTaskRepository + ReviewTaskService
- [x] Phase 4.3：Webhook → ReviewTaskService.createTask（幂等接入）
- [x] Phase 4.4：Redis Producer（RPUSH，Spring Data Redis）
- [x] Phase 4.5：Python Worker（BLPOP consumer + TaskHandler）
- [x] Phase 4.6：Retry + Idempotency（owner+repo+prNumber+commitSha）
- [x] 34 个文件变更，约 2000 行代码
- [x] Java 测试：152/152，BUILD SUCCESS
- [x] Python 测试：25/25，全部通过
- [x] Git commit：`74dadba` — feat: complete phase 4 review task and redis worker

Phase 4 实现了完整的异步任务链路：

```text
GitHub Webhook
    ↓
WebhookController
    ↓
ReviewTaskService.createTask()  ← 幂等
    ↓
ReviewTask(PENDING) → MySQL
    ↓
ReviewTaskProducer → Redis RPUSH
    ↓
Python Worker BLPOP → TaskHandler
    ↓
Java 状态 API (running/complete/failure)
    ↓
成功 → COMPLETED / 失败 → retryCount<3 → PENDING → Redis 重入队
                              retryCount>=3 → FAILED
```

当前包结构：

```text
cn.codesentinel/
├── config/
│   ├── GithubAppProperties.java
│   └── ReviewTaskProperties.java         (新增)
├── controller/
│   ├── HealthController.java
│   └── ReviewTaskController.java         (新增)
├── github/
│   └── ... (Phase 3, 无变更)
├── task/                                 (新增)
│   ├── ReviewTask.java
│   ├── ReviewTaskMessage.java
│   ├── ReviewTaskProducer.java
│   ├── ReviewTaskRepository.java
│   ├── ReviewTaskService.java
│   ├── TaskFailureResponse.java
│   ├── TaskNotFoundException.java
│   └── TaskStatus.java
└── webhook/
    ├── WebhookController.java            (修改)
    └── WebhookSignatureVerifier.java

agent/app/
├── worker/                               (新增)
│   ├── consumer.py
│   ├── handler.py
│   ├── java_client.py
│   ├── models.py
│   └── __main__.py
└── config/
    └── settings.py                       (修改)
```

下一步：

```text
Phase 5：Python AI Service + DeepSeek
```

---

### 2026-10-06

Phase 5（Python AI Service + DeepSeek）完成，含 5.1 / 5.2 两个子阶段。

Phase 5.1（commit `d9fa710`）：

- [x] Review DTO：`agent/app/schemas/review.py`（ReviewTaskRequest / ReviewTaskResult / ReviewFinding + Category/Severity 枚举，confidence 0~1）
- [x] Mock ReviewService + `POST /api/reviews` HTTP 边界（`agent/app/api/review_router.py`）
- [x] Worker 接线：`handler._process` → `AiServiceClient` → FastAPI（repository = owner/repo，files=[]）
- [x] Python 测试 54/54

Phase 5.2：

- [x] `agent/app/llm/`：DeepSeekClient（httpx.AsyncClient 直连 OpenAI-compatible API）+ LLMService（JSON 解析 + Pydantic 校验）+ exceptions（LLMConfigError / LLMException / LLMResponseError）
- [x] 结构化输出：DeepSeek json_object → json.loads → `LlmReviewOutput`（仅 findings）→ ReviewFinding[]
- [x] 基础 Review Prompt：`agent/app/prompts/review.py`（system 明确 JSON schema 与枚举约束；user 携带 PR 元数据并声明无代码内容）
- [x] 全链路 async：DeepSeekClient / LLMService / ReviewService；Worker 保持同步（AiServiceClient timeout 参数化为 AI_SERVICE_TIMEOUT=120）
- [x] 新增配置：DEEPSEEK_BASE_URL / DEEPSEEK_TIMEOUT(60) / DEEPSEEK_TEMPERATURE(0.1) / AI_SERVICE_TIMEOUT(120)
- [x] 移除 Mock Finding 生成，ReviewService 组装真实 LLM findings
- [x] Python 79/79（含 2 个 live 测试）、Java 152/152
- [x] 真实 DeepSeek 联调：files=[] → findings=[]；全链路 MySQL COMPLETED

Phase 5 最终链路（已在真实环境验证）：

```text
Redis → Python Worker → FastAPI /api/reviews
→ ReviewService → LLMService → DeepSeekClient → DeepSeek API
→ JSON → LlmReviewOutput → ReviewFinding[]
→ ReviewTaskResult → Worker → Java mark_completed → MySQL COMPLETED
```

当前 agent/app 包结构：

```text
agent/app/
├── api/review_router.py           (Phase 5.1)
├── llm/                           (Phase 5.2 新增)
│   ├── deepseek_client.py
│   ├── exceptions.py
│   └── llm_service.py
├── prompts/review.py              (Phase 5.2 新增)
├── schemas/
│   ├── llm_output.py              (Phase 5.2 新增)
│   └── review.py                  (Phase 5.1)
├── services/review_service.py     (Phase 5.2 改造：真实 LLM)
└── worker/                        (ai_client.py timeout 参数化)
```

已知问题 / 技术债：

- DEEPSEEK_API_KEY 来自系统环境变量，agent/.env 未持久化
- 本机 Redis 与 Docker Redis 端口并存（localhost:6379 解析到本机实例）
- redis-py 实装 8.1.0 与 requirements.txt 声明不符
- MySQL review_task 表为手动 DDL
- LLM 内部 retry/repair 未实现（按阶段边界，走外层 task retry）
- Java Review / Python Review 待 Phase 6 提供代码内容后生效（当前 files=[]，LLM 正确返回空 findings）

当前状态：

```text
Phase 5：Python AI Service + DeepSeek ✅ 完成
```

下一步：

```text
Phase 6：Code Context
```

---

### 2026-10-06 (2)

Phase 6（Code Context）6.1 ~ 6.5 完成。只做「纯 Python、可离线测试的上下文构建链」，**未接入真实 PR 数据**，未实现 Context Size Control / Token 控制。

已完成：

- [x] Phase 6.1：Diff Parser + Code Context 数据契约 — commit `5c8c703`
  - `schemas/code_context.py`（DiffLine / Hunk / ChangedRange / FileDiff / FileContext / CodeContext 等）
  - `context/diff_parser.py`：`detect_language` / `parse_file_status` / `parse_hunks` / `merge_changed_ranges` / `parse_patch`
  - 行号统一为 1-based + diff 新文件侧；替换只报新增侧、纯删除锚定最近新侧行、整文件删除不伪造行号；按 header 行数关闭 hunk；畸形 / 空 / `None` patch 全部降级为 `notes`
- [x] Phase 6.2：File Context — commit `f29190e`
  - `FileContent` 输入模型；`FileContext` 追加 `content` / `line_count`
  - `context/file_context_builder.py`：`split_lines` / `count_lines` / `build_file_context(s)`
  - 采用 Git 行模型（先归一 CRLF/CR，再 split + 只剥末尾空元素；**不用 `str.splitlines()`**，避免与 diff 行号错位）
  - 关联键 = 新路径，路径不符即拒绝；REMOVED 不需要内容；revision / 越界 / ADDED 行数不足 → 记 note
- [x] Phase 6.3：Method Context — commit `4cbdd6b`
  - `MethodContext`；`context/method_context_builder.py`：`find_methods` / `match_methods` / `build_method_contexts` / `attach_method_contexts`
  - Java：掩码 + 大括号深度 + 签名正则 + 关键字/前缀双重排除 + 大括号配对；无前缀构造方法用「参数列表形状」区分枚举常量
  - Python：`def` / `async def` + 括号平衡求 header + 缩进求 block 尾；`kind` 由最近外层块头判定
  - 注解 / 装饰器计入 `start_line`（含跨行）；关联用 **overlap** 而非 containment；置信度 0.9 / 0.7 / 0.6 / 0.85
- [x] Phase 6.4：Class Context — commit `c6b5391`
  - `TypeKind` + `ClassContext`；`MethodContext.enclosing_class`、`FileContext.classes`；`FileContext.enclosing_class` 首次真正填充
  - `context/class_context_builder.py`：`find_classes` / `find_anonymous_regions` / `innermost_scope` / `innermost_class` / `enclosing_class_name` / `attach_class_contexts`
  - 抽出 `context/source_scanner.py`：6.3/6.4/6.5 共用掩码、大括号、缩进、注解回溯、签名折叠、切片原语（**避免多套解析器**）
  - Java：class / interface / enum / record / `@interface` / abstract / static nested / inner / 多层嵌套 / local class；`depth` = 包含它的类型个数
  - Python：class / 多层 nested / 装饰器；docstring 与字符串内 `class X:` 被忽略
  - **anonymous class 不生成 ClassContext**（无名可报），其体区间作为"无名作用域"参与最近作用域竞争 → 内部方法不错误归属外层类
- [x] Phase 6.5：Related Code — commit `6c9bc48`
  - `RelatedKind` / `RelatedReason` + `RelatedCodeContext`；`FileContext.related_code`
  - `context/related_code_builder.py`：`build_related_code` / `attach_related_code`
  - 选择链路：`changed_ranges + changed methods → innermost_class 得 anchor → 直接成员（同类方法 / 字段 / 构造方法 / 嵌套类型）→ 去重 → 稳定排序`
  - 排序优先级：同类方法 > 字段 > 构造方法 > 嵌套类型；只取结构证据，不做名称相似度 / 语义 / 调用推断
  - 与 `changed_ranges` 重叠的候选一律丢弃（变更方法自身、被改字段、anchor 本身不重复出现，不复制整类源码）
  - Java 字段：类体大括号深度 + `java_declaration_end` 遇 `;` 才算字段；Python 类属性：赋值 / 仅注解，按语句级游标消费
  - 修复两处误报：多行初始化器续行被当独立字段、多行 `class` header 参数行被当字段（真实文件 `config/settings.py` 21 → 18 条，全仓复扫噪声文件 1 → 0）
  - 跨文件搜索 / symbol index / call graph / imports / 继承解析 **一律未实现**

测试结果：

- [x] Python 全量：**679 passed**（`test_diff_parser` 77 / `test_code_context_schemas` 122 / `test_file_context_builder` 76 / `test_method_context_builder` 120 / `test_class_context_builder` 116 / `test_related_code_builder` 89 / Phase 5 及更早 79）
- [x] Java 152/152（Phase 6 未改动 Java）
- [x] 真实源码自检：28 个 Python 文件方法识别与 `def` 行数全一致；Java 48 个类型 / 246 个方法 0 处范围或切片错误；36 个文件跑完整 6.1→6.5 产出 123 条 related code、0 问题

当前包结构（Phase 6 新增部分）：

```text
agent/app/
├── context/                        (Phase 6 新增)
│   ├── diff_parser.py              (6.1)
│   ├── file_context_builder.py     (6.2)
│   ├── method_context_builder.py   (6.3)
│   ├── class_context_builder.py    (6.4)
│   ├── related_code_builder.py     (6.5)
│   └── source_scanner.py           (6.4 抽出，6.3/6.4/6.5 共用)
└── schemas/
    └── code_context.py             (Phase 6 契约)
```

已知问题 / 技术债：

- Code Context 尚未接入真实 PR 数据（Java 接口 / Python client / 装配 / ReviewService 接线 / Prompt 渲染均未实现）
- 未实现 Context Size Control 与 Token 控制
- `_anchors` 只探测 changed range 首尾两行，跨 3 个及以上类型时中间类型可能漏成 anchor
- Python 多行字符串属性的 `end_line` 停在起始行
- Java 4 层以上嵌套泛型方法、含匿名类初始化的字段、类内部 interface/abstract 无 body 声明方法可能漏识别
- 全部定位为启发式，`source=HEURISTIC`，`confidence ≤ 0.9`

当前状态：

```text
Phase 6：Code Context 🟡 进行中（6.1 ~ 6.5 已完成，未接入真实数据）
```

下一步：

```text
Phase 6.6：Context Size Control + Token 控制
        ↓
Java PR Context 接口 → Python client → CodeContext 装配
        ↓
ReviewService / Prompt 接线 → 真实 PR 联调
```

---

### 2026-10-08

Phase 6.6.1 ~ 6.6.4（Context Size Control + Token 控制）与 Phase 6.7.1（Java 侧 PR Context 读取）完成。

已完成：

- [x] Phase 6.6.1：预算数据模型 — commit `ca97606`
  - `ContextBudget` / `ContextStats` / `Truncation`；`RelatedCodeContext.truncated`、`MethodContext.truncated`、`ClassContext.header_end_line`；`FileContext` / `CodeContext` 追加 `stats` / `truncation`（全部向后兼容）
  - `estimate_tokens(text) = ceil(other_chars/3) + cjk_chars`（确定性、无 tokenizer、无网络）
- [x] Phase 6.6.2：单文件 Context Size Control — commit `e3f0b3c`
  - `measure_context`（只测不裁，`content` / 未变更 classes 只进 `retained_source_chars`）
  - `apply_context_budget`：related 按优先级整条删；METHOD/CONSTRUCTOR/FIELD 超限即删、NESTED_TYPE 可降级声明头；changed code 与 diff 不动；输入不可变、幂等；保留条目保持输入顺序
  - `class_context_builder` 最小改动填充 `header_end_line`
- [x] Phase 6.6.3：多文件 Context Budget — commit `f4192dd`
  - `plan_file_budgets`（权重 `1 + changed_method_count`、floor 优先、确定性降级）、`apply_context_budget_to_files`（全局二次削减，changed 仍受保护）、`aggregate_stats`
- [x] Phase 6.6.4：Token 控制 — commit `d3ecb2f`
  - `tokens_for_chars` / `chars_for_tokens` / `budget_from_tokens`；未引入任何 Token SDK；未改 6.6.1~6.6.3 行为
- [x] Phase 6.7.1：Java 侧 PR Context 读取 — **尚未提交**
  - `ReviewContextProperties`（`review.context.*`，已登记 `@EnableConfigurationProperties` + `application.yml`）
  - `GithubPullRequestFilesClient`（`GET /pulls/{n}/files`、per_page=100、Link 分页、max-files 即停、max-fetch-pages、顺序保持）+ `PullRequestFile`
  - `PrContextFile` / `PrContextResponse` / `PrContextService` / `PrContextController`（`GET /api/tasks/{taskId}/pr-context`）
  - `GithubFileContentClient` 修复：URI 分段编码、encoding/size/二进制保护、合法空文件保留；`GithubPullRequestClient` 追加 Token overload；`FileContent` 追加 `contentReason`
  - Installation Token 单次复用（一次构建只取一次 Token，无全局缓存）
  - `content_reason`：`removed` / `unsupported_language` / `too_large` / `binary` / `fetch_failed:<status>`

6.7.1 设计决策（已确认）：

- `max-file-bytes` 无法在 `pulls/{n}/files` 阶段预知 → 采用 contents 响应后的 `size`/解码长度防护，不新增 Git Trees/Blobs API
- `TaskNotFoundException` 在控制器内局部返回 404；其他 GitHub/Token 异常沿用现有异常传播（容器 5xx），不新增全局错误响应体系
- `content_available` / `content_truncated` / `content_reason` 保持蛇形字段，作为 6.7.2 Python 契约

测试结果：

- [x] Python 全量：**904 passed**（`test_diff_parser` 77 / `test_code_context_schemas` 152 / `test_file_context_builder` 76 / `test_method_context_builder` 120 / `test_class_context_builder` 131 / `test_related_code_builder` 89 / `test_context_size_controller` 180 / Phase 5 及更早 79）
- [x] Java 全量：**202 passed**（基线 152 + 6.7.1 新增 50）
- [x] `git diff --check` 通过；本次 Python 零修改

当前状态：

```text
Phase 6：Code Context 🟡 进行中（6.1~6.7.1 已完成，Python 侧取码未接入；Phase 6 未完成）
```

下一步：

```text
Phase 6.7.2：Python PrContext DTO + PrContextClient
        ↓
CodeContextBuilder：PrContext → CodeContext 装配
        ↓
ReviewService 接线（取码失败降级 degraded）→ Prompt 渲染 → 真实 PR 联调
```

---

### 2026-10-08 (2)

Phase 6.7.2（Python PrContext DTO + PrContextClient）完成。

已完成：

- [x] `agent/app/schemas/pr_context.py`：`PrContext` + `PrContextFile`
  - 严格对应 Java `GET /api/tasks/{taskId}/pr-context`；普通字段沿用既有 camelCase 映射（与 `TaskMessage` 一致）
  - `content_available` / `content_truncated` / `content_reason` 固定蛇形（camelCase 变体被忽略/拒绝）；`content=null` 与合法空文件 `content=""` 区分保留
  - `content_reason` 原样保留 `removed` / `unsupported_language` / `too_large` / `binary` / `fetch_failed:*`
  - `path` / `status` 必需（缺失 → ValidationError），计数器与可选字段带容错默认值
- [x] `agent/app/context/pr_context_client.py`：`PrContextClient.fetch(task_id) -> PrContext`（async，httpx.AsyncClient）
  - base URL 复用 `settings.JAVA_SERVICE_URL`；新增 `settings.PR_CONTEXT_TIMEOUT`（30s）并同步 `.env.example`
  - 非 2xx / 非 JSON / Schema 不符：记录日志后原样抛出（与 `AiServiceClient` / `JavaServiceClient` 约定一致）
  - 纯传输层，不做装配 / Prompt / 业务判断；日志不输出文件内容
- [x] 测试 44 项（`test_pr_context_schemas.py` 29 + `test_pr_context_client.py` 15）
- [x] Python 全量 948/948（基线 904 + 新增 44）；`git diff --check` 通过

设计决策：

- DTO 普通字段用与 `TaskMessage` 相同的 camelCase 字段名直接反序列化；内容状态三字段用蛇形与 Java `@JsonProperty` 对齐
- 客户端采用 async（与未来消费者 `ReviewService`、现有 `DeepSeekClient` 一致），不新增 HTTP 依赖
- 失败降级（不得触发 Phase 4 无限重试）留到 6.7.3/6.7.4 接线实现，本阶段不提前加入

当前状态：

```text
Phase 6：Code Context 🟡 进行中（6.1~6.7.2 已完成；装配与 Prompt 未实现；Phase 6 未完成）
```

下一步：

```text
Phase 6.7.3：CodeContextBuilder：PrContext → CodeContext 装配
```

---

### 2026-10-08 (3)

Phase 6.7.3（CodeContextBuilder）完成。

已完成：

- [x] `agent/app/context/code_context_builder.py`：`CodeContextBuilder.build(pr_context) -> CodeContext`（纯装配：无 IO、无预算裁剪、无 Prompt）
- [x] 复用 Phase 6.1~6.5 全链路：`parse_patch → build_file_context → attach_method_contexts → attach_class_contexts → attach_related_code`（未新增第二套 Context 模型，未改任何既有模块）
- [x] 字段映射：
  - `repository = owner/repo`、`pr_number`、`head_sha = commitSha`；`base_sha = None`（Java 只给 base 分支名，不伪造 SHA）
  - `path/status/patch/previousPath → FileDiff`（patch=None → `patch_available=false`；renamed → `previous_path`）
  - `content → FileContent { path, revision, content, error=content_reason } → FileContext.content / line_count / content_available`
  - `content_reason` 保留在 `content.error` 与 `notes`；文件顺序与 Java 一致
- [x] 不可用内容安全语义：`content=null` 不伪造代码（methods/classes/changed_symbols/related_code 全空、line_count=0）；单文件不可用不影响整体；removed → `skipped_reason="file removed at head revision"`
- [x] 未应用预算（`stats/truncation` 保持 None），未把 title/state/refs 复制进 CodeContext，未做 schema 结构调整
- [x] 测试 30 项（`test_code_context_builder.py`）；Python 全量 978/978（基线 948 + 30）；6.1~6.6 零回归；`git diff --check` 通过

设计决策：

- `base_sha` 保持 None（不把 ref 名当 SHA）；不新增字段
- title / state / baseRef / headRef 留在 PrContext，不复制进 CodeContext（不提前为 Prompt 设计字段）
- 装配与预算解耦：预算由调用方在 6.7.4 显式调用 `apply_context_budget_to_files`（6.6.3）

当前状态：

```text
Phase 6：Code Context 🟡 进行中（6.1~6.7.3 已完成；ReviewService 接线与 Prompt 未实现；Phase 6 未完成）
```

下一步：

```text
Phase 6.7.4：ReviewService 接线（取码失败降级 degraded，不得触发 Phase 4 无限重试）
```

---

### 2026-10-08 (4)

Phase 6.7.4（ReviewService 接线）完成。

已完成：

- [x] `agent/app/services/review_service.py`：`ReviewService` 新增可选注入 `pr_context_client` / `context_builder` / `context_budget`；`review()` = `_load_context → build_messages → generate_findings → result`
- [x] `agent/app/api/review_router.py`：生产注入 `PrContextClient`（新增 `get_pr_context_client` 依赖）
- [x] 正常路径：`PrContextClient.fetch(task_id)` → `CodeContextBuilder.build` → **6.6 预算**（`apply_context_budget_to_files(context.files, budget)`，默认 `DEFAULT_BUDGET`）→ 回填 `CodeContext.stats/truncation`
- [x] `agent/app/context/context_size_controller.py` 最小追加 `aggregate_truncation(files) -> Truncation`（与 `aggregate_stats` 对称的汇总，未改 6.6 任何既有语义）
- [x] 失败降级：`_load_context` 捕获 fetch/build/budget 的全部异常，**不抛出** → `status=DEGRADED` + `report.context={available:false, degraded:true, reason:"http_error:404/500|ConnectError|ReadTimeout|ValidationError|ValueError|…"}`；日志 WARNING 明确 "PR context unavailable ... review degrades"；堆栈仅 DEBUG
- [x] CodeContext **未接入 Prompt / LLM**：`build_messages(request)` 与 `generate_findings(messages)` 与 Phase 5.2 完全一致（测试静态断言 `messages == build_messages(request)`）；context 仅写入 `report.context` 摘要（数量 / estimated_tokens / truncated）
- [x] Phase 4 重试策略未改动：LLM 失败依旧向上抛出触发既有 retry；context 失败被本地降级，不进入 retry
- [x] 未注入 client 时保持 Phase 5 行为（`COMPLETED` + `reason:"not_configured"`）
- [x] 测试 22 项（`test_review_service.py` +17、`test_context_size_controller.py` +5）；Python 全量 **1000/1000**；6.1~6.6 与 Phase 4/5 零回归；`git diff --check` 通过

设计决策：

- `status="DEGRADED"` 复用既有 `ReviewTaskResult.status` 字段表达降级（degraded ≠ failed，任务生命周期仍 COMPLETED），不新增状态机
- 降级边界只包住 context 获取/装配/预算；LLM 调用在边界之外，真实审查失败仍走 Phase 4 retry
- `report.context.reason` 只暴露失败类别，不写异常 message（validator 消息可能回显代码）
- budget 固定执行（未传时用 6.6 默认预算），可注入覆盖；不把 CodeContext 放入 Prompt（留 6.7.5）

当前状态：

```text
Phase 6：Code Context 🟡 进行中（6.1~6.7.4 已完成；Prompt 未实现；Phase 6 未完成）
```

下一步：

```text
Phase 6.7.5：Prompt 接线（CodeContext 渲染进 Prompt + file_path / 行号硬约束）
```

---

### 2026-10-08 (5)

Phase 6.7.5（Prompt 接线）完成。

已完成：

- [x] `agent/app/prompts/code_context.py`（新）：`render_code_context(context)` / `render_context_unavailable(reason)`；纯渲染，无 IO / 无预算逻辑 / 无 schema 变更
- [x] 渲染载荷对齐 6.6 预算口径：metadata（repository / PR / sha / stats）+ 每文件 status/language/changes + diff（由 hunks 重建 unified diff）+ changed methods（code + 行号 + changed_ranges + source/confidence）+ related code（kind/lines/reason/source/confidence + code）+ classes / changed_symbols 定位标签
- [x] 不可用内容：`content: unavailable (reason: removed | unsupported_language | too_large | binary | fetch_failed:<status>)`，无代码围栏、无 "None" 文本；removed 文件的删除 patch 仍可用作证据
- [x] 截断声明：budget 截断时输出 `Context truncation: THE CODE CONTEXT BELOW IS INCOMPLETE ...`（reasons / dropped / trimmed / removed_chars 全部来自 6.6 记录）；未截断时无声明
- [x] `agent/app/prompts/review.py`：`build_messages(request, context, context_report)` 三态（legacy / available / degraded）；`SYSTEM_PROMPT` 增加 file_path 与行号硬约束，原有 schema / 规则一字未删
- [x] `agent/app/services/review_service.py`：`_load_context` 返回 `(context, report)`；`build_messages` 收到渲染后的 CodeContext；只 DEBUG 记录 prompt 字符数（不含内容）
- [x] 测试 52 项（`test_code_context_prompt.py` 48 + `test_review_service.py` 净增 4）；Python 全量 **1052/1052**；6.1~6.7.4 与 Phase 4/5 零回归；`git diff --check` 通过

设计决策：

- Prompt 只携带 6.6 已度量并裁剪的载荷（diff + changed methods + related + metadata）；full content 与未变更 class 代码按既定契约留在 `retained_source_chars`，不发送，避免绕过预算
- classes / changed_symbols 仅渲染定位标签（不重复类体代码）；字段类变更由 related code 的 FIELD 项承载
- reason / truncation / stats 全部读现有字段，不在 Prompt 层重算；`estimated_tokens` 仍是预算载荷的度量（固定声明文本不计入，已知偏差很小）
- `build_messages` 向后兼容：无 context_report 时输出与 Phase 5.2 逐字节一致；`not_configured` 亦然；只有 degraded 才出现 "PR context unavailable"
- 渲染文本含不可信源码，禁止入日志（ReviewService 只记录字符数）

当前状态：

```text
Phase 6：Code Context 🟡 进行中（6.1~6.7.5 已完成；真实 PR 联调未做；Phase 6 未完成）
```

下一步：

```text
Phase 6.7.6：真实 PR 端到端联调（LLM 收到真实代码）
```

---

### 2026-10-08 (6)

Phase 6.7.6（真实 PR E2E 联调）完成并通过验收 —— **Phase 6 正式完成**。

环境修复（本机配置，未改业务代码）：

- [x] `.env` 修复：私钥路径改为实际 pem 文件名；补充 `GITHUB_INSTALLATION_ID=165170316`
- [x] Docker Desktop 启动 + `docker compose up -d mysql`（3307，既有 volume；未起 compose Redis）
- [x] Spring 用 `-Dspring-boot.run.workingDirectory=<repo root>` 启动（私钥相对路径按 CWD 解析；spring-boot:run 默认模块目录 → 曾致 /pr-context 500）
- [x] FastAPI / Worker 从 `.env` 显式导出环境变量启动；Smee 转发重建

真实 PR 联调（PR #3 `test/phase6-e2e`，GitHub API 创建，未合并）：

- [x] task 4：files=3, withContent=2, estimatedTokens=377 → COMPLETED, findings=2
- [x] task 5（modified 文件）：files=4, withContent=3, estimatedTokens=1188, related_kept=2 → COMPLETED, findings=2
- [x] task 6（受控 degraded）：坏私钥路径 → /pr-context 500 → DEGRADED, findings=0；Prompt 含 "PR context unavailable"；MySQL COMPLETED / retry_count=0（无 Phase 4 retry）
- [x] task 7（恢复后）：files=4, withContent=3, estimatedTokens=1203 → COMPLETED, findings=1
- [x] A~F 逐项核验通过（详见 §9 Phase 6.7.6 条目）：真实取码、预算口径、Prompt 含真实代码切片、findings 行号可溯源、degraded 语义
- [x] G 回归：Python 1052/1052；Java 202/202（BUILD SUCCESS）；`git diff --check` 通过
- [x] 安全检查：正常日志无 API Key / JWT / 私钥 / 密码泄漏

结论：

- **真实 E2E PASS**；未发现 6.7.x 业务代码缺陷；问题均为环境/启动配置类（已记入已知问题）
- **Phase 6 正式完成**，下一阶段只能是 **Phase 7（Static Analysis）**

---

### 2026-09-26 (2)

Phase 2 安全配置：PEM 文件路径方式 + GitHub App 凭证管理。

已完成：

- [x] 创建 `secrets/` 目录（`.gitignore` 已忽略 `secrets/`、`*.pem`、`*.key`）
- [x] `GithubAppProperties` 增加 `privateKeyPath` 字段（4 字段 record）
- [x] `application.yml` 增加 `github.app.private-key-path`（映射 `GITHUB_PRIVATE_KEY_PATH`）
- [x] `.env.example` 更新：添加 `GITHUB_PRIVATE_KEY_PATH`，推荐方式一（文件路径），保留方式二（直接粘贴内容）
- [x] `.env` 填写 `GITHUB_APP_ID=5086582`、`GITHUB_PRIVATE_KEY_PATH=secrets/codesentinel-lab.pem`
- [x] 测试适配（`GithubAppProperties` 4 字段构造器）
- [x] 全部 21 个测试通过

GitHub App 已真实创建并完成 Webhook 联调：

| 项目 | 值 |
|------|-----|
| App Name | CodeSentinel-Lab |
| App ID | 5086582 |
| 安装仓库 | zhangyu1108l/CodeSentinel |
| Webhook | Smee 代理已配置并验证通过 |
| 联调 PR | #1 (已合并至 main) |

已完成：

- [x] 将 .pem 文件放入 secrets/codesentinel-lab.pem
- [x] 在 .env 中填写 GITHUB_WEBHOOK_SECRET
- [x] Webhook 联调验证（Smee + Spring Boot，HTTP 200）

当前状态：

```text
Phase 2：GitHub App + Webhook ✅ 已完成
Webhook 接收 ✅ / 签名验证 ✅ / PR 事件解析 ✅ / GitHub App 创建 ✅ / 真实联调 ✅
```

下一步：

```text
Phase 3：GitHub API
```

---

# 20. OpenCode 使用说明

新的 OpenCode Session 进入项目后，建议首先读取：

```text
AGENTS.md
docs/PROJECT_DESIGN.md
docs/DEVELOPMENT_STATUS.md
```

推荐首次指令：

```text
请先阅读：

- AGENTS.md
- docs/PROJECT_DESIGN.md
- docs/DEVELOPMENT_STATUS.md

理解项目规则、整体方案和当前开发进度。

暂时不要修改代码。

告诉我：
1. 当前项目处于什么阶段
2. 当前阶段已经完成什么
3. 当前应该做什么
4. 你准备如何实现下一步
```

开始具体任务后：

```text
只实现 DEVELOPMENT_STATUS.md 中当前 Phase / Current Task，
严格遵守 AGENTS.md，
完成后更新 DEVELOPMENT_STATUS.md，
并运行与本次改动相关的测试和构建验证。
```

---

# 21. 状态符号

统一使用：

```text
⬜ 未开始
🟡 进行中
✅ 已完成
⚠️ 有问题
⏸️ 暂停
```

---

# 22. 维护原则

### 本文件只记录“实际进度”

不要把大量架构设计重复写到这里。

详细设计放：

```text
docs/PROJECT_DESIGN.md
```

开发规则放：

```text
AGENTS.md
```

当前执行状态放：

```text
docs/DEVELOPMENT_STATUS.md
```

### 每完成一个 Task 都更新

至少更新：

```text
Current Task
Completed
Known Issues
Next Step
```

### 不要虚报完成

只有经过实际实现和验证的功能才能标记：

```text
✅ 已完成
```

### 不要因为代码“看起来写完了”就标记完成

必须经过适当验证，例如：

```text
Build
Test
Static Check
API Verification
Integration Test
```

根据任务实际情况选择。

---

# 23. 当前唯一下一步

Phase 6（Code Context）已完成并通过真实 PR E2E 验收（6.1 ~ 6.7.6；PR #3 全链路 + 受控 degraded 演练 + 回归 1052/202）。

```text
纯 Python：Diff → File Context → Method Context → Class Context → Related Code
          → Context Size Control / Token 控制 → PrContext DTO / PrContextClient
          → CodeContextBuilder 装配 → ReviewService 接线（取码失败降级 degraded）
          → Prompt 渲染（diff + methods + related + 可用性/截断声明 + 行号硬约束）
Java：    GET /api/tasks/{taskId}/pr-context（分页 + 内容保护 + 单 Token 复用）
真实 E2E：PR #3（task 4/5/7 COMPLETED，task 6 DEGRADED；未合并）
          （6.7.1 ~ 6.7.5 尚未提交）
```

下一步只能是 **Phase 7：Static Analysis**（Java: PMD / Checkstyle / Semgrep；Python: Ruff / Bandit / Semgrep），并遵循新 Phase 流程：先阅读 / 检查 / 提计划，不直接改代码。

已知限制（不阻塞 Phase 6 验收）：Imports / namespace / package 分析未实现。

不要提前实现：

```text
LangGraph Multi-Agent (Phase 8)
GitHub Comment (Phase 9)
MySQL 历史记录 (Phase 10)
RAG
Milvus
Dashboard
VS Code
Auto Fix
```
