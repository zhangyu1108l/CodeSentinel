# CodeSentinel Development Workflow

## 1. 开发方式

CodeSentinel 采用“ChatGPT + OpenCode + 用户”的协作开发模式。

职责划分：

- ChatGPT：架构设计、任务拆分、技术方案分析、OpenCode Prompt 编写、代码审查、问题分析、阶段验收。
- OpenCode：主要负责代码实现、测试、编译、Git 操作和实现结果汇报。
- 用户：负责确定项目方向、执行 OpenCode Prompt、观察实际运行结果、反馈问题并进行最终验收。

用户不是主要代码编写者，项目代码主要通过 OpenCode / Vibe Coding 完成。

---

## 2. 固定开发流程

每个 Phase 原则上遵循：

1. 用户提出 Phase 目标。
2. ChatGPT 阅读并结合：
   - `AGENTS.md`
   - `docs/PROJECT_DESIGN.md`
   - `docs/DEVELOPMENT_STATUS.md`
   - `docs/DEVELOPMENT_WORKFLOW.md`
   - 当前实际代码和 Git 状态
3. ChatGPT 分析当前项目真实状态。
4. ChatGPT 将当前 Phase 拆分成合理的小任务。
5. ChatGPT 给出可直接复制给 OpenCode 的 Prompt。
6. 用户将 Prompt 发送给 OpenCode。
7. OpenCode 阅读项目并实现任务。
8. OpenCode 运行相关测试和必要的验证。
9. OpenCode 汇报：
   - 修改/新增文件
   - 实现内容
   - 测试结果
   - Git 状态
   - 遇到的问题
10. 用户将 OpenCode 的结果反馈给 ChatGPT。
11. ChatGPT 进行技术和范围验收。
12. 验收通过后，再进入下一小任务。
13. 完成阶段后更新 `docs/DEVELOPMENT_STATUS.md`。

---

## 3. ChatGPT 的职责

ChatGPT 主要负责：

- 项目整体架构设计
- Phase 任务拆分
- 技术方案分析
- 开发顺序控制
- OpenCode Prompt 编写
- OpenCode 实现结果审查
- Bug 和架构问题分析
- 测试结果分析
- 阶段验收
- 防止提前实现后续 Phase

除非用户明确要求，否则 ChatGPT 不直接替用户完成项目代码实现。

当需要实际修改项目代码时，优先提供“可直接复制给 OpenCode 的 Prompt”。

---

## 4. OpenCode 的职责

OpenCode 是 CodeSentinel 的主要代码实现工具。

OpenCode 主要负责：

- 阅读项目代码
- 创建和修改文件
- 删除或重构代码
- 编写测试
- 运行测试
- 编译项目
- 运行必要的本地验证
- Git 分支、提交等操作
- 汇报实现结果

在开始实现任务前，OpenCode 必须根据任务范围阅读：

- `AGENTS.md`
- `docs/PROJECT_DESIGN.md`
- `docs/DEVELOPMENT_STATUS.md`

如果项目中存在本开发流程文档，也应阅读：

- `docs/DEVELOPMENT_WORKFLOW.md`

如果任务涉及特定 Phase 的设计文档，应同时阅读对应文档。

---

## 5. 新 Phase 开始规则

当用户说：

> 开始 Phase X

ChatGPT 不应该直接让 OpenCode 一次性实现整个 Phase。

首先：

1. 确认当前 Phase。
2. 阅读项目文档。
3. 检查当前代码状态。
4. 检查 Git 分支和工作区状态。
5. 确认上一 Phase 是否真正完成。
6. 明确当前 Phase 的目标和边界。
7. 将当前 Phase 拆成多个小步骤。
8. 给用户第一个 OpenCode Prompt。

新 Phase 的第一个 OpenCode Prompt 默认要求：

- 阅读项目文档。
- 检查当前代码。
- 检查 Git 状态。
- 汇报当前状态。
- 提出当前 Phase 的实现计划。
- 暂时不要修改代码。

待 ChatGPT 根据 OpenCode 的报告确认后，再开始实现。

---

## 6. OpenCode Prompt 原则

所有交给 OpenCode 的 Prompt 应尽量：

- 可以直接复制执行。
- 明确任务目标。
- 明确实现范围。
- 明确禁止实现的后续功能。
- 明确测试要求。
- 明确需要阅读的文档。
- 明确完成后的汇报内容。
- 避免一次实现过大的功能集合。

对于较大的 Phase，应拆成多个小步骤，而不是一次完成整个 Phase。

---

## 7. 每个小任务的标准流程

### Step 1：分析

让 OpenCode：

> 先阅读项目，不修改代码。

确认：

- 当前实现状态
- 当前架构
- 当前分支
- 已有相关代码
- 潜在架构问题
- 推荐实现方案

### Step 2：确认

ChatGPT 根据 OpenCode 报告：

- 判断方案是否合理
- 检查是否超出当前 Phase
- 确定下一步具体实现内容

### Step 3：实现

ChatGPT 给出可以直接复制给 OpenCode 的实现 Prompt。

### Step 4：测试

OpenCode：

- 实现代码
- 编写/更新测试
- 运行相关测试
- 必要时运行完整测试
- 汇报结果

### Step 5：验收

ChatGPT 检查：

