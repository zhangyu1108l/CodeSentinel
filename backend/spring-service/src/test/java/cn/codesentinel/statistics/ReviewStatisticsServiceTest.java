package cn.codesentinel.statistics;

import cn.codesentinel.review.InvalidReviewHistoryFilterException;
import cn.codesentinel.review.InvalidReviewHistoryPaginationException;
import cn.codesentinel.review.ReviewHistoryDataIntegrityException;
import cn.codesentinel.review.ReviewHistoryFilter;
import cn.codesentinel.review.ReviewPageResponse;
import cn.codesentinel.statistics.ReviewStatisticsRepository.FindingAggregateRow;
import cn.codesentinel.statistics.ReviewStatisticsRepository.ReportStatisticsRow;
import cn.codesentinel.task.PublishStatus;
import cn.codesentinel.task.TaskStatus;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
class ReviewStatisticsServiceTest {

    private static final ZoneId ZONE = ZoneId.of("Asia/Shanghai");
    private static final Clock CLOCK = Clock.fixed(
            Instant.parse("2026-11-13T12:00:00Z"), ZONE);
    private static final LocalDateTime DEFAULT_FROM =
            LocalDateTime.of(2026, 10, 15, 0, 0);
    private static final LocalDateTime DEFAULT_TO =
            LocalDateTime.of(2026, 11, 13, 23, 59, 59, 999_999_000);

    @Mock
    private ReviewStatisticsRepository repository;

    private ReviewStatisticsService service;

    @BeforeEach
    void setUp() {
        service = new ReviewStatisticsService(repository, ZONE, CLOCK);
    }

    @Test
    void shouldResolveDefaultRangeToThirtyCalendarDaysIncludingToday() {
        stubReports(DEFAULT_FROM, DEFAULT_TO, List.of());

        ReviewStatisticsOverviewResponse response =
                service.overview(emptyFilter(), "DAY");

        assertEquals(DEFAULT_FROM, response.range().createdFrom());
        assertEquals(DEFAULT_TO, response.range().createdTo());
        assertEquals("Asia/Shanghai", response.range().zoneId());
        assertEquals(StatisticsGranularity.DAY,
                response.range().granularity());
        assertEquals(LocalDateTime.of(2026, 11, 13, 20, 0),
                response.generatedAt());
        verify(repository).findReportStatistics(isNull(), isNull(), isNull(),
                isNull(), isNull(), isNull(), eq(DEFAULT_FROM),
                eq(DEFAULT_TO));
        verifyNoInteractionsFindingAggregates();
    }

    @Test
    void shouldFillOnlyCreatedFromWithTodayEnd() {
        LocalDateTime from = LocalDateTime.of(2026, 11, 1, 0, 0);
        stubReports(from, DEFAULT_TO, List.of());

        ReviewStatisticsOverviewResponse response = service.overview(
                new ReviewHistoryFilter(null, null, null, null, null, null,
                        from, null), "DAY");

        assertEquals(from, response.range().createdFrom());
        assertEquals(DEFAULT_TO, response.range().createdTo());
    }

    @Test
    void shouldFillOnlyCreatedToWithTwentyNineDaysBeforeItsDate() {
        LocalDateTime to = LocalDateTime.of(2026, 11, 10, 12, 0);
        LocalDateTime from = LocalDateTime.of(2026, 10, 12, 0, 0);
        stubReports(from, to, List.of());

        ReviewStatisticsOverviewResponse response = service.overview(
                new ReviewHistoryFilter(null, null, null, null, null, null,
                        null, to), "DAY");

        assertEquals(from, response.range().createdFrom());
        assertEquals(to, response.range().createdTo());
    }

    @Test
    void shouldRejectOnlyFromInTheFuture() {
        ReviewHistoryFilter filter = new ReviewHistoryFilter(
                null, null, null, null, null, null,
                LocalDateTime.of(2026, 12, 1, 0, 0), null);

        assertThrows(InvalidReviewHistoryFilterException.class,
                () -> service.overview(filter, "DAY"));
        verifyNoInteractions(repository);
    }

