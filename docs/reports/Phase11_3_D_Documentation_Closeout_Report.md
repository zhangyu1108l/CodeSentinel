# Phase 11.3-D 文档收尾报告 — Dashboard 文档、README 与 UI 文案同步

> 阶段：Phase 11.3-D（Documentation Closeout）  
> 分支：`phase11/dashboard`  
> HEAD：`27e3a41161cfa86ee2956ba0b3626a2bcc71eec7`  
> 报告性质：实施与验证报告  
> **阶段结论：PASS（文档收尾范围）。Phase 11 整体仍为 PASS WITH WARNINGS；六项目标 6/6，P0 / P1 / P2 为 0；尚未提交、未创建 PR、未合并 `main`；Phase 12 尚未开始；P3 技术债继续保留。**  
> **重写说明：本文件原文是 48 行 blockquote 摘要，缺少正式阶段报告结构。Phase 11.4-A 依据原始摘要、当前五个授权文件、Phase 11.3-C 最终审计报告、Phase 11.3-B2-B 实施报告和 Git 只读状态完成重写。本报告不重新实施 Phase 11.3-D，也不把历史验证表述为本次重写时的新执行。**

---

## 1. 基本信息

| 项目 | 内容 |
|---|---|
| 阶段 | Phase 11.3-D |
| 任务 | Documentation Closeout：同步 Dashboard 状态文档、前端 README 与 UI 文案 |
| 日期 | 2026-11-15（上下文记录日期） |
| 分支 | `phase11/dashboard` |
| HEAD | `27e3a41161cfa86ee2956ba0b3626a2bcc71eec7` |
| `main...HEAD` | `0 0` |
| 报告性质 | 实施与验证报告 |
| 阶段结论 | **PASS（文档收尾范围）** |
| Phase 11 结论 | **PASS WITH WARNINGS；六项目标 6/6；P0 / P1 / P2 = 0 / 0 / 0** |
| 提交状态 | 尚未 commit、未创建 PR、未合并 `main` |
| 下一阶段 | Phase 12 尚未开始 |

### 1.1 日期说明

Phase 11.3-D 的原始摘要没有记录精确执行时间，Git 中也没有对应的 Phase 11 提交可供核验。本报告中的 `2026-11-15` 来自 Phase 11.3-C 审计日期和当前工作区上下文，属于**记录日期**，不等同于可独立验证的精确执行时间戳。

### 1.2 报告重写说明

本报告的重写属于 Phase 11.4-A 文档修复，不是 Phase 11.3-D 的重新实施。重写遵守以下边界：

1. 只覆盖 `docs/reports/Phase11_3_D_Documentation_Closeout_Report.md`。
2. 不修改五个被记录的源文件。
3. 不重新运行前端测试、类型检查、Lint 或构建。
4. 不修改 Git 历史，不执行任何 Git 写操作。
5. 第 7 节的验证结果全部标注为 **Phase 11.3-D 历史执行结果**。

---

## 2. 任务目标与范围

### 2.1 为什么需要本阶段

Phase 11.3-C 最终收尾审计确认六项目标已完成，但发现项目状态文档和前端说明仍停留在旧状态：

- `docs/DEVELOPMENT_STATUS.md` §16 仍写 Phase 11 “尚未启动”，六项目标仍未勾选；
- `frontend/README.md` 仍称 ECharts 未安装、Phase 11.1 没有图表，并把 Review Detail、Finding Statistics 和图表描述为范围之外；
- 首页路线图仍把 `Quality insights — 11.3` 当作未来工作；
- 首页仍使用 `Stored reports`，容易被理解为真实统计摘要；
- 顶部徽标、侧栏页脚和移动端导航仍显示 `Phase 11.1` / `Phase 11.2` 等过期阶段标识。

这些问题不改变运行时功能，但会让读者误判 Phase 11 的真实交付状态，因此需要一次独立的文档收尾。

### 2.2 本阶段目标

1. 让 `DEVELOPMENT_STATUS.md` 与 Phase 11.3-C 的验收结论一致。
2. 让 `frontend/README.md` 反映当前技术栈、页面范围、图表实现和安全边界。
3. 清理首页 Dashboard 中已经过期的路线图和阶段文案。
4. 统一布局、侧栏与移动端导航的交付标识。
5. 保留原有测试可通过的文案兼容性，不修改测试源码。
6. 不引入任何业务逻辑、接口、路由、数据结构或依赖变化。

### 2.3 授权范围

本阶段只允许修改以下五个文件，并新增本报告：

| 序号 | 文件 | 类型 |
|---:|---|---|
| 1 | `docs/DEVELOPMENT_STATUS.md` | 修改 |
| 2 | `frontend/README.md` | 修改 |
| 3 | `frontend/src/views/DashboardView.vue` | 修改 |
| 4 | `frontend/src/layouts/DashboardLayout.vue` | 修改 |
| 5 | `frontend/src/components/SidebarNav.vue` | 修改 |
| 6 | `docs/reports/Phase11_3_D_Documentation_Closeout_Report.md` | 新增/重写 |

### 2.4 明确非目标

本阶段明确不做以下事项：

- 不修改 Java 后端代码。
- 不修改数据库、DDL、索引或数据。
- 不修改 `application.yml`、`.env`、`secrets/`。
- 不修改前端路由、API 客户端、状态管理、业务逻辑或页面结构。
- 不修改测试源码、测试断言或测试配置。
- 不升级依赖，不修改 `package.json` / `package-lock.json`。
- 不修复任何 P3 技术债。
- 不提交、不创建 PR、不合并、不启动 Phase 12。

---

## 3. 修改文件清单

### 3.1 总览

