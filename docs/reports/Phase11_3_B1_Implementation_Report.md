# Phase 11.3-B1 实施报告 — 后端分类趋势扩展

> 阶段：Phase 11.3-B1（Backend Category Trend Extension）  
> 分支：`phase11/dashboard`  
> 基线 HEAD：`27e3a41161cfa86ee2956ba0b3626a2bcc71eec7`  
> 实施日期：2026-11-14  
> 实施范围：仅后端统计趋势 API 与相关测试  
> 实施结论：**后端分类趋势已实现并通过单元测试、真实 MySQL 集成测试、只读验收库集成测试；等待审查。**  
> 本阶段未进入 Phase 11.3-B2，未修改前端，未更新 `docs/DEVELOPMENT_STATUS.md`。

---

## 1. 实施目标

在 Phase 11.1–11.2.4 已交付的 Dashboard 统计能力基础上，仅扩展后端趋势 API：

1. 在现有 Review / Finding 时间序列的每个趋势点中增加：
   - `bugCount`
   - `securityCount`
   - `performanceCount`
   - `qualityCount`
   - `unknownCategoryCount`（现有 Summary 已包含 UNKNOWN 分类，因此同步支持）
2. 保持原有字段、类型、统计口径、DAY/WEEK 分桶、零填充、时区、范围限制和空范围行为不变。
3. 分类趋势必须与 `summary.categoryCounts` 使用完全相同的统计范围和完整性规则。
4. 为后续 Phase 11.3-B2 前端独立分类趋势图提供稳定的 additive API。
5. 只允许后端实施，不修改前端、数据库结构、Phase 10 代码或既有文档。

---

## 2. 实施前工作区基线

### 2.1 Git 基线

实施开始前记录：

```text
分支：phase11/dashboard
HEAD：27e3a41161cfa86ee2956ba0b3626a2bcc71eec7
main..HEAD：0
已修改（tracked）：6
已删除（tracked）：1
未跟踪条目（git status 折叠后）：53
```

已修改文件：

```text
.gitignore
backend/spring-service/src/main/java/cn/codesentinel/review/ReviewHistoryQueryService.java
backend/spring-service/src/main/java/cn/codesentinel/task/ReviewReportRepository.java
backend/spring-service/src/main/resources/application.yml
backend/spring-service/src/test/java/cn/codesentinel/CodeSentinelApplicationTests.java
docs/DEVELOPMENT_STATUS.md
```

已删除文件：

```text
frontend/.gitkeep
```

上述修改、删除和全部未跟踪内容均为本任务开始前已存在的工作区状态。本任务未执行任何 Git 写操作，未清理、恢复或覆盖它们。

### 2.2 报告文件名核对

任务清单中列出的：

```text
docs/reports/Phase11_2_4_A_Investigation_Report(1).md
```

实际文件为：

```text
docs/reports/Phase11_2_4_A_Investigation_Report.md
```

已按实际文件读取，未重命名、未修改该报告。

### 2.3 当前真实代码确认

实施前以当前源码为准，确认了以下事实：

| 检查项 | 实际情况 |
|---|---|
| `FindingAggregateRow` 字段 | `reportId`、`actualFindingCount`、`criticalCount`、`highCount`、`mediumCount`、`lowCount`、`infoCount`、`unknownSeverityCount`、`bugCount`、`securityCount`、`performanceCount`、`qualityCount`、`unknownCategoryCount` |
| Summary 分类统计 | `CATEGORY_KEYS = BUG / SECURITY / PERFORMANCE / QUALITY / UNKNOWN` |
| Summary UNKNOWN 来源 | SQL 将 `category NOT IN ('BUG','SECURITY','PERFORMANCE','QUALITY')` 计入 `unknownCategoryCount`，Service 原样累加 |
| `findingsConsistent(report)` | `actualFindingCount == declaredFindingCount`（空值按 0） |
| 趋势范围 | 默认最近 30 个自然日，最大 366 天，inclusive 边界 |
| DAY 分桶 | 应用本地自然日 |
| WEEK 分桶 | ISO-8601 周，周一开始，首尾周可超出请求边界 |
| 零填充 | 范围内每个桶都返回；空桶计数为 0 |
| 空范围 | `hasData=false`，`points=[]` |
| 原 TrendPoint 字段 | `bucketStart`、`bucketEnd`、`reviewCount`、`findingCount`、`highSeverityFindingCount` |
| 高严重度口径 | `CRITICAL + HIGH` |
| API 路径 | `GET /api/dashboard/statistics/overview`，位于 `/api/dashboard/**` loopback 边界内 |