    @Test
    void shouldAcceptExactlyThreeHundredSixtySixCalendarDays() {
        LocalDateTime from = LocalDateTime.of(2025, 11, 13, 0, 0);
        LocalDateTime to = LocalDateTime.of(2026, 11, 13, 0, 0);
        stubReports(from, to, List.of());

        ReviewStatisticsOverviewResponse response = service.overview(
                new ReviewHistoryFilter(null, null, null, null, null, null,
                        from, to), "DAY");

        assertEquals(from, response.range().createdFrom());
        assertEquals(to, response.range().createdTo());
    }

    @Test
    void shouldRejectRangeLongerThanThreeHundredSixtySixDays() {
        LocalDateTime from = LocalDateTime.of(2025, 11, 12, 0, 0);
        LocalDateTime to = LocalDateTime.of(2026, 11, 13, 0, 0);

        assertThrows(InvalidStatisticsRangeException.class,
                () -> service.reviews(new ReviewHistoryFilter(
                        null, null, null, null, null, null, from, to),
                        1, 20, null, null));
        verifyNoInteractions(repository);
    }

    @Test
    void shouldRejectInvalidGranularityPaginationAndSort() {
        assertThrows(InvalidStatisticsGranularityException.class,
                () -> service.overview(emptyFilter(), "MONTH"));

        assertThrows(InvalidReviewHistoryPaginationException.class,
                () -> service.reviews(emptyFilter(), 0, 20, null, null));
        assertThrows(InvalidReviewHistoryPaginationException.class,
                () -> service.reviews(emptyFilter(), 1, 0, null, null));
        assertThrows(InvalidReviewHistoryPaginationException.class,
                () -> service.reviews(emptyFilter(), 1, 101, null, null));

        assertThrows(InvalidStatisticsSortException.class,
                () -> service.reviews(emptyFilter(), 1, 20, "bad", "desc"));
        assertThrows(InvalidStatisticsSortException.class,
                () -> service.reviews(emptyFilter(), 1, 20, "createdAt",
                        "sideways"));
        verifyNoInteractions(repository);
    }

    @Test
    void shouldReturnSafeEmptyStatisticsForAnEmptyRange() {
        stubReports(DEFAULT_FROM, DEFAULT_TO, List.of());

        ReviewStatisticsOverviewResponse response =
                service.overview(emptyFilter(), "DAY");

        ReviewStatisticsSummary summary = response.summary();
        assertEquals(0, summary.reviewCount());
        assertEquals(0, summary.findingStatsReviewCount());
        assertEquals(0, summary.findingCount());
        assertNull(summary.averageFindingsPerReview());
        assertNull(summary.medianFindingsPerReview());
        assertNull(summary.maxFindingsInReview());
        assertEquals(0, summary.reviewsWithFindings());
        assertNull(summary.reviewsWithFindingsRatio());
        assertEquals(0, summary.highSeverityFindingCount());
        assertNull(summary.highSeverityRatio());
        assertEquals(0, summary.commentStatsReviewCount());
        assertEquals(0, summary.publishedInlineCommentCount());
        assertEquals(0, summary.reviewsWithInlineComments());
        assertNull(summary.reviewsWithInlineCommentsRatio());
        assertEquals(0, summary.summaryCommentIdPresentCount());
        assertEquals(List.of(
                        new ReviewStatisticsCount("BUG", 0),
                        new ReviewStatisticsCount("SECURITY", 0),
                        new ReviewStatisticsCount("PERFORMANCE", 0),
                        new ReviewStatisticsCount("QUALITY", 0),
                        new ReviewStatisticsCount("UNKNOWN", 0)),
                summary.categoryCounts());
        assertEquals(List.of(
                        new ReviewStatisticsCount("CRITICAL", 0),
                        new ReviewStatisticsCount("HIGH", 0),
                        new ReviewStatisticsCount("MEDIUM", 0),
                        new ReviewStatisticsCount("LOW", 0),
                        new ReviewStatisticsCount("INFO", 0),
                        new ReviewStatisticsCount("UNKNOWN", 0)),
                summary.severityCounts());
        assertEquals(List.of(
                        new ReviewStatisticsCount("PUBLISHED", 0),
                        new ReviewStatisticsCount("PARTIAL", 0),
                        new ReviewStatisticsCount("FAILED", 0),
                        new ReviewStatisticsCount("PENDING", 0),
                        new ReviewStatisticsCount("UNKNOWN", 0)),
                summary.publishStatusCounts());
        assertEquals(List.of(
                        new ReviewStatisticsCount("COMPLETED", 0),
                        new ReviewStatisticsCount("DEGRADED", 0),
                        new ReviewStatisticsCount("UNKNOWN", 0)),
                summary.aiStatusCounts());

        assertFalse(response.trend().hasData());
        assertTrue(response.trend().points().isEmpty());
        assertEquals(new ReviewStatisticsDataQuality(
                        0, 0, 0, 0, 0, 0, 0, 0, 0),
                response.dataQuality());
    }

