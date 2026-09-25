# CodeSentinel 项目方案与技术路线

> 中文名称：**代码哨兵——AI 智能代码审查系统**  
> 英文名称：**CodeSentinel**  
> Repository：`code-sentinel`

---

## 1. 项目概述

CodeSentinel 是一个面向 GitHub Pull Request 的 AI 智能代码审查系统。

开发者提交 Pull Request 后，系统通过 GitHub App + Webhook 自动获取代码变更，结合静态分析工具与 LangChain/LangGraph 多 Agent，对代码进行多维度审查，并将审查结果自动反馈到 GitHub Pull Request。

### 核心检测方向

1. Bug / 逻辑错误
2. 安全漏洞
3. 性能问题
4. 代码规范与可维护性

### 当前产品形态

第一阶段以 **GitHub PR 自动审查** 为核心，不优先开发独立 Web 产品。

目标流程：

```text
GitHub Pull Request
        ↓
Webhook
        ↓
Spring Boot 3
        ↓
创建 Review Task
        ↓
Redis 异步任务
        ↓
Python AI Service
        ↓
静态分析 + LangGraph 多 Agent
        ↓
Bug / Security / Performance / Quality
        ↓
Validator Agent
        ↓
生成 Review Report
        ↓
Spring Boot
        ↓
MySQL 保存
        ↓
GitHub PR 总结 + 行级评论
```

---

# 2. 项目目标

## 2.1 MVP 目标

第一版本必须完成以下闭环：

```text
创建 GitHub PR
        ↓
自动触发代码审查
        ↓
获取 PR Diff 与代码上下文
        ↓
运行静态分析
        ↓
AI 多 Agent 分析
        ↓
验证 Finding
        ↓
生成结构化审查报告
        ↓
写入 MySQL
        ↓
自动评论 GitHub PR
```

## 2.2 第一阶段明确不做

为了控制项目复杂度，MVP 暂时不实现：

- VS Code 插件
- GitHub Action 独立产品形态
- 用户代码实际执行
- Docker Sandbox
- Milvus / RAG
- 大规模多人多租户
- 自动生成并提交修复 Patch
- 完整商业化后台

这些能力作为后续扩展。

---

# 3. 已确定的技术决策

| 方向 | 最终方案 |
|---|---|
| 产品入口 | GitHub Pull Request 自动审查 |
| GitHub 集成 | GitHub App + Webhook + GitHub API |
| 后端 | Spring Boot 3 |
| 后端语言 | Java 21 |
| AI 服务 | Python |
| Agent 框架 | LangChain + LangGraph |
| LLM | DeepSeek API |
| 支持语言 | Java + Python |
| Bug 检测 | 支持 |
| 安全检测 | 支持 |
| 性能检测 | 支持 |
| 代码规范 | 支持 |
| 静态分析 | Java / Python 多工具 |
| 异步任务 | Redis |
| 数据库 | MySQL |
| RAG | MVP 暂不使用 |
| 向量数据库 | MVP 暂不使用，后续视需要引入 Milvus |
| GitHub 输出 | PR 总结 + 具体代码行评论 |
| Dashboard | 第二阶段 |
| GitHub App 使用范围 | 第一阶段自己测试 |
| PR 代码执行 | MVP 不执行 |

---

# 4. 总体技术架构

```text
                              ┌──────────────────────┐
                              │       GitHub         │
                              │                      │
                              │ Repository           │
                              │ Pull Request         │
                              └──────────┬───────────┘
                                         │
                                   Webhook Event
                                         │
                                         ▼
              ┌────────────────────────────────────────────┐
              │                Spring Boot 3                │
              │                                            │
              │ GitHub Webhook                             │
              │ GitHub App Authentication                  │
              │ PR / Commit / Diff API                     │
              │ Review Task Management                     │
              │ Review Result                              │
              │ GitHub Comment                             │
              │ REST API                                   │
              └──────────────┬─────────────────┬───────────┘
                             │                 │
                             ▼                 ▼
                          Redis             MySQL
                             │
                       Review Task
                             │
                             ▼
              ┌────────────────────────────────────────────┐
              │              Python AI Service             │
              │                                            │
              │ FastAPI                                    │
              │                                            │
              │              LangGraph                     │
              │                 │                          │
              │       ┌─────────┴─────────┐                │
              │       ▼         ▼         ▼                │
              │     Bug     Security  Performance          │
              │     Agent     Agent      Agent             │
              │       └─────────┬─────────┘                │
              │                 ▼                          │
              │          Quality Agent                     │
              │                 │                          │
              │                 ▼                          │
              │          Validator Agent                   │
              │                 │                          │
              │                 ▼                          │
              │         Report Generator                   │
              │                                            │
              │ Static Analysis                            │
              │ Rule Engine                                │
              │ Code Context Builder                       │
              └────────────────────────────────────────────┘
```