---

## 3. 实际修改和新增文件清单

### 3.1 修改文件

| 文件 | 说明 |
|---|---|
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsTrendPoint.java` | Trend DTO 增加 5 个分类计数字段与 Javadoc |
| `backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsService.java` | `TrendBucket`、`BucketCounts`、`findingCounts`、`buildTrend` 增加分类累计 |
| `backend/spring-service/src/test/java/cn/codesentinel/statistics/ReviewStatisticsServiceTest.java` | 扩展 DAY/WEEK 分类断言，新增跨日/跨周累计测试与一致性 helper |
| `backend/spring-service/src/test/java/cn/codesentinel/controller/DashboardStatisticsControllerTest.java` | 新增 DAY/WEEK 分类字段序列化测试 |
| `backend/spring-service/src/test/java/cn/codesentinel/statistics/ReviewStatisticsMySqlIT.java` | 扩展真实 MySQL 分类断言，新增跨周真实 MySQL 测试 |
| `backend/spring-service/src/test/java/cn/codesentinel/statistics/ReviewStatisticsAcceptanceDbIT.java` | 扩展只读验收库分类断言与 Summary/Trend 一致性断言 |

说明：`backend/spring-service/src/main/java/cn/codesentinel/statistics/` 与对应测试目录在本任务开始前均未被 Git 跟踪，因此这些文件在 `git status` 中仍折叠在 `?? .../statistics/` 下，而不是显示为 `M`。本任务是在已有文件上编辑，没有重建目录或覆盖其他文件。

### 3.2 新增文件

| 文件 | 说明 |
|---|---|
| `docs/reports/Phase11_3_B1_Implementation_Report.md` | 本实施报告 |

### 3.3 明确未修改

- `frontend/` 下任何文件
- `DashboardLocalAccessFilter`
- `application.yml`
- Phase 10 Controller / Service / DTO / Repository
- `ReviewStatisticsSummary`、`ReviewStatisticsDataQuality`、Review History / Detail API
- 数据库表结构、索引、迁移脚本
- 依赖文件（未新增依赖）
- `docs/DEVELOPMENT_STATUS.md`
- 任何既有 Phase 报告

---

## 4. DTO 变更

### 4.1 变更前

```java
public record ReviewStatisticsTrendPoint(
        LocalDate bucketStart,
        LocalDate bucketEnd,
        long reviewCount,
        long findingCount,
        long highSeverityFindingCount) {
}
```

### 4.2 变更后

```java
public record ReviewStatisticsTrendPoint(
        LocalDate bucketStart,
        LocalDate bucketEnd,
        long reviewCount,
        long findingCount,
        long highSeverityFindingCount,
        long bugCount,
        long securityCount,
        long performanceCount,
        long qualityCount,
        long unknownCategoryCount) {
}
```

### 4.3 兼容性

- 原有 5 个字段全部保留，字段名、顺序前缀和类型均未改变。
- 新增字段全部使用 `long`，与现有计数类型一致。
- 新增字段为 additive JSON 字段，现有消费者忽略未知字段即可继续工作。
- 所有字段均为 primitive `long`，零填充桶返回 `0`，不会出现 `null`。
- 空范围仍返回 `hasData=false`、`points=[]`，不会产生任何伪趋势点。

---

## 5. Service 趋势累计逻辑

### 5.1 `TrendBucket`

新增累计字段：

```java
private long bugCount;
private long securityCount;
private long performanceCount;
private long qualityCount;
private long unknownCategoryCount;
```

`reviewCount`、`findingCount`、`highSeverityFindingCount` 的字段与累计方式保持不变。

### 5.2 `BucketCounts`

由：

```java
private record BucketCounts(long findingCount,
                            long highSeverityFindingCount) {
}
```

扩展为：

```java
private record BucketCounts(long findingCount,
                            long highSeverityFindingCount,
                            long bugCount,
                            long securityCount,
                            long performanceCount,
                            long qualityCount,
                            long unknownCategoryCount) {
}
```

### 5.3 `findingCounts`

直接复用现有 `FindingAggregateRow`，没有新增 SQL 分类聚合：

```java
private static BucketCounts findingCounts(
        Snapshot snapshot, ReportStatisticsRow report) {
    FindingAggregateRow aggregate =
            snapshot.aggregates().get(report.getReportId());
    if (aggregate == null) {
        return new BucketCounts(0L, 0L, 0L, 0L, 0L, 0L, 0L);
    }
    return new BucketCounts(
            count(aggregate.getActualFindingCount()),
            count(aggregate.getCriticalCount())
                    + count(aggregate.getHighCount()),
            count(aggregate.getBugCount()),
            count(aggregate.getSecurityCount()),
            count(aggregate.getPerformanceCount()),
            count(aggregate.getQualityCount()),
            count(aggregate.getUnknownCategoryCount()));
}
```

`aggregate == null` 只可能出现在报告声明 0 条、实际也是 0 条 Finding 的情况；返回全 0，与 Summary 的跳过逻辑等价。

### 5.4 `buildTrend` 累计

```java
bucket.reviewCount++;
if (findingsConsistent(report)) {
    BucketCounts counts = findingCounts(snapshot, report);
    bucket.findingCount += counts.findingCount();
    bucket.highSeverityFindingCount +=
            counts.highSeverityFindingCount();
    bucket.bugCount += counts.bugCount();
    bucket.securityCount += counts.securityCount();
    bucket.performanceCount += counts.performanceCount();
    bucket.qualityCount += counts.qualityCount();
    bucket.unknownCategoryCount +=
            counts.unknownCategoryCount();
}
```

关键点：

1. `reviewCount` 在完整性判断之前累计，报告级口径不变。
2. 所有 Finding 级计数（原有 `findingCount`、`highSeverityFindingCount` 和新增分类计数）都在同一个 `findingsConsistent(report)` 分支内累计。
3. 不存在“只过滤 `findingCount`、却遗漏分类累计”的路径。
4. 不改变 `highSeverityFindingCount = CRITICAL + HIGH` 的原有定义。

### 5.5 趋势点构造

```java
new ReviewStatisticsTrendPoint(
        bucket.start, bucket.end,
        bucket.reviewCount, bucket.findingCount,
        bucket.highSeverityFindingCount,
        bucket.bugCount, bucket.securityCount,
        bucket.performanceCount, bucket.qualityCount,
        bucket.unknownCategoryCount)
