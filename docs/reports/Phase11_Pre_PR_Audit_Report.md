# Phase 11 Pre-PR Audit Report — 提交前只读审查

> 审计日期：2026-11-15  
> 分支：`phase11/dashboard`  
> HEAD：`27e3a41161cfa86ee2956ba0b3626a2bcc71eec7`  
> 审计性质：只读。未修改源码、测试、配置、数据库或既有文档；只新增本报告。  
> 审计对象：Phase 11 Dashboard 全部未提交变更（11.1 → 11.3-D）  
> **结论：有条件具备进入 PR 准备阶段（CONDITIONAL GO）。Phase 11 代码与测试证据可支持 PR；但必须先处理 Phase 11.3-D 报告内容异常、排除 Phase 10 历史报告、确认本地 `.env` / `secrets/` 不被提交，并在 PR 描述中披露 P3 与验证缺口。**

一句话结论：

> **当前 142 个变更路径中，80 个属于 Phase 11 功能/工程配置、28 个属于 Phase 11 测试、30 个属于 Phase 11 文档、4 个属于 Phase 10 历史报告、0 个构建产物、0 个无法归属。推荐 PR 纳入 137 个现有 Phase 11 文件（暂排除内容异常的 11.3-D 报告），加上本审查报告后可纳入 138 个；若先重写 11.3-D 报告，则可纳入 139 个。Phase 10 的 4 个报告应排除。未发现硬编码密钥、Token、密码、私钥、数据库导出或用户数据；未发现 Phase 12 越界代码。**

---

## 1. 审计范围与只读边界

### 1.1 已读取的资料

- `AGENTS.md`
- `docs/PROJECT_DESIGN.md`（重点 §23 Dashboard 设计）
- `docs/DEVELOPMENT_WORKFLOW.md`
- `docs/DEVELOPMENT_STATUS.md`
- `docs/reports/Phase11_3_C_Final_Closeout_Audit_Report.md`
- `docs/reports/Phase11_3_D_Documentation_Closeout_Report.md`
- Phase 11 各子阶段报告、当前源码、测试、配置与 Git 状态

### 1.2 本阶段实际执行

- 只读 Git 命令：`status` / `diff` / `ls-files` / `branch` / `rev-parse` / `rev-list` / `check-ignore` / `log`。
- 只读源码、测试、配置、报告与图片检查。
- 只读文件名、大小、PNG magic bytes 与敏感模式扫描。
- 未运行后端测试、MySQL IT、前端测试、类型检查、Lint、构建或浏览器 E2E。
- 未清理、未重新生成、未覆盖任何测试报告或构建产物。
- 未执行任何 Git 写操作。
- 只新增本报告：`docs/reports/Phase11_Pre_PR_Audit_Report.md`。

### 1.3 与历史报告冲突时的处理

以当前源码、当前 Git 状态和实际文件内容为准。历史报告的结论只作为证据来源，不直接当作当前事实。

---

## 2. 当前分支、HEAD 与 main 对比

| 项目 | 值 |
|---|---|
| 当前分支 | `phase11/dashboard` |
| HEAD | `27e3a41161cfa86ee2956ba0b3626a2bcc71eec7` |
| HEAD 提交说明 | `Merge pull request #8 from zhangyu1108l/feature/phase10-mysql-history` |
| `main...HEAD` | `0 0` |
| 暂存区 | 空 |
| tracked 修改 | 6 |
| tracked 删除 | 1 |
| tracked 变更合计 | 7 |
| untracked 文件 | 135（`git status` 折叠为 58 个条目） |
| 变更路径合计 | 142 |

关键事实：

1. `phase11/dashboard` 当前没有领先 `main` 的任何提交；Phase 11 全部变更仍在工作区，尚未 commit。
2. HEAD 仍是 Phase 10 的 PR #8 merge commit，因此 PR 创建前必须先把 Phase 11 变更提交到当前分支。
3. `git diff` 只能看到 7 个 tracked 变更；新增后端、整个前端、报告和截图都是 untracked，必须通过 `git ls-files --others --exclude-standard` 才能完整盘点。
4. 本审查开始前与结束后，分支、HEAD、`main...HEAD`、tracked 变更数量必须保持不变；只允许新增本报告。

---

## 3. 完整变更文件分类

分类定义：

| 类别 | 定义 | 数量 |
|---|---|---:|
| A | Phase 11 功能实现与工程配置 | 80 |
| B | Phase 11 测试 | 28 |
| C | Phase 11 文档与报告 | 30 |
| D | Phase 1–10 历史遗留文档 | 4 |
| E | 构建产物、缓存、临时文件 | 0（均在 ignore 中，不在变更清单） |
| F | 无法确认归属 | 0 |

合计：**142 个路径 = 7 个 tracked + 135 个 untracked**。分类计数已用脚本核对：A=80、B=28、C=30、D=4，无重复、无遗漏。

### 3.1 A — Phase 11 功能实现与工程配置（80）

#### A-1 tracked 变更（5）

| 文件 | 状态 | 类别 | 变更目的 | 入 PR | 判断依据 |
|---|---|---|---|---|---|
| `.gitignore` | M | A | 增加 Node / Frontend 忽略项（`node_modules/`、`.eslintcache`） | ✅ 是 | 仅为前端工程配置；无密钥 |
| `backend/spring-service/src/main/java/cn/codesentinel/review/ReviewHistoryQueryService.java` | M | A | 将 `toReportResponse` 改为 package-private，供 Dashboard 列表复用 | ✅ 是 | 方法可见性调整；Dashboard 列表依赖；无行为变更 |
| `backend/spring-service/src/main/java/cn/codesentinel/task/ReviewReportRepository.java` | M | A | 增加 Dashboard 历史列表分页查询 `searchHistory` | ✅ 是 | Phase 11.2.2-A 查询；C 报告 §6.1 |
| `backend/spring-service/src/main/resources/application.yml` | M | A | 增加 `server.forward-headers-strategy: none`，防止转发头改写 loopback 边界 | ✅ 是 | Dashboard 安全边界；Diff 仅 3 行 |
| `frontend/.gitkeep` | D | A | 删除占位文件，前端已有真实内容 | ✅ 是 | 前端目录已完整实现；保留会导致空占位残留 |

#### A-2 后端主代码（22）

