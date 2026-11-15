package cn.codesentinel.statistics;

import cn.codesentinel.review.InvalidReviewHistoryFilterException;
import cn.codesentinel.review.InvalidReviewHistoryPaginationException;
import cn.codesentinel.review.ReviewHistoryFilter;
import cn.codesentinel.review.ReviewPageResponse;
import cn.codesentinel.task.PublishStatus;
import cn.codesentinel.task.TaskStatus;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfSystemProperty;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Read-only acceptance test of the Phase 11.2.4-B1 statistics API against
 * the isolated Phase 11.2.3-B database {@code codesentinel_accept_1123b}.
 *
 * <p>The test is disabled unless the system property
 * {@code codesentinel.acceptance.db=true} is set, and it refuses any URL
 * that does not name the acceptance database. It never inserts, updates or
 * deletes data; Hikari connections are read-only and the test transaction
 * rolls back. The fixed clock keeps the default 30-day range independent of
 * the machine date.
 */
@DataJpaTest(properties = {
        "spring.jpa.hibernate.ddl-auto=none",
        "spring.datasource.hikari.read-only=true"
})
@AutoConfigureTestDatabase(
        replace = AutoConfigureTestDatabase.Replace.NONE)
@Import(ReviewStatisticsAcceptanceDbIT.FixedClockConfig.class)
@Transactional(readOnly = true)
@Tag("acceptance-db")
@EnabledIfSystemProperty(named = "codesentinel.acceptance.db",
        matches = "true")
class ReviewStatisticsAcceptanceDbIT {

    private static final String ACCEPTANCE_DATABASE =
            "codesentinel_accept_1123b";
    private static final ZoneId ZONE = ZoneId.of("Asia/Shanghai");
    private static final Clock CLOCK = Clock.fixed(
            Instant.parse("2026-11-13T12:00:00Z"), ZONE);
    private static final LocalDateTime DEFAULT_FROM =
            LocalDateTime.of(2026, 10, 15, 0, 0);
    private static final LocalDateTime DEFAULT_TO =
            LocalDateTime.of(2026, 11, 13, 23, 59, 59, 999_999_000);

    @Autowired
    private ReviewStatisticsService service;
    @Autowired
    private JdbcTemplate jdbcTemplate;

    @DynamicPropertySource
    static void acceptanceDatabaseProperties(
            DynamicPropertyRegistry registry) {
        String url = requiredProperty("codesentinel.acceptance.db.url");
        String path = url.substring(url.lastIndexOf('/') + 1);
        int queryIndex = path.indexOf('?');
        if (queryIndex >= 0) {
            path = path.substring(0, queryIndex);
        }
        if (!ACCEPTANCE_DATABASE.equals(path)) {
            throw new IllegalStateException(
                    "Acceptance test refuses a URL that is not the isolated "
                            + ACCEPTANCE_DATABASE + " database");
        }
        registry.add("spring.datasource.url", () -> url);
        registry.add("spring.datasource.username", () -> requiredProperty(
                "codesentinel.acceptance.db.username"));
        registry.add("spring.datasource.password", () -> requiredProperty(
                "codesentinel.acceptance.db.password"));
        registry.add("spring.datasource.driver-class-name",
                () -> "com.mysql.cj.jdbc.Driver");
        registry.add("spring.jpa.hibernate.ddl-auto", () -> "none");
    }

