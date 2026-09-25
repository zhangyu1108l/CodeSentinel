# CodeSentinel Project Instructions

## 1. 项目身份

项目名称：CodeSentinel  
中文名称：代码哨兵——AI 智能代码审查系统

项目定位：

> 一个面向 GitHub Pull Request 的 AI 智能代码审查系统，通过 GitHub App + Webhook 自动触发审查，结合静态分析工具与 LangChain/LangGraph 多 Agent，对 Java / Python 代码进行 Bug、安全、性能、代码质量等维度的分析，并将经过验证的结果自动反馈到 GitHub PR。

项目核心闭环：

```text
GitHub PR
  ↓
GitHub App Webhook
  ↓
Spring Boot 3
  ↓
Review Task
  ↓
Redis
  ↓
Python AI Service
  ↓
Code Context + Static Analysis
  ↓
LangGraph Multi-Agent
  ↓
Validator
  ↓
Report
  ↓
Spring Boot
  ↓
MySQL
  ↓
GitHub PR Summary + Inline Comments
```

---

## 2. 总体开发原则

### 2.1 优先保证核心闭环

所有开发应优先保证下面的主链路可用：

```text
PR
→ Webhook
→ Task
→ AI Review
→ Finding
→ Validator
→ Report
→ MySQL
→ GitHub Comment
```

不要在核心链路没有跑通之前，大量开发外围功能。

### 2.2 不为了堆技术而堆技术

不要为了“看起来高级”强制加入没有实际价值的技术。

当前 MVP：

- 不使用 Milvus
- 不使用 RAG
- 不执行用户 PR 代码
- 不做 VS Code 插件
- 不做独立 GitHub Action 产品
- 不做复杂多租户系统
- 不做自动修复 Patch
- 不做复杂 Dashboard

这些功能只有在核心 Review 闭环稳定后才允许进入后续阶段。

### 2.3 不擅自改变已确定的架构

已确定的核心技术：

- Java 21
- Spring Boot 3
- Python 3.12+
- FastAPI
- LangChain
- LangGraph
- DeepSeek API
- GitHub App
- GitHub REST API
- MySQL 8
- Redis
- Docker Compose

除非用户明确要求，否则不要擅自替换核心技术栈。

### 2.4 不猜测需求

遇到真正影响架构、接口、数据模型、安全边界的问题：

1. 先检查已有项目文档和代码。
2. 如果已有明确约定，遵循已有约定。
3. 如果确实缺少关键信息，再询问用户。
4. 不要因为个人偏好擅自增加功能。

---

# 3. 架构边界

## 3.1 Spring Boot 负责什么

Spring Boot 是：

> 业务后端 + GitHub 集成层

负责：

- GitHub Webhook
- Webhook 签名验证
- GitHub App Authentication
- Installation Token 管理
- Repository / Pull Request 信息
- Commit / Diff / Changed Files 获取
- Review Task
- Redis 任务投递
- Review 结果接收
- MySQL 持久化
- GitHub PR Summary
- GitHub Inline Comment
- REST API
- 后续 Dashboard API

Spring Boot 不负责：

- Prompt 编排
- LangGraph Workflow
- 多 Agent 推理
- 大量 LLM 业务逻辑
- Python Agent 内部状态管理

---

## 3.2 Python 负责什么

Python AI Service 是：

> AI 分析层

负责：

- FastAPI
- LangChain
- LangGraph
- DeepSeek
- Agent
- Prompt
- Code Context
- Static Analysis 调度
- Rule Engine
- Finding
- Validator
- Report Generator

Python 不负责：

- GitHub Webhook 核心业务
- GitHub App 权限体系
- GitHub 最终评论业务逻辑
- Spring Boot 业务数据库的直接管理

---

## 3.3 两个服务之间的原则

两个服务之间通过明确的 API / Task Schema 通信。

禁止：

- 互相读取对方数据库
- 共享内部实现
- 通过未定义字段传输数据
- 把大量业务逻辑跨服务复制

建议使用稳定的数据契约：