| 文件 | 状态 | 类别 | 变更目的 | 入 PR | 判断依据 |
|---|---|---|---|---|---|
| `backend/spring-service/src/main/java/cn/codesentinel/controller/DashboardReviewController.java` | ?? | A | `GET /api/dashboard/reviews` 历史列表 | ✅ 是 | C §6.1；仅 GET |
| `backend/spring-service/src/main/java/cn/codesentinel/controller/DashboardReviewDetailController.java` | ?? | A | `GET /api/dashboard/reviews/{taskId}`、findings、comments | ✅ 是 | C §5.1；仅 GET |
| `backend/spring-service/src/main/java/cn/codesentinel/controller/DashboardStatisticsController.java` | ?? | A | `GET /api/dashboard/statistics/overview`、`/reviews` | ✅ 是 | C §6.1；仅 GET |
| `backend/spring-service/src/main/java/cn/codesentinel/review/InvalidReviewHistoryFilterException.java` | ?? | A | 历史列表非法筛选异常 | ✅ 是 | 历史列表错误契约 |
| `backend/spring-service/src/main/java/cn/codesentinel/review/InvalidReviewHistoryPaginationException.java` | ?? | A | 历史列表非法分页异常 | ✅ 是 | 历史列表错误契约 |
| `backend/spring-service/src/main/java/cn/codesentinel/review/ReviewHistoryFilter.java` | ?? | A | 历史列表筛选模型 | ✅ 是 | 被 Controller/Service 使用 |
| `backend/spring-service/src/main/java/cn/codesentinel/review/ReviewHistoryListService.java` | ?? | A | 历史列表查询编排与响应映射 | ✅ 是 | C §5.1；调用 Repository |
| `backend/spring-service/src/main/java/cn/codesentinel/security/DashboardLocalAccessFilter.java` | ?? | A | `/api/dashboard/**` 仅允许 loopback；忽略转发头；fail-closed | ✅ 是 | C §5.2、§8；安全边界核心 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/InvalidStatisticsGranularityException.java` | ?? | A | 非法 DAY/WEEK 粒度异常 | ✅ 是 | 统计 API 错误契约 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/InvalidStatisticsRangeException.java` | ?? | A | 非法统计范围异常 | ✅ 是 | 统计 API 错误契约 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/InvalidStatisticsSortException.java` | ?? | A | 非法统计排序异常 | ✅ 是 | 统计 API 错误契约 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsCount.java` | ?? | A | 分类/严重度计数投影 | ✅ 是 | C §6.2 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsDataQuality.java` | ?? | A | 数据质量披露 DTO | ✅ 是 | C §6.2、§6.3 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsOverviewResponse.java` | ?? | A | 统计概览响应 | ✅ 是 | C §6.1 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsRange.java` | ?? | A | 统计范围 DTO | ✅ 是 | 统计 API 契约 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsRepository.java` | ?? | A | 原生 SQL 聚合（分类、严重度、趋势） | ✅ 是 | C §6.1、§6.3 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsReviewItem.java` | ?? | A | 对比表行 DTO | ✅ 是 | 统计对比表 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsService.java` | ?? | A | 统计编排、范围、快照、Summary、Trend、对比表 | ✅ 是 | C §6.1–§6.3 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsSummary.java` | ?? | A | Summary 10 项指标与分布 DTO | ✅ 是 | C §6.2 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsTrend.java` | ?? | A | 趋势容器 | ✅ 是 | C §4.2 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsTrendPoint.java` | ?? | A | 趋势点，含 5 个分类字段 | ✅ 是 | C §4.2、§4.3 |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/StatisticsGranularity.java` | ?? | A | DAY/WEEK 枚举 | ✅ 是 | 统计 API 契约 |

#### A-3 前端工程配置与工具链（18）

| 文件 | 状态 | 类别 | 变更目的 | 入 PR | 判断依据 |
|---|---|---|---|---|---|
| `frontend/.editorconfig` | ?? | A | 前端代码格式约定 | ✅ 是 | 工程配置；无密钥 |
| `frontend/.env.example` | ?? | A | 仅示例变量：空 `VITE_API_BASE_URL` 与本地代理目标 | ✅ 是 | 无实际凭证；安全扫描通过 |
| `frontend/.gitattributes` | ?? | A | LF 行尾约定 | ✅ 是 | 工程配置 |
| `frontend/.gitignore` | ?? | A | 忽略 `dist`、`node_modules`、`.env`、缓存等 | ✅ 是 | 与根 `.gitignore` 配合 |
| `frontend/.oxlintrc.json` | ?? | A | oxlint 规则 | ✅ 是 | Lint 配置 |
| `frontend/components.d.ts` | ?? | A | unplugin-vue-components 自动生成组件类型声明 | ✅ 是 | `tsconfig.app.json` include 该文件；不提交会导致 fresh clone 类型检查缺声明 |
| `frontend/env.d.ts` | ?? | A | Vite 环境类型 | ✅ 是 | TypeScript 配置 |
| `frontend/eslint.config.ts` | ?? | A | ESLint 配置 | ✅ 是 | Lint 配置 |
| `frontend/index.html` | ?? | A | Vite 入口 HTML | ✅ 是 | 前端入口 |
| `frontend/package-lock.json` | ?? | A | 依赖锁定 | ✅ 是（见风险） | 可复现构建；含两个 registry，需确认镜像策略 |
| `frontend/package.json` | ?? | A | 前端依赖与脚本 | ✅ 是 | 构建/测试入口 |
| `frontend/public/favicon.svg` | ?? | A | 站点图标 | ✅ 是 | 静态资源 |
| `frontend/tsconfig.app.json` | ?? | A | 应用 TS 配置，include `components.d.ts` | ✅ 是 | 类型检查依赖 |
| `frontend/tsconfig.json` | ?? | A | TS 项目引用 | ✅ 是 | 工程配置 |
| `frontend/tsconfig.node.json` | ?? | A | Node/Vite 配置类型 | ✅ 是 | 工程配置 |
| `frontend/tsconfig.vitest.json` | ?? | A | 测试 TS 配置 | ✅ 是 | 测试配置 |
| `frontend/vite.config.ts` | ?? | A | Vite 插件、`127.0.0.1` 绑定、dev proxy | ✅ 是 | 开发服务器安全边界 |
| `frontend/vitest.config.ts` | ?? | A | Vitest 配置 | ✅ 是 | 测试配置 |

#### A-4 前端应用源码（35）

