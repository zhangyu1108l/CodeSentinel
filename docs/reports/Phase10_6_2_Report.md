# Phase 10.6.2 真实 MySQL 集成测试报告

> 实施日期：2026-11-05
> 分支：`feature/phase10-mysql-history`
> HEAD：`ccfaecc23b5340d0a7a8d012f283b59020e345c0`

---

## 1. 实施范围

本阶段仅新增测试代码、test-scope Maven 依赖和测试专用 Maven profile，没有修改生产代码、Entity、Repository、Controller、`application.yml`、`review_history.sql` 或 `review_result_delivery.sql`。

### 新增测试文件

```text
backend/spring-service/src/test/java/cn/codesentinel/review/
├── ReviewHistoryMySqlTestBase.java
├── ReviewHistoryMySqlMappingIT.java
├── ReviewHistoryMySqlConstraintIT.java
├── ReviewHistoryMySqlWriteIT.java
├── ReviewHistoryMySqlQueryIT.java
└── ReviewHistoryMySqlConcurrencyIT.java
```

### Maven 变更

`backend/spring-service/pom.xml`：

- 新增 test-scope 依赖：
  - `org.testcontainers:testcontainers-junit-jupiter:2.0.3`
  - `org.testcontainers:testcontainers-mysql:2.0.3`
- 新增属性：
  - `testcontainers.version=2.0.3`
- 新增 `mysql-it` Maven profile：
  - 使用 `maven-failsafe-plugin`
  - 匹配 `**/*IT.java`
  - 通过 `mvn -Pmysql-it verify` 执行集成测试

Testcontainers 1.20.6 在 Docker 29.6.2 上出现 `/info` 400，升级到 2.0.3 后 Testcontainers 可正常识别 Docker Desktop。测试运行前需要设置当前环境的 Docker endpoint：

```powershell
$env:DOCKER_HOST = 'npipe:////./pipe/dockerDesktopLinuxEngine'
mvn -Pmysql-it verify
```

该设置仅用于 Docker 连接，不读取或复用 `.env` 中的 `codesentinel` 数据库配置。

---

## 2. 测试环境

| 项目 | 值 |
|---|---|
| 测试数据库 | Testcontainers 临时 MySQL 容器 |
| 容器内数据库名 | `codesentinel_it` |
| 镜像 | `mysql:8.0.46` |
| 实际服务端版本 | `8.0.46`（每个测试前断言） |
| JDBC URL | Testcontainers 动态提供 |
| 初始化脚本 | `classpath:db/review_history.sql` |
| 测试表 | 仅 `review_report`、`review_finding`、`review_comment` |
| `review_task` / `review_result_delivery` | 不创建、不写入 |
| 真实 GitHub API | 不调用 |
| 当前 `codesentinel` 数据库 | 不作为测试目标 |

测试基类使用：

```java
@DataJpaTest(properties = {
        "spring.jpa.hibernate.ddl-auto=none",
        "spring.jpa.properties.hibernate.generate_statistics=true"
})
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Import({ReviewHistoryService.class, ReviewHistoryQueryService.class})
@Transactional(propagation = Propagation.NOT_SUPPORTED)
```

`NOT_SUPPORTED` 是必要的：`ReviewHistoryService` 的 Repository 调用必须拥有独立事务，才能验证唯一键冲突后的新事务重读。

Testcontainers 容器采用 JVM 级单例启动，避免多个 IT 类之间 Spring TestContext 缓存复用旧 JDBC URL；Ryuk 在 JVM 退出时清理容器。

---

## 3. 测试模块与结果

### 3.1 JPA 真实映射：7 项通过

文件：`ReviewHistoryMySqlMappingIT.java`

覆盖：

- `CHAR(40)`：40 字符 SHA round-trip，真实列类型 `char(40)`；
- `DATETIME(6)`：`123456` 微秒保存/读取一致，`DATETIME_PRECISION=6`；
- `TEXT`：60KB references_json 与 NULL round-trip，真实列类型 `text`；
- `DOUBLE`：confidence round-trip，真实列类型 `double`；
- `EnumType.STRING`：`PublishStatus.PARTIAL` round-trip，`varchar(20)`；
- nullable `github_comment_id`：NULL 读取正常，多行 NULL 可共存；
- 字段长度/NULL：`rule_id=255`、`title=1000`、`file_path=1024`，NOT NULL/可空属性一致。

### 3.2 唯一约束：5 项通过

文件：`ReviewHistoryMySqlConstraintIT.java`

覆盖：

- `review_report.task_id` 重复 → 唯一键冲突；
- `review_finding(report_id, ordinal)` 重复 → 唯一键冲突；
- `review_comment(report_id, finding_ordinal)` 重复 → 唯一键冲突；
- 非 NULL `github_comment_id` 重复 → 唯一键冲突；
- 多个 NULL `github_comment_id` → 允许共存。

唯一键冲突均断言 MySQL **1062 / SQLState 23000**。

### 3.3 历史写入：8 项通过

文件：`ReviewHistoryMySqlWriteIT.java`（H1–H8）

覆盖：