```text
ReviewTaskRequest
ReviewTaskResult
ReviewFinding
ReviewReport
```

任何 Schema 变化必须同步检查消费者和生产者。

---

# 4. MVP 功能范围

## 4.1 必须完成

### GitHub

- GitHub App
- Pull Request Webhook
- Webhook Signature 验证
- PR 信息获取
- Commit 获取
- Diff 获取
- Changed Files 获取
- PR Summary
- Inline Comments

### AI Review

- Java
- Python
- Bug
- Security
- Performance
- Code Quality
- Planner Agent
- Bug Agent
- Security Agent
- Performance Agent
- Quality Agent
- Validator Agent
- Reporter Agent

### 工程设施

- MySQL
- Redis
- Docker Compose
- Review Task
- Review Report
- Review Finding
- Review Comment
- 日志
- 错误处理
- 基础测试

---

## 4.2 MVP 禁止擅自增加

以下功能必须经过用户明确要求后再实现：

- Milvus
- RAG
- VS Code Extension
- GitHub Action 独立入口
- 自动生成修复 Patch
- 自动提交 Commit
- 自动 Merge
- `REQUEST_CHANGES`
- `APPROVE`
- 执行不可信 PR 代码
- Docker Sandbox
- 多租户
- SSO
- 商业化计费
- 复杂权限系统

---

# 5. GitHub 集成规范

## 5.1 GitHub App 优先

正式架构使用 GitHub App，而不是把 Personal Access Token 作为核心认证方案。

第一阶段只考虑：

```text
GitHub App
→ 安装到测试 Repository
→ Webhook
→ Installation Authentication
```

后续再扩展为公开安装模式。

---

## 5.2 最小权限原则

GitHub App 只申请完成项目所需的最小权限。

严禁为了方便直接申请过大的 Repository 权限。

权限发生变化时必须同步检查：

- GitHub App 配置
- API 调用
- 文档
- 安全设计

---

## 5.3 Webhook 安全

所有 Webhook 必须验证：

```text
X-Hub-Signature-256
```

禁止：

- 直接相信请求来源
- 关闭签名验证
- 在日志输出 Webhook Secret
- 在代码中硬编码 Secret

Webhook 处理逻辑：

```text
Request
 ↓
读取原始请求体
 ↓
HMAC SHA-256 验证
 ↓
验证通过
 ↓
解析事件
```

---

## 5.4 Webhook 必须快速返回

禁止在 Webhook 请求线程内：

```text
调用 LLM
等待 AI 审查
等待大量 GitHub API
等待完整 Review
```

正确方案：

```text
Webhook
 ↓
验证
 ↓
解析
 ↓
创建 ReviewTask
 ↓
Redis
 ↓
立即返回 2xx
```

AI Review 必须异步执行。

---

## 5.5 GitHub Token

Installation Access Token：

- 不写死
- 不提交 Git
- 不永久保存
- 不输出到日志
- 按需获取
- 必要时缓存
- 接近过期时刷新

---

## 5.6 GitHub 评论

MVP 自动评论只使用：

```text
COMMENT
```

不要擅自实现：

```text
APPROVE
REQUEST_CHANGES
```

Inline Comment 必须尽可能绑定：

- commit SHA
- file path
- line
- side

如果无法可靠定位具体行，不得伪造行号。

---

# 6. AI Agent 架构规范

## 6.1 Agent 必须职责单一

不要创建一个“万能 Review Agent”。

推荐职责：

```text
Planner
Bug
Security
Performance
Quality
Validator
Reporter
```

每个 Agent 应该拥有：

- 明确输入
- 明确输出
- 明确职责
- 明确 Prompt
- 可独立测试

---

## 6.2 LangGraph 是主工作流编排层

LangGraph 用来负责：

- State
- Node
- Edge
- Conditional Routing
- Agent Workflow

不要把复杂状态机全部写成散落的 Python 函数调用。

推荐：

```text
state.py
nodes.py
workflow.py
```

---

## 6.3 Agent 不直接操作基础设施

