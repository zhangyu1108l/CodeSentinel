# Phase 11.2.2-B.1 Report — Review History 质量收尾

> 执行日期：2026-11-12
> 分支：`phase11/dashboard`
> 起始 HEAD：`27e3a41161cfa86ee2956ba0b3626a2bcc71eec7`
> 阶段：Phase 11.2.2-B.1
> 依据：Phase 11.2.2-B 最终只读审计结论（PASS，6 个非阻断 WARN）

---

## 1. 结论

本次仅处理 Phase 11.2.2-B 最终审计中的 6 个非阻断 WARN，不扩展功能。

| WARN | 状态 | 处理结果 |
|---|---|---|
| P1 空页丢失分页入口 | **已修复** | 当 `items.length === 0` 且 `totalItems > 0` 时仍显示分页 |
| P2 Refresh / Retry 不清除旧筛选错误 | **已修复** | `loadReviews()` 开始时清除 `filterError`，筛选条件保持不变 |
| P3 仓库名 / Commit SHA 截断 | **已修复** | 仓库名增加 `title`；Commit SHA 原有 `title` 已保留并验证 |
| T1 旧请求 `finally` 竞态测试不足 | **已补强** | 新增用例验证旧请求结算不会清除新请求 Loading |
| T2 清空筛选测试未验证 page size | **已补强** | 先切换到 size=50 和第 2 页，再清空筛选并断言 |
| T3 null 字段无 UI 测试 | **已补强** | 新增 `summaryCommentId=null`、`publishedAt=null` 用例 |

**总体结果：6/6 WARN 已处理，无新增 FAIL，未引入新依赖。**

---

## 2. 修改文件

| 文件 | 修改内容 |
|---|---|
| `frontend/src/views/ReviewHistoryView.vue` | P1 分页位置与空状态文案；P2 清除旧筛选错误；P3 仓库名 `title` |
| `frontend/src/__tests__/ReviewHistoryView.spec.ts` | 新增 / 补强 T1、T2、T3、P1、P2、P3 相关测试与断言 |
| `docs/reports/Phase11_2_2_B_1_Report.md` | 本报告 |

未修改：

- 后端代码
- API 契约
- `DashboardLocalAccessFilter`
- Phase 10 代码与报告
- `docs/DEVELOPMENT_STATUS.md`
- `frontend/components.d.ts`（构建后内容未变化）
- 任何已有依赖

---

## 3. UI 修复详情

### P1：空页时保留分页入口

**文件**：`frontend/src/views/ReviewHistoryView.vue`

**修改**

1. 分页组件从表格专用的 `<template v-else>` 中移出，改为独立渲染：

```vue
<div
  v-if="!initialLoading && !errorMessage && totalItems > 0"
  class="pagination-row"
>
  ...
</div>
```

2. 真正的 Empty 状态保持原行为：当 `totalItems === 0` 时不渲染分页。
3. 当 `items.length === 0 && totalItems > 0` 时，Empty 状态文案改为：

```text
No reviews on this page
```

真正的空列表仍显示：

```text
No reviews match the current filters
```

**效果**

- 空页但仍有总记录时，分页组件仍可用。
- 用户可以通过页码 / 上一页 / 下一页返回有效页。
- 未新增 `watch`、轮询或自动重试逻辑，不会产生无限自动请求。
- `totalItems` / `totalPages` / `size` 变化会自然驱动 `el-pagination` 重新计算页数；页码变化继续走现有 `handlePageChange` 与 `requestSequence` 保护。

---

### P2：Refresh / Retry 清除旧筛选错误

**文件**：`frontend/src/views/ReviewHistoryView.vue`

**修改**

在 `loadReviews()` 开始时清空 `filterError`：

```ts
loading.value = true
errorMessage.value = ''
filterError.value = ''
```

`loadReviews()` 同时被 Refresh、Retry、分页、筛选应用等路径复用，因此：

- Refresh / Retry 会清除已经过期的筛选错误。
- 当前筛选表单值不会被修改。
- 原有 `AbortController`、`requestSequence`、`finally` 保护未改变。

---

### P3：完整显示仓库名和 Commit SHA

**文件**：`frontend/src/views/ReviewHistoryView.vue`

**修改**

为仓库名增加原生 `title`，截断时可通过悬停查看完整值：

```vue
<span
  class="repo-name"
  :title="`${row.owner}/${row.repo}`"
>
  {{ row.owner }}/{{ row.repo }}
</span>
```

Commit SHA 在当前工作区中已存在：

```vue
<code class="commit-sha" :title="row.commitSha">
```

本次保留并验证该属性，未引入 Element Plus Tooltip 或新依赖，表格布局与响应式行为不变。

---

## 4. 新增与补强测试

**文件**：`frontend/src/__tests__/ReviewHistoryView.spec.ts`

### T1：旧请求 `finally` 不得清除新请求 Loading

**用例名**：

```text
keeps the newer request loading when a stale request settles
```

**断言步骤**

1. 第一个请求保持 pending。
2. 提交筛选条件，发起第二个请求。
3. 第二个请求也保持 pending。
4. 断言第一个请求已被 abort。
5. resolve 第一个请求（旧请求）。
6. 断言：

```text
aria-busy === "true"
.history-loading 仍存在
.history-table 不存在
```

7. resolve 第二个请求。
8. 断言：

```text
aria-busy === "false"
.history-loading 消失
.history-table 出现
页面显示第二个请求的 #21
```

**验证目标**