| 文件 | 改动性质 | 是否改变业务逻辑 | 当前状态 |
|---|---|---|---|
| `docs/DEVELOPMENT_STATUS.md` | 状态账本、六项目标勾选、P3 登记 | 否 | 已更新并与 11.3-C 结论一致 |
| `frontend/README.md` | 技术栈、功能范围、安全边界说明 | 否 | 已移除过期说明 |
| `frontend/src/views/DashboardView.vue` | 路线图、卡片文案、区块副标题 | 否 | 仅展示文案变化 |
| `frontend/src/layouts/DashboardLayout.vue` | 顶部徽标、侧栏页脚、移动端页脚 | 否 | 仅展示文案变化 |
| `frontend/src/components/SidebarNav.vue` | 导航状态说明 | 否 | 仅展示文案变化 |
| `docs/reports/Phase11_3_D_Documentation_Closeout_Report.md` | 阶段报告 | 否 | 本文件，已重写为完整报告 |

### 3.2 `docs/DEVELOPMENT_STATUS.md`

**原有问题**

- §16 仍把 Phase 11 描述为“尚未启动”。
- 六项 Dashboard 目标仍全部未勾选。
- 项目当前阶段、下一阶段、当前任务与 Phase 11.3-C 的 PASS WITH WARNINGS 结论不一致。
- P3 技术债尚未在状态文档中集中登记。

**实际修改内容**

- 将当前阶段更新为：Phase 11 Dashboard 实现与验收完成，PASS WITH WARNINGS，六项目标 6/6。
- 明确代码位于 `phase11/dashboard`，尚未提交、未创建 PR、未合并 `main`。
- 将下一阶段标记为 Phase 12：Custom Rules，状态为未开始。
- 在当前任务说明中补充 Phase 11 的实现、验收、分支和未提交状态。
- 在 §16 中勾选全部六项目标。
- 新增 Phase 11 状态表，记录六项目标、最终审计、P0/P1/P2、分支、提交/PR/合并和 Phase 12。
- 新增 Phase 11 P3 技术债 A–D 四组，全部标注为“待后续处理/未修复”。
- 在文档末尾的遗留问题中补充 Phase 11 P3 技术债指向。

**修改后的状态**

- Phase 11 状态为“实现与验收完成（PASS WITH WARNINGS；六项目标 6/6）”。
- 六项目标全部为 `[x]`。
- 当前分支、未提交/未 PR/未合并、Phase 12 未开始均有明确记录。
- P3 技术债已登记，但没有被描述为已修复。

**是否改变业务逻辑**

否。该文件是项目状态文档，不参与运行时逻辑。

### 3.3 `frontend/README.md`

**原有问题**

- 仍写有 “ECharts is intentionally not installed yet: Phase 11.1 contains no charts”。
- 仍把 Review Detail、Finding Statistics 和图表描述为范围之外。
- 没有说明当前 Dashboard 已包含 Review History、Review Detail、Review Insights、Finding Statistics 和五分类趋势。
- 没有清楚说明 Dashboard BFF 的同源访问方式和浏览器不持有内部 Token 的边界。

**实际修改内容**

- 保留并确认技术栈：Vue 3、TypeScript、Vite、Vue Router、Element Plus、Axios、Vitest + Vue Test Utils。
- 明确图表使用原生 SVG/CSS 渲染，ECharts 不是依赖。
- 在 Scope 中补充 Dashboard 首页、Review History、Review Detail、Review Insights、Finding Statistics、Review / Finding / High + Critical 趋势，以及 Bug / Security / Performance / Quality / Unknown 五分类趋势和 DAY/WEEK 切换。
- 说明 Review History、Review Detail、Review Insights 通过同源 `/api/dashboard/**` BFF 读取数据。
- 说明 Phase 10 的服务间 API 仍受 `X-Internal-Token` 保护，但该凭证不会嵌入浏览器代码。
- 说明前端不存储、不发送内部 Token。
- 删除“图表和详情不在范围内”等过期表述。
- 保留 “Custom Rules and authentication remain out of scope”，与 Phase 12 尚未开始的现状一致。

**修改后的状态**

README 可作为当前 Dashboard 的独立说明文档：技术栈、运行命令、环境变量、目录结构、安全边界和功能范围均与当前源码一致。

**是否改变业务逻辑**

否。该文件只影响文档阅读，不参与构建或运行。

### 3.4 `frontend/src/views/DashboardView.vue`

**原有问题**

- 路线图仍包含 `Quality insights — 11.3`，把已经完成的统计能力显示为未来计划。
- 首页卡片仍使用 `Stored reports`，容易被理解为首页展示了真实统计摘要。
- `Next up` 区块的副标题没有反映 Dashboard 已交付后的定位。

**实际修改内容**

- `roadmap` 数组只保留 `Custom rules — 12`，移除已完成的 `Quality insights — 11.3`。
- 将 `Stored reports` 改为 `Review archive`。
- 将 `Next up` 副标题更新为：`Planned work beyond the delivered dashboard scope.`
- 保留原有 health 检查、pipeline 展示、environment 信息和刷新逻辑。

**修改后的状态**

- 首页不再把已完成的统计能力标为未来路线图。
- “Review archive” 与 Review History 页面的实际能力一致。
- “Next up” 只表达 Dashboard 交付范围之外的计划。

**是否改变业务逻辑**

否。修改仅发生在模板和静态数组文案，未改变数据请求、路由、状态或交互行为。

### 3.5 `frontend/src/layouts/DashboardLayout.vue`

**原有问题**

- 顶部徽标仍显示 `Phase 11.1`。
- 桌面侧栏页脚仍显示 `Phase 11.1`。
- 移动端抽屉页脚仍显示 `Phase 11.1`。

**实际修改内容**