| 文件 | 状态 | 类别 | 变更目的 | 入 PR | 判断依据 |
|---|---|---|---|---|---|
| `frontend/src/App.vue` | ?? | A | 根组件 | ✅ 是 | 前端入口 |
| `frontend/src/main.ts` | ?? | A | Vue 应用启动 | ✅ 是 | 前端入口 |
| `frontend/src/router/index.ts` | ?? | A | `/`、`/reviews`、`/reviews/:taskId`、`/insights`、404 | ✅ 是 | C §5.2、§7.1 |
| `frontend/src/config/app.ts` | ?? | A | 非敏感应用常量与 API base URL | ✅ 是 | 无 Token；C §7.1 |
| `frontend/src/assets/styles/main.css` | ?? | A | 全局样式 | ✅ 是 | UI 实现 |
| `frontend/src/api/client.ts` | ?? | A | 同源 Axios 客户端；不发送内部 Token | ✅ 是 | C §7.1；安全边界 |
| `frontend/src/api/health.ts` | ?? | A | 健康检查 API | ✅ 是 | Dashboard 首页 |
| `frontend/src/api/index.ts` | ?? | A | API 导出 | ✅ 是 | API 模块 |
| `frontend/src/api/review-detail.ts` | ?? | A | Review Detail BFF API | ✅ 是 | Phase 11.2.3 |
| `frontend/src/api/review-history.ts` | ?? | A | Review History BFF API | ✅ 是 | Phase 11.2.2 |
| `frontend/src/api/statistics.ts` | ?? | A | Statistics BFF API | ✅ 是 | Phase 11.2.4 |
| `frontend/src/types/api.ts` | ?? | A | 通用 API 类型 | ✅ 是 | 前端契约 |
| `frontend/src/types/statistics.ts` | ?? | A | 统计契约，含 5 个分类字段 | ✅ 是 | B2-B / C §7.1 |
| `frontend/src/utils/api-error.ts` | ?? | A | API 错误归一化 | ✅ 是 | 错误处理 |
| `frontend/src/utils/category-trend.ts` | ?? | A | 五分类趋势系列配置 | ✅ 是 | B2-B；C §7.1 |
| `frontend/src/utils/review-display.ts` | ?? | A | Review 展示格式 | ✅ 是 | Detail/History UI |
| `frontend/src/utils/statistics-error.ts` | ?? | A | 统计错误处理 | ✅ 是 | Insights UI |
| `frontend/src/utils/statistics-format.ts` | ?? | A | 统计数值/时间格式 | ✅ 是 | Insights UI |
| `frontend/src/utils/trend-geometry.ts` | ?? | A | 单/多系列 SVG 几何 | ✅ 是 | 原生 SVG 图表 |
| `frontend/src/composables/useReviewStatistics.ts` | ?? | A | 对比表统计状态 | ✅ 是 | Insights |
| `frontend/src/composables/useStatisticsOverview.ts` | ?? | A | Overview 状态与快照 | ✅ 是 | Insights |
| `frontend/src/components/BrandMark.vue` | ?? | A | 品牌标识 | ✅ 是 | 布局组件 |
| `frontend/src/components/SidebarNav.vue` | ?? | A | 侧边导航 | ✅ 是 | C §7.1 |
| `frontend/src/components/insights/CategoryTrendChart.vue` | ?? | A | 五分类趋势图 | ✅ 是 | B2-B；C §7.1 |
| `frontend/src/components/insights/DistributionBars.vue` | ?? | A | 分类/严重度分布条 | ✅ 是 | Insights |
| `frontend/src/components/insights/InsightsFilterBar.vue` | ?? | A | Insights 筛选栏 | ✅ 是 | Insights |
| `frontend/src/components/insights/ReviewComparisonTable.vue` | ?? | A | Review 对比表 | ✅ 是 | C §5.2、§7.1 |
| `frontend/src/components/insights/StatCard.vue` | ?? | A | 统计指标卡 | ✅ 是 | Insights |
| `frontend/src/components/insights/TrendChart.vue` | ?? | A | Review/Finding/High+Critical 趋势 | ✅ 是 | C §7.1 |
| `frontend/src/layouts/DashboardLayout.vue` | ?? | A | Dashboard 布局、导航、页脚 | ✅ 是 | C §7.1；11.3-D 文案已更新 |
| `frontend/src/views/DashboardView.vue` | ?? | A | Dashboard 首页 | ✅ 是 | C §7.1；11.3-D 文案已更新 |
| `frontend/src/views/InsightsView.vue` | ?? | A | Review Insights 页面 | ✅ 是 | C §7.1 |
| `frontend/src/views/NotFoundView.vue` | ?? | A | 404 页面 | ✅ 是 | 路由 |
| `frontend/src/views/ReviewDetailView.vue` | ?? | A | Review Detail 页面 | ✅ 是 | C §7.1 |
| `frontend/src/views/ReviewHistoryView.vue` | ?? | A | Review History 页面 | ✅ 是 | C §7.1 |

### 3.2 B — Phase 11 测试（28）

#### B-1 tracked 测试（1）

| 文件 | 状态 | 类别 | 变更目的 | 入 PR | 判断依据 |
|---|---|---|---|---|---|
| `backend/spring-service/src/test/java/cn/codesentinel/CodeSentinelApplicationTests.java` | M | B | 增加 `ReviewStatisticsRepository` `@MockBean`，保持上下文测试 | ✅ 是 | 仅测试上下文；C 审计已覆盖 |

#### B-2 后端测试（10）

| 文件 | 状态 | 类别 | 变更目的 | 入 PR | 判断依据 |
|---|---|---|---|---|---|
| `backend/spring-service/src/test/java/cn/codesentinel/controller/DashboardReviewControllerTest.java` | ?? | B | 历史列表 Controller 测试（12 项） | ✅ 是 | C §6.5 |
| `backend/spring-service/src/test/java/cn/codesentinel/controller/DashboardReviewDetailControllerTest.java` | ?? | B | Detail Controller 测试（17 项） | ✅ 是 | C §6.5 |
| `backend/spring-service/src/test/java/cn/codesentinel/controller/DashboardStatisticsControllerTest.java` | ?? | B | Statistics Controller 测试（16 项） | ✅ 是 | C §6.5 |
| `backend/spring-service/src/test/java/cn/codesentinel/review/ReviewHistoryListMySqlIT.java` | ?? | B | 历史列表 MySQL IT | ✅ 是 | `*IT`，`mysql-it` profile |
| `backend/spring-service/src/test/java/cn/codesentinel/review/ReviewHistoryListServiceTest.java` | ?? | B | 历史列表 Service 测试（8 项） | ✅ 是 | C §6.5 |
| `backend/spring-service/src/test/java/cn/codesentinel/security/DashboardLocalAccessFilterTest.java` | ?? | B | loopback 过滤器测试（12 项） | ✅ 是 | C §6.5 |
| `backend/spring-service/src/test/java/cn/codesentinel/security/DashboardLocalAccessFilterTomcatTest.java` | ?? | B | Tomcat 路径变体测试（8 项） | ✅ 是 | C §6.5 |
| `backend/spring-service/src/test/java/cn/codesentinel/statistics/ReviewStatisticsAcceptanceDbIT.java` | ?? | B | 验收库只读 IT；默认禁用 | ✅ 是 | `@EnabledIfSystemProperty(codesentinel.acceptance.db=true)`；P3 |
| `backend/spring-service/src/test/java/cn/codesentinel/statistics/ReviewStatisticsMySqlIT.java` | ?? | B | 统计 MySQL IT | ✅ 是 | `*IT`，`mysql-it` profile |
| `backend/spring-service/src/test/java/cn/codesentinel/statistics/ReviewStatisticsServiceTest.java` | ?? | B | 统计 Service 测试（20 项） | ✅ 是 | C §6.5 |

#### B-3 前端测试与测试设置（17）