Agent 尽量通过明确的 Tool 调用：

```text
GitHub Tool
Static Analysis Tool
Context Tool
Rule Tool
```

不要在 Prompt / Agent 文件中直接：

- 写 MySQL SQL
- 操作 Redis
- 直接调用 GitHub HTTP
- 修改系统文件

基础设施应该放在独立模块。

---

# 7. Finding 规范

所有 Agent 必须最终输出统一 Finding Schema。

推荐字段：

```json
{
  "category": "SECURITY",
  "severity": "HIGH",
  "confidence": 0.94,
  "rule_id": "CWE-89",
  "title": "Potential SQL Injection",
  "file_path": "src/UserRepository.java",
  "start_line": 52,
  "end_line": 52,
  "description": "Potential SQL injection risk.",
  "reason": "External input is directly concatenated into SQL.",
  "suggestion": "Use parameterized queries.",
  "references": [
    "CWE-89",
    "OWASP"
  ]
}
```

### category

允许：

```text
BUG
SECURITY
PERFORMANCE
QUALITY
```

### severity

允许：

```text
CRITICAL
HIGH
MEDIUM
LOW
INFO
```

### confidence

范围：

```text
0.0 ~ 1.0
```

任何进入最终 Report 的 Finding 必须有：

- category
- severity
- confidence
- title
- file_path
- 行号（如果可可靠定位）
- description
- reason
- suggestion

---

# 8. Validator 规范

Validator 是最终质量闸门。

流程必须尽量遵循：

```text
Agent Finding
    ↓
重新读取相关代码
    ↓
结合 Diff
    ↓
结合 Static Analysis
    ↓
结合 Rule
    ↓
判断是否真实问题
    ↓
确认 severity
    ↓
确认 confidence
```

不能：

```text
Agent 说有问题
 ↓
直接评论
```

Validator 的职责：

- 判断是否真实问题
- 降低误报
- 修正严重程度
- 修正置信度
- 确认评论位置是否合理
- 删除重复 Finding

---

# 9. Static Analysis 规范

LLM 不是唯一检测手段。

原则：

```text
Static Analysis
        +
LLM Semantic Analysis
        ↓
Validator
```

---

## 9.1 Java

第一阶段：

- PMD
- Checkstyle
- Semgrep

后续可选：

- SpotBugs

---

## 9.2 Python

第一阶段：

- Ruff
- Bandit
- Semgrep

---

## 9.3 静态分析结果

统一转换成内部结构，例如：

```text
StaticAnalysisResult
```

不要让上层 Agent 直接依赖某个工具的原始 JSON 格式。

---

# 10. Code Context 规范

不能只把 Git Diff 丢给 LLM。

Code Context Builder 应尽量提供：

```text
PR 信息
+
Diff
+
Changed File
+
Changed Method
+
Class
+
Import
+
相关代码
+
Static Analysis Result
```

第一阶段优先使用：

- AST
- Tree-sitter
- JavaParser
- ripgrep
- 简单依赖分析

不要为了代码上下文强行引入 Milvus。

---

# 11. Prompt 规范

Prompt 必须：

- 明确角色
- 明确输入
- 明确检查目标
- 明确输出 Schema
- 明确禁止无依据推测
- 明确要求引用代码证据
- 明确要求区分确定问题和潜在问题

禁止使用过度宽泛的 Prompt：

```text
“帮我看看这里有没有问题”
```

应当明确：

```text
分析目标
检查范围
代码上下文
规则
输出格式
置信度
```

Prompt 不应散落在业务代码中。

统一放在：

```text
agent/prompts/
```

---

# 12. Rule Engine 规范

MVP 使用结构化规则库，不使用 RAG。

目录建议：

```text
rules/
├── security/
├── java/
├── python/
├── performance/
└── quality/
```

每条规则尽量具备：

```text
rule_id
name
category
language
description
severity
detection_hint
recommendation
references
```

示例：

```yaml
rule_id: SEC-001
name: SQL Injection
category: SECURITY
language:
  - java
  - python
severity: HIGH
```