    @Test
    void shouldMatchTheAcceptedDatabaseSnapshot() {
        long reportsBefore = countRows("review_report");
        long findingsBefore = countRows("review_finding");
        long commentsBefore = countRows("review_comment");
        long tasksBefore = countRows("review_task");
        assertEquals(6, reportsBefore);
        assertEquals(50, findingsBefore);
        assertEquals(26, commentsBefore);
        assertEquals(7, tasksBefore);

        ReviewStatisticsOverviewResponse response =
                service.overview(emptyFilter(), "DAY");

        assertEquals(DEFAULT_FROM, response.range().createdFrom());
        assertEquals(DEFAULT_TO, response.range().createdTo());
        assertEquals("Asia/Shanghai", response.range().zoneId());
        assertEquals(StatisticsGranularity.DAY,
                response.range().granularity());
        assertEquals(LocalDateTime.of(2026, 11, 13, 20, 0),
                response.generatedAt());

        ReviewStatisticsSummary summary = response.summary();
        assertEquals(6, summary.reviewCount());
        assertEquals(5, summary.findingStatsReviewCount());
        assertEquals(48, summary.findingCount());
        assertEquals(9.6, summary.averageFindingsPerReview(), 0.000001);
        assertEquals(1.0, summary.medianFindingsPerReview(), 0.000001);
        assertEquals(45L, summary.maxFindingsInReview());
        assertEquals(4, summary.reviewsWithFindings());
        assertEquals(0.8, summary.reviewsWithFindingsRatio(), 0.000001);
        assertEquals(19, summary.highSeverityFindingCount());
        assertEquals(19.0 / 48.0, summary.highSeverityRatio(), 0.000001);
        assertEquals(5, summary.commentStatsReviewCount());
        assertEquals(25, summary.publishedInlineCommentCount());
        assertEquals(1, summary.reviewsWithInlineComments());
        assertEquals(0.2, summary.reviewsWithInlineCommentsRatio(),
                0.000001);
        assertEquals(3, summary.summaryCommentIdPresentCount());

        assertEquals(List.of(
                        new ReviewStatisticsCount("BUG", 12),
                        new ReviewStatisticsCount("SECURITY", 12),
                        new ReviewStatisticsCount("PERFORMANCE", 11),
                        new ReviewStatisticsCount("QUALITY", 12),
                        new ReviewStatisticsCount("UNKNOWN", 1)),
                summary.categoryCounts());
        assertEquals(List.of(
                        new ReviewStatisticsCount("CRITICAL", 10),
                        new ReviewStatisticsCount("HIGH", 9),
                        new ReviewStatisticsCount("MEDIUM", 9),
                        new ReviewStatisticsCount("LOW", 10),
                        new ReviewStatisticsCount("INFO", 9),
                        new ReviewStatisticsCount("UNKNOWN", 1)),
                summary.severityCounts());
        assertEquals(List.of(
                        new ReviewStatisticsCount("PUBLISHED", 3),
                        new ReviewStatisticsCount("PARTIAL", 2),
                        new ReviewStatisticsCount("FAILED", 1),
                        new ReviewStatisticsCount("PENDING", 0),
                        new ReviewStatisticsCount("UNKNOWN", 0)),
                summary.publishStatusCounts());
        assertEquals(List.of(
                        new ReviewStatisticsCount("COMPLETED", 4),
                        new ReviewStatisticsCount("DEGRADED", 1),
                        new ReviewStatisticsCount("UNKNOWN", 1)),
                summary.aiStatusCounts());

        assertEquals(new ReviewStatisticsDataQuality(
                        6, 5, 5, 1, 1, 1, 1, 1, 0),
                response.dataQuality());

        assertEquals(reportsBefore, countRows("review_report"));
        assertEquals(findingsBefore, countRows("review_finding"));
        assertEquals(commentsBefore, countRows("review_comment"));
        assertEquals(tasksBefore, countRows("review_task"));
    }