```

---

## 6. UNKNOWN 处理方式

现有 Summary 的分类统计包含 UNKNOWN：

```text
BUG / SECURITY / PERFORMANCE / QUALITY / UNKNOWN
```

其来源是 `FindingAggregateRow.getUnknownCategoryCount()`，SQL 规则为：

```sql
COUNT(CASE WHEN f.category NOT IN
    ('BUG', 'SECURITY', 'PERFORMANCE', 'QUALITY') THEN 1 END)
    AS unknownCategoryCount
```

本阶段趋势直接复用同一个 getter，因此：

- 不静默丢弃未知 Category。
- 不在 Java 层重新定义一套分类规则。
- 与 Summary 的 UNKNOWN 口径完全一致。
- 未来若业务扩展已知分类集合，必须同时修改 SQL 与 `CATEGORY_KEYS`；当前 Summary 和 Trend 共享同一数据源，不会出现两套口径。

新增 DTO 字段命名为 `unknownCategoryCount`，与 `FindingAggregateRow` 及 Summary 的概念保持一致。

---

## 7. 数据完整性过滤方式

### 7.1 完整性规则

```java
private static boolean findingsConsistent(ReportStatisticsRow report) {
    return count(report.getActualFindingCount())
            == count(report.getDeclaredFindingCount());
}
```

即实际 `review_finding` 行数必须等于 `review_report.finding_count`。

### 7.2 装载阶段校验

`loadSnapshot` 在构建快照时已经执行：

1. 报告必须能关联到 `review_task`，否则 fail closed。
2. Finding 聚合行必须能对应到报告，否则 fail closed。
3. 报告的 `actualFindingCount` 必须等于聚合行的 `actualFindingCount`，否则 fail closed。
4. 重复聚合行、孤立聚合行均 fail closed。

### 7.3 趋势阶段过滤

在 `buildTrend` 中，只有 `findingsConsistent(report) == true` 的报告才进入 `BucketCounts` 累加。因此：

- 声明 3 条、实际 2 条的报告（如验收数据 report 2003）不会把其 BUG/SECURITY 行计入任何分类桶。
- 该报告的 `reviewCount` 仍按报告级口径计入，不受影响。
- `dataQuality.reportsExcludedFromFindingStats` 的计算完全未改动。

---

## 8. Summary 与 Trend 一致性验证

### 8.1 必须成立的不变量

在同一统计范围、同一完整性规则下：

```text
SUM(trend.bugCount)
+ SUM(trend.securityCount)
+ SUM(trend.performanceCount)
+ SUM(trend.qualityCount)
+ SUM(trend.unknownCategoryCount)
= summary.categoryCounts 对应分类总数
```

同时：

```text
SUM(trend.findingCount) = summary.findingCount
SUM(trend.highSeverityFindingCount) = summary.highSeverityFindingCount
SUM(trend.reviewCount) = summary.reviewCount
```

### 8.2 成立原因

1. Summary 与 Trend 使用同一个 `Snapshot`、同一批 `ReportStatisticsRow` 和 `FindingAggregateRow`。
2. 两者使用同一个 `findingsConsistent` 过滤函数。
3. 分类计数全部来自同一 `FindingAggregateRow` 的同一组 getter。
4. SQL 的分类计数是穷尽的：已知四类 + 其余全部归入 UNKNOWN，因此每个一致报告的“五类之和 = Finding 总数”。

### 8.3 测试证据

单元测试与真实 MySQL 测试均增加了显式断言 helper：

```text
assertCategoryTotalsMatchSummary(summary, trend)
```

它在每个用例中同时校验：

- 5 个分类累计与 `summary.categoryCounts` 一致；
- `findingCount` 累计一致；
- `highSeverityFindingCount` 累计一致；
- `reviewCount` 累计一致。

验收快照的期望值：

| 范围 | BUG | SECURITY | PERFORMANCE | QUALITY | UNKNOWN | Finding | High+Critical | Review |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 30 日合计 | 12 | 12 | 11 | 12 | 1 | 48 | 19 | 6 |
| 2026-10-26 周 | 12 | 12 | 11 | 12 | 1 | 48 | 19 | 6 |
| 2026-11-01 日 | 12 | 11 | 11 | 11 | 0 | 45 | 18 | 1 |
| 2026-10-29 日 | 0 | 1 | 0 | 0 | 0 | 1 | 1 | 1 |
| 2026-10-28 日 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 1 |
| 2026-10-27 日 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 1 |
| 2026-10-30 日（不一致报告） | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| 2026-10-26 日（空桶） | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

上述数值已由以下三类测试共同验证：

- `ReviewStatisticsServiceTest`（Mock Repository）
- `ReviewStatisticsMySqlIT`（真实 Testcontainers MySQL）
- `ReviewStatisticsAcceptanceDbIT`（只读验收库 `codesentinel_accept_1123b`）

---

## 9. DAY / WEEK 零填充验证

本阶段未改变任何分桶代码，只增加桶内字段。已验证：

| 行为 | 结果 |
|---|---|
| DAY 自然日分桶 | 不变，30 日范围仍返回 30 个点 |
| WEEK ISO-8601 周一分桶 | 不变，仍返回 5 个周桶 |
| 首尾周超出请求边界 | 保留 |
| 应用时区 `Asia/Shanghai` | 保留 |
| 默认 30 个自然日 | 保留 |
| 最大 366 天 | 保留 |
| 范围 inclusive | 保留 |
| 空范围 `hasData=false`、`points=[]` | 保留 |
| 空 DAY 桶新增字段 | `0`，不是 `null` |
| 空 WEEK 桶新增字段 | `0`，不是 `null` |
| 不一致报告所在桶 | Finding 与分类计数均为 `0`，Review 计数保留 |

测试中显式验证了：

- `2026-10-26` 日空桶：五类均为 0。
- `2026-10-12` 周空桶：五类均为 0。
- `2026-10-30` 不一致报告桶：`bugCount`、`securityCount` 等均为 0。

---

## 10. 新增测试清单

### 10.1 `ReviewStatisticsServiceTest`

新增测试：

| 测试 | 覆盖点 |
|---|---|
| `shouldAggregateCategoryTrendsAcrossDaysAndWeeks` | 多报告跨 DAY 桶、跨 WEEK 桶；同一周多报告；同一桶多分类；零分类；UNKNOWN；不一致报告整体排除；分类累计与 Summary 一致；DAY/WEEK 零填充；旧指标不变 |

扩展测试：

| 测试 | 新增断言 |
|---|---|
| `shouldZeroFillDailyTrendAndExcludeInconsistentFindings` | 空日桶五类为 0；10-27 UNKNOWN=1；10-28 QUALITY=1；10-29 SECURITY=1；10-30 不一致报告五类为 0；11-01 五类为 12/11/11/11/0；总量与 Summary 一致 |
| `shouldUseIsoWeeksStartingOnMonday` | 空周桶五类为 0；10-26 周五类为 12/12/11/12/1；周累计与 Summary 一致 |

新增 helper：

```text
assertCategoryCounts(...)
categoryTotal(...)
assertCategoryTotalsMatchSummary(...)
```

### 10.2 `DashboardStatisticsControllerTest`

新增测试：

| 测试 | 覆盖点 |
|---|---|
| `shouldSerializeCategoryTrendCountsForDayAndWeek` | DAY 请求返回新字段；WEEK 请求返回新字段；原字段仍存在；0 值序列化为 0；空趋势契约不变 |

同时保留了原有的参数校验、错误响应、安全边界和空响应测试。

### 10.3 `ReviewStatisticsMySqlIT`

扩展测试：

| 测试 | 新增断言 |
|---|---|
| `shouldZeroFillDailyAndWeeklyTrends` | 真实 MySQL 下空日/空周五类为 0；UNKNOWN、SECURITY、QUALITY 分类正确；不一致报告分类不进入；日/周累计与 Summary 一致 |

新增测试：

| 测试 | 覆盖点 |
|---|---|
| `shouldAggregateCategoryTrendsAcrossWeeksOnRealMySql` | 真实 MySQL 下跨两个周桶累计；同一周多报告；多分类；UNKNOWN；Summary/Trend 一致性 |

### 10.4 `ReviewStatisticsAcceptanceDbIT`

扩展测试：

| 测试 | 新增断言 |
|---|---|
| `shouldZeroFillDailyAndWeeklyTrends` | 只读验收库下空日/空周五类为 0；真实分类值正确；不一致报告分类不进入；日/周累计与 Summary 一致 |

本测试类未新增测试方法，仍为 12 个测试；仅在原有方法内增加分类断言，未削弱任何旧断言。

### 10.5 测试覆盖对照

| 任务要求 | 覆盖测试 |
|---|---|
| 多报告跨多个 DAY 桶 | `shouldAggregateCategoryTrendsAcrossDaysAndWeeks`、验收快照测试 |
| 多报告跨多个 WEEK 桶 | `shouldAggregateCategoryTrendsAcrossDaysAndWeeks`、`shouldAggregateCategoryTrendsAcrossWeeksOnRealMySql` |
| 同一桶多种 Category | 上述两个测试均覆盖 |
| 某 Category 为 0 | 空桶、单分类桶断言 |
| 未知 Category | 2006 / MYSTERY 数据断言 |
| 不一致报告整体排除 | 2003 / 3004 数据断言 |
| 分类累计与 Summary 一致 | 所有扩展测试中的 `assertCategoryTotalsMatchSummary` |
| DAY 零填充新字段为 0 | 10-26 空日断言 |
| WEEK 零填充新字段为 0 | 10-12 空周断言 |
| 空范围契约 | 原有测试继续通过 |
| 旧指标不回归 | 原有断言全部保留并通过 |

---

## 11. Maven 测试结果

### 11.1 编译

```text
mvn -q -DskipTests compile
mvn -q -DskipTests test-compile
```

结果：均成功，无编译错误。

### 11.2 定向单元测试

```text
mvn -q "-Dtest=ReviewStatisticsServiceTest,DashboardStatisticsControllerTest" test
```

结果：

| 测试类 | Tests | Failures | Errors | Skipped |
|---|---:|---:|---:|---:|
| `ReviewStatisticsServiceTest` | 20 | 0 | 0 | 0 |
| `DashboardStatisticsControllerTest` | 16 | 0 | 0 | 0 |

### 11.3 后端完整单元测试

```text
mvn -q test
```

结果：

| 指标 | 数值 |
|---|---:|
| 测试集 | 47 |
| Tests | 543 |
| Failures | 0 |
| Errors | 0 |
| Skipped | 0 |

对比 Phase 11.2.4-C 基线（47 个测试集 / 541 个测试）：新增 2 个测试方法，测试集数量不变，全部通过。

### 11.4 完整 MySQL 集成测试

```text
mvn -q -Pmysql-it "-Dsurefire.skip=true" verify
```

结果：

| 指标 | 数值 |
|---|---:|
| 测试集 | 10 |
| Tests | 77 |
| Failures | 0 |
| Errors | 0 |
| Skipped | 12 |

说明：

- `ReviewStatisticsMySqlIT`：10 个测试全部通过。
- 其余 9 个 IT 测试集全部通过。
- 12 个 skipped 全部来自 `ReviewStatisticsAcceptanceDbIT`，该测试类默认由 `@EnabledIfSystemProperty` 关闭，符合既有设计。
- 对比 Phase 11.2.4-C 基线（10 个测试集 / 76 个测试）：新增 1 个 MySQL IT 测试。

### 11.5 只读验收库集成测试

```text
mvn -q -Pmysql-it \
  -Dit.test=ReviewStatisticsAcceptanceDbIT \
  -Dsurefire.skip=true \
  -Dcodesentinel.acceptance.db=true \
  -Dcodesentinel.acceptance.db.url=jdbc:mysql://127.0.0.1:3307/codesentinel_accept_1123b \
  verify