Rule Engine 和 LLM Agent 解耦。

---

# 13. RAG / Milvus 规则

当前：

> 不做 RAG，不接 Milvus。

后续如果出现实际业务需求，例如：

- 企业内部开发规范
- 项目级代码规范
- 大量安全文档
- 框架官方文档
- 历史 Review 知识

再考虑：

```text
Documents
 ↓
Embedding
 ↓
Milvus
 ↓
Retriever
 ↓
Agent
```

不得为了堆技术栈提前实现。

---

# 14. 数据库规范

数据库：

```text
MySQL 8
```

核心实体：

```text
github_installation
repository
pull_request
review_task
review_report
review_finding
review_comment
```

关系：

```text
github_installation
    ↓ 1:N
repository
    ↓ 1:N
pull_request
    ↓ 1:N
review_task
    ↓ 1:1
review_report
    ↓ 1:N
review_finding
    ↓ 0:N
review_comment
```

---

## 14.1 数据库原则

- 不允许把 JSON 当成所有业务数据的替代品
- 核心查询字段必须结构化
- 状态使用明确枚举
- 保留 created_at / updated_at
- 外键关系保持清晰
- 不在 Controller 中直接写 SQL
- 数据访问层与业务层分离

---

# 15. Redis 规范

Redis 主要负责：

- Review Task
- 异步任务
- 短期状态
- 幂等
- 必要缓存

Redis 不替代 MySQL 历史记录。

长期 Review 数据必须写 MySQL。

---

# 16. 幂等性

GitHub Webhook 可能重复投递。

系统必须考虑幂等。

至少需要依据合适的：

```text
GitHub delivery id
Repository
PR Number
Commit SHA
Event
```

组合判断是否重复任务。

禁止：

```text
同一个 PR / Commit
重复产生无限 Review Task
```

---

# 17. 任务状态

推荐状态：

```text
PENDING
RUNNING
COMPLETED
FAILED
```

状态流转：

```text
PENDING
   ↓
RUNNING
   ↓
COMPLETED

RUNNING
   ↓
FAILED
```

状态不能随意回退。

如果支持重试，必须明确：

```text
retry_count
last_error
```

避免死循环重试。

---

# 18. 错误处理

系统必须区分：

### 用户/请求错误

例如：

```text
400
401
403
404
```

### GitHub API 错误

例如：

```text
权限不足
Rate Limit
Token 过期
资源不存在
```

### AI 错误

例如：

```text
LLM Timeout
API Error
Invalid JSON
Schema Validation Error
```

### 内部错误

例如：

```text
数据库异常
Redis 异常
内部服务不可用
```

不要吞掉异常。

不要使用：

```python
except Exception:
    pass
```

除非有非常明确的原因并记录日志。

---

# 19. 日志规范

日志必须帮助定位：

```text
ReviewTask
Repository
PR
Commit
Agent
```

推荐：

```text
INFO
WARN
ERROR
DEBUG
```

不要记录：

- GitHub Secret
- Private Key
- DeepSeek API Key
- Webhook Secret
- Installation Token
- 用户敏感数据

必要时对代码内容和 Token 脱敏。

---

# 20. 配置管理

所有外部配置放环境变量 / `.env`。

例如：

```text
GITHUB_APP_ID
GITHUB_PRIVATE_KEY
GITHUB_WEBHOOK_SECRET
DEEPSEEK_API_KEY
DEEPSEEK_MODEL
MYSQL_HOST
MYSQL_PORT
MYSQL_DATABASE
MYSQL_USERNAME
MYSQL_PASSWORD
REDIS_HOST
REDIS_PORT
```

禁止：

```text
代码中硬编码 Secret
```

配置类必须集中管理。

---

# 21. Python 代码规范

遵循：

- Python 3.12+
- 类型注解
- Pydantic Schema
- async 优先用于 IO 型 API
- 明确模块边界
- 小函数
- 单一职责
- 避免循环依赖
- 明确异常类型

推荐：