| 文件 | 状态 | 类别 | 变更目的 | 入 PR | 判断依据 |
|---|---|---|---|---|---|
| `frontend/src/__tests__/App.spec.ts` | ?? | B | App 测试 | ✅ 是 | 16 个测试文件之一 |
| `frontend/src/__tests__/CategoryTrendChart.spec.ts` | ?? | B | 五分类趋势图测试 | ✅ 是 | B2-B；16 项 |
| `frontend/src/__tests__/DashboardLayout.spec.ts` | ?? | B | 布局测试；断言 `Phase 11.1` | ✅ 是 | 现有 150 项测试之一；测试文案耦合 |
| `frontend/src/__tests__/DashboardView.spec.ts` | ?? | B | 首页测试；断言 `Phases 1–10 complete` | ✅ 是 | 现有 150 项测试之一；测试文案耦合 |
| `frontend/src/__tests__/InsightsView.spec.ts` | ?? | B | Insights 页面测试 | ✅ 是 | B2-B |
| `frontend/src/__tests__/ReviewComparisonTable.spec.ts` | ?? | B | 对比表测试 | ✅ 是 | Phase 11.2.4 |
| `frontend/src/__tests__/ReviewDetailView.spec.ts` | ?? | B | Detail 页面测试 | ✅ 是 | Phase 11.2.3 |
| `frontend/src/__tests__/ReviewHistoryView.spec.ts` | ?? | B | History 页面测试 | ✅ 是 | Phase 11.2.2 |
| `frontend/src/__tests__/TrendChart.spec.ts` | ?? | B | 原趋势图测试 | ✅ 是 | B2-B 仅补 fixture |
| `frontend/src/__tests__/api-error.spec.ts` | ?? | B | API 错误测试 | ✅ 是 | 前端测试 |
| `frontend/src/__tests__/review-detail-api.spec.ts` | ?? | B | Detail API 测试 | ✅ 是 | 前端测试 |
| `frontend/src/__tests__/review-history-api.spec.ts` | ?? | B | History API 测试 | ✅ 是 | 前端测试 |
| `frontend/src/__tests__/router.spec.ts` | ?? | B | 路由测试 | ✅ 是 | 前端测试 |
| `frontend/src/__tests__/statistics-api.spec.ts` | ?? | B | Statistics API 测试 | ✅ 是 | 前端测试 |
| `frontend/src/__tests__/statistics-format.spec.ts` | ?? | B | 统计格式测试 | ✅ 是 | 前端测试 |
| `frontend/src/__tests__/trend-geometry.spec.ts` | ?? | B | 趋势几何测试 | ✅ 是 | B2-B |
| `frontend/src/test/setup.ts` | ?? | B | Vitest 全局设置 | ✅ 是 | 测试配置 |

### 3.3 C — Phase 11 文档与报告（30）

#### C-1 Phase 11 报告与文档（18）

| 文件 | 状态 | 类别 | 变更目的 | 入 PR | 判断依据 |
|---|---|---|---|---|---|
| `docs/DEVELOPMENT_STATUS.md` | M | C | Phase 11 状态、六项目标、P3、下一步 | ✅ 是 | 11.3-D 当前内容；已核对 |
| `frontend/README.md` | ?? | C | 前端范围、图表实现、安全边界 | ✅ 是 | 11.3-D 当前内容；已核对 |
| `docs/reports/Phase11_2_2_B_1_Report.md` | ?? | C | Review History 后端收尾 | ✅ 是 | Phase 11.2.2-B.1 |
| `docs/reports/Phase11_2_2_B_Report.md` | ?? | C | Review History 前端列表 | ✅ 是 | Phase 11.2.2-B |
| `docs/reports/Phase11_2_3_A_Investigation_Report.md` | ?? | C | Review Detail 调查 | ✅ 是 | Phase 11.2.3-A |
| `docs/reports/Phase11_2_3_B_Acceptance_Report.md` | ?? | C | Review Detail 验收 | ✅ 是 | Phase 11.2.3-B |
| `docs/reports/Phase11_2_3_B_Implementation_Report.md` | ?? | C | Review Detail 实施 | ✅ 是 | Phase 11.2.3-B |
| `docs/reports/Phase11_2_4_A_Investigation_Report.md` | ?? | C | Finding Statistics 调查 | ✅ 是 | Phase 11.2.4-A |
| `docs/reports/Phase11_2_4_B1_Code_Audit_Report.md` | ?? | C | 统计后端代码审计 | ✅ 是 | Phase 11.2.4-B1 |
| `docs/reports/Phase11_2_4_B1_Implementation_Report.md` | ?? | C | 统计后端实施 | ✅ 是 | Phase 11.2.4-B1 |
| `docs/reports/Phase11_2_4_B2_Implementation_Report.md` | ?? | C | Insights 前端实施 | ✅ 是 | Phase 11.2.4-B2 |
| `docs/reports/Phase11_2_4_C_Acceptance_Report.md` | ?? | C | Statistics + Insights 验收 | ✅ 是 | Phase 11.2.4-C |
| `docs/reports/Phase11_3_A_Investigation_Report.md` | ?? | C | Dashboard 收尾缺口调查 | ✅ 是 | Phase 11.3-A |
| `docs/reports/Phase11_3_B1_Implementation_Report.md` | ?? | C | 后端分类趋势 | ✅ 是 | Phase 11.3-B1 |
| `docs/reports/Phase11_3_B2_A_Investigation_Report.md` | ?? | C | 前端分类趋势调查 | ✅ 是 | Phase 11.3-B2-A |
| `docs/reports/Phase11_3_B2_B_Implementation_Report.md` | ?? | C | 前端分类趋势实施 | ✅ 是 | Phase 11.3-B2-B |
| `docs/reports/Phase11_3_C_Final_Closeout_Audit_Report.md` | ?? | C | 最终收尾审计（PASS WITH WARNINGS） | ✅ 是 | Phase 11.3-C |
| `docs/reports/Phase11_3_D_Documentation_Closeout_Report.md` | ?? | C | 文档收尾报告 | ⚠️ 条件 | **内容异常**：48 行 blockquote 摘要，非完整报告；见 §11.1 |

#### C-2 Phase 11 验收截图（12）

> 这些图片是 Phase 11.2.4-C 的历史验收证据。抽样检查显示为 mock demo 数据，未发现凭证字段；截图中的顶部/侧栏仍显示 `Phase 11.1` / `Phase 11.2`，属于 11.3-D 文案更新前的历史状态。

| 文件 | 状态 | 类别 | 变更目的 | 入 PR | 判断依据 |
|---|---|---|---|---|---|
| `docs/reports/assets/phase11_2_4_c/01-insights-default-day.png` | ?? | C | Insights 默认 DAY 截图 | ✅ 建议 | 11.2.4-C 验收证据；PNG |
| `docs/reports/assets/phase11_2_4_c/02-insights-weekly.png` | ?? | C | Weekly 截图 | ✅ 建议 | 同上 |
| `docs/reports/assets/phase11_2_4_c/03-insights-filter-owner.png` | ?? | C | Owner 筛选截图 | ✅ 建议 | 同上 |
| `docs/reports/assets/phase11_2_4_c/04-insights-unknown-values.png` | ?? | C | UNKNOWN 值截图 | ✅ 建议 | 同上 |
| `docs/reports/assets/phase11_2_4_c/05-insights-date-range.png` | ?? | C | 日期范围截图 | ✅ 建议 | 同上 |
| `docs/reports/assets/phase11_2_4_c/06-insights-sort-high-desc.png` | ?? | C | High 降序截图 | ✅ 建议 | 同上 |
| `docs/reports/assets/phase11_2_4_c/07-insights-empty.png` | ?? | C | 空状态截图 | ✅ 建议 | 同上 |
| `docs/reports/assets/phase11_2_4_c/08-insights-overview-initial-error.png` | ?? | C | Overview 初始错误截图 | ✅ 建议 | 同上 |
| `docs/reports/assets/phase11_2_4_c/09-insights-reviews-initial-error.png` | ?? | C | 对比表初始错误截图 | ✅ 建议 | 同上 |
| `docs/reports/assets/phase11_2_4_c/10-insights-refresh-error.png` | ?? | C | 刷新错误截图 | ✅ 建议 | 同上 |
| `docs/reports/assets/phase11_2_4_c/11-insights-narrow-390.png` | ?? | C | 390px 窄屏截图 | ✅ 建议 | 同上 |
| `docs/reports/assets/phase11_2_4_c/12-insights-narrow-navigation.png` | ?? | C | 窄屏导航截图 | ✅ 建议 | 同上 |