---

# 5. 服务职责划分

## 5.1 Spring Boot 3

定位：

> **业务后端 + GitHub 集成层**

负责：

- GitHub Webhook 接收
- Webhook 签名验证
- GitHub App 认证
- 获取 PR 信息
- 获取 Commit / Diff / 文件
- 创建 ReviewTask
- Redis 任务投递
- Review 结果接收
- MySQL 数据持久化
- GitHub PR 评论
- Review 查询接口
- 后续 Dashboard API

Spring Boot 不负责复杂的 LLM Agent 推理。

---

## 5.2 Python AI Service

定位：

> **AI 分析层**

负责：

- LangChain
- LangGraph
- DeepSeek API
- Agent
- Prompt
- 代码上下文处理
- 静态分析工具调用
- 规则匹配
- Finding 生成
- Finding 验证
- 报告生成

Python 不负责：

- GitHub 业务权限
- 核心业务数据库管理
- GitHub PR 最终评论逻辑

---

# 6. GitHub 自动审查流程

## 6.1 Pull Request 创建

开发者：

```text
git push
    ↓
创建 Pull Request
```

GitHub 发送：

```text
pull_request
```

重点监听：

```text
opened
synchronize
reopened
```

---

## 6.2 Spring Boot 接收 Webhook

```text
POST /api/github/webhook
```

处理：

```text
接收请求
   ↓
验证 X-Hub-Signature-256
   ↓
解析 Webhook Payload
   ↓
判断是否为 Pull Request 事件
   ↓
获取 repository / PR / commit 信息
   ↓
创建 ReviewTask
   ↓
发送 Redis
   ↓
快速返回 200
```

Webhook 不应该等待 AI 审查完成。

---

# 7. 异步任务架构

错误方案：

```text
GitHub
 ↓
Webhook
 ↓
Spring Boot
 ↓
调用 AI
 ↓
等待
 ↓
返回
```

正确方案：

```text
GitHub
 ↓
Webhook
 ↓
Spring Boot
 ↓
创建 ReviewTask
 ↓
Redis
 ↓
立即返回
```

随后：

```text
Redis
 ↓
Python Worker
 ↓
执行 Review
 ↓
返回 Review Result
 ↓
Spring Boot
```

---

# 8. AI Review 工作流

LangGraph 工作流：

```text
START
  ↓
Load PR Context
  ↓
Detect Language
  ↓
Build Code Context
  ↓
Run Static Analysis
  ↓
Planner
  ↓
┌────────────────┬────────────────┬────────────────┬────────────────┐
│                │                │                │
▼                ▼                ▼                ▼
Bug Agent    Security Agent  Performance Agent  Quality Agent
│                │                │                │
└────────────────┴────────────────┴────────────────┘
                         ↓
                  Merge Findings
                         ↓
                    Deduplicate
                         ↓
                  Validator Agent
                         ↓
               Severity / Confidence
                         ↓
                  Report Generator
                         ↓
                        END
```

---

# 9. Agent 设计

## 9.1 Planner Agent

职责：

- 判断代码语言
- 分析 PR 修改范围
- 判断需要进行哪些维度审查
- 控制后续 Agent 调用
- 减少无意义的模型调用

示例：

```json
{
  "languages": ["java"],
  "areas": [
    "security",
    "bug",
    "performance",
    "quality"
  ]
}
```