如果删除 `finally` 中的：

```ts
sequence === requestSequence
```

旧请求结算后会错误地把新请求的 `loading` 置为 `false`，该测试会失败。

---

### T2：清空筛选保留 page size

**用例名**：

```text
clears every filter, keeps the page size, and reloads from page 1
```

**断言步骤**

1. 初始加载为 page=1、size=20。
2. 修改 page size 为 50。
3. 切换到第 2 页。
4. 设置 `owner=acme`、`taskStatus=FAILED` 并提交。
5. 点击 Clear filters。
6. 断言最后一次请求参数为：

```text
page=1, size=50
```

7. 断言 owner 输入框已清空。
8. 断言页面进入 Empty 状态。

该测试现在能够验证：

- 清空筛选后页码重置为 1。
- 清空筛选后 page size 保持 50，而不是回退到默认 20。
- 筛选条件确实被清除。

---

### T3：null 字段显示

**用例名**：

```text
renders placeholders for null summary and published timestamp
```

**构造数据**

```ts
summaryCommentId: null
publishedAt: null
```

**断言**

```text
Summary Comment 显示 No summary
Published At 显示 —
页面不出现字符串 null
页面无错误状态
表格正常渲染
```

---

### 额外覆盖：P1 / P2 / P3

| 用例 / 断言 | 覆盖点 |
|---|---|
| `keeps pagination available when an empty page still has total items` | 当前页 5、`totalPages=3`、`totalItems=45` 且 items 为空时分页仍存在；点击第 1 页可重新加载并显示表格 |
| `renders an empty state when no reviews match` 增加分页不存在断言 | 真正的 `totalItems=0` Empty 状态不被分页影响 |
| `clears a stale filter error on reload and keeps the filters` | 非法时间范围错误在 Refresh 后消失，owner 输入值保留 |
| 正常渲染用例增加 `title` 断言 | `.repo-name` 的 title 为 `owner/repo`；`.commit-sha` 的 title 为完整 SHA |

---

## 5. 完整验证结果

### 5.1 `npm run type-check`

```text
> codesentinel-dashboard@0.1.0 type-check
> vue-tsc --build
```

**通过。**

### 5.2 `npm run lint:check`

```text
> codesentinel-dashboard@0.1.0 lint:check
> oxlint . && eslint .
```

**通过。**

### 5.3 `npm run test:unit`

```text
Test Files  7 passed (7)
Tests       46 passed (46)
```

**通过。**

测试数量由审计时的 42 个增加到 46 个：

- 新增 P1 空页分页用例
- 新增 P2 旧筛选错误清除用例
- 新增 T1 旧请求 `finally` 竞态用例
- 新增 T3 null 字段用例
- T2 清空筛选用例补强
- P3 `title` 断言补入现有渲染用例

### 5.4 `npm run build`

```text
> npm run type-check && npm run build-only
> vite build
✓ 1725 modules transformed.
✓ built in 600ms
```

**通过。**

构建生成 `frontend/dist/`，该目录未被 Git 跟踪，未出现在 `git status` 中。
`frontend/components.d.ts` 构建前后内容一致，未发生内容变化，未手动恢复或删除。

### 5.5 `git diff --check`

```text
warning: in the working copy of '.gitignore', LF will be replaced by CRLF the next time Git touches it
```

无 whitespace error；仅存在既有的 `.gitignore` 换行提示。

---

## 6. Git 状态

### 6.1 分支与 HEAD

```text
branch: phase11/dashboard
HEAD:   27e3a41161cfa86ee2956ba0b3626a2bcc71eec7
```

HEAD 未变化。

### 6.2 工作区

修复前已有的修改和未跟踪文件全部保留，包括：

- `.gitignore` 修改
- 后端 Phase 11.2.2-A 相关修改与新增文件
- `docs/DEVELOPMENT_STATUS.md` 既有修改
- Phase 10 报告
- `frontend/.gitkeep` 删除状态
- `frontend/` 未跟踪文件

本次新增：

```text
?? docs/reports/Phase11_2_2_B_1_Report.md
```

`frontend/components.d.ts` 未被删除、恢复或改写内容。
`frontend/dist/` 为构建产物，已被忽略。

### 6.3 Git 写操作

未执行：

```text
git commit
git push
git merge
git rebase
git reset
git checkout
```

---

## 7. 尚存限制

1. **未执行真实浏览器 E2E**
   本次未启动 Spring Boot + MySQL 并在浏览器中完整走查 `/reviews`。分页空页、tooltip 悬停和响应式布局仍建议作为人工验收项。

2. **P1 的视觉表现依赖 Element Plus 分页组件**
   功能测试已覆盖“空页仍显示分页”和“点击有效页可返回”，但不同 `totalPages` / 当前页组合下的具体高亮与按钮状态，建议人工快速确认。

3. **窄屏视觉未人工验证**
   表格列较多，仓库名 / commit SHA 截断与 tooltip 的实际显示效果建议在浏览器中确认。

4. **`DashboardLayout.vue` 仍显示 Phase 11.1 标签**
   该问题在审计前已存在，不属于本次 B.1 修复范围。

5. **构建产物未提交**
   `frontend/dist/` 为本地构建输出，未纳入 Git；`components.d.ts` 内容未变化。

---

## 8. 验收状态

Phase 11.2.2-B.1 的 6 个 WARN 已全部处理，验证命令全部通过。

**等待人工验收，未进入 Review Detail 或统计图表阶段。**