- 顶部徽标改为 `Dashboard`。
- 桌面侧栏页脚改为 `Dashboard` + `Phase 11.1–11.3 delivered · v{{ APP_VERSION }}`。
- 移动端抽屉页脚使用同一组文案。
- 保留原有导航、抽屉、折叠、面包屑和版本展示结构。

**修改后的状态**

顶部、桌面侧栏和移动端导航对当前交付范围的描述一致。

**是否改变业务逻辑**

否。修改仅涉及模板文本，未改变布局结构、路由跳转、响应式逻辑或组件行为。

### 3.6 `frontend/src/components/SidebarNav.vue`

**原有问题**

- 侧栏导航底部仍用 `Phase 11.2` 标识当前能力，落后于 Phase 11.3 的实际交付状态。

**实际修改内容**

- 将状态标签改为 `Available`。
- 将说明文本改为 `Review history and insights are live`。
- 保留 Dashboard、Review History、Review Insights 三个菜单项及其路由。

**修改后的状态**

侧栏导航明确表达 Review History 和 Review Insights 已可用，不再使用过期的阶段编号。

**是否改变业务逻辑**

否。菜单项、路由和高亮逻辑均未变化，仅更新展示文案。

### 3.7 新增/重写报告

本阶段新增的报告路径为：

```text
docs/reports/Phase11_3_D_Documentation_Closeout_Report.md
```

该文件是 Phase 11.3-D 唯一新增的文档产物。本次 Phase 11.4-A 只重写其内容，不改变路径，也不新增其他文件。

### 3.8 变更性质汇总

| 变更类型 | 文件 | 说明 |
|---|---|---|
| 项目状态账本 | `docs/DEVELOPMENT_STATUS.md` | 文档 |
| 前端说明文档 | `frontend/README.md` | 文档 |
| Vue 模板文案 | `DashboardView.vue`、`DashboardLayout.vue`、`SidebarNav.vue` | 仅展示文本 |
| 阶段报告 | 本文件 | 文档 |
| Java / SQL / 配置 / 测试 / 依赖 | 无 | 未修改 |

---

## 4. `DEVELOPMENT_STATUS.md` 更新

### 4.1 Phase 11 当前状态

`docs/DEVELOPMENT_STATUS.md` 当前记录：

| 项目 | 当前内容 |
|---|---|
| 当前阶段 | Phase 11：Dashboard — 实现与验收完成（PASS WITH WARNINGS；六项目标 6/6） |
| 分支 | `phase11/dashboard` |
| 提交 / PR / 合并 | 尚未提交、尚未创建 PR、尚未合并 `main` |
| 最终审计 | Phase 11.3-C，PASS WITH WARNINGS |
| P0 / P1 / P2 | 0 / 0 / 0 |
| 下一阶段 | Phase 12：Custom Rules — 未开始 |
| Phase 12 启动条件 | 等待 Phase 11 提交/PR/合并后再启动 |

### 4.2 六项 Dashboard 目标勾选状态

`docs/DEVELOPMENT_STATUS.md` §16 当前为：

- [x] Review History
- [x] Finding Statistics
- [x] Security Trend
- [x] Bug Trend
- [x] Performance Trend
- [x] Quality Trend

六项均为已完成。该勾选与 Phase 11.3-C 报告中的 6/6 结论一致。

### 4.3 P3 技术债登记

`DEVELOPMENT_STATUS.md` 新增了 P3 技术债章节，按 A–D 分组登记，共 18 项：

- **A. 性能技术债**：`review_report.created_at` 缺少索引；统计对比表在 Java 内存排序和分页。
- **B. 测试与验证债**：验收库 IT 默认禁用；真实 UI 第 2 页未验证；生产构建 E2E 未验证；多浏览器/真实移动设备未验证；无 CI；真实 GitHub PR E2E 与 Publisher → History → Query 接缝 E2E 未验证。
- **C. 文档与界面债**：范围条省略微秒；History Controller 缺少通用异常兜底；首页尚未展示真实动态统计摘要。
- **D. 契约与数据边界债**：B1 排序 tie-breaker 差异；History `commitSha` 来源差异；SQL `NOT IN` 的 NULL 语义；SQL 枚举与 Java 大小写语义；验收数据库 URL 未限制 host/port；早期报告错误字段和测试计数口径差异。

该章节明确写明：

> 以上事项均标记为“待后续处理/技术债”，尚未修复；不得据此修改业务代码、数据库或测试。

### 4.4 状态文档没有声称的内容

`DEVELOPMENT_STATUS.md` 没有声称：

- Phase 11 已提交；
- Phase 11 已创建 PR；
- Phase 11 已合并 `main`；
- Phase 12 已启动；
- P3 已修复；
- 真实 GitHub E2E 已通过。

---

## 5. `frontend/README.md` 更新

### 5.1 技术栈

README 当前记录：

- Vue 3 + TypeScript
- Vite
- Vue Router
- Element Plus（通过 `unplugin-vue-components` 按需引入）
- Axios
- Vitest + Vue Test Utils

### 5.2 图表实现

README 明确写明：

> Charts are rendered with native SVG/CSS; ECharts is not a dependency.

这是一项重要修正。Phase 11 的 Review/Finding 趋势图和五分类趋势图均由原生 SVG/CSS 实现，不依赖 ECharts。

### 5.3 功能范围

README 的 Scope 当前列出：

- Dashboard 首页：后端健康状态、pipeline 概览和环境信息。
- Review History：筛选、分页和排序。
- Review Detail：report、finding 和 comment 视图。
- Review Insights：summary metrics、分布和数据质量披露。
- Review / Finding / High + Critical 趋势。
- Bug / Security / Performance / Quality / Unknown 五分类趋势，支持 DAY/WEEK 切换。
- 原生 SVG/CSS 图表，无 ECharts 依赖。