### 3.4 D — Phase 1–10 历史遗留文档（4）

| 文件 | 状态 | 类别 | 变更目的 | 入 PR | 判断依据 |
|---|---|---|---|---|---|
| `docs/reports/Phase10_Final_Merge_Gate_Report.md` | ?? | D | Phase 10 合并前最终门禁报告 | ❌ 否 | Phase 10 历史文档；与 Phase 11 无关 |
| `docs/reports/Phase10_Merge_Report.md` | ?? | D | Phase 10 PR #8 合并报告 | ❌ 否 | 同上 |
| `docs/reports/Phase10_PR_Review_Report.md` | ?? | D | Phase 10 PR 审查报告 | ❌ 否 | 同上 |
| `docs/reports/Phase10_Post_Merge_Verification_Report.md` | ?? | D | Phase 10 合并后验证报告 | ❌ 否 | 同上 |

说明：`docs/reports/Phase10_6_2_Report.md` 与 `docs/reports/Phase10_6_2_Supplementary_Audit.md` 已在 Git 中 tracked，不属于本次变更。上述 4 个 Phase 10 报告是未提交的历史文档，不应混入 Phase 11 PR。

### 3.5 E — 构建产物、缓存、临时文件（0 个进入变更清单）

以下项目存在于工作区，但被 ignore 或不属于变更清单，**不得进入 PR**：

| 路径/模式 | 状态 | 依据 |
|---|---|---|
| `frontend/node_modules/` | ignored | `frontend/.gitignore:10`；根 `.gitignore` 也新增 `node_modules/` |
| `frontend/dist/` | ignored | `frontend/.gitignore:12` |
| `backend/spring-service/target/` | ignored | 根 `.gitignore:8` |
| `*.tsbuildinfo` | ignored | `frontend/.gitignore:33` |
| `.eslintcache` | ignored | 根 `.gitignore` / `frontend/.gitignore:35` |
| `.env` | ignored | 根 `.gitignore:154`；本地存在但未 tracked |
| `secrets/` | ignored | 根 `.gitignore:164`；本地存在 2 个条目，未 tracked |
| `coverage/`、`logs`、`*.log` | ignored | 前端 `.gitignore` |

未发现数据库导出、`.dump`、`.bak`、`.zip`、`.7z`、IDE 本地配置或临时脚本进入变更清单。

### 3.6 F — 无法确认归属（0）

全部 142 个路径均可确认归属。`frontend/components.d.ts` 是自动生成文件，但归属明确为 Phase 11 前端，且被 `tsconfig.app.json` include；不属于“无法确认”。

---

## 4. 推荐进入 Phase 11 PR 的文件清单

### 4.1 推荐纳入

| 范围 | 数量 | 说明 |
|---|---:|---|
| A — Phase 11 功能与工程配置 | 80 | 后端 22 + 前端 53 + tracked 5 |
| B — Phase 11 测试 | 28 | 后端 10 + 前端 17 + tracked 1 |
| C — Phase 11 文档（暂排除异常 D 报告） | 29 | 15 份 Phase 11 报告 + 12 张截图 + README + DEVELOPMENT_STATUS |
| **小计（现有文件）** | **137** | 142 − 4 个 Phase 10 报告 − 1 个异常 D 报告 |
| 本审查报告 | 1 | `docs/reports/Phase11_Pre_PR_Audit_Report.md` |
| **推荐合计** | **138** | 若先重写 11.3-D 报告，则为 139 |

补充：

- 12 张截图属于推荐纳入的验收证据；如果仓库希望控制 PR 体积，可作为可选文件裁剪，此时推荐数量减少 12。
- 本审查报告本身是 Phase 11 文档；如果希望 PR 仅含实现与既有报告，也可在 PR 创建后单独提交，不影响代码合并。
- 若 11.3-D 报告在提交前被重写为完整报告，则应纳入，推荐数量变为 139。

### 4.2 关键纳入理由

1. **后端 22 个主代码文件**是六项目标的实际实现，且全部仅 GET、无写操作。
2. **前端 71 个文件**构成 Dashboard 的完整可运行应用；整个前端当前都是 untracked，不能只挑部分文件。
3. **测试 28 个文件**提供单元、Controller、安全过滤与 MySQL IT 证据；不提交会丢失回归保护。
4. **`components.d.ts`** 被 `tsconfig.app.json` include，且 `type-check` 不经过 Vite 插件生成它；提交可保证 fresh clone 可类型检查。
5. **`frontend/.gitkeep` 删除**必须与前端文件一起提交，否则会出现空占位残留。
6. **`application.yml` 的 forward-headers 配置**是 loopback 安全边界的一部分，必须与过滤器一起提交。
7. **`docs/DEVELOPMENT_STATUS.md`** 已记录 Phase 11 状态、六项目标和 P3；是 Phase 11 正式收尾文档。

---

## 5. 明确排除的文件清单

### 5.1 必须排除

| 文件 | 原因 |
|---|---|
| `docs/reports/Phase10_Final_Merge_Gate_Report.md` | Phase 10 历史文档，不属于 Phase 11 |
| `docs/reports/Phase10_Merge_Report.md` | 同上 |
| `docs/reports/Phase10_PR_Review_Report.md` | 同上 |
| `docs/reports/Phase10_Post_Merge_Verification_Report.md` | 同上 |

### 5.2 条件排除

| 文件 | 原因 | 处理建议 |
|---|---|---|
| `docs/reports/Phase11_3_D_Documentation_Closeout_Report.md` | 当前内容只有 48 行 blockquote 摘要，不是完整报告；见 §11.1 | 提交前重写为完整报告；否则从 PR 排除，后续单独补交 |

### 5.3 绝对不得进入 Git 的本地文件

- `.env`（本地存在，已 ignore）
- `secrets/`（本地存在，已 ignore；未读取内容）
- `frontend/.env` / `.env.local`（未发现；均 ignore）
- `node_modules/`、`dist/`、`target/`、`*.tsbuildinfo`、`.eslintcache`
- 日志、缓存、数据库导出、IDE 本地配置、临时文件

---

## 6. 无法确认归属的文件

**无。** 142 个路径均已映射到 A/B/C/D；E 类未进入变更清单；F 类为 0。