    @Test
    void shouldComputeAcceptanceNumbersAndExcludeInconsistentReports() {
        stubAcceptanceFixture();

        ReviewStatisticsOverviewResponse response =
                service.overview(emptyFilter(), "DAY");
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
    }

    @Test
    void shouldZeroFillDailyTrendAndExcludeInconsistentFindings() {
        stubAcceptanceFixture();

        ReviewStatisticsOverviewResponse response =
                service.overview(emptyFilter(), "DAY");
        ReviewStatisticsTrend trend = response.trend();

        assertEquals(StatisticsGranularity.DAY, trend.granularity());
        assertTrue(trend.hasData());
        assertEquals(30, trend.points().size());
        assertEquals(LocalDate.of(2026, 10, 15),
                trend.points().get(0).bucketStart());
        assertEquals(LocalDate.of(2026, 11, 13),
                trend.points().get(29).bucketEnd());

        ReviewStatisticsTrendPoint october26 =
                point(trend, LocalDate.of(2026, 10, 26));
        assertEquals(0, october26.reviewCount());
        assertCategoryCounts(october26, 0, 0, 0, 0, 0);

        ReviewStatisticsTrendPoint october27 =
                point(trend, LocalDate.of(2026, 10, 27));
        assertCategoryCounts(october27, 0, 0, 0, 0, 1);

        ReviewStatisticsTrendPoint october28 =
                point(trend, LocalDate.of(2026, 10, 28));
        assertCategoryCounts(october28, 0, 0, 0, 1, 0);

        ReviewStatisticsTrendPoint october29 =
                point(trend, LocalDate.of(2026, 10, 29));
        assertCategoryCounts(october29, 0, 1, 0, 0, 0);

        ReviewStatisticsTrendPoint october30 =
                point(trend, LocalDate.of(2026, 10, 30));
        assertEquals(1, october30.reviewCount());
        assertEquals(0, october30.findingCount());
        assertEquals(0, october30.highSeverityFindingCount());
        // Report 2003 is findings-inconsistent, so its BUG/SECURITY rows
        // must not enter any category bucket either.
        assertCategoryCounts(october30, 0, 0, 0, 0, 0);

        ReviewStatisticsTrendPoint november1 =
                point(trend, LocalDate.of(2026, 11, 1));
        assertEquals(1, november1.reviewCount());
        assertEquals(45, november1.findingCount());
        assertEquals(18, november1.highSeverityFindingCount());
        assertCategoryCounts(november1, 12, 11, 11, 11, 0);

        assertEquals(6, trend.points().stream()
                .mapToLong(ReviewStatisticsTrendPoint::reviewCount).sum());
        assertEquals(48, trend.points().stream()
                .mapToLong(ReviewStatisticsTrendPoint::findingCount).sum());
        assertEquals(19, trend.points().stream()
                .mapToLong(ReviewStatisticsTrendPoint::highSeverityFindingCount)
                .sum());
        assertCategoryTotalsMatchSummary(response.summary(), trend);
    }