```text
app/
├── agents/
├── graph/
├── analyzers/
├── tools/
├── rules/
├── prompts/
├── schemas/
├── services/
└── config/
```

---

# 22. Java 代码规范

遵循：

- Java 21
- Spring Boot 3
- Controller / Service / Repository 分层
- DTO 与 Entity 分离
- Service 处理业务逻辑
- Repository 处理数据访问
- GitHub Client 独立封装
- 使用 RestClient 进行 HTTP 调用
- 构造器注入
- 不使用字段注入
- 明确异常类型
- 使用统一响应模型（项目已有约定时遵循已有约定）

禁止：

```java
@Autowired
private XxxService xxxService;
```

优先：

```java
@RequiredArgsConstructor
```

或显式构造器注入。

---

# 23. API 规范

API 必须保持：

```text
/api/github/...
/api/reviews/...
/api/tasks/...
/api/reports/...
```

Webhook：

```text
POST /api/github/webhook
```

查询 Review：

```text
GET /api/reviews/{reviewId}
```

查询 Finding：

```text
GET /api/reviews/{reviewId}/findings
```

不要在没有必要的情况下随意修改已经使用中的 API。

修改接口时：

1. 更新 DTO
2. 更新 Controller
3. 更新 Service
4. 更新调用方
5. 更新测试
6. 更新文档

---

# 24. 服务间 API

Spring Boot → Python 的调用必须使用明确 Schema。

例如：

```json
{
  "task_id": "123",
  "repository": "owner/repo",
  "pr_number": 42,
  "commit_sha": "abc123",
  "files": []
}
```

Python 返回：

```json
{
  "task_id": "123",
  "status": "COMPLETED",
  "report": {},
  "findings": []
}
```

不要传递：

```text
Python 内部对象
Java 内部 Entity
数据库 Entity
```

跨服务只传输稳定 DTO / Schema。

---

# 25. 测试规范

每个重要模块都必须考虑测试。

## Spring Boot

至少测试：

- Webhook Signature
- Webhook Event Parsing
- GitHub Client
- Task Service
- Redis Task
- Review Result
- GitHub Comment
- Repository / Service

## Python

至少测试：

- Finding Schema
- Agent 输出解析
- Validator
- Rule Engine
- Code Context
- Static Analysis Adapter
- LangGraph 节点

---

# 26. AI 评测规范

不能只测试：

> 接口返回 200。

必须建立人工可验证的代码审查测试集。

目录：

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

每个案例应包含：

```text
code
expected_category
expected_rule
expected_location
expected_severity
```

重点指标：

```text
Precision
Recall
False Positive Rate
Line Localization Accuracy
```

优先关注误报率。

---

# 27. 安全边界

MVP：

> 严禁执行来自 GitHub PR 的不可信代码。

允许：

- 读取源码
- 读取 Diff
- 静态分析
- LLM 分析

不允许直接：

```text
mvn test
pytest
npm install
python user_code.py
java user_code
```

除非以后专门设计：

```text
Sandbox
Docker isolation
Resource limit
Network isolation
Timeout
Filesystem isolation
```

---

# 28. Docker 规范

所有基础设施尽量容器化。

推荐：

```text
docker-compose.yml
```

服务：

```text
spring-service
ai-service
mysql
redis
```

后续可加入：

```text
frontend
nginx
milvus
```

不要在本地开发环境依赖大量手工配置。

---

# 29. 项目目录约束

推荐：

```text
code-sentinel/
├── backend/
│   └── spring-service/
├── agent/
├── frontend/
├── knowledge/
├── action/
├── infra/
├── docs/
├── AGENTS.md
└── README.md
```

原则：

- `backend/`：Spring Boot
- `agent/`：Python AI
- `frontend/`：后续 Dashboard
- `knowledge/`：规则 / 文档资源
- `action/`：后续 GitHub Action
- `infra/`：Docker / 部署
- `docs/`：设计文档

---

# 30. Git 操作规范

不要擅自执行：

```text
git reset --hard
git clean -fd
git push --force
```

