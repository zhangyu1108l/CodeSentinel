# Phase 11.2.2-B Report — Review History 前端列表

> 执行日期：2026-11-12  
> 分支：`phase11/dashboard`  
> 起始 HEAD：`27e3a41161cfa86ee2956ba0b3626a2bcc71eec7`  
> 阶段：Phase 11.2.2-B（Review History 列表页面）

---

## 1. 实现功能

- 将 `/reviews` 占位页面替换为真实的 Review History 列表页面。
- 通过现有 Axios API client 调用同源 Dashboard BFF：
  - `GET /api/dashboard/reviews`
- 支持服务端分页：
  - 默认 `page=1`、`size=20`
  - 可选每页条数：`10 / 20 / 50 / 100`
  - 展示总数、页码、上一页/下一页。
- 支持全部已实现筛选条件：
  - `owner`
  - `repo`
  - `prNumber`
  - `taskStatus`
  - `aiStatus`
  - `publishStatus`
  - `createdFrom`
  - `createdTo`
- 展示后端真实返回的全部字段：
  - `taskId`
  - `owner`
  - `repo`
  - `prNumber`
  - `commitSha`
  - `taskStatus`
  - `aiStatus`
  - `publishStatus`
  - `findingCount`
  - `publishedCommentCount`
  - `summaryCommentId`
  - `publishedAt`
  - `createdAt`
  - `updatedAt`
- 实现页面状态：
  - 首次加载：Loading 骨架屏
  - 后续刷新/翻页：保留当前列表，显示 “Updating review history…” 提示
  - 空列表：Empty 状态
  - 请求失败：Error 状态 + Retry
  - 手动刷新：Refresh
- 请求竞态与取消：
  - 每次请求创建独立 `AbortController`
  - 新请求发起时中止旧请求
  - 使用递增请求序号忽略过期响应
  - 组件卸载时中止在途请求并阻止卸载后的状态更新
- 清除筛选：
  - 清空全部筛选条件
  - 回到第 1 页
  - 保留当前每页条数
  - 立即重新加载。
- 适配现有 `DashboardLayout` 与响应式断点：
  - 筛选区 `4 → 3 → 2 → 1` 列
  - 窄屏操作按钮换行
  - 表格横向滚动，保留全部字段
  - 分页区域可换行/横向滚动。
- 同步更新了少量已过时的界面文案：
  - Dashboard 的 Review History 卡片由 “Planned” 改为 “Available”
  - 侧边栏提示由 “Review history integration” 改为 “Review history is live”
  - frontend README 中的安全边界与范围说明。

未实现（按要求排除）：

- Review Detail
- Finding Statistics
- Security / Bug / Performance / Quality Trends
- Pinia
- ECharts
- 任何新依赖
- Phase 11.3 功能

---

## 2. API 调用方式

### 2.1 请求

使用现有 `src/api/client.ts` 中的 Axios 实例与 `apiGet`，新增
`src/api/review-history.ts`：

```text
GET /api/dashboard/reviews?page=1&size=20&owner=acme&repo=sentinel&prNumber=42
    &taskStatus=COMPLETED&aiStatus=DEGRADED&publishStatus=PARTIAL
    &createdFrom=2026-01-01T00:00:00&createdTo=2026-02-01T23:59:59
```

参数构造规则：

- `page`、`size` 始终发送。
- 可选字符串筛选先 `trim()`；空字符串不发送。
- `prNumber` 仅在为正整数时发送。
- 状态枚举传后端定义的精确值：
  - `taskStatus`: `PENDING | RUNNING | COMPLETED | FAILED`
  - `aiStatus`: `COMPLETED | DEGRADED`
  - `publishStatus`: `PENDING | PUBLISHED | PARTIAL | FAILED`
- 时间筛选格式为后端 `LocalDateTime` 可直接解析的：
  - `YYYY-MM-DDTHH:mm:ss`
- 日期范围选择器通过 `value-format="YYYY-MM-DD[T]HH:mm:ss"` 保证输出不含时区偏移。

### 2.2 响应

页面按真实响应契约使用：

```json
{
  "items": [
    {
      "taskId": 7,
      "owner": "owner",
      "repo": "repo",
      "prNumber": 42,
      "commitSha": "abc123...",
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
  ],
  "page": 1,
  "size": 20,
  "totalItems": 1,
  "totalPages": 1,
  "hasNext": false
}
```

### 2.3 错误处理

沿用现有 `toApiError` / `getErrorMessage`：