    @Test
    void shouldUseIsoWeeksStartingOnMonday() {
        stubAcceptanceFixture();

        ReviewStatisticsOverviewResponse response =
                service.overview(emptyFilter(), "WEEK");
        ReviewStatisticsTrend trend = response.trend();

        assertEquals(5, trend.points().size());
        assertEquals(LocalDate.of(2026, 10, 12),
                trend.points().get(0).bucketStart());
        assertEquals(LocalDate.of(2026, 10, 18),
                trend.points().get(0).bucketEnd());
        assertEquals(LocalDate.of(2026, 11, 9),
                trend.points().get(4).bucketStart());
        assertEquals(LocalDate.of(2026, 11, 15),
                trend.points().get(4).bucketEnd());

        ReviewStatisticsTrendPoint emptyWeek =
                point(trend, LocalDate.of(2026, 10, 12));
        assertCategoryCounts(emptyWeek, 0, 0, 0, 0, 0);

        ReviewStatisticsTrendPoint week =
                point(trend, LocalDate.of(2026, 10, 26));
        assertEquals(6, week.reviewCount());
        assertEquals(48, week.findingCount());
        assertEquals(19, week.highSeverityFindingCount());
        assertCategoryCounts(week, 12, 12, 11, 12, 1);
        assertCategoryTotalsMatchSummary(response.summary(), trend);
    }

    @Test
    void shouldAggregateCategoryTrendsAcrossDaysAndWeeks() {
        List<ReportStatisticsRow> reports = List.of(
                report(3001, 1101, "owner", "repo", 1, "COMPLETED",
                        "COMPLETED", "PUBLISHED",
                        LocalDateTime.of(2026, 10, 20, 10, 0),
                        4, 4, 0, 0, false),
                report(3002, 1102, "owner", "repo", 2, "COMPLETED",
                        "COMPLETED", "PUBLISHED",
                        LocalDateTime.of(2026, 10, 21, 11, 0),
                        2, 2, 0, 0, false),
                report(3003, 1103, "owner", "repo", 3, "COMPLETED",
                        "COMPLETED", "PUBLISHED",
                        LocalDateTime.of(2026, 10, 28, 9, 0),
                        1, 1, 0, 0, false),
                report(3004, 1104, "owner", "repo", 4, "COMPLETED",
                        "COMPLETED", "PUBLISHED",
                        LocalDateTime.of(2026, 10, 22, 8, 0),
                        2, 1, 0, 0, false));
        List<FindingAggregateRow> aggregates = List.of(
                aggregate(3001, 4, 1, 1, 1, 0, 0, 1,
                        2, 0, 1, 0, 1),
                aggregate(3002, 2, 0, 0, 1, 0, 1, 0,
                        0, 1, 0, 1, 0),
                aggregate(3003, 1, 0, 1, 0, 0, 0, 0,
                        1, 0, 0, 0, 0),
                aggregate(3004, 1, 0, 0, 0, 1, 0, 0,
                        0, 0, 0, 1, 0));
        stubAcceptanceRange(reports, aggregates);

        ReviewStatisticsOverviewResponse response =
                service.overview(emptyFilter(), "DAY");
        ReviewStatisticsSummary summary = response.summary();

        assertEquals(4, summary.reviewCount());
        assertEquals(3, summary.findingStatsReviewCount());
        assertEquals(7, summary.findingCount());
        assertEquals(3, summary.highSeverityFindingCount());

        ReviewStatisticsTrend daily = response.trend();
        assertEquals(30, daily.points().size());
        ReviewStatisticsTrendPoint october20 =
                point(daily, LocalDate.of(2026, 10, 20));
        assertEquals(1, october20.reviewCount());
        assertEquals(4, october20.findingCount());
        assertEquals(2, october20.highSeverityFindingCount());
        assertCategoryCounts(october20, 2, 0, 1, 0, 1);

        ReviewStatisticsTrendPoint october21 =
                point(daily, LocalDate.of(2026, 10, 21));
        assertCategoryCounts(october21, 0, 1, 0, 1, 0);

        ReviewStatisticsTrendPoint inconsistent =
                point(daily, LocalDate.of(2026, 10, 22));
        assertEquals(1, inconsistent.reviewCount());
        assertEquals(0, inconsistent.findingCount());
        assertCategoryCounts(inconsistent, 0, 0, 0, 0, 0);

        ReviewStatisticsTrendPoint october28 =
                point(daily, LocalDate.of(2026, 10, 28));
        assertEquals(1, october28.reviewCount());
        assertEquals(1, october28.findingCount());
        assertEquals(1, october28.highSeverityFindingCount());
        assertCategoryCounts(october28, 1, 0, 0, 0, 0);

        assertEquals(3, categoryTotal(daily, "BUG"));
        assertEquals(1, categoryTotal(daily, "SECURITY"));
        assertEquals(1, categoryTotal(daily, "PERFORMANCE"));
        assertEquals(1, categoryTotal(daily, "QUALITY"));
        assertEquals(1, categoryTotal(daily, "UNKNOWN"));
        assertCategoryTotalsMatchSummary(summary, daily);

        ReviewStatisticsTrend weekly =
                service.overview(emptyFilter(), "WEEK").trend();
        assertEquals(5, weekly.points().size());
        assertCategoryCounts(point(weekly, LocalDate.of(2026, 10, 12)),
                0, 0, 0, 0, 0);

        ReviewStatisticsTrendPoint firstWeek =
                point(weekly, LocalDate.of(2026, 10, 19));
        assertEquals(3, firstWeek.reviewCount());
        assertEquals(6, firstWeek.findingCount());
        assertEquals(2, firstWeek.highSeverityFindingCount());
        assertCategoryCounts(firstWeek, 2, 1, 1, 1, 1);

        ReviewStatisticsTrendPoint secondWeek =
                point(weekly, LocalDate.of(2026, 10, 26));
        assertEquals(1, secondWeek.reviewCount());
        assertEquals(1, secondWeek.findingCount());
        assertEquals(1, secondWeek.highSeverityFindingCount());
        assertCategoryCounts(secondWeek, 1, 0, 0, 0, 0);

        assertCategoryTotalsMatchSummary(summary, weekly);
    }

