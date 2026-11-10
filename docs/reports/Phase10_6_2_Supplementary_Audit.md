# Phase 10.6.2 补充审查报告

> 审查日期：2026-11-05
> 范围：`Phase10_6_2_Report.md` 中 T4/T5/T7 的测试覆盖映射
> 本轮未修改代码、测试、配置、DDL；未执行数据库写入；仅新增本审计报告。

---

## 1. 结论汇总

| 项目 | 状态 | 结论 |
|---|---|---|
| T4：读者与 `ensureHistory` 自愈并发 | **PARTIAL** | 实际存在读写并发测试，但报告把 T4 错误映射到 I6（两个写线程），映射不准确 |
| T5：`ensurePublishHistory` 中途失败与重试收敛 | **FAIL** | 没有符合要求的中途失败测试；I8 只是唯一键冲突，且没有重试收敛验证 |
| T7：事务失败后的数据状态 | **PASS（范围有限）** | I8 在真实 MySQL 中验证了先提交 comment、后续失败、report 未更新；未验证重试收敛 |

报告中“T4/T5/T7 分别由 I6/I7/I8 覆盖”的说法不准确：

- T4 = I6 **错误**：I6 是两个写线程的并发 `ensureHistory`；
- T5 = I7 **错误**：I7 是两个写线程的并发成功 `ensurePublishHistory`；
- T7 = I8 **正确**，但 I8 也是 T5 的失败场景，不能反过来替代 T5。

---

## 2. T4：读者与 ensureHistory 自愈并发 — PARTIAL

### 实际测试位置

文件：

```text
backend/spring-service/src/test/java/cn/codesentinel/review/ReviewHistoryMySqlConcurrencyIT.java
```

方法：

```java
t3ReaderNeverObservesPartialFindingsDuringSelfHeal()
```

行号：约 L84–L128。

### 并发协调方式

- 使用 `ExecutorService.newFixedThreadPool(2)`；
- 使用一个 `CountDownLatch start` 同时放行 writer 和 reader；
- writer 执行：
  ```java
  historyService.ensureHistory(task, delivery);
  ```
- reader 执行 20 次：
  ```java
  queryService.getFindings(taskId, 1, 20);
  ```
- 没有使用 `CyclicBarrier` 强制 reader 在 writer 的中间事务点读取；只有起始 latch。

### 读者执行的查询

reader 调用真实 `ReviewHistoryQueryService.getFindings(taskId, 1, 20)`：

- 真实 MySQL 查询 `review_report` / `review_finding`；
- `ReviewTaskService` 是 mock，只提供合成 task；
- 其他部分均为真实 Repository/数据库。

### 如何验证完整 200 或 409

reader 对每次查询：

- 捕获 `ReviewHistoryIncompleteException`（对应 409 安全失败）；
- 如果返回 200，则断言：
  ```java
  assertEquals(2, page.totalItems());
  assertEquals(2, page.items().size());
  ```
- 因此任何 200 的部分结果（例如 total=2 但 items=1）都会失败；
- writer 和 reader 都结束后，再查询一次，断言最终为 2/2。

### 与报告描述的差异

报告中：

- 3.6 节确实描述了“读者与 ensureHistory 自愈并发”；
- 但随后把 **T4 映射为 I6**；
- I6 实际是 `ReviewHistoryMySqlWriteIT#i6ConcurrentEnsureHistoryCreatesOneReportAndCompleteFindings`，是两个 writer 的并发，不是 reader/writer。

所以：

- **实际 T4 场景覆盖：PASS**（由上述 `t3ReaderNeverObserves...` 覆盖）；
- **报告映射：FAIL**；
- **综合状态：PARTIAL**。

### 测试强度限制

现有 T4 测试使用起始 latch，没有使用 barrier 精确保证 reader 一定在 writer 的中间状态读取；并发交错依赖调度。
但它确实同时启动真实 reader/writer，并且对任何 200 结果做完整性断言，不是“两个写线程冒充读写并发”。

---

## 3. T5：ensurePublishHistory 中途失败 — FAIL

### 报告中的错误映射

`Phase10_6_2_Report.md` 将：

```text
T5（并发 ensurePublishHistory）= I7
```

这是错误的。

`ReviewHistoryMySqlWriteIT#i7ConcurrentEnsurePublishHistoryCreatesOneCommentSet`（L347–L366）：

- 两个线程并发调用 `ensurePublishHistory`；
- 两个线程都成功；
- 断言最终 1 条 comment、report count=1；
- 没有制造任何中途失败，也不是失败后重试测试。

### 实际最接近的测试

`ReviewHistoryMySqlWriteIT#i8DuplicateGithubIdWithMissingTargetOrdinalRethrows`（L369–L401）：

1. 另一个 report 已有 `github_comment_id=501`；
2. target report + 2 findings 已存在；
3. outcome 有两条 PUBLISHED：
   - 第一条 id=600；
   - 第二条 id=501；
4. `ensurePublishHistory` 先成功插入第一条 comment；
5. 第二条 comment 插入触发 `github_comment_id` 唯一键冲突；
6. 捕获 DIV 后重读 target report/ordinal，发现 ordinal 1 不存在，原异常重抛；
7. 断言 target report 仍为 PENDING，target comment 数为 1。