- 网络错误、超时、取消、HTTP 错误统一为 `ApiError`。
- 后端 `400 {"error":"invalid_filter"}` / `{"error":"invalid_pagination"}`
  以及 `500 {"error":"internal_error"}` 均通过现有错误归一化处理。
- 页面只展示归一化后的安全消息，不展示原始响应体或堆栈。

### 2.4 安全边界

- 仅请求相对路径 `/api/dashboard/reviews`。
- 不调用 `/api/reviews/**`。
- 不读取、不发送、不保存 `X-Internal-Token`。
- 不使用 `localStorage` / `sessionStorage` / Cookie 保存令牌。
- 未修改后端接口、安全过滤器或 Phase 10 代码。

---

## 3. 页面展示效果

### 3.1 页头

- Eyebrow：`Reviews`
- 标题：`Review History`
- 说明：浏览已存储的审查报告、AI 状态与 GitHub 发布结果。
- 右侧：
  - 当前总条数徽标
  - 加载时切换为 `Loading`
  - Refresh 按钮

### 3.2 筛选面板

一行/多行响应式筛选区：

- Owner
- Repository
- Pull request（数字输入，最小 1）
- Task status
- AI status
- Publish status
- Created at（日期时间范围）

操作：

- `Apply filters`：应用筛选并回到第 1 页
- `Clear filters`：清空筛选并重新加载
- 时间范围倒置时在本地显示错误，不发请求

### 3.3 结果区

- 首次加载显示 7 行骨架屏。
- 空结果显示 Empty 插图与说明：
  - `No reviews match the current filters`
  - 有筛选条件时提供 `Clear filters`
  - 无筛选条件时提供 `Refresh`
- 错误状态显示：
  - `Unable to load review history`
  - 归一化错误消息
  - `Retry`
- 正常状态显示表格：

| 列 | 内容 |
|---|---|
| Review | `#taskId`、完整 `commitSha`（超长省略，悬停显示完整值） |
| Repository | `owner/repo`、`PR #prNumber` |
| Task status | 状态 Tag |
| AI status | 状态 Tag |
| Publish status | 状态 Tag |
| Findings | `findingCount` |
| Comments | `publishedCommentCount`、`Summary #summaryCommentId` |
| Published | `publishedAt` |
| Created | `createdAt` |
| Updated | `updatedAt` |

- 表格下方为分页：
  - 总数
  - 每页条数选择
  - 上一页 / 页码 / 下一页

### 3.4 响应式

- `> 1180px`：筛选 4 列
- `≤ 1180px`：筛选 3 列
- `≤ 900px`：筛选 2 列
- `≤ 640px`：
  - 筛选 1 列
  - 页头操作换行
  - 错误操作换行
  - 分页左对齐
- 表格在窄屏保持全部列，通过横向滚动查看。

---

## 4. 修改文件

### 新增

- `frontend/src/api/review-history.ts`
  - Review History API 模块、参数构造、端点常量。
- `frontend/src/__tests__/ReviewHistoryView.spec.ts`
  - 页面交互、状态、分页、筛选、竞态、卸载取消测试。
- `frontend/src/__tests__/review-history-api.spec.ts`
  - API 参数构造与响应解析测试。
- `docs/reports/Phase11_2_2_B_Report.md`
  - 本报告。

### 修改

- `frontend/src/views/ReviewHistoryView.vue`
  - 占位页替换为真实列表页面。
- `frontend/src/types/api.ts`
  - 新增 Review History 类型、状态枚举联合类型、查询类型。
- `frontend/src/api/client.ts`
  - `apiGet` 增加可选查询参数；更新安全边界注释。
- `frontend/src/api/index.ts`
  - 导出 Review History API。
- `frontend/src/__tests__/App.spec.ts`
  - mock `getReviewHistory`；将占位页断言改为真实空状态断言。
- `frontend/src/views/DashboardView.vue`
  - Review History 卡片状态与文案同步；
  - 移除已完成的 Review History explorer 路线图条目。
- `frontend/src/components/SidebarNav.vue`
  - 侧边栏提示文案同步。
- `frontend/README.md`
  - 更新目录、安全边界与 Phase 11.2.2-B 范围说明。
- `frontend/components.d.ts`
  - 由 `unplugin-vue-components` 在构建时自动更新，新增
    `ElDatePicker`、`ElInput`、`ElInputNumber`、`ElOption`、`ElPagination`、
    `ElSelect`、`ElTable`、`ElTableColumn`、`ElTag` 等声明。

未新增 npm 依赖，未修改 `package.json` / `package-lock.json`。

---

## 5. 测试结果

执行目录：`frontend/`