```

结果：

| 指标 | 数值 |
|---|---:|
| Tests | 12 |
| Failures | 0 |
| Errors | 0 |
| Skipped | 0 |

首次执行时，命令工作目录为 `backend/spring-service`，但读取了错误相对路径的 `.env`，导致用户名/密码为空、Spring 上下文加载失败（12 个 context 错误）。该次执行在测试 SQL 之前即失败，未对数据库执行任何 INSERT / UPDATE / DELETE / DDL。修正 `.env` 路径后重新执行，12/12 通过。

### 11.6 前端验证

本阶段未修改 `frontend/`，因此未运行前端测试。前端现有 121 个测试不受后端 additive JSON 字段影响，留待 Phase 11.3-B2 消费新字段时统一验证。

---

## 12. 数据库只读性说明

### 12.1 验收库

- 数据库：`codesentinel_accept_1123b`
- 地址：`127.0.0.1:3307`
- 验收测试类：`ReviewStatisticsAcceptanceDbIT`

只读保护：

1. `spring.datasource.hikari.read-only=true`
2. `@Transactional(readOnly = true)`
3. URL 必须精确包含 `codesentinel_accept_1123b`，否则测试主动拒绝启动
4. 测试仅调用 `SELECT` / `COUNT(*)`
5. 不执行 INSERT、UPDATE、DELETE、DDL
6. 不清理、不重建验收数据库

执行前后行数核对：

| 表 | 执行前 | 执行后 |
|---|---:|---:|
| `review_report` | 6 | 6 |
| `review_finding` | 50 | 50 |
| `review_comment` | 26 | 26 |
| `review_task` | 7 | 7 |

只读核对命令仅使用 `SELECT COUNT(*)`。

### 12.2 MySQL IT

`ReviewStatisticsMySqlIT` 使用独立 Testcontainers MySQL 容器：

- `mysql:8.0.46`
- 数据库名 `codesentinel_statistics_it`
- `ddl-auto=create-drop`
- 每个测试前清空并重新灌入测试夹具

该容器与验收库完全隔离；测试中的 INSERT / DELETE 只作用于一次性容器，不触碰 `codesentinel_accept_1123b`。

### 12.3 本阶段未改变数据库

- 未新增表
- 未新增字段
- 未新增索引
- 未新增迁移脚本
- 未修改 DDL

---

## 13. API 兼容性说明

### 13.1 变更类型

`GET /api/dashboard/statistics/overview` 的 `trend.points[]` 新增 5 个字段：

```json
{
  "bucketStart": "2026-11-01",
  "bucketEnd": "2026-11-01",
  "reviewCount": 1,
  "findingCount": 45,
  "highSeverityFindingCount": 18,
  "bugCount": 12,
  "securityCount": 11,
  "performanceCount": 11,
  "qualityCount": 11,
  "unknownCategoryCount": 0
}
```

### 13.2 保持不变

- 原有字段名、类型和含义不变。
- `trend.granularity`、`trend.hasData`、`trend.points` 结构不变。
- 空趋势仍为 `hasData=false`、`points=[]`。
- `/api/dashboard/statistics/reviews` 完全未修改。
- 参数校验与错误码不变：
  - `invalid_pagination`
  - `invalid_filter`
  - `invalid_granularity`
  - `invalid_sort`
  - `invalid_range`
  - `internal_error`
- `/api/dashboard/**` 的 loopback 访问边界未修改。
- 未读取 `REVIEW_HISTORY_INTERNAL_TOKEN`，未新增敏感字段。

### 13.3 前端影响

- 当前 `frontend/src/types/statistics.ts` 未包含新字段，但 JSON 反序列化会忽略未知字段。
- 现有 Review/Finding 趋势图不受影响。
- Phase 11.3-B2 可直接在类型中追加这 5 个字段并绘制独立分类趋势图。

### 13.4 响应体积

最坏情况为 366 个 DAY 点，每个点新增 5 个 `long` 字段，估算新增不超过约 15 KB（未压缩）。对本地 Dashboard API 可接受。

---

## 14. 未解决问题及限制

1. **Phase 11.3-B2 尚未开始**：前端分类趋势图仍需后续实现，本阶段只提供后端数据。
2. **`review_report.created_at` 索引缺失（W2）**：Phase 11.2.4-C 已记录的全表扫描风险仍然存在，本阶段未修改数据库结构。该问题不阻塞本阶段。
3. **验收库 IT 默认关闭（W3）**：`ReviewStatisticsAcceptanceDbIT` 仍需要显式系统属性才会执行，符合既有设计；本次已显式执行并通过。
4. **真实 UI 翻页未验证（W1）**、**范围条省略微秒（W4）**、**E2E 方法与截图限制（W5）**：均属于前端/验收遗留，与本阶段后端分类趋势无关，未处理。
5. **UNKNOWN 语义继承既有 SQL**：任何不在四个已知值中的存储 Category 都计入 `unknownCategoryCount`，与 Summary 一致。若未来新增已知分类，需要同步修改 SQL 与 `CATEGORY_KEYS`，否则会继续归入 UNKNOWN。
6. **未新增分类趋势的独立端点**：本阶段按任务要求扩展现有趋势点，未新增 API 路径，避免扩大范围。
7. 未发现新的阻断性缺陷、数据一致性问题或安全边界问题。

---

## 15. Git 分支和 HEAD 是否保持不变

| 项目 | 实施前 | 实施后 |
|---|---|---|
| 分支 | `phase11/dashboard` | `phase11/dashboard` |
| HEAD | `27e3a41161cfa86ee2956ba0b3626a2bcc71eec7` | `27e3a41161cfa86ee2956ba0b3626a2bcc71eec7` |
| `main..HEAD` | 0 | 0 |

本阶段未执行：

```text
git commit
git push
git merge
git rebase
git reset
git clean
git checkout
git switch
git stash
git cherry-pick
```

未修改分支、HEAD、暂存区或 Git 配置。

---

## 16. 工作区保护检查结果

### 16.1 基线对比

| 项目 | 实施前 | 实施后 | 变化 |
|---|---:|---:|---|
| tracked modified | 6 | 6 | 无 |
| tracked deleted | 1 | 1 | 无 |
| untracked status 条目 | 53 | 54 | 仅新增本报告 |

实施后 `git diff --stat` 仍为：

```text
.gitignore                                         |   6 +
.../review/ReviewHistoryQueryService.java          |   8 +-
.../codesentinel/task/ReviewReportRepository.java  |  44 +++++-
.../src/main/resources/application.yml             |   3 +
.../codesentinel/CodeSentinelApplicationTests.java |   4 +
docs/DEVELOPMENT_STATUS.md                         | 156 ++++++++++++++++-----
frontend/.gitkeep                                  |   0
7 files changed, 182 insertions(+), 39 deletions(-)
```

与实施前完全一致。

### 16.2 受保护文件

以下既有修改未被触碰：

```text
backend/spring-service/src/main/java/cn/codesentinel/review/ReviewHistoryQueryService.java
backend/spring-service/src/main/java/cn/codesentinel/task/ReviewReportRepository.java
backend/spring-service/src/main/resources/application.yml
backend/spring-service/src/test/java/cn/codesentinel/CodeSentinelApplicationTests.java
.gitignore
```

- `frontend/.gitkeep` 的删除状态未恢复、未处理。
- `docs/DEVELOPMENT_STATUS.md` 未修改。
- 既有 Phase 报告未修改。
- 未清理任何测试生成文件或既有未跟踪文件。
- `target/` 测试产物为构建输出，未纳入 Git 跟踪范围。
- `.env` 仅被只读解析用于验收库连接，未修改、未提交、未在报告中输出任何凭证值。

### 16.3 本任务实际触碰的文件

```text
backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsTrendPoint.java
backend/spring-service/src/main/java/cn/codesentinel/statistics/ReviewStatisticsService.java
backend/spring-service/src/test/java/cn/codesentinel/statistics/ReviewStatisticsServiceTest.java
backend/spring-service/src/test/java/cn/codesentinel/controller/DashboardStatisticsControllerTest.java
backend/spring-service/src/test/java/cn/codesentinel/statistics/ReviewStatisticsMySqlIT.java
backend/spring-service/src/test/java/cn/codesentinel/statistics/ReviewStatisticsAcceptanceDbIT.java
docs/reports/Phase11_3_B1_Implementation_Report.md
```

---

## 17. 结论

Phase 11.3-B1 后端分类趋势扩展已完成：

- 5 个分类计数字段已加入趋势点 DTO。
- 分类累计严格复用现有 Finding 聚合与完整性规则。
- Summary 与 Trend 的分类累计在单元测试、真实 MySQL 和只读验收库中均保持一致。
- DAY/WEEK 分桶、零填充、时区、范围与空范围行为未改变。
- 旧字段与旧 API 行为无回归。
- 未修改前端、数据库结构、Phase 10 代码或受保护文档。
- 分支与 HEAD 保持不变。

本阶段到此停止，等待 ChatGPT 审查与用户下一步授权；不进入 Phase 11.3-B2，不更新 `DEVELOPMENT_STATUS.md`，不开始 Phase 12。