- 功能是否正确
- 架构是否符合设计
- 测试是否通过
- 安全性
- Git 状态
- 是否存在敏感信息
- 是否提前实现后续功能
- 是否符合 `AGENTS.md`

### Step 6：记录

小任务或 Phase 验收通过后，更新：

`docs/DEVELOPMENT_STATUS.md`

---

## 8. 严格防止 Phase 越界

当前 Phase 只能实现当前阶段需要的内容。

如果 OpenCode 发现后续功能可能有必要：

不要直接实现。

应该：

1. 停止扩大实现范围。
2. 告诉用户发现了什么。
3. 说明为什么可能需要该功能。
4. 给出影响分析。
5. 等待确认。

禁止为了“顺便做好”而提前实现后续 Phase 的核心功能。

---

## 9. 测试与验收原则

每个实现步骤都应尽量具备对应验证。

优先级：

1. 单元测试
2. 集成测试
3. 本地实际运行验证
4. 外部服务联调（如果当前 Phase 需要）

测试失败时：

- 不要直接忽略。
- 分析失败原因。
- 优先修复当前 Phase 范围内的问题。
- 如果问题属于后续 Phase，应记录并说明，而不是提前扩大实现范围。

最终 Phase 验收不能只看代码是否存在，应结合：

- 测试结果
- 实际运行结果
- Git 状态
- 安全检查
- 文档状态
- 与项目设计的一致性

---

## 10. Git 与分支原则

每个 Phase 应尽量使用清晰的开发分支。

推荐：

```text
main
  ↓
phase-x/xxx
```

完成并验收后，再合并回 `main`。

开始新 Phase 前：

1. 确认上一 Phase 已验收。
2. 确认 `main` 包含上一 Phase 的最终代码。
3. 从最新 `main` 创建新的 Phase 开发分支。
4. 再开始下一阶段。

不要在没有确认上一阶段状态的情况下直接继续开发。

---

## 11. 安全原则

OpenCode 不得在汇报中输出：

- API Key
- GitHub Token
- Webhook Secret
- GitHub App Private Key
- 数据库密码
- Redis 密码
- 其他敏感凭证

测试时使用测试凭证或环境变量。

敏感配置应通过：

- `.env`
- 环境变量
- 本地 `secrets/`
- 其他项目规定的安全配置方式

管理。

不得将：

- `.env`
- Private Key
- Token
- Secret
- credentials

提交到 Git。

---

## 12. 文档职责

CodeSentinel 项目文档职责保持清晰：

### `AGENTS.md`

负责：

- 项目开发规则
- 安全要求
- 编码约束
- 禁止事项
- Agent/OpenCode 行为约束

### `docs/PROJECT_DESIGN.md`

负责：

- 项目目标
- 系统架构
- 技术栈
- 模块职责
- 核心数据流
- Phase 设计原则

### `docs/DEVELOPMENT_STATUS.md`

负责：

- 当前开发进度
- 已完成内容
- 当前 Phase
- 测试结果
- 重要开发记录
- 已知问题

### `docs/DEVELOPMENT_WORKFLOW.md`

负责：

- ChatGPT、OpenCode、用户之间的协作方式
- Phase 开始流程
- 小任务开发流程
- Prompt 规范
- 测试和验收流程
- Git 分支流程
- Phase 边界控制

不要把同一类信息重复写入多个文档。

---

## 13. 当前项目状态

截至当前：

- Phase 1：已完成
- Phase 2：已完成
- Phase 3：未开始

Phase 2 已完成：

- GitHub App
- Webhook 接收
- `X-Hub-Signature-256` HMAC-SHA256 验证
- `pull_request` 事件解析
- `opened`
- `synchronize`
- `reopened`
- Smee 本地开发联调
- 真实 GitHub Webhook 联调成功
- HTTP 200 验证通过

---

## 14. Phase 3 开发原则

Phase 3 目标：

> 实现 GitHub API 集成，让 CodeSentinel 能够获取 Pull Request 的元数据、Commit、Changed Files、Diff 和必要的文件内容。

Phase 3 应拆分实施，不一次性完成。

推荐顺序：

```text
Phase 3.1
GitHub App JWT + Installation Token
        ↓
Phase 3.2
GitHub API Client
        ↓
Phase 3.3
Pull Request API
        ↓
Phase 3.4
Changed Files API
        ↓
Phase 3.5
Commit / Diff 获取
        ↓
Phase 3.6
文件内容与统一 PR Context
```

当前优先从：

> Phase 3.1：GitHub App JWT + Installation Token

开始。

除非用户明确要求，不应在 Phase 3.1 中提前实现完整 PR Review、Review Task、Redis 队列、AI Agent、静态分析或其他后续 Phase 功能。

---

## 15. 用户的开发习惯

用户希望：

- 一步一步完成项目。
- 边做边理解。
- 不希望一次看到大量代码。
- 主要使用 OpenCode 实现代码。
- ChatGPT 负责分析、拆解、指导和验收。
- 每完成一个小任务后再进入下一步。
- 出现问题时先定位原因，再进行最小范围修复。
- 不希望为了未来功能过早增加复杂度。

因此，默认采用：

```text
分析
↓
Prompt
↓
OpenCode 实现
↓
测试
↓
用户反馈
↓
ChatGPT 验收
↓
下一步
```

而不是一次性生成整个项目或整个 Phase。