| 命令 | 结果 |
|---|---|
| `npm run type-check` | ✅ 通过（`vue-tsc --build`） |
| `npm run lint:check` | ✅ 通过（`oxlint . && eslint .`） |
| `npm run test:unit` | ✅ 7 个测试文件 / 42 项测试全部通过 |
| `npm run build` | ✅ 通过（1725 modules transformed，产物生成成功） |

新增测试覆盖：

- 正常加载列表并展示全部字段。
- Loading 状态。
- Empty 状态。
- API 错误状态。
- Retry。
- 翻页。
- 修改每页条数并回到第 1 页。
- 多条件筛选（owner/repo/prNumber/taskStatus/aiStatus/publishStatus/createdFrom/createdTo）。
- 清除筛选。
- 快速切换筛选时的请求竞态：
  - 旧请求被 abort
  - 旧响应晚到不会覆盖新结果。
- 组件卸载时取消在途请求。
- API 端点、参数构造、空值省略、响应解析。

说明：本轮没有启动 Spring Boot + MySQL 做浏览器端真实联调；页面行为通过契约核对与 mock API 单元测试验证。

---

## 6. Git 状态

- 当前分支：`phase11/dashboard`
- 当前 HEAD：`27e3a41161cfa86ee2956ba0b3626a2bcc71eec7`
- 未执行：`commit`、`push`、`merge`、`rebase`、`reset`、`checkout`
- `frontend/` 下文件仍整体处于未跟踪状态（与 Phase 11.1/11.2.2-A 当前工作区状态一致）。

保留的既有状态：

- `docs/DEVELOPMENT_STATUS.md` 的既有修改未触碰。
- `docs/reports/Phase10_*.md` 既有未跟踪报告未触碰。
- `.gitignore` 既有修改未触碰。
- `frontend/.gitkeep` 的删除状态保留。
- 后端 Phase 11.2.2-A 相关修改/未跟踪文件未触碰。
- `frontend/components.d.ts` 仅由构建工具自动生成更新。

本阶段新增的报告文件：

```text
docs/reports/Phase11_2_2_B_Report.md
```

---

## 7. 已知限制

1. 未执行真实后端联调  
   本轮未启动 Spring Boot/MySQL，也未在浏览器中连接真实
   `/api/dashboard/reviews`。接口字段、参数、枚举和错误格式已按当前后端代码核对，
   但建议人工验收时启动后端做一次真实数据加载。

2. 筛选为精确匹配  
   与后端 `ReviewHistoryFilter` 一致，`owner`、`repo` 为精确匹配，不支持模糊搜索。

3. 筛选与分页状态未同步到 URL  
   刷新页面会回到默认筛选与第 1 页；本阶段未引入路由 query 同步。

4. 窄屏表格采用横向滚动  
   为保证展示全部后端字段，移动端未改为卡片列表，需要横向滚动查看宽表。

5. 时间显示不做时区转换  
   后端返回 `LocalDateTime` 字符串，前端仅将 `T` 替换为空格并去除小数秒，
   保持后端本地时间语义。

6. DashboardLayout 阶段标识仍为 Phase 11.1  
   本次未修改 `DashboardLayout.vue` 的头部/侧边栏阶段徽标，属于后续统一文案整理范围。

7. Dashboard BFF 仍为应用层 loopback 边界  
   该限制属于 Phase 11.2.2-A 后端设计；若通过同主机反向代理暴露 Dashboard，
   代理层必须自行提供认证。

---

## 8. 遗留问题

- 建议人工验收时补充一次真实后端浏览器联调：
  - 准备含 `review_report` 数据的本地 MySQL
  - 启动 Spring Boot
  - 启动 `npm run dev`
  - 验证真实分页、筛选、空状态与错误状态。
- `DashboardLayout` 的 Phase 11.1 徽标与页脚可在后续阶段统一更新。
- 本阶段不包含 Review Detail、Finding Statistics、趋势图和 Phase 11.3 内容。

除上述验证与文案项外，未发现阻塞 Phase 11.2.2-B 验收的功能问题。

---

## 9. 结论

Phase 11.2.2-B 已完成：

- `/reviews` 已从占位页变为可用的 Review History 列表。
- 分页、全部筛选条件、真实字段展示、Loading/Empty/Error/Retry 均已实现。
- 请求竞态与组件卸载取消已实现并有测试覆盖。
- 安全边界保持不变，前端不接触内部令牌。
- 类型检查、Lint、单元测试、生产构建全部通过。

等待人工验收，未提交、未推送、未合并。