需要特别说明但不影响归属的文件：

- `frontend/components.d.ts`：自动生成，但被 `tsconfig.app.json` include，建议提交。
- `frontend/package-lock.json`：生成文件，但属于依赖锁定，建议提交；registry 混合问题见 §12.4。

---

## 7. 安全检查结果

### 7.1 敏感信息扫描

对 141 个现有变更文件（142 个路径中排除已删除的 `frontend/.gitkeep`）执行只读扫描：

| 检查项 | 结果 |
|---|---|
| 私钥头（`BEGIN ... PRIVATE KEY`） | 未发现 |
| GitHub Token / PAT 前缀 | 未发现 |
| `sk-` / `AKIA` / Slack token 前缀 | 未发现 |
| `password` / `secret` / `api_key` / `access_token` 的长字面量赋值 | 未发现 |
| URI 内嵌用户名/密码 | 未发现 |
| `REVIEW_HISTORY_INTERNAL_TOKEN`、`DEEPSEEK_API_KEY`、`GITHUB_PRIVATE_KEY` 等长字面量赋值 | 未发现 |
| `application.yml` 凭证属性 | 4 处均为环境变量占位符；未输出值 |
| `.env` / `.env.local` 进入变更清单 | 未发现 |
| 数据库导出 / `.dump` / `.bak` / `.zip` / `.7z` | 未发现 |
| 日志 / 缓存 / IDE 本地配置 | 未发现 |
| 大于 1 MB 的单文件 | 未发现 |

### 7.2 本地敏感目录

| 路径 | 状态 | 结论 |
|---|---|---|
| `.env` | 本地存在；`git check-ignore` 命中 `.gitignore:154` | 未 tracked；不得加入 PR |
| `secrets/` | 本地存在 2 个条目；`git check-ignore` 命中 `.gitignore:164` | 未 tracked；未读取内容；不得加入 PR |
| `frontend/.env.example` | 变更清单内 | 仅空 API base URL 与 localhost 代理目标；安全 |
| `frontend/.env` / `.env.local` | 不存在 | 无风险 |

### 7.3 图片资源

- 12 个文件均为 PNG magic bytes `89 50 4E 47 0D 0A 1A 0A`。
- 抽样查看 `01-insights-default-day.png`：显示 mock demo 仓库（`acme/sentinel-demo` 等）与统计界面，未发现凭证字段或真实用户数据。
- 未逐一视觉审查其余 11 张；它们均为 11.2.4-C 验收截图，建议在 PR 中标注为历史证据。
- 截图中的 UI 仍显示 `Phase 11.1` / `Phase 11.2`，这是 11.3-D 文案更新前的状态；不影响其作为 11.2.4-C 历史证据，但可能与当前 UI 不一致。

### 7.4 安全结论

**未发现需要阻止 PR 的敏感信息或不应提交的构建产物。** 本地 `.env` 与 `secrets/` 是本次审计最重要的“不要误提交”对象；当前 Git 状态显示它们已被 ignore 且未 tracked。

---

## 8. P3 技术债处理建议

判定标准：

- **阻断 PR**：是否导致六项目标缺失、核心链路断裂、安全边界可绕过、必须立即停止。
- **PR 前修复**：是否必须在提交前修改代码/数据库/测试。
- **可作为已知限制合并**：是否可在 PR 描述中披露后合并。
- **PR 披露**：是否应写入 PR 描述或已知限制。

| # | P3 事项 | 阻断 PR | PR 前修复 | 可作为已知限制合并 | PR 披露 | 建议 |
|---|---|---|---|---|---|---|
| A1 | `review_report.created_at` 缺少索引，统计查询可能全表扫描 | 否 | 否 | 是 | 是 | 后续迁移/性能评估；当前数据量小 |
| A2 | `/api/dashboard/statistics/reviews` Java 内存排序与分页 | 否 | 否 | 是 | 是 | 后续下推 SQL；大数据量前处理 |
| B1 | `ReviewStatisticsAcceptanceDbIT` 默认禁用 | 否 | 否 | 是 | 是 | 合并前可显式启用跑一次；不强制 |
| B2 | 真实 UI 第 2 页未验证 | 否 | 否 | 是 | 是 | 合并前手动翻页验证；或后续补 E2E |
| B3 | 生产构建产物浏览器 E2E 未验证 | 否 | 否 | 是 | 是 | 建议 `npm run build` + `preview` 做 smoke；非阻断 |
| B4 | 多浏览器/真实移动设备未验证 | 否 | 否 | 是 | 是 | 后续补兼容性验证 |
| B5 | 仓库尚无 CI 自动回归 | 否 | 否 | 是 | 是 | 后续单独建设 CI |
| B6 | 真实 GitHub PR E2E、Publisher → History → Query 接缝 E2E 未验证 | 否 | 否 | 是 | 是 | 继承 Phase 9/10 验证债；不阻断 Dashboard PR |
| C1 | 范围条显示时间省略微秒 | 否 | 否 | 是 | 可选 | 后续 UI 精度打磨 |
| C2 | History Controller 缺少通用异常兜底 | 否 | 否 | 是 | 是 | 后续统一错误契约；Spring 默认错误不泄露堆栈 |
| C3 | 首页尚未展示真实动态统计摘要 | 否 | 否 | 是 | 可选 | 设计上允许静态摘要；非阶段阻断 |
| D1 | B1 排序 tie-breaker 与早期设计示例存在差异 | 否 | 否 | 是 | 是 | 作为契约说明保留 |
| D2 | History `commitSha` 数据来源与早期设计示例不同 | 否 | 否 | 是 | 是 | 作为数据来源说明保留 |
| D3 | SQL `NOT IN` 对 `NULL` 的处理需关注 | 否 | 否 | 是 | 是 | 当前 DDL 为 `NOT NULL`；外部导入前处理 |
| D4 | SQL 枚举比较与 Java 状态判断大小写语义需统一 | 否 | 否 | 是 | 是 | 后续契约统一 |
| D5 | 验收数据库 URL 未限制 host/port | 否 | 否 | 是 | 是 | 默认禁用且只读；启用 CI 前加固 |
| D6 | 早期报告错误响应字段与测试计数口径差异 | 否 | 否 | 是 | 是 | 文档修正；以 C 报告 46/538 为准 |

补充发现（不属于原 17 项 P3）：

| # | 事项 | 阻断 PR | PR 前修复 | 可作为已知限制合并 | PR 披露 | 建议 |
|---|---|---|---|---|---|---|
| X1 | 11.3-D 报告内容异常（48 行摘要，非完整报告） | 否（代码） | **是（若纳入）** | 条件性 | 是 | 重写或排除；不得把摘要当完整报告提交 |
| X2 | 测试文案耦合：`DashboardLayout.spec.ts:50` 断言 `Phase 11.1`，`DashboardView.spec.ts:54` 断言 `Phases 1–10 complete` | 否 | 否 | 是 | 是 | 后续统一文案时同步更新测试 |
| X3 | `package-lock.json` 同时使用 `registry.npmjs.org` 与 `registry.npmmirror.com` | 否 | 建议确认 | 是 | 是 | 确认镜像策略；必要时用官方 registry 重新生成 lockfile |
| X4 | 12 张验收截图显示 11.3-D 更新前的 `Phase 11.1` / `Phase 11.2` 文案 | 否 | 否 | 是 | 建议 | 作为历史证据保留并标注，或重新截图 |
| X5 | `docs/DEVELOPMENT_WORKFLOW.md` §13 仍停留在 2026-10-11 / Phase 8 状态 | 否 | 否 | 是 | 可选 | 不在本 PR 范围；后续单独更新 |