### 为什么这不能算 T5

用户要求 T5 是：

- `ensurePublishHistory` 中途失败；
- 失败前后 report/finding/comment 的实际状态；
- **后续重试是否能够收敛**。

I8：

- 唯一失败原因是**唯一键冲突**；
- 用户已明确：**“如果只是测试唯一键冲突，不算覆盖 T5”**；
- 没有失败后的重试调用；
- 没有证明修复冲突/故障后再次执行能够收敛；
- 没有覆盖非唯一键的 Repository/数据库中途失败。

因此：

- **T5：FAIL**；
- 报告中的 `T5 = I7` 是错误映射；
- I8 只能作为 T7 的失败状态证据，不能替代 T5。

### 建议补充

新增专用 T5 测试（未来独立授权）：

- 使用 Testcontainers 真实 MySQL；
- 通过测试专用故障注入（非生产代码、非生产表结构）让 `ensurePublishHistory` 在第二条 comment 写入时失败；
- 断言第一条 comment 已提交、report 未更新；
- 移除故障后使用修正后的 delivery/outcome 重试；
- 断言最终 comments/report 收敛；
- 不使用真实 GitHub。

---

## 4. T7：事务失败后的数据状态 — PASS（范围有限）

### 实际测试位置

`ReviewHistoryMySqlWriteIT#i8DuplicateGithubIdWithMissingTargetOrdinalRethrows`（L369–L401）。

### 已成功提交的 Repository 操作

在 target task 上：

1. `ensureHistory` 已成功提交：
   - target `review_report`；
   - target 2 条 `review_finding`；
2. `ensurePublishHistory` 的第一条 comment：
   - `ReviewComment(report_id=target, finding_ordinal=0, github_comment_id=600)`；
   - 通过 `commentRepository.saveAndFlush` 独立事务提交；
3. 第二条 comment 尚未成功。

### 异常发生点

第二条 comment：

```text
finding_ordinal=1, github_comment_id=501
```

与另一个 report 的已有 comment 发生全局唯一键冲突：

- MySQL 1062 / SQLSTATE 23000；
- `insertCommentSafely` 捕获 DIV；
- 新一次查询 target report 的 comments 只找到 ordinal 0，没有 ordinal 1；
- 重抛原始 `DataIntegrityViolationException`；
- `ensurePublishHistory` 的 report 更新代码未执行。

### 真实数据库验证

异常之后，测试使用真实 Repository 查询：

```java
ReviewReport targetReport = reportRepository
        .findByTaskId(targetTaskId).orElseThrow();
assertEquals(PublishStatus.PENDING, targetReport.getPublishStatus());
assertEquals(1, commentRepository
        .findByReportIdOrderByFindingOrdinalAsc(targetReport.getId())
        .size());
```

因此：

- 第一条 comment 在真实 MySQL 中仍然存在（数量 1）；
- target report 仍为 PENDING，说明 report 更新未提交；
- 不是 mock 断言，而是真实数据库事务结果。

### 限制

T7 的 PASS 是**范围有限**的：

- 只覆盖唯一键冲突导致的失败；
- 未断言 `published_comment_count=0`；
- 未断言第一条 comment 的具体 ID/字段；
- 未验证失败后的重试收敛（这属于 T5，不属于 T7）。

**T7：PASS（范围有限）。**

---

## 5. 镜像版本

### 当前配置

`ReviewHistoryMySqlTestBase.java`：

```java
new MySQLContainer<>("mysql:8.0")
```

测试基类在每个测试前执行：

```java
assertEquals("8.0.46",
        jdbcTemplate.queryForObject("SELECT VERSION()", String.class));
```

### 实际情况

- 本地镜像 tag：`mysql:8.0`；
- 实际运行的 Testcontainers MySQL：8.0.46；
- 当前生产容器也使用同一镜像 ID；
- 测试会因版本不等于 8.0.46 而失败，因此不会静默使用其他版本。

### 建议

建议后续将测试镜像固定为：

```java
new MySQLContainer<>("mysql:8.0.46")
```

或使用 `DockerImageName.parse("mysql:8.0.46")`。

理由：

- `mysql:8.0` 是浮动 tag，未来可能随镜像更新漂移；
- 当前测试的版本断言能发现漂移，但会把“镜像拉取/更新”问题变成测试失败；
- 固定 8.0.46 与当前真实环境一致，可复现性更好。

本轮**不修改**该配置；需要用户批准后在测试代码中调整。

---

## 6. 报告描述与实际覆盖的差异汇总

| 报告描述 | 实际代码 | 差异 |
|---|---|---|
| T4 = I6 | I6 是两个 writer 并发 `ensureHistory` | 错误；T4 实际由 `t3ReaderNeverObserves...` 覆盖 |
| T5 = I7 | I7 是两个 writer 并发成功 `ensurePublishHistory` | 错误；I7 不包含中途失败 |
| T5 已由 I8 覆盖 | I8 是唯一键冲突中途失败 | 不满足 T5；用户明确要求唯一键冲突不算覆盖 |
| T7 = I8 | I8 真实 MySQL 失败状态 | 正确，但范围有限 |
| “T4/T5/T7 分别由 I6/I7/I8 覆盖” | 仅 T7 映射正确 | T4/T5 映射需修正 |