同时保留：

> Custom Rules and authentication remain out of scope.

这与 Phase 12 尚未开始、Dashboard 当前不包含自定义规则和认证的现状一致。

### 5.4 Dashboard BFF 与安全边界

README 当前说明：

- Phase 10 的服务间 Review History API 仍由服务级 `X-Internal-Token` 保护。
- 该凭证不会嵌入浏览器代码。
- Review History、Review Detail、Review Insights 通过同源 Dashboard BFF `/api/dashboard/**` 读取数据。
- 该 BFF 在应用层限制为 loopback peer，并且不接收、不转发 `X-Internal-Token`。
- 浏览器不存储、不发送内部 Token。

README 同时记录开发服务器的边界：

- Vite dev server 显式绑定 `127.0.0.1`。
- 不应使用 `vite --host 0.0.0.0` 暴露到局域网。
- 同主机反向代理必须自行实施认证，因为代理到 Spring Boot 的连接会表现为 loopback。

### 5.5 删除的过期说法

README 已删除或不再包含：

- ECharts 故意未安装、Phase 11.1 没有图表；
- Review Detail、Finding Statistics、图表不在范围内；
- 把 Dashboard 描述为只有首页和健康检查的旧范围说明。

---

## 6. Dashboard UI 文案更新

### 6.1 `DashboardView.vue`

| 位置 | 修改前 | 修改后 |
|---|---|---|
| 路线图 | `Quality insights — 11.3` | 仅保留 `Custom rules — 12` |
| Review history 卡片 | `Stored reports` | `Review archive` |
| Next up 副标题 | 旧副标题未反映 Dashboard 已交付 | `Planned work beyond the delivered dashboard scope.` |

说明：

- `Quality insights — 11.3` 已由 Phase 11.3-B1 和 11.3-B2-B 完成，不应继续显示为未来路线图。
- `Review archive` 比 `Stored reports` 更准确地描述 Review History 的用途。
- `Next up` 只保留 Phase 12 的 Custom Rules，不再暗示 Dashboard 统计能力尚未交付。

### 6.2 `DashboardLayout.vue`

| 位置 | 修改前 | 修改后 |
|---|---|---|
| 顶部徽标 | `Phase 11.1` | `Dashboard` |
| 桌面侧栏页脚 | `Phase 11.1` | `Dashboard` + `Phase 11.1–11.3 delivered · v{{ APP_VERSION }}` |
| 移动端抽屉页脚 | `Phase 11.1` | 同桌面侧栏页脚 |

说明：

- 顶部徽标不再把整个 Dashboard 标记为 Phase 11.1。
- 页脚明确表达 Phase 11.1–11.3 已交付，同时保留前端版本号。
- 桌面和移动端文案保持一致。

### 6.3 `SidebarNav.vue`

| 位置 | 修改前 | 修改后 |
|---|---|---|
| 侧栏状态标签 | `Phase 11.2` | `Available` |
| 侧栏状态说明 | 旧阶段说明 | `Review history and insights are live` |

说明：

- Review History 和 Review Insights 已可用，`Available` 比阶段编号更直接。
- 菜单项、路由和高亮逻辑没有变化。

### 6.4 未改变的内容

本阶段没有改变：

- 路由表；
- 页面结构；
- 组件层级；
- API 客户端；
- 数据请求与响应处理；
- 筛选、分页、排序逻辑；
- 图表几何计算；
- 样式布局；
- 测试源码。

### 6.5 测试文案兼容性

Phase 11.3-C 记录的测试文案耦合仍然存在：

- `frontend/src/__tests__/DashboardLayout.spec.ts:50` 断言页面包含 `Phase 11.1`；
- `frontend/src/__tests__/DashboardView.spec.ts:54` 断言页面包含 `Phases 1–10 complete`。

本阶段没有修改测试，而是保留兼容子串：

- 页脚 `Phase 11.1–11.3 delivered` 仍包含 `Phase 11.1`；
- 首页 pipeline 卡片仍保留 `Phases 1–10 complete`。

因此历史 150 项前端测试仍可通过。该兼容策略同时也是一项已登记的 P3，见第 8 节。

---

## 7. 验证结果

### 7.1 历史执行结果

以下结果均为 **Phase 11.3-D 阶段在 `frontend/` 目录执行的历史记录**。本次 Phase 11.4-A 重写报告时**没有重新执行**这些命令，也没有重新构建前端。

| 验证项目 | 结果 |
|---|---|
| `npm run type-check` | **PASS** |
| `npm run lint:check` | **PASS** |
| `npm run test:unit` | **PASS，16 个测试文件 / 150 个测试** |
| `npm run build` | **PASS，1758 modules transformed，生成 `dist`** |

补充说明：

- 原始 11.3-D 摘要中的命令前缀因格式损坏被截断（例如显示为 `pm run ...`）。上表按 `frontend/package.json` 的实际脚本名还原为 `npm run ...`。
- `npm run build` 在 `package.json` 中定义为 `npm run type-check && npm run build-only`，因此该结果同时覆盖生产构建和类型检查。
- `npm run lint:check` 是非修改性的 oxlint + ESLint 校验。
- 16 个测试文件 / 150 个测试与 Phase 11.3-B2-B 和 Phase 11.3-C 的历史记录一致。

### 7.2 本次重写没有执行的验证