---

## 9.2 Bug Agent

负责发现：

- NullPointer
- 边界条件错误
- 逻辑错误
- 异常处理问题
- 状态错误
- 资源泄漏
- 并发问题
- 错误返回值
- 潜在运行时问题

核心目标：

> 判断问题是否真实存在，而不是仅仅指出“可能有问题”。

---

## 9.3 Security Agent

负责：

- SQL Injection
- Command Injection
- XSS
- SSRF
- Path Traversal
- Broken Access Control
- Authentication 问题
- 敏感信息泄露
- 不安全加密
- 安全配置问题

安全知识来源可以包括：

- OWASP
- CWE
- Java 安全实践
- Python 安全实践

---

## 9.4 Performance Agent

### Java

重点检测：

- N+1 Query
- 循环数据库查询
- 循环 HTTP 请求
- 不合理集合操作
- 不必要对象创建
- 重复计算
- 锁竞争
- 阻塞 IO
- 缓存使用问题

### Python

重点检测：

- 低效循环
- 重复 IO
- 重复网络请求
- 不合理数据结构
- 同步阻塞
- 重复计算

---

## 9.5 Quality Agent

负责：

- 命名
- 重复代码
- 方法过长
- 类职责过多
- 异常处理
- 日志规范
- 可读性
- 可维护性
- 代码组织
- 设计问题

---

## 9.6 Validator Agent

这是项目的重要核心模块。

前面 Agent 发现：

```text
Potential SQL Injection
```

不能直接评论 GitHub。

Validator 需要重新验证：

```text
Finding
   ↓
读取相关代码
   ↓
结合 Diff
   ↓
结合静态分析结果
   ↓
结合规则
   ↓
判断真实性
```

输出：

```json
{
  "valid": true,
  "severity": "HIGH",
  "confidence": 0.94
}
```

如果：

```json
{
  "valid": false
}
```

则丢弃该 Finding。

---

# 10. 静态分析层

## 10.1 Java

第一阶段：

- PMD
- Checkstyle
- Semgrep

后续可以加入：

- SpotBugs

## 10.2 Python

第一阶段：

- Ruff
- Bandit
- Semgrep

作用：

```text
源码
 ↓
静态规则
 ↓
确定性问题
 ↓
提供证据
 ↓
交给 Agent
```

最终采用：

```text
Static Analysis
        +
LLM Semantic Analysis
        ↓
Validator
        ↓
Final Finding
```

不能把所有判断都交给 LLM。

---

# 11. Code Context Builder

仅提供 Git Diff 给 LLM 通常不够。

例如：

```diff
- userService.getUser(id)
+ userService.getUser(userId)
```

模型还需要知道：

- `getUser()` 做什么
- `userId` 从哪里来
- 是否经过权限验证
- 相关 Service / Repository 如何实现

因此需要构建：

```text
PR Diff
 ↓
修改文件
 ↓
修改方法
 ↓
所属 Class
 ↓
Imports
 ↓
相关方法
 ↓
相关类
 ↓
构建上下文
```

第一阶段优先使用代码结构分析，不强行引入向量数据库。

可考虑：

- Tree-sitter
- JavaParser
- ripgrep
- AST
- 简单依赖关系分析

---

# 12. Finding 统一数据结构

所有 Agent 必须输出统一结构。

建议：

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

统一结构能够方便：

```text
Validator
MySQL
GitHub Comment
Dashboard
```

---

# 13. 严重程度与置信度

建议每个 Finding 都有：

```text
severity
confidence
```

严重程度：

```text
CRITICAL
HIGH
MEDIUM
LOW
INFO
```

置信度：

```text
0.00 ~ 1.00
```

可设置初步策略：

```text
高严重度 + 高置信度
    → 直接行级评论

中严重度 + 高置信度
    → 行级评论

低严重度 / 低置信度
    → 汇总报告
```

具体阈值在测试阶段根据结果调整。

---

# 14. GitHub 输出设计

## 14.1 PR 总结

例如：