    @Test
    void shouldComputeEvenMedianIncludingZeroFindingReports() {
        List<ReportStatisticsRow> reports = List.of(
                report(1, 11, "owner", "repo", 1, "COMPLETED",
                        "COMPLETED", "PUBLISHED",
                        LocalDateTime.of(2026, 11, 1, 10, 0),
                        1, 1, 0, 0, false),
                report(2, 12, "owner", "repo", 2, "COMPLETED",
                        "COMPLETED", "PUBLISHED",
                        LocalDateTime.of(2026, 11, 2, 10, 0),
                        2, 2, 0, 0, false),
                report(3, 13, "owner", "repo", 3, "COMPLETED",
                        "COMPLETED", "PUBLISHED",
                        LocalDateTime.of(2026, 11, 3, 10, 0),
                        3, 3, 0, 0, false),
                report(4, 14, "owner", "repo", 4, "COMPLETED",
                        "COMPLETED", "PUBLISHED",
                        LocalDateTime.of(2026, 11, 4, 10, 0),
                        4, 4, 0, 0, false));
        List<FindingAggregateRow> aggregates = List.of(
                aggregate(1, 1, 0, 0, 0, 0, 1, 0,
                        1, 0, 0, 0, 0),
                aggregate(2, 2, 0, 0, 0, 0, 2, 0,
                        2, 0, 0, 0, 0),
                aggregate(3, 3, 0, 0, 0, 0, 3, 0,
                        3, 0, 0, 0, 0),
                aggregate(4, 4, 0, 0, 0, 0, 4, 0,
                        4, 0, 0, 0, 0));
        stubAcceptanceRange(reports, aggregates);

        ReviewStatisticsSummary summary =
                service.overview(emptyFilter(), "DAY").summary();

        assertEquals(2.5, summary.averageFindingsPerReview(), 0.000001);
        assertEquals(2.5, summary.medianFindingsPerReview(), 0.000001);
        assertEquals(4L, summary.maxFindingsInReview());
    }

