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

**Phase 5：Python AI Service + DeepSeek — 已完成（5.1 HTTP 边界 + 5.2 DeepSeek 真实调用）**

## 当前任务

Phase 5 已完成。下一步：Phase 6（Code Context）。

## 当前总体进度

```text
Phase 1  基础工程                 ✅ 已完成
Phase 2  GitHub App + Webhook     ✅ 已完成
Phase 3  GitHub API               ✅ 已完成
Phase 4  Review Task + Redis      ✅ 已完成
Phase 5  Python AI Service        ✅ 已完成
Phase 6  Code Context             ⬜ 未开始
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

## 子任务

- [ ] Diff Parser
- [ ] File Context
- [ ] Method Context
- [ ] Class Context
- [ ] Related Code
- [ ] Context Size Control
- [ ] Token 控制

## Phase 6 状态

**⬜ 未开始**

## 当前任务

暂无。

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

暂无。

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

```text
Phase 6：Code Context
```

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
Code Context → 提供给 LLM（files 携带真实代码内容）
```

不要提前实现：

```text
Static Analysis (Phase 7)
LangGraph Multi-Agent (Phase 8)
GitHub Comment (Phase 9)
RAG
Milvus
Dashboard
VS Code
Auto Fix
```