| 项目 | 本次是否执行 | 说明 |
|---|---|---|
| Backend unit tests | 否 | 未运行 Maven |
| MySQL integration tests | 否 | 未连接数据库 |
| Frontend `type-check` | 否 | 只做 Markdown 重写 |
| Frontend `lint:check` | 否 | 只做 Markdown 重写 |
| Frontend unit tests | 否 | 只做 Markdown 重写 |
| Frontend build | 否 | 只做 Markdown 重写 |
| Browser E2E | 否 | 未启动浏览器 |
| GitHub E2E | 否 | 未触发真实 PR |

### 7.3 历史验证能证明什么

Phase 11.3-D 的历史结果可以证明：

- 五个授权文件修改后，前端 TypeScript 类型契约仍然一致；
- Lint 校验通过；
- 16 个测试文件、150 个测试通过；
- 生产构建成功，共转换 1758 个模块；
- 文案修改没有破坏现有页面和测试。

### 7.4 历史验证不能证明什么

Phase 11.3-D 的历史结果不能证明：

- 后端 46 个 suite / 538 个测试在 11.3-D 阶段重新执行过；
- MySQL 集成测试在 11.3-D 阶段重新执行过；
- 生产构建产物上的浏览器 E2E 已通过；
- 多浏览器或真实移动设备已验证；
- 真实 GitHub PR 全链路 E2E 已执行；
- Publisher → History → Query 接缝 E2E 已覆盖。

这些缺口继续作为 P3/验证债保留，见第 8 节。

### 7.5 Markdown 结构检查

Phase 11.3-D 原始摘要记录了对 `DEVELOPMENT_STATUS.md` 和 `README.md` 的代码围栏成对闭合检查。

本次重写完成后，已对本报告执行以下检查：

1. 标题层级按 `#` → `##` → `###` → `####` 连续，无跳级；
2. 25 个表格均有表头和分隔行；
3. 代码围栏共 2 个，成对闭合；
4. 第 3 节五个文件逐一记录；
5. 第 8 节保留全部 P3 事项；
6. 报告内容与当前五个文件的源码一致。

---

## 8. P3 技术债与遗留问题

### 8.1 状态口径

本阶段不修复代码、数据库、测试或工程设施层面的 P3；只在文档/UI 层面清理 P3-01 与 P3-09 所描述的表现。需要区分三类状态：

| 状态 | 含义 |
|---|---|
| 本阶段已处理（文档层面） | Phase 11.3-D 更新了对应文档或 UI 文案；不代表底层技术债消失 |
| 仍存在 / 未修复 | 已登记，但本阶段没有修改代码、数据库、测试或工程设施 |
| NOT VERIFIED | 没有足够执行证据，不能声称通过 |

Phase 11.3-C 的 P3-01（过期文案与路线图）和 P3-09（状态文档滞后）已由本阶段在文档/UI 层面处理；**其余 P3 均未修复**。

按 `DEVELOPMENT_STATUS.md` §16 的 A–D 分组逐项统计：A 类 2 项、B 类 7 项、C 类 3 项、D 类 6 项，合计 **18 项**。该合计按 8.2 的登记行计数，A–D 内部无重复；F-01–F-09 与 X1–X5 是后续的编号对照/补充登记，不计入 A–D 的 18 项。

### 8.2 `DEVELOPMENT_STATUS.md` 登记的 A–D 项

| 分组 | 项数 |
|---|---:|
| A. 性能技术债 | 2 |
| B. 测试与验证债 | 7 |
| C. 文档与界面债 | 3 |
| D. 契约与数据边界债 | 6 |
| **合计** | **18** |

计数说明：

- B 类在 `DEVELOPMENT_STATUS.md` 中为 6 个 bullet；最后一个 bullet 同时包含“真实 GitHub PR 全链路 E2E”和“Publisher → History → Query 接缝 E2E”两个独立验证项，本报告按两项登记，因此 B 类为 7 项。
- D 类最后一行将“早期报告错误响应字段”和“测试计数口径”合并为一条文档口径问题，按 1 项计；两者在 F-09 / F-06 中有独立编号，不重复计入 A–D 合计。
- 未发现 A–D 内部重复登记。

#### A. 性能技术债

| 事项 | 状态 | 影响 | 后续建议 |
|---|---|---|---|
| `review_report.created_at` 缺少索引，统计查询可能全表扫描 | **未修复** | 生产数据量大时查询成本上升 | 评估索引或迁移；当前数据量下可接受 |
| `/api/dashboard/statistics/reviews` 在 Java 内存排序和分页 | **未修复** | 大范围查询产生额外内存和 CPU 成本 | 后续将排序/分页下推 SQL |

#### B. 测试与验证债

| 事项 | 状态 | 影响 | 后续建议 |
|---|---|---|---|
| `ReviewStatisticsAcceptanceDbIT` 默认禁用，需要显式启用 | **未修复** | 常规回归容易漏跑验收库测试 | 记录显式命令；CI 增加专项 job |
| 真实 UI 第 2 页尚未验证 | **NOT VERIFIED** | 多页交互缺少真实浏览器证据 | 用大数据集补浏览器 E2E 或手动验证 |
| 生产构建产物上的浏览器 E2E 尚未验证 | **NOT VERIFIED** | 只验证过 Vite dev server | 使用 `npm run build` + `npm run preview` 做 smoke |
| 多浏览器和真实移动设备尚未验证 | **NOT VERIFIED** | 只有 Chrome + 视口模拟证据 | 后续补浏览器矩阵和真机验证 |
| 当前项目尚无 CI 自动回归 | **未修复** | 回归依赖人工执行 | 后续建设 CI 流水线 |
| 真实 GitHub PR 全链路 E2E 尚未验证 | **NOT VERIFIED** | 真实 GitHub 写入和评论链路缺少证据 | 在具备权限和测试仓库后补做 |
| Publisher → History → Query 接缝 E2E 尚未验证 | **NOT VERIFIED** | 持久化到查询的跨阶段接缝未做单一 E2E | 后续补端到端接缝测试 |