```text
🤖 CodeSentinel AI Code Review

本次审查共发现 6 个问题：

HIGH:   1
MEDIUM: 2
LOW:    3

审查维度：

✓ Bug
✓ Security
✓ Performance
✓ Code Quality

请查看具体代码行评论。
```

## 14.2 行级评论

例如：

```text
UserRepository.java:52

🔴 HIGH Security Issue

发现潜在 SQL Injection。

原因：
外部输入直接参与 SQL 拼接。

建议：
使用参数化查询。

Rule:
CWE-89
```

MVP 只自动生成：

```text
COMMENT
```

暂不自动执行：

```text
REQUEST_CHANGES
APPROVE
```

避免 AI 误判直接影响 PR 流程。

---

# 15. GitHub App

第一阶段只安装到自己的测试 Repository。

权限设计遵循最小权限原则。

核心能力：

```text
读取：
Repository
Pull Request
Commit
Diff
Files

写入：
Pull Request Comments / Reviews
```

GitHub App Installation Token 不长期保存到数据库，应按需获取并缓存。

---

# 16. MySQL 数据库设计

第一版核心表：

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
        │
        │ 1:N
        ▼
   repository
        │
        │ 1:N
        ▼
  pull_request
        │
        │ 1:N
        ▼
   review_task
        │
        │ 1:1
        ▼
   review_report
        │
        │ 1:N
        ▼
 review_finding
        │
        │ 0:N
        ▼
 review_comment
```

---

# 17. 核心表建议

## review_task

```text
id
repository_id
pr_number
commit_sha
status
started_at
completed_at
error_message
created_at
updated_at
```

状态：

```text
PENDING
RUNNING
COMPLETED
FAILED
```

---

## review_report

```text
id
task_id
total_findings
critical_count
high_count
medium_count
low_count
summary
created_at
```

---

## review_finding

```text
id
report_id
category
severity
rule_id
title
description
file_path
start_line
end_line
code_snippet
reason
suggestion
confidence
status
created_at
```

---

## review_comment

```text
id
finding_id
github_comment_id
file_path
line
side
commit_sha
comment_body
status
created_at
```

---

# 18. Redis 设计

Redis 不作为永久历史数据库。

主要负责：

- 异步任务
- 任务状态
- 短期缓存
- 幂等控制

示例：

```text
review:task:{taskId}
```

任务状态：

```text
PENDING
RUNNING
COMPLETED
FAILED
```

---

# 19. 为什么 MVP 暂时不做 RAG

代码审查的核心问题不是：

> “我不知道知识在哪。”

而是：

> “这段代码是否真的存在问题？”

因此第一阶段使用：

```text
Static Analyzer
+
Rule Engine
+
LLM Agent
+
Validator
```

已经可以完成核心代码审查。

RAG 后续更适合用于：

### 企业内部规范

```text
Java 开发规范
数据库开发规范
API 设计规范
安全规范
日志规范
```

### 项目自定义规范

```text
Controller 必须鉴权
禁止某种 API
Service 必须使用某种方式
```

### 官方文档 / 框架规范

例如：

```text
Spring
MyBatis
JDK
Python
```

以后再：

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

因此：

> **RAG 是增强模块，不是 CodeSentinel MVP 的核心模块。**

---

# 20. 项目目录

建议采用 Monorepo：

```text
code-sentinel/
│
├── backend/
│   └── spring-service/
│       ├── src/main/java/...
│       │
│       ├── github/
│       ├── webhook/
│       ├── review/
│       ├── task/
│       ├── report/
│       ├── repository/
│       ├── comment/
│       └── common/
│
├── agent/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── planner.py
│   │   │   ├── bug_agent.py
│   │   │   ├── security_agent.py
│   │   │   ├── performance_agent.py
│   │   │   ├── quality_agent.py
│   │   │   ├── validator.py
│   │   │   └── reporter.py
│   │   │
│   │   ├── graph/
│   │   │   ├── state.py
│   │   │   ├── nodes.py
│   │   │   └── workflow.py
│   │   │
│   │   ├── analyzers/
│   │   ├── tools/
│   │   ├── rules/
│   │   ├── prompts/
│   │   ├── schemas/
│   │   └── config/
│   │
│   └── tests/
│
├── frontend/
│
├── action/
│
├── knowledge/
│   ├── owasp/
│   ├── cwe/
│   ├── java/
│   └── python/
│
├── infra/
│   ├── docker/
│   └── docker-compose.yml
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── API.md
│   ├── AGENT_DESIGN.md
│   └── DATABASE.md
│
├── AGENTS.md
└── README.md
```

---

# 21. 开发技术路线

## Phase 1：基础工程

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

完成：

- Monorepo
- 项目骨架
- 环境配置
- 日志
- 基础 API
- Docker 开发环境

---

## Phase 2：GitHub App

目标：

```text
GitHub App
 ↓