    @Test
    void shouldRetainUnknownPublishAndAiStatuses() {
        List<ReportStatisticsRow> reports = new ArrayList<>(
                acceptanceReports());
        reports.add(report(2007, 1007, "omega", "mystery-status", 19,
                "COMPLETED", "WHATEVER", "MYSTERY",
                LocalDateTime.of(2026, 10, 26, 4, 0),
                0, 0, 0, 0, false));
        stubAcceptanceRange(reports, acceptanceAggregates());

        ReviewStatisticsOverviewResponse response =
                service.overview(emptyFilter(), "DAY");

        assertEquals(7, response.summary().reviewCount());
        assertEquals(1, count(response.summary().publishStatusCounts(),
                "UNKNOWN"));
        assertEquals(2, count(response.summary().aiStatusCounts(),
                "UNKNOWN"));
        assertEquals(1,
                response.dataQuality().unknownPublishStatusReportCount());
        assertEquals(2, response.dataQuality().unknownAiStatusReportCount());
    }

    @Test
    void shouldPassAllFiltersToTheRepository() {
        LocalDateTime from = LocalDateTime.of(2026, 10, 1, 0, 0);
        LocalDateTime to = LocalDateTime.of(2026, 11, 1, 23, 59, 59);
        stubReports(from, to, List.of());
        ReviewHistoryFilter filter = new ReviewHistoryFilter(
                " owner ", "repo", 42, TaskStatus.COMPLETED,
                PublishStatus.PUBLISHED, "degraded", from, to);

        ReviewStatisticsOverviewResponse response =
                service.overview(filter, "DAY");

        verify(repository).findReportStatistics(
                "owner", "repo", 42, "COMPLETED", "PUBLISHED", "DEGRADED",
                from, to);
        assertEquals(from, response.range().createdFrom());
        assertEquals(to, response.range().createdTo());
    }

    @Test
    void shouldFailClosedWhenAReportHasNoTask() {
        ReportStatisticsRow orphan = report(2001, 1001, null, null, 0,
                null, "COMPLETED", "PUBLISHED",
                LocalDateTime.of(2026, 11, 1, 10, 0),
                0, 0, 0, 0, false);
        stubReports(DEFAULT_FROM, DEFAULT_TO, List.of(orphan));

        assertThrows(ReviewHistoryDataIntegrityException.class,
                () -> service.overview(emptyFilter(), "DAY"));
        verifyNoInteractionsFindingAggregates();
    }

    @Test
    void shouldFailClosedWhenFindingAggregatesDisagree() {
        ReportStatisticsRow report = report(2001, 1001, "owner", "repo", 1,
                "COMPLETED", "COMPLETED", "PUBLISHED",
                LocalDateTime.of(2026, 11, 1, 10, 0),
                2, 2, 0, 0, false);
        stubAcceptanceRange(List.of(report), List.of(
                aggregate(2001, 1, 1, 0, 0, 0, 0, 0,
                        1, 0, 0, 0, 0)));

        assertThrows(ReviewHistoryDataIntegrityException.class,
                () -> service.overview(emptyFilter(), "DAY"));
    }

    @Test
    void shouldFailClosedWhenFindingAggregateIsMissing() {
        ReportStatisticsRow report = report(2001, 1001, "owner", "repo", 1,
                "COMPLETED", "COMPLETED", "PUBLISHED",
                LocalDateTime.of(2026, 11, 1, 10, 0),
                2, 2, 0, 0, false);
        stubAcceptanceRange(List.of(report), List.of());

        assertThrows(ReviewHistoryDataIntegrityException.class,
                () -> service.overview(emptyFilter(), "DAY"));
    }