#### C. 文档与界面债

| 事项 | 状态 | 影响 | 后续建议 |
|---|---|---|---|
| 范围条显示时间省略微秒 | **未修复** | 仅显示层精度问题，不影响请求边界 | 后续 UI 精度打磨 |
| History Controller 缺少通用异常兜底 | **未修复** | 未预期异常走 Spring 默认错误体，错误契约不完全一致 | 统一错误契约；低优先级 |
| 首页尚未展示真实动态统计摘要 | **未修复** | 首页仍是静态概览，`Review archive` 只是文案修正 | 可选增强，非 Phase 11 阻断项 |

#### D. 契约与数据边界债

| 事项 | 状态 | 影响 | 后续建议 |
|---|---|---|---|
| B1 审计中的排序 tie-breaker 与早期设计示例存在差异 | **未修复** | 正常分页稳定性不受影响，属文档/实现差异 | 统一文档或明确以实现为准 |
| History `commitSha` 数据来源与早期设计示例不同 | **未修复** | 正常写入路径两者相等；绕过应用直接改库时可能不同 | 记录数据来源约定 |
| SQL `NOT IN` 对 `NULL` 的处理需要未来外部数据导入时关注 | **未修复** | 当前 DDL 为 `NOT NULL`，正常数据不触发 | 外部导入前做非空校验/规范化 |
| SQL 枚举比较与 Java 状态判断的大小写语义需要统一 | **未修复** | 正常写入为大写枚举；外部导入小写值时可能出现口径差异 | 后续统一大小写契约 |
| 验收数据库 URL 尚未限制 host/port | **未修复** | 测试只读，风险有限；属测试安全加固项 | 增加 host/port 白名单 |
| 部分早期报告的错误响应字段和测试计数存在口径差异 | **未修复** | 文档与实现不完全一致 | 以当前实现和干净测试结果为准修正文档 |

### 8.3 Pre-PR Audit 新增发现

| 编号 | 事项 | 状态 | 说明 |
|---|---|---|---|
| X1 | 11.3-D 报告原文只有 48 行 blockquote 摘要，不是完整报告 | **本次重写已处理** | 本文件已重写为完整报告；不表示其他 P3 已修复 |
| X2 | 测试文案耦合：`DashboardLayout.spec.ts:50` 断言 `Phase 11.1`，`DashboardView.spec.ts:54` 断言 `Phases 1–10 complete` | **未修复** | 本阶段保留兼容子串，未修改测试 |
| X3 | `frontend/package-lock.json` 同时使用 `registry.npmjs.org` 与 `registry.npmmirror.com` | **未修复** | 未发现认证 Token；需确认镜像策略 |
| X4 | 12 张 11.2.4-C 验收截图仍显示旧 `Phase 11.1` / `Phase 11.2` 文案 | **未处理** | 属于历史证据，建议标注或后续重拍 |
| X5 | `docs/DEVELOPMENT_WORKFLOW.md` §13 仍停留在 2026-10-11 / Phase 8 状态 | **未修复** | 不在本阶段授权范围 |

### 8.4 其他已登记的契约差异（F-01–F-09）

| 编号 | 事项 | 状态 |
|---|---|---|
| F-01 | 默认排序 tie-breaker 使用 `report_id DESC`，早期设计示例写 `task_id DESC` | 未修复 |
| F-02 | `/reviews` 的 `commitSha` 取自任务提交，早期示例用报告提交 | 未修复 |
| F-03 | `NOT IN` 对 `NULL` 的 SQL 语义可能漏计未知 category/severity | 未修复（当前列为 NOT NULL） |
| F-04 | 验收数据库 URL 只校验数据库名，未锁定 host/port | 未修复 |
| F-05 | `handleDataIntegrity` 日志措辞比早期报告描述更宽 | 未修复（措辞精度） |
| F-06 | B1 报告 47/543 与干净结果 46/538 的计数口径差异 | 未修复（陈旧 surefire 产物导致） |
| F-07 | publish status 分布和 `dataQuality` 增加 `UNKNOWN` 契约 | 未修复（已文档化扩展） |
| F-08 | SQL 枚举比较与 Java 状态判断大小写敏感性不一致 | 未修复 |
| F-09 | 早期报告错误响应示例使用 `code`，实际契约为 `error` | 未修复（文档差异） |

### 8.5 非阻断理由

上述 P3 不会导致：

- 六项目标缺失；
- 正常写入路径下统计数据错误；
- 非 loopback 请求绕过 Dashboard 安全边界；
- 核心页面无法打开或链路断裂；
- 数据库结构或数据被破坏。

它们主要影响生产规模性能、验证完整度、文档准确性和后续维护成本。因此 Phase 11 的整体结论仍为 **PASS WITH WARNINGS**，而不是 PASS 或 BLOCKED。

---

## 9. Git 状态与操作边界

### 9.1 Phase 11.3-D 实施阶段的 Git 状态

| 项目 | 值 | 可验证性 |
|---|---|---|
| 分支 | `phase11/dashboard` | 可独立确认 |
| HEAD | `27e3a41161cfa86ee2956ba0b3626a2bcc71eec7` | 可独立确认 |
| HEAD 提交说明 | `Merge pull request #8 from zhangyu1108l/feature/phase10-mysql-history` | 可独立确认 |
| `main...HEAD` | `0 0` | 可独立确认 |
| 暂存区 | 空 | 可独立确认 |
| tracked 修改 | 6 | 可独立确认 |
| tracked 删除 | 1（`frontend/.gitkeep`） | 可独立确认 |
| untracked 文件（阶段结束） | 135 | Pre-PR Audit 独立复核确认 |
| untracked status 条目（阶段结束） | 58 | Pre-PR Audit 独立复核确认 |
| untracked 文件（阶段开始） | 134 | 原始摘要记录，Phase 11.3-C 报告可佐证 |
| untracked status 条目（阶段开始） | 57 | 原始摘要记录，未独立确认 |