除非用户明确要求。

开发时优先：

```text
git status
git diff
git log
```

检查当前工作区。

不要覆盖用户已有修改。

---

## 30.1 GitHub Flow 分支策略

本项目采用 GitHub Flow 分支模型。

### 分支规则

仅保留一个长期分支：

```text
main
```

`main` 分支存放稳定、可运行的代码。**禁止直接在 `main` 上开发。**

### 开发流程

```text
1. 从 main 创建临时功能分支
        ↓
2. 在临时分支上开发
        ↓
3. 开发完成后提交 Pull Request（临时分支 → main）
        ↓
4. CodeSentinel 自动触发代码审查
        ↓
5. 审查通过后合并 PR
        ↓
6. 合并完成后删除临时分支
```

### 分支命名

临时分支命名应简洁、描述性强，推荐格式：

```text
feature/<简短描述>
fix/<简短描述>
refactor/<简短描述>
docs/<简短描述>
```

示例：

```text
feature/add-webhook-verification
fix/null-pointer-in-task-service
refactor/extract-github-client
docs/update-api-docs
```

### 关键原则

- **不直接在 main 上开发**：任何代码变更必须通过分支 + PR。
- **PR 最小化**：每个 PR 聚焦单一功能或修复，避免超大 PR。
- **PR 触发审查**：每次 PR 的 `opened` / `synchronize` / `reopened` 事件自动触发 CodeSentinel 代码审查。
- **审查通过再合并**：AI 审查结果作为重要参考，但最终合并决策由开发者判断。
- **合并后清理**：PR 合并后及时删除临时分支，保持仓库整洁。

### 禁止操作

```text
git push --force 到 main
直接在 main 上 commit
长期保留已合并的临时分支
```

---

# 31. 修改代码前的工作方式

OpenCode 执行任务时必须：

### 第一步：理解上下文

先查看：

```text
AGENTS.md
相关子目录 AGENTS.md
README.md
docs/
相关代码
配置文件
```

### 第二步：定位最小修改范围

先判断：

```text
需要改哪些文件？
为什么？
影响哪些模块？
```

不要为了一个小功能大规模重构。

### 第三步：实现

遵循现有项目风格。

### 第四步：验证

至少运行与改动直接相关的：

- 编译
- 单元测试
- 静态检查
- API 验证

### 第五步：总结

说明：

```text
修改了什么
为什么修改
验证了什么
还有什么已知限制
```

---

# 32. 重构规范

不要因为：

> “这里可以写得更优雅”

就主动大规模重构。

允许重构的情况：

- 明确存在 Bug
- 明确违反项目架构
- 阻碍当前功能开发
- 用户明确要求
- 为解决测试/性能问题必须修改

重构必须控制范围。

---

# 33. 第三方库规范

增加第三方依赖之前：

1. 确认现有依赖无法解决问题。
2. 确认该库确实必要。
3. 优先使用成熟、稳定、官方维护的库。
4. 检查与当前版本兼容性。
5. 更新依赖文件。
6. 更新文档（如有必要）。
7. 跑测试。

不要为一个很小的功能引入重量级依赖。

---

# 34. GitHub API 规范

GitHub API 调用统一放在：

```text
github/
```

不要在业务 Service 中散落：

```text
HttpClient
RestClient
URL 拼接
Token
JSON 解析
```

建议：

```text
GitHubPullRequestClient
GitHubRepositoryClient
GitHubCommentClient
GitHubAppAuthService
```

业务层只表达：

```text
获取 PR
获取 Diff
创建 Comment
```

而不是：

```text
怎么调用 GitHub HTTP
```

---

# 35. LLM 调用规范

LLM 调用统一封装。

不要在多个 Agent 中重复：

```python
ChatOpenAI(...)
```

或者：

```python
requests.post(...)
```

推荐：

```text
LLMService
```

统一处理：

- Model
- API Key
- Timeout
- Retry
- Temperature
- Structured Output
- Error Handling

Agent 只关心：

```text
Prompt + Input → Output
```