    @Test
    void shouldExposeInconsistentCountsAndUnknownBucketsInReviews() {
        stubAcceptanceFixture();

        ReviewPageResponse<ReviewStatisticsReviewItem> page =
                service.reviews(emptyFilter(), 1, 20, null, null);

        assertEquals(6, page.totalItems());
        assertEquals(1, page.totalPages());
        assertFalse(page.hasNext());
        assertEquals(List.of(1001L, 1002L, 1003L, 1004L, 1005L, 1006L),
                page.items().stream()
                        .map(ReviewStatisticsReviewItem::taskId)
                        .toList());

        ReviewStatisticsReviewItem incompleteFindings = item(page, 1003);
        assertEquals(3, incompleteFindings.declaredFindingCount());
        assertEquals(2, incompleteFindings.actualFindingCount());
        assertFalse(incompleteFindings.findingsConsistent());
        assertEquals(1, incompleteFindings.highSeverityFindingCount());

        ReviewStatisticsReviewItem incompleteComments = item(page, 1005);
        assertEquals(2, incompleteComments.declaredCommentCount());
        assertEquals(1, incompleteComments.actualCommentCount());
        assertFalse(incompleteComments.commentsConsistent());

        ReviewStatisticsReviewItem unknown = item(page, 1006);
        assertEquals("UNKNOWN", unknown.aiStatus());
        assertEquals("PUBLISHED", unknown.publishStatus());
        assertEquals(1, unknown.unknownCategoryCount());
        assertEquals(1, unknown.unknownSeverityCount());

        ReviewStatisticsReviewItem corruptReferences = item(page, 1004);
        assertTrue(corruptReferences.findingsConsistent());
        assertTrue(corruptReferences.commentsConsistent());
        assertEquals(1, corruptReferences.highSeverityFindingCount());
    }

    @Test
    void shouldPaginateAndSortDeterministically() {
        stubAcceptanceFixture();

        ReviewPageResponse<ReviewStatisticsReviewItem> page2 =
                service.reviews(emptyFilter(), 2, 2, "createdAt", "desc");
        assertEquals(List.of(1003L, 1004L), page2.items().stream()
                .map(ReviewStatisticsReviewItem::taskId).toList());
        assertEquals(6, page2.totalItems());
        assertEquals(3, page2.totalPages());
        assertTrue(page2.hasNext());

        ReviewPageResponse<ReviewStatisticsReviewItem> beyond =
                service.reviews(emptyFilter(), 10, 20, null, null);
        assertTrue(beyond.items().isEmpty());
        assertFalse(beyond.hasNext());

        ReviewPageResponse<ReviewStatisticsReviewItem> byFindings =
                service.reviews(emptyFilter(), 1, 3,
                        "actualFindingCount", "desc");
        assertEquals(List.of(1001L, 1003L, 1006L),
                byFindings.items().stream()
                        .map(ReviewStatisticsReviewItem::taskId).toList());

        ReviewPageResponse<ReviewStatisticsReviewItem> ascending =
                service.reviews(emptyFilter(), 1, 3,
                        "actualFindingCount", "asc");
        assertEquals(List.of(1002L, 1006L, 1005L),
                ascending.items().stream()
                        .map(ReviewStatisticsReviewItem::taskId).toList());
    }

    private void stubAcceptanceFixture() {
        stubAcceptanceRange(acceptanceReports(), acceptanceAggregates());
    }

    private void stubAcceptanceRange(List<ReportStatisticsRow> reports,
                                     List<FindingAggregateRow> aggregates) {
        stubReports(DEFAULT_FROM, DEFAULT_TO, reports);
        when(repository.findFindingAggregates(
                org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any(),
                eq(DEFAULT_FROM), eq(DEFAULT_TO))).thenReturn(aggregates);
    }

    private void stubReports(LocalDateTime from, LocalDateTime to,
                             List<ReportStatisticsRow> reports) {
        when(repository.findReportStatistics(
                org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any(),
                eq(from), eq(to)))
                .thenReturn(reports);
    }