阶段开始到结束的唯一新增路径是本报告：

- `docs/reports/Phase11_3_D_Documentation_Closeout_Report.md`

因此 untracked 从 134 增加到 135 个文件；`git status` 条目从 57 增加到 58，是因为新增报告所在目录的状态折叠发生变化。

### 9.2 tracked 文件说明

本阶段开始时，工作区已有以下 Phase 11 相关 tracked 变更，它们不是 Phase 11.3-D 产生的：

- `.gitignore`
- `backend/spring-service/src/main/java/cn/codesentinel/review/ReviewHistoryQueryService.java`
- `backend/spring-service/src/main/java/cn/codesentinel/task/ReviewReportRepository.java`
- `backend/spring-service/src/main/resources/application.yml`
- `backend/spring-service/src/test/java/cn/codesentinel/CodeSentinelApplicationTests.java`
- `docs/DEVELOPMENT_STATUS.md`
- `frontend/.gitkeep`（删除）

Phase 11.3-D 只修改其中的 `docs/DEVELOPMENT_STATUS.md`，没有修改其他 tracked 文件。

### 9.3 本阶段明确未执行的 Git 操作

Phase 11.3-D 没有执行：

- `git add`
- `git commit`
- `git push`
- `git merge`
- `git rebase`
- `git reset`
- `git clean`
- `git checkout`
- `git switch`
- `git stash`
- `git cherry-pick`

没有创建 PR，没有合并 `main`，没有删除分支，没有改写历史。

### 9.4 Phase 11.4-A 重写的只读核对

重写本报告前后，工作区状态为：

| 项目 | 重写前 | 重写后 |
|---|---|---|
| 分支 | `phase11/dashboard` | `phase11/dashboard` |
| HEAD | `27e3a41161cfa86ee2956ba0b3626a2bcc71eec7` | `27e3a41161cfa86ee2956ba0b3626a2bcc71eec7` |
| `main...HEAD` | `0 0` | `0 0` |
| 暂存区 | 空 | 空 |
| tracked 修改 | 6 | 6 |
| tracked 删除 | 1 | 1 |
| untracked 文件 | 136 | 136 |
| untracked status 条目 | 59 | 59 |

其中 136 / 59 已包含 Pre-PR Audit 报告。重写只覆盖一个既有的 untracked 报告文件，没有新增或删除路径；重写后只读复核确认分支、HEAD、`main...HEAD`、暂存区、tracked 和 untracked 数量均未变化。

### 9.5 当前状态解释

当前 `phase11/dashboard` 相对 `main` 为 `0 0`，说明 Phase 11 的所有变更仍在工作区，尚未形成提交。HEAD 仍是 Phase 10 的 PR #8 merge commit。这不是 Phase 11.3-D 的缺陷，而是整个 Phase 11 尚未进入提交流程的现状。

---

## 10. 安全与范围检查

### 10.1 本阶段未修改的对象

| 对象 | 状态 | 说明 |
|---|---|---|
| `.env` | **未修改** | 未读取、未写入、未纳入报告 |
| `secrets/` | **未修改** | 未读取内容、未写入 |
| `backend/spring-service/src/main/resources/application.yml` | **未修改** | 本阶段无配置变化 |
| 数据库 | **未修改** | 未执行 DDL/DML，未连接数据库写入 |
| 后端 Java 代码 | **未修改** | 无 Java 变更 |
| 前端业务逻辑 | **未修改** | 只改模板文案和静态数组 |
| 测试源码 | **未修改** | 未改断言、未改测试配置 |
| 路由 / API / Schema | **未修改** | 无契约变化 |
| 依赖 | **未修改** | 未改 `package.json` / `package-lock.json` |
| Phase 12 功能 | **未新增** | 未实现 Custom Rules |

### 10.2 敏感信息检查

对五个修改文件和本报告检查：

- 未发现 GitHub Token、PAT、私钥、API Key、密码或 Webhook Secret。
- 未发现数据库连接凭证。
- 未发现用户数据或数据库导出。
- 未发现内部 Token 被写入前端代码或文档示例。
- `frontend/README.md` 只说明 `X-Internal-Token` 的存在和边界，没有提供任何真实值。

### 10.3 范围检查结论

Phase 11.3-D 的变更范围与授权一致：

- 两个文档文件；
- 三个 Vue 模板文案；
- 一份阶段报告。

没有后端、数据库、测试、依赖、路由或业务逻辑变化。没有启动 Phase 12，也没有处理 Pre-PR Audit 中的其他问题。

---

## 11. 最终结论

### 11.1 结论表

| 项目 | 结论 |
|---|---|
| Phase 11.3-D | **PASS（文档收尾范围）** |
| Phase 11 整体 | **PASS WITH WARNINGS** |
| 六项 Dashboard 目标 | **6/6 完成** |
| P0 / P1 / P2 | **0 / 0 / 0** |
| Phase 11 提交状态 | **尚未提交、未创建 PR、未合并 `main`** |
| Phase 12 | **尚未开始** |
| P3 技术债 | **A–D 共 18 项继续保留；除 P3-01 / P3-09 的文档表现外均未修复** |
| 真实 GitHub E2E | **NOT VERIFIED** |
| Publisher → History → Query 接缝 E2E | **NOT VERIFIED** |

### 11.2 一句话结论