- `ensureHistory` 创建 report/findings，`finding_count` 正确；
- `ensurePublishHistory` 仅为 PUBLISHED 项创建 comment；
- PUBLISHED 但 commentId=null → `github_comment_id` NULL；
- FAILED/SKIPPED 不创建 comment；
- summary-only → `summary_comment_id` 写入，`published_comment_count` 不含 summary；
- summary id fill-only，`published_at` 不被 null 清空；
- 空 findings/comments 可表示；
- `published_at` microsecond round-trip。

### 3.4 幂等与自愈：8 项通过

文件：`ReviewHistoryMySqlWriteIT.java`（I1–I8）

覆盖：

- 重复 `ensureHistory` 不重复创建 report/finding，已有行 ID/createdAt 不变；
- 手工删除一个 finding 后再次 `ensureHistory` 只补缺失 ordinal；
- 已有 report 的 `commit_sha` 不一致 → 安全失败、零新增；
- 重复 `ensurePublishHistory` 不重复创建 comment；
- 已有 comment 身份不一致 → 失败且不覆盖；
- 并发 `ensureHistory` → 最终一条 report + 完整 findings；
- 并发 `ensurePublishHistory` → 最终一套 comments，report count/status 收敛；
- 目标 ordinal 不存在时发生 `github_comment_id` 唯一冲突 → 原始异常重抛；先成功的 comment 保留、report 不提前更新。

### 3.5 查询/分页/references：12 项通过

文件：`ReviewHistoryMySqlQueryIT.java`

覆盖：

- detail 字段、任务上下文、三种状态；
- findings 默认分页、第二页、size=100；
- `ordinal ASC` 排序；
- comments 分页、`findingOrdinal ASC`、NULL github id；
- 超末页返回空页且元数据正确；
- 空 findings/comments；
- findings/comments 计数与 report 不一致 → `ReviewHistoryIncompleteException`；
- references 含 null 元素、NULL/空数组；
- 非法 references JSON / 非数组 → `ReviewHistoryDataIntegrityException`，不泄露原始 JSON；
- PENDING 发布状态；
- Hibernate Statistics 验证 findings 分页查询数量有界（≤4），未出现 N+1。

### 3.6 事务与并发：3 项独立测试通过

文件：`ReviewHistoryMySqlConcurrencyIT.java`

覆盖：

- `@@transaction_isolation` = `REPEATABLE-READ`；
- 两个 REPEATABLE READ 事务：第一个事务读取后，另一个事务插入 finding，第一个事务再次读取仍保持旧快照；
- 读者与 `ensureHistory` 自愈并发：读者只会看到 409（未完成）或完整 2 条 findings，不会看到 total/items 不一致的部分结果。

此外，`ReviewHistoryMySqlWriteIT` 中的 I6/I7/I8 覆盖并发 `ensureHistory`、并发 `ensurePublishHistory` 及失败后数据状态：

- T4（读者 + ensureHistory 自愈并发）= `ReviewHistoryMySqlConcurrencyIT#t3ReaderNeverObservesPartialFindingsDuringSelfHeal`；
- T5（ensurePublishHistory 中途失败 + 重试收敛）= 新增的 `ReviewHistoryMySqlWriteIT#t5EnsurePublishHistoryMidFailureRetainsCommittedCommentAndRetryConverges`；
- T6（唯一键冲突后新事务重读）= U1–U4 + I6/I8；
- T7（事务失败后的数据状态）= I8，真实数据库断言已加强。

### 3.7 T5 中途失败与重试收敛：1 项通过

文件：`ReviewHistoryMySqlWriteIT.java`

方法：

```text
t5EnsurePublishHistoryMidFailureRetainsCommittedCommentAndRetryConverges
```

故障注入方式：

- 测试专用 `ReviewCommentRepository` 动态代理包裹真实 Repository；
- 第一次 comment `saveAndFlush` 委托真实 MySQL 并提交；
- 第二次 comment `saveAndFlush` 在代理层抛出非唯一键的 `DataIntegrityViolationException`；
- 不使用触发器、不修改表结构、不使用 Mockito 替代真实 Repository。

失败后断言：

- 第一条 comment（ordinal 0、id 600、src/File0.java）真实存在；
- 第二条 comment 不存在；
- report 仍为 PENDING，`published_comment_count=0`、`summary_comment_id=null`、`published_at=null`。

解除故障后再次执行 `ensurePublishHistory`：

- 两条 comment 均存在（ordinal 0/1，id 600/601）；
- report 收敛为 `PARTIAL`、`published_comment_count=2`、`published_at` 复制成功。

---

## 4. MySQL 实际验证证据

- Testcontainers 容器实际服务端版本：`8.0.46`（测试基类每个测试前断言）；
- `CHAR(40)`：`information_schema.COLUMNS.COLUMN_TYPE = char(40)`；
- `DATETIME(6)`：`DATETIME_PRECISION = 6`，微秒 round-trip 通过；
- `references_json`：`TEXT`，60KB 文本与 NULL round-trip 通过；
- `confidence`：`DOUBLE` round-trip；
- `publish_status`：`VARCHAR(20)` + `EnumType.STRING`；
- 多个 NULL `github_comment_id` 可共存；
- 非 NULL 重复 `github_comment_id` 被 MySQL 1062 拒绝；
- `REPEATABLE-READ` 隔离级别与跨事务快照行为通过；
- 并发自愈最终收敛，无重复 report/finding/comment。