    @Test
    void shouldExposeEveryAcceptedReviewAndItsConsistencyFlags() {
        ReviewPageResponse<ReviewStatisticsReviewItem> page =
                service.reviews(emptyFilter(), 1, 20, "createdAt", "desc");

        assertEquals(6, page.totalItems());
        assertEquals(1, page.totalPages());
        assertFalse(page.hasNext());
        assertEquals(List.of(1001L, 1002L, 1003L, 1004L, 1005L, 1006L),
                page.items().stream()
                        .map(ReviewStatisticsReviewItem::taskId).toList());

        ReviewStatisticsReviewItem report2001 = item(page, 1001);
        assertEquals("acme", report2001.owner());
        assertEquals("sentinel-demo", report2001.repo());
        assertEquals(42, report2001.prNumber());
        assertEquals("DEGRADED", report2001.aiStatus());
        assertEquals("PARTIAL", report2001.publishStatus());
        assertEquals(45, report2001.declaredFindingCount());
        assertEquals(45, report2001.actualFindingCount());
        assertTrue(report2001.findingsConsistent());
        assertEquals(25, report2001.declaredCommentCount());
        assertEquals(25, report2001.actualCommentCount());
        assertTrue(report2001.commentsConsistent());
        assertEquals(18, report2001.highSeverityFindingCount());

        ReviewStatisticsReviewItem report2002 = item(page, 1002);
        assertEquals(0, report2002.declaredFindingCount());
        assertEquals(0, report2002.actualFindingCount());
        assertTrue(report2002.findingsConsistent());
        assertEquals(0, report2002.declaredCommentCount());
        assertEquals(0, report2002.actualCommentCount());
        assertTrue(report2002.commentsConsistent());

        ReviewStatisticsReviewItem report2003 = item(page, 1003);
        assertEquals(3, report2003.declaredFindingCount());
        assertEquals(2, report2003.actualFindingCount());
        assertFalse(report2003.findingsConsistent());
        assertEquals(1, report2003.highSeverityFindingCount());
        assertEquals(1, report2003.bugCount());
        assertEquals(1, report2003.securityCount());

        ReviewStatisticsReviewItem report2004 = item(page, 1004);
        assertTrue(report2004.findingsConsistent());
        assertEquals(1, report2004.actualFindingCount());
        assertEquals(1, report2004.highSeverityFindingCount());

        ReviewStatisticsReviewItem report2005 = item(page, 1005);
        assertEquals(1, report2005.declaredFindingCount());
        assertEquals(1, report2005.actualFindingCount());
        assertTrue(report2005.findingsConsistent());
        assertEquals(2, report2005.declaredCommentCount());
        assertEquals(1, report2005.actualCommentCount());
        assertFalse(report2005.commentsConsistent());

        ReviewStatisticsReviewItem report2006 = item(page, 1006);
        assertEquals("UNKNOWN", report2006.aiStatus());
        assertEquals("PUBLISHED", report2006.publishStatus());
        assertEquals(1, report2006.unknownCategoryCount());
        assertEquals(1, report2006.unknownSeverityCount());

        assertEquals("COMPLETED", report2006.taskStatus());
        assertEquals("6666666666666666666666666666666666666666",
                report2006.commitSha());
    }

    @Test
    void shouldExcludeReport2003FromFindingsAndReport2005FromComments() {
        ReviewStatisticsOverviewResponse response =
                service.overview(emptyFilter(), "DAY");

        // All 6 reports remain in report-level metrics.
        assertEquals(6, response.summary().reviewCount());
        assertEquals(3, count(response.summary().publishStatusCounts(),
                "PUBLISHED"));
        assertEquals(2, count(response.summary().publishStatusCounts(),
                "PARTIAL"));
        assertEquals(1, count(response.summary().publishStatusCounts(),
                "FAILED"));
        assertEquals(4, count(response.summary().aiStatusCounts(),
                "COMPLETED"));
        assertEquals(1, count(response.summary().aiStatusCounts(),
                "DEGRADED"));

        // 50 rows exist, but report 2003 (3 declared / 2 actual) is excluded.
        assertEquals(48, response.summary().findingCount());
        assertEquals(5, response.summary().findingStatsReviewCount());
        assertEquals(1,
                response.dataQuality().reportsExcludedFromFindingStats());
        assertEquals(1,
                response.dataQuality().unknownCategoryFindingCount());
        assertEquals(1,
                response.dataQuality().unknownSeverityFindingCount());

        // 26 rows exist, but report 2005 (2 declared / 1 actual) is excluded.
        assertEquals(25, response.summary().publishedInlineCommentCount());
        assertEquals(5, response.summary().commentStatsReviewCount());
        assertEquals(1,
                response.dataQuality().reportsExcludedFromCommentStats());
    }

    @Test
    void shouldTreatCorruptReferencesJsonAsIrrelevant() {
        String references = jdbcTemplate.queryForObject(
                "SELECT references_json FROM review_finding "
                        + "WHERE report_id = 2004", String.class);
        assertEquals("{bad", references);

        ReviewStatisticsOverviewResponse response =
                service.overview(new ReviewHistoryFilter(
                        "delta", null, null, null, null, null,
                        null, null), "DAY");
        assertEquals(1, response.summary().reviewCount());
        assertEquals(1, response.summary().findingCount());
        assertEquals(1, response.summary().highSeverityFindingCount());
        assertEquals(1, response.summary().findingStatsReviewCount());

        ReviewStatisticsReviewItem item = service.reviews(
                        new ReviewHistoryFilter("delta", null, null, null,
                                null, null, null, null),
                        1, 20, null, null)
                .items().get(0);
        assertTrue(item.findingsConsistent());
        assertTrue(item.commentsConsistent());
        assertEquals(1, item.criticalCount());
        assertEquals(1, item.highSeverityFindingCount());
    }