---

# 36. 结构化输出规范

优先使用：

```text
Pydantic
```

进行 LLM 输出验证。

不要默认相信：

```text
LLM 返回的 JSON 一定正确
```

必须：

```text
LLM Output
 ↓
Parse
 ↓
Schema Validation
 ↓
Retry / Repair
 ↓
Valid Finding
```

---

# 37. Token / 成本控制

代码审查必须关注 Token 成本。

不要：

```text
整个 Repository
 ↓
全部发给 LLM
```

优先：

```text
Diff
+
必要上下文
+
相关代码
+
静态分析结果
```

Planner 应负责决定哪些 Agent 真正需要运行。

---

# 38. 并发原则

Agent 初始实现可以使用串行流程保证稳定性。

后续在验证正确性后，再考虑：

```text
Bug
Security
Performance
Quality
```

并行执行。

不要为了“看起来像 Multi-Agent”盲目并行。

---

# 39. 代码审查结果原则

最终 Finding 必须：

- 有证据
- 有定位
- 有原因
- 有建议
- 有置信度
- 有规则依据（适用时）

不要输出大量没有代码证据的泛化建议，例如：

```text
“建议优化代码性能。”
“这里可能存在安全问题。”
“最好增加异常处理。”
```

必须尽可能说明：

```text
哪里
为什么
证据是什么
如何修复
```

---

# 40. 最终质量标准

CodeSentinel 不以：

> Agent 数量多

作为项目质量标准。

真正重要的是：

```text
准确性
低误报
正确定位
可解释
可复现
可测试
可扩展
稳定
```

优先级：

```text
正确性
  >
稳定性
  >
可维护性
  >
性能
  >
功能数量
```

---

# 41. 当前开发路线

严格按照以下路线推进：

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

之后：

```text
Phase 11
Dashboard
    ↓
Phase 12
Custom Rules
    ↓
Phase 13
RAG / Milvus（只有存在实际需求时）
    ↓
Phase 14
GitHub Action
    ↓
Phase 15
VS Code
    ↓
Phase 16
Sandbox + Auto Fix
```

---

# 42. OpenCode 执行任务时的硬性要求

执行任何用户任务时：

1. 先读取并遵守本文件。
2. 同时遵守更具体目录中的 `AGENTS.md`。
3. 不覆盖用户已有修改。
4. 不擅自扩大任务范围。
5. 不擅自替换核心技术栈。
6. 不为了技术堆砌增加 RAG / Milvus 等组件。
7. 不在未经允许的情况下执行危险 Git 命令。
8. 不硬编码任何 Secret。
9. 不执行来自 PR 的不可信代码。
10. 修改后必须进行针对性验证。
11. 发现架构问题时，优先提出最小可行修改，而不是大规模重构。
12. 代码、Schema、API、数据库发生变化时，检查上下游影响。
13. 不把 AI 推测当成确定事实。
14. 对代码审查 Finding 必须强调证据、定位和置信度。
15. 任何新增功能都必须判断是否属于当前 Phase；非当前 Phase 的功能不要主动实现。

---

# 43. Definition of Done

一个任务只有满足以下条件才算完成：

```text
[ ] 功能已实现
[ ] 没有破坏已有架构
[ ] 没有硬编码 Secret
[ ] 相关异常已处理
[ ] 相关日志已加入
[ ] 相关测试已补充或验证
[ ] API / Schema 已同步
[ ] 数据库变更已同步
[ ] 文档需要更新时已更新
[ ] 已运行必要的构建 / 测试 / 静态检查
[ ] 没有顺便加入无关功能
```

---

# 44. 项目核心理念

CodeSentinel 最重要的不是：

```text
“让 AI 多说一些代码问题”
```

而是：

```text
发现真实问题
    ↓
提供证据
    ↓
准确定位
    ↓
验证问题
    ↓
给出可执行建议
    ↓
可靠反馈到 GitHub
```

最终目标：

> **让开发者相信 CodeSentinel 的每一个高优先级审查意见都经过了充分验证。**