---

## 7. 是否需要后续修复

### 必须修复

1. **修正 `Phase10_6_2_Report.md` 的 T4/T5/T7 映射**
   - T4 → `ReviewHistoryMySqlConcurrencyIT#t3ReaderNeverObservesPartialFindingsDuringSelfHeal`；
   - T5 → **没有合格测试**，删除 `T5=I7` 的表述；
   - T7 → I8（保留，注明范围有限）。

2. **补充 T5 专用测试**
   - 必须是非唯一键的中途失败 + 失败后重试收敛；
   - 不能只用 I8 的唯一键冲突替代。

### 建议修复

3. 将测试镜像固定到 `mysql:8.0.46`；
4. 为 T7 增加 `published_comment_count=0` 和第一条 comment 具体字段断言；
5. T4 可考虑用 `CyclicBarrier` 或测试钩子增强交错确定性，但当前读写并发测试已存在。

---

## 8. Git 状态

本审计只读检查，未修改现有代码、测试、配置或 DDL。
唯一新增交付物是本报告文件；未提交、未推送、未 reset/clean/checkout。

```text
分支: feature/phase10-mysql-history
HEAD: ccfaecc23b5340d0a7a8d012f283b59020e345c0
```

**总结（原始审计时点）：T4 PARTIAL，T5 FAIL，T7 PASS（范围有限）。**

---

## 9. 补充实施更新（2026-11-05）

> 本节记录后续补充实施结果，不覆盖上述原始审计结论与过程。

### T5：已补充并通过

新增：

```text
ReviewHistoryMySqlWriteIT
  └── t5EnsurePublishHistoryMidFailureRetainsCommittedCommentAndRetryConverges
```

故障注入机制：

- 测试专用 `ReviewCommentRepository` 动态代理包裹真实 Repository；
- 第一次 comment 的 `saveAndFlush` 委托真实 MySQL 并提交；
- 第二次 comment 的 `saveAndFlush` 在代理层抛出非唯一键的 `DataIntegrityViolationException`；
- 不使用唯一键冲突、触发器、表结构变更或 Mockito 替代真实 Repository。

失败后真实数据库状态：

- 第一条 comment（ordinal=0、github_comment_id=600、src/File0.java）存在；
- 第二条 comment 不存在；
- target report 仍为 PENDING，`published_comment_count=0`、`summary_comment_id=null`、`published_at=null`。

解除故障后重试：

- 两条 comment 均存在（ordinal 0/1，id 600/601）；
- report 收敛为 PARTIAL，`published_comment_count=2`，`published_at` 正确。

**T5 当前状态：PASS。**

### T4：报告映射已修正

`Phase10_6_2_Report.md` 已改为：

```text
T4 = ReviewHistoryMySqlConcurrencyIT
     #t3ReaderNeverObservesPartialFindingsDuringSelfHeal
```

不再把 T4 映射到 I6（两个写线程）。
实际测试仍是真实 reader/writer 并发；原始审计指出的映射问题已修正。

### T7：断言已加强

I8 现在额外断言：

- target report `published_comment_count=0`；
- `summary_comment_id=null`；
- `published_at=null`；
- 已提交 comment 的 ordinal=0、github_comment_id=600、file_path=src/File0.java、行号 10/10。

**T7 当前状态：PASS（范围仍限于真实唯一键冲突失败状态）。**

### 镜像版本

测试镜像已固定为：

```java
new MySQLContainer<>("mysql:8.0.46")
```

保留每个测试前的 `SELECT VERSION()` = `8.0.46` 断言。

### 最新测试结果（Phase 10.6.2 补充审计时点快照，历史记录，非当前状态）

> 以下 428 unit / 44 IT 是 Phase 10.6.2 补充审计时点的历史数字，不是当前状态。
> 当前测试数量请以 `docs/DEVELOPMENT_STATUS.md` 为准。

```text
mvn -Pmysql-it verify
Tests run: 428 (unit) + 44 (integration)
Failures: 0, Errors: 0, Skipped: 0
BUILD SUCCESS
```

`mvn test`：428/428 通过。

### 当前 Git 状态（Phase 10.6.2 补充审计时点快照，历史记录，非当前状态）

> 以下 7 tracked / 38 untracked 是 Phase 10.6.2 补充审计时点的历史快照，不是当前状态。
> 当前 Git 状态请以 `docs/DEVELOPMENT_STATUS.md` 为准。

```text
分支: feature/phase10-mysql-history
HEAD: ccfaecc23b5340d0a7a8d012f283b59020e345c0
已跟踪修改: 7
未跟踪文件: 38
```

补充实施未修改生产代码、Entity、Repository、Controller、`application.yml`、`review_history.sql` 或 `review_result_delivery.sql`；未连接当前 codesentinel 执行写操作；未调用 GitHub；未提交/推送。