**结论：没有 P3 需要阻断 Phase 11 PR。** 但 X1 是文档纳入条件；A1/A2/B1–B6/D5 应在 PR 描述中明确披露。

---

## 9. 测试证据核对

### 9.1 本次 Pre-PR 审计实际执行

| 项目 | 本次是否执行 | 说明 |
|---|---|---|
| Backend unit tests | ❌ 未执行 | 只读审计，未运行 Maven |
| MySQL integration tests | ❌ 未执行 | 未连接数据库 |
| Frontend unit tests | ❌ 未执行 | 未运行 Vitest |
| Type-check | ❌ 未执行 | 未运行 `vue-tsc` |
| Lint | ❌ 未执行 | 未运行 oxlint/eslint |
| Build | ❌ 未执行 | 未运行 Vite build |
| Browser E2E | ❌ 未执行 | 未启动浏览器 |
| GitHub E2E | ❌ 未执行 | 未触发真实 PR |

本审计的结论基于历史证据与源码/文件核对，不把历史执行表述为本次执行。

### 9.2 历史证据

| 项目 | 执行阶段/时间 | 结果 | 证据 |
|---|---|---|---|
| Backend unit tests | Phase 11.3-C，2026-11-15 | 46 个 suite / 538 个测试，0 失败 / 0 错误 / 0 跳过 | C 报告 §6.5、§9.1 |
| MySQL IT（继承） | 2026-11-14 failsafe 产物 | 10 个 suite / 77 个测试，0 失败 / 0 错误 / 12 跳过 | C 报告 §9.3 |
| `ReviewStatisticsAcceptanceDbIT` 显式启用 | B1 阶段 | 12/12 通过 | B1 报告；C 报告 §9.3 |
| Frontend unit tests | Phase 11.3-D，2026-11-15 | 16 个测试文件 / 150 个测试通过 | 11.3-D 摘要；B2-B 报告 |
| Type-check | Phase 11.3-D | 通过 | 11.3-D 摘要 |
| Lint | Phase 11.3-D | 通过（oxlint + eslint） | 11.3-D 摘要 |
| Build | Phase 11.3-D | 通过，1758 modules，生成 `dist` | 11.3-D 摘要 |
| Browser E2E | 11.2.4-C / 11.3-B2-B | 通过；Vite dev server、Chrome/CDP、390×844 模拟 | C 报告 §9.4 |
| GitHub E2E | 从未执行 | NOT VERIFIED | C 报告；DEVELOPMENT_STATUS |

### 9.3 默认跳过与未覆盖

| 事项 | 状态 | 说明 |
|---|---|---|
| `ReviewStatisticsAcceptanceDbIT` | 默认跳过 | 仅 `-Dcodesentinel.acceptance.db=true` 时运行；failsafe 中 12 项跳过 |
| `ReviewStatisticsMySqlIT` / `ReviewHistoryListMySqlIT` | 默认不随 `mvn test` 执行 | 需要 `-Pmysql-it` / failsafe |
| 真实 UI 第 2 页 | NOT VERIFIED | 历史证据只覆盖第 1 页 |
| 生产构建浏览器 E2E | NOT VERIFIED | 历史 E2E 使用 Vite dev server |
| 多浏览器 / 真实移动设备 | NOT VERIFIED | 只有 Chrome + 视口模拟 |
| 真实 GitHub PR 全链路 | NOT VERIFIED | Phase 11 读取已持久化数据，不走 Webhook/AI/评论 |

### 9.4 建议 PR 前补跑

至少：

```bash
cd backend/spring-service
mvn test

cd ../../frontend
npm run type-check
npm run lint:check
npm run test:unit
npm run build
```

可选：

```bash
cd backend/spring-service
mvn -Pmysql-it verify
```

如需更高证据等级，再补生产构建 `npm run preview` 浏览器 smoke 与第 2 页验证。不要为了“全绿”清理测试报告或删除默认跳过项。

---

## 10. 与历史报告/当前源码的差异

| 事项 | 历史报告/资料 | 当前实际 | 处理 |
|---|---|---|---|
| 11.3-D 报告内容 | 任务期望完整 12 节报告 | 实际仅 48 行 blockquote 摘要（2,355 bytes），首行为 `> Phase 11.3-D 文档收尾已完成...`，无完整文件清单/Git 前后对比/P3 明细 | **不修改**；建议提交前重写或排除（X1） |
| 11.3-D 报告事实 | 摘要声称状态文档、README、Vue 文案已更新 | 已逐项核对，事实与源码一致 | 摘要可作为线索，但不能替代完整报告 |
| 11.3-C 报告 §16 | 审计时写“六项仍未勾选、Phase 11 尚未启动” | 当前 `DEVELOPMENT_STATUS.md` 已全部勾选并写“实现与验收完成、未提交/未合并” | C 报告是历史快照，不是当前缺陷 |
| B1 测试计数 | 47 suites / 543 tests | 干净聚合为 46 suites / 538 tests | 以 C 报告 46/538 为准；陈旧 surefire 文件导致 47/543 |
| 前端测试计数 | B2-B 150 | 11.3-D 复跑仍为 16 文件 / 150 测试 | 一致 |
| 首页路线图 | 曾显示 `Quality insights — 11.3` | 当前已移除，仅保留 `Custom rules — 12` | 一致 |
| 布局/导航 Phase 文案 | 曾显示 `Phase 11.1` / `Phase 11.2` | 当前已改为 `Dashboard` / `Available` / `Phase 11.1–11.3 delivered` | 一致；测试仍保留旧字符串断言（X2） |
| README 图表说明 | 曾称 ECharts 未安装、无图表 | 当前称原生 SVG/CSS、无 ECharts 依赖 | 一致 |
| `DEVELOPMENT_WORKFLOW.md` §13 | 仍写 2026-10-11 / Phase 8 进行中 | 当前已到 Phase 11 | 历史文档未更新；不在本 PR 变更范围（X5） |
| 验收截图 | 12 张 11.2.4-C 截图 | 截图中仍显示 `Phase 11.1` / `Phase 11.2` | 历史证据；建议标注或重拍（X4） |

---

## 11. 重点发现

### 11.1 11.3-D 报告内容异常（必须处理）

当前文件：

```text
docs/reports/Phase11_3_D_Documentation_Closeout_Report.md
```

实际状态：