    private void verifyNoInteractionsFindingAggregates() {
        verify(repository, org.mockito.Mockito.never())
                .findFindingAggregates(isNull(), isNull(), isNull(), isNull(),
                        isNull(), isNull(), eq(DEFAULT_FROM), eq(DEFAULT_TO));
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

    private static List<ReportStatisticsRow> acceptanceReports() {
        return List.of(
                report(2001, 1001, "acme", "sentinel-demo", 42,
                        "COMPLETED", "DEGRADED", "PARTIAL",
                        LocalDateTime.of(2026, 11, 1, 10, 0),
                        45, 45, 25, 25, true),
                report(2002, 1002, "beta", "empty-demo", 7,
                        "COMPLETED", "COMPLETED", "FAILED",
                        LocalDateTime.of(2026, 10, 31, 9, 0),
                        0, 0, 0, 0, false),
                report(2003, 1003, "gamma", "incomplete-demo", 9,
                        "COMPLETED", "COMPLETED", "PUBLISHED",
                        LocalDateTime.of(2026, 10, 30, 8, 0),
                        3, 2, 0, 0, false),
                report(2004, 1004, "delta", "corrupt-demo", 11,
                        "COMPLETED", "COMPLETED", "PUBLISHED",
                        LocalDateTime.of(2026, 10, 29, 7, 0),
                        1, 1, 0, 0, false),
                report(2005, 1005, "epsilon", "comment-mismatch", 13,
                        "COMPLETED", "COMPLETED", "PARTIAL",
                        LocalDateTime.of(2026, 10, 28, 6, 0),
                        1, 1, 2, 1, true),
                report(2006, 1006, "zeta", "unknown-enums", 15,
                        "COMPLETED", "UNKNOWN", "PUBLISHED",
                        LocalDateTime.of(2026, 10, 27, 5, 0),
                        1, 1, 0, 0, true));
    }

    private static List<FindingAggregateRow> acceptanceAggregates() {
        return List.of(
                aggregate(2001, 45, 9, 9, 9, 9, 9, 0,
                        12, 11, 11, 11, 0),
                aggregate(2003, 2, 0, 1, 1, 0, 0, 0,
                        1, 1, 0, 0, 0),
                aggregate(2004, 1, 1, 0, 0, 0, 0, 0,
                        0, 1, 0, 0, 0),
                aggregate(2005, 1, 0, 0, 0, 1, 0, 0,
                        0, 0, 0, 1, 0),
                aggregate(2006, 1, 0, 0, 0, 0, 0, 1,
                        0, 0, 0, 0, 1));
    }

    private static ReportStatisticsRow report(
            long reportId, long taskId, String owner, String repo, int prNumber,
            String taskStatus, String aiStatus, String publishStatus,
            LocalDateTime createdAt, int declaredFindings, long actualFindings,
            int declaredComments, long actualComments, boolean summaryId) {
        ReportStatisticsRow row = mock(ReportStatisticsRow.class);
        when(row.getReportId()).thenReturn(reportId);
        when(row.getTaskId()).thenReturn(taskId);
        when(row.getOwner()).thenReturn(owner);
        when(row.getRepo()).thenReturn(repo);
        when(row.getPrNumber()).thenReturn(prNumber);
        when(row.getCommitSha()).thenReturn(String.format("%040d", taskId));
        when(row.getTaskStatus()).thenReturn(taskStatus);
        when(row.getAiStatus()).thenReturn(aiStatus);
        when(row.getPublishStatus()).thenReturn(publishStatus);
        when(row.getCreatedAt()).thenReturn(createdAt);
        when(row.getDeclaredFindingCount()).thenReturn(declaredFindings);
        when(row.getActualFindingCount()).thenReturn(actualFindings);
        when(row.getDeclaredCommentCount()).thenReturn(declaredComments);
        when(row.getActualCommentCount()).thenReturn(actualComments);
        when(row.getSummaryCommentIdPresent()).thenReturn(summaryId ? 1 : 0);
        return row;
    }

    private static FindingAggregateRow aggregate(
            long reportId, long total, long critical, long high, long medium,
            long low, long info, long unknownSeverity, long bug, long security,
            long performance, long quality, long unknownCategory) {
        FindingAggregateRow row = mock(FindingAggregateRow.class);
        when(row.getReportId()).thenReturn(reportId);
        when(row.getActualFindingCount()).thenReturn(total);
        when(row.getCriticalCount()).thenReturn(critical);
        when(row.getHighCount()).thenReturn(high);
        when(row.getMediumCount()).thenReturn(medium);
        when(row.getLowCount()).thenReturn(low);
        when(row.getInfoCount()).thenReturn(info);
        when(row.getUnknownSeverityCount()).thenReturn(unknownSeverity);
        when(row.getBugCount()).thenReturn(bug);
        when(row.getSecurityCount()).thenReturn(security);
        when(row.getPerformanceCount()).thenReturn(performance);
        when(row.getQualityCount()).thenReturn(quality);
        when(row.getUnknownCategoryCount()).thenReturn(unknownCategory);
        return row;
    }
}