Webhook
 ↓
Spring Boot
```

完成：

- GitHub App 创建
- App 私钥
- Webhook Secret
- Webhook Signature 验证
- PR Event 解析
- Installation 信息保存

验收：

```text
创建 Pull Request
        ↓
Spring Boot 正确收到事件
```

---

## Phase 3：GitHub API

完成：

- PR 信息获取
- Commit 获取
- Diff 获取
- Changed Files 获取
- 文件内容获取

最终得到：

```text
Repository
PR
Commit
Diff
Changed Files
```

---

## Phase 4：Review Task

实现：

```text
Webhook
 ↓
ReviewTask
 ↓
Redis
```

完成：

- Task 创建
- 状态管理
- Redis 投递
- Python Worker 消费
- 失败重试基础机制

---

## Phase 5：Python AI Service

先不做复杂多 Agent。

先跑通：

```text
Spring Boot
 ↓
Python
 ↓
DeepSeek
 ↓
结构化 Finding
 ↓
Spring Boot
```

目标：

> 先证明完整链路是通的。

---

## Phase 6：Code Context

完成：

- Diff 解析
- 文件定位
- 方法定位
- Class 上下文
- 关联代码
- 基础代码上下文构建

---

## Phase 7：Static Analysis

Java：

```text
PMD
Checkstyle
Semgrep
```

Python：

```text
Ruff
Bandit
Semgrep
```

统一转换为：

```text
StaticAnalysisResult
```

---

## Phase 8：LangGraph Multi-Agent

逐步加入：

```text
Planner
 ↓
Bug Agent
 ↓
Security Agent
 ↓
Performance Agent
 ↓
Quality Agent
 ↓
Validator
 ↓
Reporter
```

先串行跑通，再根据成本和性能考虑并行。

---

## Phase 9：GitHub Comment

实现：

```text
Finding
 ↓
file_path
 ↓
line
 ↓
commit_sha
 ↓
GitHub Review Comment
```

同时生成：

```text
PR Summary
```

完成真正的：

```text
GitHub
    ↕
CodeSentinel
```

闭环。

---

## Phase 10：数据库与历史审查

完整保存：

- PR
- Task
- Report
- Finding
- Comment

确保可以查询：

```text
某仓库历史审查
某 PR 审查
某次 Finding
某类问题数量
```

---

# 22. 测试体系

不能只测试“系统能不能运行”。

需要建立自己的代码审查测试集：

```text
test-cases/
├── java/
│   ├── bug/
│   ├── security/
│   ├── performance/
│   └── quality/
│
└── python/
    ├── bug/
    ├── security/
    ├── performance/
    └── quality/
```

每个测试案例包含：

```text
源代码
预期问题
问题类别
严重程度
正确行号
```

重点指标：

```text
Precision
Recall
False Positive Rate
Line Localization Accuracy
```

特别关注：

> **误报率**

因为代码审查系统如果大量产生错误评论，实际使用价值会明显下降。

---

# 23. 第二阶段扩展

MVP 稳定之后：

## Dashboard

```text
Web Dashboard
      ↓
Review History
      ↓
Finding Statistics
      ↓
Code Quality Trend
```

可以展示：

```text
Bug 趋势
Security 趋势
Performance 趋势
Quality 趋势
```

---

## 自定义规则

支持：

```text
Project Rule
Team Rule
Custom Rule
```

例如：

```text
Controller 必须鉴权
禁止直接访问某 API
Repository 必须使用统一方式
```

---

# 24. 第三阶段扩展

## RAG / Milvus

使用场景：

```text
企业规范
项目规范
安全规范
框架文档
历史 Review
```

架构：

```text
Rule / Documents
       ↓