- 大小：2,355 bytes
- 行数：48
- 内容：整篇为 `>` 引用的摘要，首行为 `> Phase 11.3-D 文档收尾已完成，并已停在验证与报告阶段。`
- 缺少：修改文件清单、逐文件具体修改、完整 P3 登记、Git before/after、未执行操作、剩余事项等完整报告结构。

核对结果：

- 摘要中的事实（DEVELOPMENT_STATUS 六项勾选、README 修正、首页/导航文案、前端四项验证、Git 58/135 计数）与当前源码/状态基本一致。
- 但它是“摘要”，不是 11.3-D 任务要求的完整报告；不能作为正式收尾报告提交。

建议：

1. 在提交前重写为完整报告；或
2. 暂时从 Phase 11 PR 排除，后续单独补交。

本审计不修改该文件。

### 11.2 整个前端均为 untracked

`frontend/` 下 71 个文件全部未 tracked。这意味着：

- Phase 11 PR 必然是一个包含完整前端应用的大 PR；
- 不能只提交 `src/` 而遗漏 `package.json`、`package-lock.json`、`tsconfig`、`vite.config.ts` 等；
- `components.d.ts` 必须纳入，否则 fresh clone 的类型检查可能缺声明；
- `frontend/.gitkeep` 删除应与前端文件一起提交。

### 11.3 Phase 10 历史报告混在工作区

4 个 `Phase10_*` 报告仍未提交。它们不是 Phase 11 变更，**不应进入 Phase 11 PR**。如果希望保留，应另开文档 PR 或在后续维护中单独处理。

### 11.4 本地 `.env` 与 `secrets/`

两者均存在且被 ignore，不在变更清单。提交前应再次确认 `git status` 不包含它们；不得为了“完整”而强制添加。

---

## 12. PR 风险与建议

### 12.1 风险等级

| 风险 | 等级 | 说明 | 建议 |
|---|---|---|---|
| 11.3-D 报告内容异常 | 中（文档） | 不是完整报告；若提交会降低 PR 文档质量 | 重写或排除 |
| PR 体积大 | 中 | 142 个现有路径 + 报告；前端 71 个文件；截图约 4.8 MB | 接受为 Phase 11 收尾 PR；可选裁剪截图 |
| 整个前端首次提交 | 中 | review 负担大；遗漏配置会导致不可构建 | 按 §4 清单整体提交；提交前 fresh clone 验证 |
| Phase 10 报告混入 | 低-中 | 范围污染 | 明确排除 4 个文件 |
| P3 未修复 | 低 | 已有登记；不阻断 | PR 描述披露 |
| 无 CI | 低-中 | 只能依赖本地验证 | 合并前手动跑全量；后续补 CI |
| E2E 缺口 | 中 | 生产构建/多浏览器/GitHub E2E 未验证 | 披露；可选补 smoke |
| package-lock 混合 registry | 低-中 | 可能影响其他环境安装 | 确认镜像策略或重新生成 |
| 截图与当前 UI 不一致 | 低 | 历史截图显示旧 Phase 文案 | 标注为历史证据或重拍 |
| 测试文案耦合 | 低 | 未来改文案需同步测试 | 登记 P3 |

### 12.2 PR 描述建议披露

```text
- Phase 11 Dashboard: PASS WITH WARNINGS (6/6 goals)
- P3 known limitations: created_at index, in-memory stats sorting/paging,
  acceptance DB IT disabled by default, no CI, production-build E2E not run,
  multi-browser/mobile not verified, GitHub E2E not run
- Real GitHub PR E2E and Publisher → History → Query E2E remain NOT VERIFIED
- Local .env / secrets are not part of this PR
- Phase 10 reports are intentionally excluded
- 11.3-D report status: rewritten / excluded (choose one)
```

### 12.3 建议提交顺序

1. 先处理 11.3-D 报告（重写或排除）。
2. 确认 `git status` 不含 `.env`、`secrets/`、`dist`、`node_modules`、`target`、`*.tsbuildinfo`。
3. 将 A/B/C 文件按清单加入暂存区；排除 D 类 4 个 Phase 10 报告。
4. 提交到 `phase11/dashboard`。
5. 推送并创建 PR（需用户明确授权；本阶段不执行）。
6. PR 描述写入 P3、验证缺口与排除项。

### 12.4 package-lock registry 说明

`frontend/package-lock.json` 的 `resolved` URL 同时出现：

```text
registry.npmjs.org
registry.npmmirror.com
```

未发现 `_authToken`、`_auth`、`npmAuth` 或密码字段；`token` 命中仅为 `@csstools/css-tokenizer` 包名。该混合 registry 可能影响其他环境的可复现安装。建议确认项目是否允许 npmmirror；如不允许，应在提交前用官方 registry 重新生成 lockfile（本审计不修改）。

---

## 13. 是否具备进入 PR 准备阶段

### 13.1 结论

**CONDITIONAL GO — 有条件具备。**

代码、测试与文件归属已经足够支持进入 PR 准备阶段；但必须先完成以下条件，才能提交/创建 PR。

### 13.2 必须满足的条件

| # | 条件 | 状态 |
|---|---|---|
| 1 | 重写 11.3-D 报告，或从 PR 排除 | ⬜ 待处理 |
| 2 | 排除 4 个 Phase 10 历史报告 | ⬜ 待处理 |
| 3 | 确认 `.env` / `secrets/` / `dist` / `node_modules` / `target` 不进入暂存区 | ⬜ 待确认 |
| 4 | 确认 `components.d.ts` 纳入、`frontend/.gitkeep` 删除纳入 | ⬜ 待确认 |
| 5 | PR 描述披露 P3 与验证缺口 | ⬜ 待编写 |
| 6 | 提交前补跑 backend `mvn test` 与 frontend 四项检查 | ⬜ 建议执行 |
| 7 | 确认 package-lock registry 策略 | ⬜ 待确认 |

### 13.3 完成条件后的预期

- PR 纳入 138 个现有 Phase 11 文件（或重写 D 报告后 139 个）+ 本审查报告。
- Phase 10 的 4 个报告不进入 PR。
- 不包含任何本地敏感文件或构建产物。
- PR 描述明确 PASS WITH WARNINGS、P3、未验证项与排除项。
- 代码合并后，Phase 11 正式关闭；Phase 12 另行启动。

---

## 14. 最终只读复核

本报告创建后应再次执行：

```bash
git status --short --branch
git diff --stat
git diff --name-status
git branch --show-current
git rev-parse HEAD
git rev-list --left-right --count main...HEAD
git ls-files --others --exclude-standard | Measure-Object
```

预期：

- 分支仍为 `phase11/dashboard`；
- HEAD 仍为 `27e3a41161cfa86ee2956ba0b3626a2bcc71eec7`；
- `main...HEAD` 仍为 `0 0`；
- tracked 仍为 6 modified + 1 deleted；
- untracked 从 135 个文件增加到 136 个文件（仅新增本报告）；
- 除本报告外，没有新的文件变化。

> **Phase 11 实现与验收完成（PASS WITH WARNINGS，6/6），但当前仍未提交、未创建 PR、未合并 `main`；Phase 12 尚未开始。本报告不构成 PR 创建、提交或合并授权。**