> **Phase 11.3-D 已把 Dashboard 的状态文档、前端 README 和 UI 文案同步到 Phase 11.3-C 的实际验收状态；六项目标 6/6，Phase 11 整体 PASS WITH WARNINGS，但代码仍未提交、未创建 PR、未合并 `main`，Phase 12 尚未开始，P3 技术债继续保留。**

### 11.3 PASS 的范围

本报告的 PASS 仅表示：

- 五个授权文件的文档/文案收尾已完成；
- 历史前端验证记录通过；
- 没有发现新的 P0 / P1 / P2；
- 变更范围没有越界。

本报告的 PASS 不表示：

- 所有 P3 已修复；
- 后端测试在 11.3-D 阶段重新执行；
- MySQL IT 在 11.3-D 阶段重新执行；
- 真实浏览器 E2E 或真实 GitHub E2E 已通过；
- Phase 11 已合并。

---

## 12. 后续建议

1. **冻结 Phase 11.3-D 的五个文件与本报告**：后续提交流程不应再修改其内容，除非发现事实错误。
2. **进入 Phase 11 Pre-PR 最终准备**：按 Pre-PR Audit 的分类清单确认纳入文件，排除 4 个 Phase 10 历史报告。
3. **提交前确认敏感文件不入库**：再次检查 `.env`、`secrets/`、`dist`、`node_modules`、`target`、`*.tsbuildinfo`、`.eslintcache` 不在暂存区。
4. **提交前补跑验证（建议）**：后端 `mvn test`、前端 `npm run type-check`、`npm run lint:check`、`npm run test:unit`、`npm run build`；如条件允许，再运行 `mvn -Pmysql-it verify`。
5. **PR 描述披露已知限制**：P3 技术债、默认跳过的验收 IT、生产构建 E2E、多浏览器/移动端、真实 GitHub E2E 和 Publisher → History → Query 接缝 E2E 的未验证状态。
6. **确认 package-lock registry 策略**：在提交前决定是否保留 `npmmirror.com` 混合来源，必要时用官方 registry 重新生成 lockfile。
7. **不启动 Phase 12**：Phase 12 必须等待 Phase 11 提交、PR 审查和合并完成后再开始。
8. **合并后再处理 P3**：将性能、验证、文档和契约类 P3 纳入后续迭代，不在本 PR 中顺手修复。

---

## 附录 A：证据来源

| 来源 | 用途 | 性质 |
|---|---|---|
| 当前 `docs/DEVELOPMENT_STATUS.md` | 核对 Phase 11 状态、六项勾选、P3 A–D | 当前源码 |
| 当前 `frontend/README.md` | 核对技术栈、图表、范围和 BFF 说明 | 当前源码 |
| 当前 `DashboardView.vue` | 核对路线图、Review archive、Next up | 当前源码 |
| 当前 `DashboardLayout.vue` | 核对顶部徽标和页脚 | 当前源码 |
| 当前 `SidebarNav.vue` | 核对 Available 标签 | 当前源码 |
| `Phase11_3_C_Final_Closeout_Audit_Report.md` | PASS WITH WARNINGS、P3 汇总、测试证据 | 历史审计 |
| `Phase11_3_B2_B_Implementation_Report.md` | 150 项前端测试、1758 modules 构建证据 | 历史实施 |
| `Phase11_Pre_PR_Audit_Report.md` | 文件分类、135/58 Git 状态、X1–X5 | 历史审查 |
| Phase 11.3-D 原始 48 行摘要 | 五项修改、四项验证、Git 57→58 / 134→135 | 历史摘要 |
| 当前 Git 只读状态 | 分支、HEAD、tracked/untracked 数量 | 本次核对 |

## 附录 B：五个文件核对表

| 文件 | 要求的修改事实 | 当前证据 | 核对结果 |
|---|---|---|---|
| `docs/DEVELOPMENT_STATUS.md` | Phase 11 实现与验收完成、PASS WITH WARNINGS、6/6、未提交/未 PR/未合并、Phase 12 未开始、P3 A–D 18 项登记 | 当前阶段、§16、P3 A–D 章节均存在 | **已核实** |
| `frontend/README.md` | Vue 3/TS/Vite/Element Plus、原生 SVG/CSS、History/Detail/Insights/Statistics/五分类趋势、BFF、无内部 Token | Stack、Scope、Security boundary 与源码一致 | **已核实** |
| `DashboardView.vue` | 移除 Quality insights 11.3、Stored reports → Review archive、更新 Next up | 路线图仅 Custom rules；`Review archive`；新副标题 | **已核实** |
| `DashboardLayout.vue` | 顶部、侧栏、移动端页脚文案调整 | 顶部 `Dashboard`；两处页脚 `Dashboard` + `Phase 11.1–11.3 delivered` | **已核实** |
| `SidebarNav.vue` | Phase 11.2 → Available | `Available` + `Review history and insights are live` | **已核实** |

## 附录 C：报告结构检查表

| 检查项 | 结果 |
|---|---|
| 基本信息 | 已包含 |
| 任务目标与范围 | 已包含 |
| 五个文件逐一修改记录 | 已包含 |
| `DEVELOPMENT_STATUS.md` 更新 | 已包含 |
| `frontend/README.md` 更新 | 已包含 |
| Dashboard UI 文案更新 | 已包含 |
| 验证结果及历史标注 | 已包含 |
| P3 技术债与遗留问题 | 已包含 |
| Git 状态与操作边界 | 已包含 |
| 安全与范围检查 | 已包含 |
| 最终结论 | 已包含 |
| 后续建议 | 已包含 |

> **报告结束。Phase 11.3-D 文档收尾完成；Phase 11 仍未提交、未创建 PR、未合并 `main`；Phase 12 尚未开始；P3 技术债继续保留，底层问题未修复。**