Embedding
       ↓
Milvus
       ↓
Retriever
       ↓
Agent
```

---

## GitHub Action

最终支持：

```yaml
- uses: code-sentinel/action@v1
```

---

## VS Code 插件

支持：

```text
选中代码
   ↓
Review
   ↓
CodeSentinel API
   ↓
Finding
   ↓
编辑器提示
```

---

## 自动修复

后期可增加：

```text
Finding
 ↓
Fix Agent
 ↓
生成 Patch
 ↓
Sandbox 测试
 ↓
用户确认
 ↓
创建 Commit
```

该能力必须建立在安全隔离机制上。

---

# 25. 安全设计原则

MVP 不执行 Pull Request 中的用户代码。

当前只：

```text
读取源码
读取 Diff
运行静态分析
调用 LLM
```

后续如果需要执行测试，需要引入：

```text
Docker Sandbox
资源限制
CPU 限制
内存限制
超时
文件系统隔离
网络限制
最小权限
```

绝不能直接在主机执行来自不可信 PR 的代码。

---

# 26. MVP 最终闭环

当以下流程全部成功时，说明 MVP 完成：

```text
1. 开发者提交 PR

2. GitHub 发送 Webhook

3. Spring Boot 验证并接收

4. 创建 ReviewTask

5. Redis 投递任务

6. Python Worker 获取任务

7. 获取 Diff / Code Context

8. 运行 Java / Python 静态分析

9. Planner 决定审查方向

10. Bug / Security / Performance / Quality Agent 分析

11. Validator 二次验证

12. Reporter 生成结构化报告

13. Spring Boot 保存 MySQL

14. GitHub 自动发布 PR Summary

15. GitHub 自动发布 Inline Comments
```

---

# 27. 项目核心亮点

CodeSentinel 最终重点突出以下能力：

### 1. Multi-Agent Code Review

```text
Planning
→ Analysis
→ Validation
→ Reporting
```

### 2. Static Analysis + LLM

```text
确定性规则
+
语义理解
```

### 3. GitHub 原生自动化

```text
PR
→ Webhook
→ Review
→ Inline Comment
```

### 4. Evidence-Based Finding

每一个 Finding 都包含：

```text
文件
行号
规则
原因
证据
严重程度
置信度
修改建议
```

### 5. 历史代码质量分析

```text
PR
 ↓
Review History
 ↓
Quality Trend
```

---

# 28. 最终项目架构一句话总结

> **CodeSentinel 是一个基于 Spring Boot 3 + Python + LangChain/LangGraph + GitHub API 的 AI 代码审查系统，通过静态分析与多 Agent 协同，对 GitHub Pull Request 中的 Java/Python 代码进行 Bug、安全、性能和代码质量审查，并将经过 Validator 验证后的问题自动反馈到 GitHub PR，同时保存历史审查数据用于代码质量趋势分析。**

---

# 29. 当前项目开发原则

1. **先跑通闭环，再增加复杂能力。**
2. **不要为了堆技术而强行加入 RAG / Milvus。**
3. **LLM 不负责所有判断，静态分析和规则引擎共同提供证据。**
4. **所有 Agent 使用统一 Finding Schema。**
5. **所有 AI Finding 在写入 GitHub 前经过 Validator。**
6. **Webhook 与 AI Review 必须异步解耦。**
7. **MVP 不执行不可信 PR 代码。**
8. **先保证 Java + Python 两种语言，后续再扩展。**
9. **先支持自己测试的 GitHub App，后续再考虑开放给其他用户。**
10. **优先保证审查准确性和低误报，而不是盲目增加 Agent 数量。**

---

# 30. 当前开发顺序总览

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
    ↓
第二阶段 Dashboard / Custom Rules
    ↓
第三阶段 RAG / Milvus / GitHub Action / VS Code / Auto Fix
```