    @Test
    void shouldNotIncludeTask1008WithoutAReport() {
        assertEquals(1, jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM review_task WHERE id = 1008",
                Integer.class));

        ReviewStatisticsOverviewResponse response = service.overview(
                new ReviewHistoryFilter("eta", "task-without-report", 17,
                        null, null, null, null, null), "DAY");
        assertEquals(0, response.summary().reviewCount());
        assertEquals(0, response.summary().findingCount());
        assertFalse(response.trend().hasData());

        ReviewPageResponse<ReviewStatisticsReviewItem> page =
                service.reviews(new ReviewHistoryFilter(
                                "eta", null, null, null, null, null,
                                null, null),
                        1, 20, null, null);
        assertEquals(0, page.totalItems());
        assertTrue(page.items().isEmpty());
    }

    @Test
    void shouldReturnAnEmptySnapshotForAnEmptyRange() {
        ReviewStatisticsOverviewResponse response = service.overview(
                new ReviewHistoryFilter(null, null, null, null, null, null,
                        LocalDateTime.of(2020, 1, 1, 0, 0),
                        LocalDateTime.of(2020, 12, 31, 23, 59, 59)),
                "DAY");

        assertEquals(0, response.summary().reviewCount());
        assertEquals(0, response.summary().findingCount());
        assertEquals(0, response.summary().publishedInlineCommentCount());
        assertNull(response.summary().averageFindingsPerReview());
        assertNull(response.summary().medianFindingsPerReview());
        assertNull(response.summary().maxFindingsInReview());
        assertNull(response.summary().reviewsWithFindingsRatio());
        assertNull(response.summary().highSeverityRatio());
        assertNull(response.summary().reviewsWithInlineCommentsRatio());
        assertFalse(response.trend().hasData());
        assertTrue(response.trend().points().isEmpty());
        assertEquals(new ReviewStatisticsDataQuality(
                        0, 0, 0, 0, 0, 0, 0, 0, 0),
                response.dataQuality());
        assertTrue(service.reviews(new ReviewHistoryFilter(
                                null, null, null, null, null, null,
                                LocalDateTime.of(2020, 1, 1, 0, 0),
                                LocalDateTime.of(2020, 12, 31, 23, 59, 59)),
                        1, 20, null, null).items().isEmpty());
    }

    @Test
    void shouldUseApplicationLocalInclusiveTimeBoundaries() {
        LocalDateTime createdAt = LocalDateTime.of(2026, 11, 1, 10, 0);
        assertEquals(1, service.overview(new ReviewHistoryFilter(
                        null, null, null, null, null, null,
                        createdAt, createdAt), "DAY")
                .summary().reviewCount());

        assertEquals(0, service.overview(new ReviewHistoryFilter(
                        "acme", null, null, null, null, null,
                        createdAt.plusNanos(1_000), null), "DAY")
                .summary().reviewCount());
        assertEquals(0, service.overview(new ReviewHistoryFilter(
                        "acme", null, null, null, null, null, null,
                        createdAt.minusNanos(1_000)), "DAY")
                .summary().reviewCount());

        // A range whose first/last calendar dates are the stored local dates.
        ReviewStatisticsOverviewResponse oneDay = service.overview(
                new ReviewHistoryFilter(null, null, null, null, null, null,
                        LocalDateTime.of(2026, 11, 1, 0, 0),
                        LocalDateTime.of(2026, 11, 1, 23, 59, 59, 999_999_000)),
                "DAY");
        assertEquals(1, oneDay.summary().reviewCount());
        assertEquals(45, oneDay.summary().findingCount());
        assertEquals(1, oneDay.trend().points().size());
        assertEquals(LocalDate.of(2026, 11, 1),
                oneDay.trend().points().get(0).bucketStart());
    }

    @Test
    void shouldZeroFillDailyAndWeeklyTrends() {
        ReviewStatisticsOverviewResponse daily =
                service.overview(emptyFilter(), "DAY");
        ReviewStatisticsTrend dailyTrend = daily.trend();
        assertTrue(dailyTrend.hasData());
        assertEquals(30, dailyTrend.points().size());
        assertEquals(LocalDate.of(2026, 10, 15),
                dailyTrend.points().get(0).bucketStart());
        assertEquals(LocalDate.of(2026, 11, 13),
                dailyTrend.points().get(29).bucketEnd());

        ReviewStatisticsTrendPoint october27 =
                point(dailyTrend, LocalDate.of(2026, 10, 27));
        assertEquals(1, october27.reviewCount());
        assertEquals(1, october27.findingCount());
        assertEquals(0, october27.highSeverityFindingCount());
        assertCategoryCounts(october27, 0, 0, 0, 0, 1);

        ReviewStatisticsTrendPoint october29 =
                point(dailyTrend, LocalDate.of(2026, 10, 29));
        assertEquals(1, october29.reviewCount());
        assertEquals(1, october29.findingCount());
        assertEquals(1, october29.highSeverityFindingCount());
        assertCategoryCounts(october29, 0, 1, 0, 0, 0);

        ReviewStatisticsTrendPoint october30 =
                point(dailyTrend, LocalDate.of(2026, 10, 30));
        assertEquals(1, october30.reviewCount());
        assertEquals(0, october30.findingCount());
        assertEquals(0, october30.highSeverityFindingCount());
        assertCategoryCounts(october30, 0, 0, 0, 0, 0);

        ReviewStatisticsTrendPoint november1 =
                point(dailyTrend, LocalDate.of(2026, 11, 1));
        assertEquals(1, november1.reviewCount());
        assertEquals(45, november1.findingCount());
        assertEquals(18, november1.highSeverityFindingCount());
        assertCategoryCounts(november1, 12, 11, 11, 11, 0);

        assertEquals(6, dailyTrend.points().stream()
                .mapToLong(ReviewStatisticsTrendPoint::reviewCount).sum());
        assertEquals(48, dailyTrend.points().stream()
                .mapToLong(ReviewStatisticsTrendPoint::findingCount).sum());
        assertEquals(19, dailyTrend.points().stream()
                .mapToLong(ReviewStatisticsTrendPoint::highSeverityFindingCount)
                .sum());
        assertCategoryTotalsMatchSummary(daily.summary(), dailyTrend);

        ReviewStatisticsOverviewResponse weeklyResponse =
                service.overview(emptyFilter(), "WEEK");
        ReviewStatisticsTrend weekly = weeklyResponse.trend();
        assertEquals(5, weekly.points().size());
        assertEquals(LocalDate.of(2026, 10, 12),
                weekly.points().get(0).bucketStart());
        assertEquals(LocalDate.of(2026, 11, 9),
                weekly.points().get(4).bucketStart());
        assertCategoryCounts(point(weekly, LocalDate.of(2026, 10, 12)),
                0, 0, 0, 0, 0);
        ReviewStatisticsTrendPoint week =
                point(weekly, LocalDate.of(2026, 10, 26));
        assertEquals(6, week.reviewCount());
        assertEquals(48, week.findingCount());
        assertEquals(19, week.highSeverityFindingCount());
        assertCategoryCounts(week, 12, 12, 11, 12, 1);
        assertCategoryTotalsMatchSummary(weeklyResponse.summary(), weekly);
    }

    @Test
    void shouldPaginateAndSortLikeTheReviewHistoryList() {
        ReviewPageResponse<ReviewStatisticsReviewItem> firstPage =
                service.reviews(emptyFilter(), 1, 2, "createdAt", "desc");
        assertEquals(List.of(1001L, 1002L),
                firstPage.items().stream()
                        .map(ReviewStatisticsReviewItem::taskId).toList());
        assertEquals(6, firstPage.totalItems());
        assertEquals(3, firstPage.totalPages());
        assertTrue(firstPage.hasNext());

        ReviewPageResponse<ReviewStatisticsReviewItem> secondPage =
                service.reviews(emptyFilter(), 2, 2, "createdAt", "desc");
        assertEquals(List.of(1003L, 1004L),
                secondPage.items().stream()
                        .map(ReviewStatisticsReviewItem::taskId).toList());
        assertTrue(secondPage.hasNext());

        ReviewPageResponse<ReviewStatisticsReviewItem> thirdPage =
                service.reviews(emptyFilter(), 3, 2, "createdAt", "desc");
        assertEquals(List.of(1005L, 1006L),
                thirdPage.items().stream()
                        .map(ReviewStatisticsReviewItem::taskId).toList());
        assertFalse(thirdPage.hasNext());

        ReviewPageResponse<ReviewStatisticsReviewItem> byFindingsDesc =
                service.reviews(emptyFilter(), 1, 3,
                        "actualFindingCount", "desc");
        assertEquals(List.of(1001L, 1003L, 1006L),
                byFindingsDesc.items().stream()
                        .map(ReviewStatisticsReviewItem::taskId).toList());

        ReviewPageResponse<ReviewStatisticsReviewItem> byFindingsAsc =
                service.reviews(emptyFilter(), 1, 3,
                        "actualFindingCount", "asc");
        assertEquals(List.of(1002L, 1006L, 1005L),
                byFindingsAsc.items().stream()
                        .map(ReviewStatisticsReviewItem::taskId).toList());

        assertTrue(service.reviews(emptyFilter(), 10, 20, null, null)
                .items().isEmpty());
    }

    @Test
    void shouldRejectInvalidRangeFiltersPaginationAndSort() {
        assertThrows(InvalidStatisticsRangeException.class,
                () -> service.overview(new ReviewHistoryFilter(
                        null, null, null, null, null, null,
                        LocalDateTime.of(2025, 1, 1, 0, 0),
                        LocalDateTime.of(2026, 11, 13, 0, 0)), "DAY"));
        assertThrows(InvalidReviewHistoryFilterException.class,
                () -> service.overview(new ReviewHistoryFilter(
                        null, null, null, null, null, null,
                        LocalDateTime.of(2026, 11, 2, 0, 0),
                        LocalDateTime.of(2026, 11, 1, 0, 0)), "DAY"));
        assertThrows(InvalidReviewHistoryPaginationException.class,
                () -> service.reviews(emptyFilter(), 0, 20, null, null));
        assertThrows(InvalidReviewHistoryPaginationException.class,
                () -> service.reviews(emptyFilter(), 1, 101, null, null));
        assertThrows(InvalidStatisticsSortException.class,
                () -> service.reviews(emptyFilter(), 1, 20,
                        "unknownSort", "desc"));
        assertThrows(InvalidStatisticsSortException.class,
                () -> service.reviews(emptyFilter(), 1, 20,
                        "createdAt", "sideways"));
        assertThrows(InvalidStatisticsGranularityException.class,
                () -> service.overview(emptyFilter(), "MONTH"));
    }

    @Test
    void shouldApplyEveryFilterToTheAcceptedData() {
        ReviewStatisticsOverviewResponse response = service.overview(
                new ReviewHistoryFilter("acme", "sentinel-demo", 42,
                        TaskStatus.COMPLETED, PublishStatus.PARTIAL,
                        "DEGRADED",
                        LocalDateTime.of(2026, 11, 1, 0, 0),
                        LocalDateTime.of(2026, 11, 1, 23, 59, 59)),
                "DAY");
        assertEquals(1, response.summary().reviewCount());
        assertEquals(45, response.summary().findingCount());
        assertEquals(25, response.summary().publishedInlineCommentCount());

        assertEquals(0, service.overview(new ReviewHistoryFilter(
                        "missing-owner", null, null, null, null, null,
                        null, null), "DAY")
                .summary().reviewCount());
        assertEquals(0, service.overview(new ReviewHistoryFilter(
                        "acme' OR '1'='1", null, null, null, null, null,
                        null, null), "DAY")
                .summary().reviewCount());
    }

    @Test
    void shouldReturnTheSameSnapshotToConcurrentReaders() throws Exception {
        long reportsBefore = countRows("review_report");
        long findingsBefore = countRows("review_finding");
        long commentsBefore = countRows("review_comment");

        ExecutorService executor = Executors.newFixedThreadPool(8);
        try {
            List<Future<ReviewStatisticsSummary>> futures =
                    new ArrayList<>();
            for (int i = 0; i < 16; i++) {
                futures.add(executor.submit(() ->
                        service.overview(emptyFilter(), "DAY").summary()));
            }
            for (Future<ReviewStatisticsSummary> future : futures) {
                ReviewStatisticsSummary summary =
                        future.get(20, TimeUnit.SECONDS);
                assertEquals(6, summary.reviewCount());
                assertEquals(5, summary.findingStatsReviewCount());
                assertEquals(48, summary.findingCount());
                assertEquals(25, summary.publishedInlineCommentCount());
            }
        } finally {
            executor.shutdownNow();
        }

        assertEquals(reportsBefore, countRows("review_report"));
        assertEquals(findingsBefore, countRows("review_finding"));
        assertEquals(commentsBefore, countRows("review_comment"));
    }

    private long countRows(String table) {
        Long count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM " + table, Long.class);
        return count == null ? 0 : count;
    }

    private static String requiredProperty(String name) {
        String value = System.getProperty(name);
        if (value == null || value.isBlank()) {
            throw new IllegalStateException(
                    "Missing required system property " + name);
        }
        return value;
    }

    private static ReviewHistoryFilter emptyFilter() {
        return new ReviewHistoryFilter(null, null, null, null, null, null,
                null, null);
    }

    private static ReviewStatisticsTrendPoint point(
            ReviewStatisticsTrend trend, LocalDate start) {
        return trend.points().stream()
                .filter(point -> point.bucketStart().equals(start))
                .findFirst()
                .orElseThrow();
    }

    private static void assertCategoryCounts(ReviewStatisticsTrendPoint point,
                                             long bug, long security,
                                             long performance, long quality,
                                             long unknown) {
        assertEquals(bug, point.bugCount());
        assertEquals(security, point.securityCount());
        assertEquals(performance, point.performanceCount());
        assertEquals(quality, point.qualityCount());
        assertEquals(unknown, point.unknownCategoryCount());
    }

    private static long categoryTotal(ReviewStatisticsTrend trend,
                                      String category) {
        return trend.points().stream()
                .mapToLong(point -> switch (category) {
                    case "BUG" -> point.bugCount();
                    case "SECURITY" -> point.securityCount();
                    case "PERFORMANCE" -> point.performanceCount();
                    case "QUALITY" -> point.qualityCount();
                    case "UNKNOWN" -> point.unknownCategoryCount();
                    default -> throw new IllegalArgumentException(category);
                })
                .sum();
    }

    private static void assertCategoryTotalsMatchSummary(
            ReviewStatisticsSummary summary, ReviewStatisticsTrend trend) {
        for (String category : List.of("BUG", "SECURITY", "PERFORMANCE",
                "QUALITY", "UNKNOWN")) {
            assertEquals(count(summary.categoryCounts(), category),
                    categoryTotal(trend, category));
        }
        assertEquals(summary.findingCount(),
                trend.points().stream()
                        .mapToLong(ReviewStatisticsTrendPoint::findingCount)
                        .sum());
        assertEquals(summary.highSeverityFindingCount(),
                trend.points().stream()
                        .mapToLong(
                                ReviewStatisticsTrendPoint::highSeverityFindingCount)
                        .sum());
        assertEquals(summary.reviewCount(),
                trend.points().stream()
                        .mapToLong(ReviewStatisticsTrendPoint::reviewCount)
                        .sum());
    }

    private static ReviewStatisticsReviewItem item(
            ReviewPageResponse<ReviewStatisticsReviewItem> page,
            long taskId) {
        return page.items().stream()
                .filter(item -> item.taskId() == taskId)
                .findFirst()
                .orElseThrow();
    }

    private static long count(List<ReviewStatisticsCount> counts,
                              String key) {
        return counts.stream()
                .filter(count -> count.key().equals(key))
                .findFirst()
                .orElseThrow()
                .count();
    }

    @TestConfiguration(proxyBeanMethods = false)
    static class FixedClockConfig {

        @Bean
        ReviewStatisticsService reviewStatisticsService(
                ReviewStatisticsRepository repository) {
            return new ReviewStatisticsService(repository, ZONE, CLOCK);
        }
    }
}
