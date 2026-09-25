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

**Phase 0：项目初始化 / 开始开发**

## 当前任务

**尚未开始具体编码**

## 当前总体进度

```text
Phase 1  基础工程                 ⬜ 未开始
Phase 2  GitHub App + Webhook     ⬜ 未开始
Phase 3  GitHub API               ⬜ 未开始
Phase 4  Review Task + Redis      ⬜ 未开始
Phase 5  Python AI Service        ⬜ 未开始
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

**⬜ 未开始**

## 已完成

- [ ] 创建 Monorepo
- [ ] 创建 Spring Boot 项目
- [ ] 创建 Python 项目
- [ ] 创建 Docker Compose
- [ ] 配置 MySQL
- [ ] 配置 Redis
- [ ] 基础测试通过

## 当前任务

暂无。

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

- [ ] 创建 GitHub App
- [ ] 配置 App ID
- [ ] 配置 Private Key
- [ ] 配置 Webhook Secret
- [ ] 配置 Repository 权限
- [ ] Webhook Controller
- [ ] `X-Hub-Signature-256` 验证
- [ ] `pull_request` Event 解析
- [ ] 支持 `opened`
- [ ] 支持 `synchronize`
- [ ] 支持 `reopened`
- [ ] Webhook 幂等基础设计

## Phase 2 状态

**⬜ 未开始**

## 当前任务

暂无。

## 阻塞问题

暂无。

---

# 6. Phase 3：GitHub API

## 目标

让 Spring Boot 能够获取 PR 审查所需的全部代码信息。

## 子任务

- [ ] Installation Token 获取
- [ ] Token 缓存 / 刷新
- [ ] Repository API
- [ ] Pull Request API
- [ ] Commit API
- [ ] Changed Files API
- [ ] Diff 获取
- [ ] 文件内容获取
- [ ] GitHub API 错误处理
- [ ] Rate Limit 处理基础机制

## 关键输出

系统至少能够获得：

```text
Repository
PR
Commit
Diff
Changed Files
File Content
```

## Phase 3 状态

**⬜ 未开始**

## 当前任务

暂无。

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

- [ ] ReviewTask Entity
- [ ] ReviewTask Repository
- [ ] ReviewTask Service
- [ ] Task Status
- [ ] Redis Task Producer
- [ ] Python Worker
- [ ] Task 消费
- [ ] 基础失败处理
- [ ] retry_count
- [ ] 幂等控制

## 任务状态

```text
PENDING
RUNNING
COMPLETED
FAILED
```

## Phase 4 状态

**⬜ 未开始**

## 当前任务

暂无。

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

- [ ] LLM Service
- [ ] DeepSeek 配置
- [ ] Timeout
- [ ] Retry
- [ ] Pydantic Schema
- [ ] Structured Output
- [ ] 基础 Review Prompt
- [ ] Java Review
- [ ] Python Review
- [ ] Service-to-Service API

## Phase 5 状态

**⬜ 未开始**

## 当前任务

暂无。

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
Phase 1：基础工程
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
Phase 1：基础工程
```

目标：

```text
Spring Boot 3
+
Python FastAPI
+
MySQL
+
Redis
+
Docker Compose
```

不要提前实现：

```text
GitHub App
Agent
Static Analysis
RAG
Milvus
Dashboard
VS Code
Auto Fix
```