---

## 5. 完整测试结果

### 集成测试（mysql-it profile）

```text
mvn -Pmysql-it verify
```

| 测试类 | 数量 | 结果 |
|---|---:|---|
| `ReviewHistoryMySqlMappingIT` | 7 | PASS |
| `ReviewHistoryMySqlConstraintIT` | 5 | PASS |
| `ReviewHistoryMySqlWriteIT` | 17 | PASS |
| `ReviewHistoryMySqlQueryIT` | 12 | PASS |
| `ReviewHistoryMySqlConcurrencyIT` | 3 | PASS |
| **合计** | **44** | **Failures 0 / Errors 0 / Skipped 0** |

### 单元测试

```text
mvn test
Tests run: 428, Failures: 0, Errors: 0, Skipped: 0
BUILD SUCCESS
```

`mvn -Pmysql-it verify` 同时执行了 428 个单元测试和 44 个集成测试，全部通过。

### 并发稳定性

- `ReviewHistoryMySqlConcurrencyIT` 3 项在单独运行和全量 `mysql-it` 运行中均通过；
- `ReviewHistoryMySqlWriteIT` 的 I6/I7 并发用例在单独运行和全量运行中均通过；
- 未观察到不稳定的并发测试结果；并发用例使用 `CountDownLatch`/`CompletableFuture` 式等待，无 `sleep` 猜测调度。

---

## 6. 当前 codesentinel 数据库只读复核

测试完成后通过只读 SELECT 查询当前真实数据库：

```text
review_task              8
review_result_delivery   3
review_report            0
review_finding           0
review_comment           0
```

当前 `codesentinel` 数据库未被测试写入，结构未变化。

---

## 7. 数据隔离与清理

- 所有测试写入仅在 Testcontainers 临时 MySQL 容器内；
- 容器数据库为 `codesentinel_it`；
- 只初始化 `review_history.sql` 的三张历史表；
- 不创建/不写入 `review_task`、`review_result_delivery`；
- `ReviewTaskService` 使用 mock，合成 task ID 从 `9_000_000_000L` 起，不使用现有 task ID 1–8；
- 不调用 `ReviewResultPublishService`，不触发 GitHub API；
- 测试类 `@BeforeEach` 只清理临时容器中的 comments → findings → reports；
- Testcontainers 容器由 Ryuk 在 JVM 退出时销毁；
- 没有退化到本机 MySQL、`codesentinel_it` 专用 schema 或当前 `codesentinel` 数据库。

---

## 8. 遗留风险

### L-1 保留

`ReviewHistoryService` 捕获 `DataIntegrityViolationException` 后通过重读确认并发赢家；真实唯一键 1062 / SQLState 23000 已验证，但“非唯一键 DIV 可能被误吞”的 L-1 风险仍未关闭。

本阶段未通过以下方式处理 L-1：

- 未修改生产表结构；
- 未添加触发器/约束；
- 未按错误码收窄异常；
- 未修改生产代码。

该风险留给后续独立阶段处理。

### 其他限制

- Testcontainers 环境依赖 Docker Desktop 的 `npipe:////./pipe/dockerDesktopLinuxEngine`，需要在运行命令前设置 `DOCKER_HOST`；
- Testcontainers 2.0.3 为本项目新增测试依赖；1.20.6 与 Docker 29.6.2 的 `/info` 握手不兼容；
- `review_result_delivery` 既有的 `received_at`/`published_at` 为 `DATETIME`（0 精度），本阶段未改动该表，也未将其纳入新表精度断言；
- 并发测试验证了可观察的一致性状态，但不对外部 GitHub 发布链路做真实验证；
- 未进入 Phase 10.6.3。

---

## 9. Git 状态

```text
分支: feature/phase10-mysql-history
HEAD: ccfaecc23b5340d0a7a8d012f283b59020e345c0
已跟踪修改: 7（原 6 个 Phase 10.3–10.5 修改 + pom.xml 测试依赖/profile）
未跟踪文件: 38（原 30 + 6 个新测试文件 + 本报告 + 补充审计报告）
```

本阶段未提交、未推送、未合并；未 reset/clean/checkout；未修改 Phase 10.2–10.5 已有实现。

---

## 10. 结论

Phase 10.6.2 真实 MySQL 集成测试已完成：

- 44 项集成测试全部通过；
- 428 项既有单元测试全部通过；
- 真实 MySQL 8.0.46 的 CHAR(40)、DATETIME(6)、TEXT、DOUBLE、EnumType.STRING、唯一键、多 NULL、REPEATABLE-READ、并发自愈、T5 中途失败与重试收敛、T7 真实失败状态均已验证；
- 当前 `codesentinel` 数据库的既有数据与三张历史空表保持不变；
- L-1 保留，不扩大本阶段范围。

**Phase 10.6.2 测试实施完成，等待 ChatGPT 审查。**