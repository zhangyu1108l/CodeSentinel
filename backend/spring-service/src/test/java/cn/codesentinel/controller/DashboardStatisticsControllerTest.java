package cn.codesentinel.controller;

import cn.codesentinel.review.InvalidReviewHistoryPaginationException;
import cn.codesentinel.review.ReviewHistoryDataIntegrityException;
import cn.codesentinel.review.ReviewHistoryFilter;
import cn.codesentinel.review.ReviewPageResponse;
import cn.codesentinel.statistics.InvalidStatisticsGranularityException;
import cn.codesentinel.statistics.InvalidStatisticsRangeException;
import cn.codesentinel.statistics.InvalidStatisticsSortException;
import cn.codesentinel.statistics.ReviewStatisticsCount;
import cn.codesentinel.statistics.ReviewStatisticsDataQuality;
import cn.codesentinel.statistics.ReviewStatisticsOverviewResponse;
import cn.codesentinel.statistics.ReviewStatisticsRange;
import cn.codesentinel.statistics.ReviewStatisticsReviewItem;
import cn.codesentinel.statistics.ReviewStatisticsService;
import cn.codesentinel.statistics.ReviewStatisticsSummary;
import cn.codesentinel.statistics.ReviewStatisticsTrend;
import cn.codesentinel.statistics.ReviewStatisticsTrendPoint;
import cn.codesentinel.statistics.StatisticsGranularity;
import cn.codesentinel.task.PublishStatus;
import cn.codesentinel.task.TaskStatus;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

import java.net.URI;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.not;
import static org.hamcrest.Matchers.nullValue;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(DashboardStatisticsController.class)
@TestPropertySource(properties = "review.history.internal-token=")
class DashboardStatisticsControllerTest {

    private static final LocalDateTime FROM =
            LocalDateTime.of(2026, 10, 15, 0, 0);
    private static final LocalDateTime TO =
            LocalDateTime.of(2026, 11, 13, 23, 59, 59, 999_999_000);

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private ReviewStatisticsService statisticsService;

    @Test
    void shouldUseOverviewDefaultsAndReturnTheEmptySnapshot() throws Exception {
        when(statisticsService.overview(any(ReviewHistoryFilter.class),
                eq("DAY"))).thenReturn(emptyOverview());

        mockMvc.perform(get("/api/dashboard/statistics/overview"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.range.createdFrom")
                        .value("2026-10-15T00:00:00"))
                .andExpect(jsonPath("$.range.createdTo")
                        .value("2026-11-13T23:59:59.999999"))
                .andExpect(jsonPath("$.range.zoneId").value("Asia/Shanghai"))
                .andExpect(jsonPath("$.range.granularity").value("DAY"))
                .andExpect(jsonPath("$.summary.reviewCount").value(0))
                .andExpect(jsonPath("$.summary.averageFindingsPerReview")
                        .value(nullValue()))
                .andExpect(jsonPath("$.summary.medianFindingsPerReview")
                        .value(nullValue()))
                .andExpect(jsonPath("$.summary.maxFindingsInReview")
                        .value(nullValue()))
                .andExpect(jsonPath("$.trend.hasData").value(false))
                .andExpect(jsonPath("$.trend.points").isEmpty())
                .andExpect(jsonPath("$.dataQuality.totalReportCount")
                        .value(0));

        ArgumentCaptor<ReviewHistoryFilter> filterCaptor =
                ArgumentCaptor.forClass(ReviewHistoryFilter.class);
        verify(statisticsService).overview(filterCaptor.capture(), eq("DAY"));
        ReviewHistoryFilter filter = filterCaptor.getValue();
        assertNull(filter.owner());
        assertNull(filter.repo());
        assertNull(filter.prNumber());
        assertNull(filter.taskStatus());
        assertNull(filter.publishStatus());
        assertNull(filter.aiStatus());
        assertNull(filter.createdFrom());
        assertNull(filter.createdTo());
    }

    @Test
    void shouldPassAllOverviewParameters() throws Exception {
        when(statisticsService.overview(any(ReviewHistoryFilter.class),
                eq("WEEK"))).thenReturn(emptyOverview());

        mockMvc.perform(get("/api/dashboard/statistics/overview")
                        .param("owner", " owner ")
                        .param("repo", "repo")
                        .param("prNumber", "42")
                        .param("taskStatus", "COMPLETED")
                        .param("publishStatus", "PARTIAL")
                        .param("aiStatus", "degraded")
                        .param("createdFrom", "2026-10-01T00:00:00")
                        .param("createdTo", "2026-11-01T23:59:59")
                        .param("granularity", "week"))
                .andExpect(status().isOk());

        ArgumentCaptor<ReviewHistoryFilter> filterCaptor =
                ArgumentCaptor.forClass(ReviewHistoryFilter.class);
        verify(statisticsService).overview(filterCaptor.capture(),
                eq("week"));
        ReviewHistoryFilter filter = filterCaptor.getValue();
        assertEquals("owner", filter.owner());
        assertEquals("repo", filter.repo());
        assertEquals(42, filter.prNumber());
        assertEquals(TaskStatus.COMPLETED, filter.taskStatus());
        assertEquals(PublishStatus.PARTIAL, filter.publishStatus());
        assertEquals("DEGRADED", filter.aiStatus());
        assertEquals(LocalDateTime.of(2026, 10, 1, 0, 0),
                filter.createdFrom());
        assertEquals(LocalDateTime.of(2026, 11, 1, 23, 59, 59),
                filter.createdTo());
    }

    @Test
    void shouldUseReviewsDefaults() throws Exception {
        when(statisticsService.reviews(any(ReviewHistoryFilter.class),
                eq(1), eq(20), eq("createdAt"), eq("desc")))
                .thenReturn(emptyPage(1, 20));

        mockMvc.perform(get("/api/dashboard/statistics/reviews"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items").isEmpty())
                .andExpect(jsonPath("$.page").value(1))
                .andExpect(jsonPath("$.size").value(20))
                .andExpect(jsonPath("$.totalItems").value(0))
                .andExpect(jsonPath("$.totalPages").value(0))
                .andExpect(jsonPath("$.hasNext").value(false));

        verify(statisticsService).reviews(any(ReviewHistoryFilter.class),
                eq(1), eq(20), eq("createdAt"), eq("desc"));
    }

    @Test
    void shouldPassAllReviewsParameters() throws Exception {
        when(statisticsService.reviews(any(ReviewHistoryFilter.class),
                eq(2), eq(50), eq("actualFindingCount"), eq("asc")))
                .thenReturn(emptyPage(2, 50));

        mockMvc.perform(get("/api/dashboard/statistics/reviews")
                        .param("page", "2")
                        .param("size", "50")
                        .param("sort", "actualFindingCount")
                        .param("direction", "asc")
                        .param("owner", "owner")
                        .param("repo", "repo")
                        .param("prNumber", "42")
                        .param("taskStatus", "COMPLETED")
                        .param("publishStatus", "PUBLISHED")
                        .param("aiStatus", "COMPLETED")
                        .param("createdFrom", "2026-10-01T00:00:00")
                        .param("createdTo", "2026-11-01T23:59:59"))
                .andExpect(status().isOk());

        ArgumentCaptor<ReviewHistoryFilter> filterCaptor =
                ArgumentCaptor.forClass(ReviewHistoryFilter.class);
        verify(statisticsService).reviews(filterCaptor.capture(),
                eq(2), eq(50), eq("actualFindingCount"), eq("asc"));
        ReviewHistoryFilter filter = filterCaptor.getValue();
        assertEquals("owner", filter.owner());
        assertEquals("repo", filter.repo());
        assertEquals(42, filter.prNumber());
        assertEquals(TaskStatus.COMPLETED, filter.taskStatus());
        assertEquals(PublishStatus.PUBLISHED, filter.publishStatus());
        assertEquals("COMPLETED", filter.aiStatus());
    }

    @Test
    void shouldMapAllReviewItemFields() throws Exception {
        when(statisticsService.reviews(any(ReviewHistoryFilter.class),
                eq(1), eq(20), eq("createdAt"), eq("desc")))
                .thenReturn(new ReviewPageResponse<>(
                        List.of(reviewItem()), 1, 20, 1, 1, false));

        mockMvc.perform(get("/api/dashboard/statistics/reviews"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items[0].taskId").value(1003))
                .andExpect(jsonPath("$.items[0].owner").value("gamma"))
                .andExpect(jsonPath("$.items[0].repo")
                        .value("incomplete-demo"))
                .andExpect(jsonPath("$.items[0].prNumber").value(9))
                .andExpect(jsonPath("$.items[0].commitSha")
                        .value("0123456789abcdef0123456789abcdef01234567"))
                .andExpect(jsonPath("$.items[0].createdAt")
                        .value("2026-10-30T08:00:00"))
                .andExpect(jsonPath("$.items[0].taskStatus")
                        .value("COMPLETED"))
                .andExpect(jsonPath("$.items[0].aiStatus")
                        .value("COMPLETED"))
                .andExpect(jsonPath("$.items[0].publishStatus")
                        .value("PUBLISHED"))
                .andExpect(jsonPath("$.items[0].declaredFindingCount")
                        .value(3))
                .andExpect(jsonPath("$.items[0].actualFindingCount")
                        .value(2))
                .andExpect(jsonPath("$.items[0].findingsConsistent")
                        .value(false))
                .andExpect(jsonPath("$.items[0].declaredCommentCount")
                        .value(0))
                .andExpect(jsonPath("$.items[0].actualCommentCount")
                        .value(0))
                .andExpect(jsonPath("$.items[0].commentsConsistent")
                        .value(true))
                .andExpect(jsonPath("$.items[0].criticalCount").value(0))
                .andExpect(jsonPath("$.items[0].highCount").value(1))
                .andExpect(jsonPath("$.items[0].highSeverityFindingCount")
                        .value(1))
                .andExpect(jsonPath("$.items[0].bugCount").value(1))
                .andExpect(jsonPath("$.items[0].securityCount").value(1))
                .andExpect(jsonPath("$.items[0].unknownCategoryCount")
                        .value(0))
                .andExpect(jsonPath("$.items[0].unknownSeverityCount")
                        .value(0))
                .andExpect(jsonPath("$.items[0].reportId").doesNotExist());
    }

    @Test
    void shouldSerializeCategoryTrendCountsForDayAndWeek() throws Exception {
        when(statisticsService.overview(any(ReviewHistoryFilter.class),
                eq("DAY"))).thenReturn(overviewWithTrend(dayTrend()));
        when(statisticsService.overview(any(ReviewHistoryFilter.class),
                eq("WEEK"))).thenReturn(overviewWithTrend(weekTrend()));

        mockMvc.perform(get("/api/dashboard/statistics/overview")
                        .param("granularity", "DAY"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.trend.granularity").value("DAY"))
                .andExpect(jsonPath("$.trend.hasData").value(true))
                .andExpect(jsonPath("$.trend.points[0].bucketStart")
                        .value("2026-10-19"))
                .andExpect(jsonPath("$.trend.points[0].bucketEnd")
                        .value("2026-10-19"))
                .andExpect(jsonPath("$.trend.points[0].reviewCount").value(2))
                .andExpect(jsonPath("$.trend.points[0].findingCount").value(4))
                .andExpect(jsonPath("$.trend.points[0].highSeverityFindingCount")
                        .value(2))
                .andExpect(jsonPath("$.trend.points[0].bugCount").value(2))
                .andExpect(jsonPath("$.trend.points[0].securityCount").value(0))
                .andExpect(jsonPath("$.trend.points[0].performanceCount")
                        .value(1))
                .andExpect(jsonPath("$.trend.points[0].qualityCount").value(0))
                .andExpect(jsonPath("$.trend.points[0].unknownCategoryCount")
                        .value(1))
                .andExpect(jsonPath("$.trend.points[1].bugCount").value(0))
                .andExpect(jsonPath("$.trend.points[1].securityCount").value(0))
                .andExpect(jsonPath("$.trend.points[1].performanceCount")
                        .value(0))
                .andExpect(jsonPath("$.trend.points[1].qualityCount").value(0))
                .andExpect(jsonPath("$.trend.points[1].unknownCategoryCount")
                        .value(0))
                .andExpect(jsonPath("$.summary.reviewCount").value(0))
                .andExpect(jsonPath("$.summary.categoryCounts[0].key")
                        .value("BUG"));

        mockMvc.perform(get("/api/dashboard/statistics/overview")
                        .param("granularity", "WEEK"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.trend.granularity").value("WEEK"))
                .andExpect(jsonPath("$.trend.points[0].bucketStart")
                        .value("2026-10-12"))
                .andExpect(jsonPath("$.trend.points[0].bugCount").value(3))
                .andExpect(jsonPath("$.trend.points[0].securityCount").value(1))
                .andExpect(jsonPath("$.trend.points[0].performanceCount")
                        .value(1))
                .andExpect(jsonPath("$.trend.points[0].qualityCount").value(1))
                .andExpect(jsonPath("$.trend.points[0].unknownCategoryCount")
                        .value(1));

        verify(statisticsService).overview(any(ReviewHistoryFilter.class),
                eq("DAY"));
        verify(statisticsService).overview(any(ReviewHistoryFilter.class),
                eq("WEEK"));
    }

    @Test
    void shouldRejectInvalidPagination() throws Exception {
        mockMvc.perform(get("/api/dashboard/statistics/reviews")
                        .param("page", "0"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error")
                        .value("invalid_pagination"));

        mockMvc.perform(get("/api/dashboard/statistics/reviews")
                        .param("size", "0"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error")
                        .value("invalid_pagination"));

        mockMvc.perform(get("/api/dashboard/statistics/reviews")
                        .param("size", "101"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error")
                        .value("invalid_pagination"));

        mockMvc.perform(get("/api/dashboard/statistics/reviews")
                        .param("page", "abc"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error")
                        .value("invalid_pagination"));

        verifyNoInteractions(statisticsService);
    }

    @Test
    void shouldRejectInvalidFilters() throws Exception {
        mockMvc.perform(get("/api/dashboard/statistics/overview")
                        .param("prNumber", "0"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("invalid_filter"));

        mockMvc.perform(get("/api/dashboard/statistics/overview")
                        .param("aiStatus", "UNKNOWN"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("invalid_filter"));

        mockMvc.perform(get("/api/dashboard/statistics/overview")
                        .param("taskStatus", "UNKNOWN"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("invalid_filter"));

        mockMvc.perform(get("/api/dashboard/statistics/overview")
                        .param("prNumber", "abc"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("invalid_filter"));

        mockMvc.perform(get("/api/dashboard/statistics/overview")
                        .param("createdFrom", "not-a-date"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("invalid_filter"));

        mockMvc.perform(get("/api/dashboard/statistics/overview")
                        .param("createdFrom", "2026-02-01T00:00:00")
                        .param("createdTo", "2026-01-01T00:00:00"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("invalid_filter"));

        verifyNoInteractions(statisticsService);
    }

    @Test
    void shouldMapInvalidGranularitySortAndRange() throws Exception {
        when(statisticsService.overview(any(ReviewHistoryFilter.class),
                eq("MONTH"))).thenThrow(
                new InvalidStatisticsGranularityException("bad granularity"));
        mockMvc.perform(get("/api/dashboard/statistics/overview")
                        .param("granularity", "MONTH"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error")
                        .value("invalid_granularity"));

        when(statisticsService.reviews(any(ReviewHistoryFilter.class),
                eq(1), eq(20), eq("bad"), eq("desc")))
                .thenThrow(new InvalidStatisticsSortException("bad sort"));
        mockMvc.perform(get("/api/dashboard/statistics/reviews")
                        .param("sort", "bad"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("invalid_sort"));

        when(statisticsService.overview(any(ReviewHistoryFilter.class),
                eq("DAY"))).thenThrow(
                new InvalidStatisticsRangeException("bad range"));
        mockMvc.perform(get("/api/dashboard/statistics/overview"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("invalid_range"));
    }

    @Test
    void shouldReturnSafeInternalErrorForIntegrityFailure() throws Exception {
        when(statisticsService.overview(any(ReviewHistoryFilter.class),
                eq("DAY"))).thenThrow(new ReviewHistoryDataIntegrityException(
                "Missing review_task for report id=7; SQL=SELECT * FROM x"));

        mockMvc.perform(get("/api/dashboard/statistics/overview"))
                .andExpect(status().isInternalServerError())
                .andExpect(content().string(
                        "{\"error\":\"internal_error\"}"));
    }

    @Test
    void shouldNotLeakUnexpectedExceptionDetails() throws Exception {
        when(statisticsService.overview(any(ReviewHistoryFilter.class),
                eq("DAY"))).thenThrow(new RuntimeException(
                "SQL syntax error near SELECT password=super-secret"));

        mockMvc.perform(get("/api/dashboard/statistics/overview"))
                .andExpect(status().isInternalServerError())
                .andExpect(content().string(
                        "{\"error\":\"internal_error\"}"))
                .andExpect(content().string(
                        not(containsString("super-secret"))))
                .andExpect(content().string(
                        not(containsString("SQL"))));
    }

    @Test
    void shouldNotRequireOrEchoTheInternalToken() throws Exception {
        when(statisticsService.overview(any(ReviewHistoryFilter.class),
                eq("DAY"))).thenReturn(emptyOverview());

        mockMvc.perform(get("/api/dashboard/statistics/overview"))
                .andExpect(status().isOk())
                .andExpect(content().string(
                        not(containsString("super-secret-token"))));

        mockMvc.perform(get("/api/dashboard/statistics/overview")
                        .header("X-Internal-Token", "super-secret-token"))
                .andExpect(status().isOk())
                .andExpect(content().string(
                        not(containsString("super-secret-token"))));
    }

    @Test
    void shouldRejectNonLocalPeer() throws Exception {
        mockMvc.perform(get("/api/dashboard/statistics/overview")
                        .with(remoteAddr("203.0.113.10")))
                .andExpect(status().isForbidden())
                .andExpect(content().string(""));

        verifyNoInteractions(statisticsService);
    }

    @Test
    void shouldRejectEncodedAndMatrixDashboardPathsFromNonLocalPeer()
            throws Exception {
        for (String path : new String[]{
                "/api/dashboard;x/statistics/overview",
                "/api/%64ashboard/statistics/overview",
                "/api/dashboard%3Bx/statistics/overview",
                "/api/%2564ashboard/statistics/overview"}) {
            mockMvc.perform(get(URI.create(path))
                            .with(remoteAddr("203.0.113.10")))
                    .andExpect(status().isForbidden())
                    .andExpect(content().string(""));
        }

        verifyNoInteractions(statisticsService);
    }

    @Test
    void shouldNotTrustForwardedHeaders() throws Exception {
        mockMvc.perform(get("/api/dashboard/statistics/overview")
                        .header("X-Forwarded-For", "127.0.0.1")
                        .header("Forwarded", "for=127.0.0.1")
                        .with(remoteAddr("203.0.113.10")))
                .andExpect(status().isForbidden());

        verifyNoInteractions(statisticsService);
    }

    @Test
    void shouldAllowIpv6Loopback() throws Exception {
        when(statisticsService.overview(any(ReviewHistoryFilter.class),
                eq("DAY"))).thenReturn(emptyOverview());

        mockMvc.perform(get("/api/dashboard/statistics/overview")
                        .with(remoteAddr("0:0:0:0:0:0:0:1")))
                .andExpect(status().isOk());
    }

    private static ReviewPageResponse<ReviewStatisticsReviewItem> emptyPage(
            int page, int size) {
        return new ReviewPageResponse<>(List.of(), page, size, 0, 0, false);
    }

    private static ReviewStatisticsOverviewResponse emptyOverview() {
        return new ReviewStatisticsOverviewResponse(
                new ReviewStatisticsRange(FROM, TO, "Asia/Shanghai",
                        StatisticsGranularity.DAY),
                LocalDateTime.of(2026, 11, 13, 20, 0),
                new ReviewStatisticsSummary(
                        0, 0, 0, null, null, null, 0, null, 0, null,
                        0, 0, 0, null, 0,
                        List.of(new ReviewStatisticsCount("BUG", 0),
                                new ReviewStatisticsCount("SECURITY", 0),
                                new ReviewStatisticsCount("PERFORMANCE", 0),
                                new ReviewStatisticsCount("QUALITY", 0),
                                new ReviewStatisticsCount("UNKNOWN", 0)),
                        List.of(new ReviewStatisticsCount("CRITICAL", 0),
                                new ReviewStatisticsCount("HIGH", 0),
                                new ReviewStatisticsCount("MEDIUM", 0),
                                new ReviewStatisticsCount("LOW", 0),
                                new ReviewStatisticsCount("INFO", 0),
                                new ReviewStatisticsCount("UNKNOWN", 0)),
                        List.of(new ReviewStatisticsCount("PUBLISHED", 0),
                                new ReviewStatisticsCount("PARTIAL", 0),
                                new ReviewStatisticsCount("FAILED", 0),
                                new ReviewStatisticsCount("PENDING", 0),
                                new ReviewStatisticsCount("UNKNOWN", 0)),
                        List.of(new ReviewStatisticsCount("COMPLETED", 0),
                                new ReviewStatisticsCount("DEGRADED", 0),
                                new ReviewStatisticsCount("UNKNOWN", 0))),
                new ReviewStatisticsTrend(StatisticsGranularity.DAY,
                        false, List.of()),
                new ReviewStatisticsDataQuality(
                        0, 0, 0, 0, 0, 0, 0, 0, 0));
    }

    private static ReviewStatisticsTrend dayTrend() {
        return new ReviewStatisticsTrend(StatisticsGranularity.DAY, true,
                List.of(
                        new ReviewStatisticsTrendPoint(
                                LocalDate.of(2026, 10, 19),
                                LocalDate.of(2026, 10, 19),
                                2, 4, 2, 2, 0, 1, 0, 1),
                        new ReviewStatisticsTrendPoint(
                                LocalDate.of(2026, 10, 20),
                                LocalDate.of(2026, 10, 20),
                                0, 0, 0, 0, 0, 0, 0, 0)));
    }

    private static ReviewStatisticsTrend weekTrend() {
        return new ReviewStatisticsTrend(StatisticsGranularity.WEEK, true,
                List.of(new ReviewStatisticsTrendPoint(
                        LocalDate.of(2026, 10, 12),
                        LocalDate.of(2026, 10, 18),
                        3, 6, 2, 3, 1, 1, 1, 1)));
    }

    private static ReviewStatisticsOverviewResponse overviewWithTrend(
            ReviewStatisticsTrend trend) {
        ReviewStatisticsOverviewResponse base = emptyOverview();
        return new ReviewStatisticsOverviewResponse(
                new ReviewStatisticsRange(FROM, TO, "Asia/Shanghai",
                        trend.granularity()),
                base.generatedAt(), base.summary(), trend,
                base.dataQuality());
    }

    private static ReviewStatisticsReviewItem reviewItem() {
        return new ReviewStatisticsReviewItem(
                1003L, "gamma", "incomplete-demo", 9,
                "0123456789abcdef0123456789abcdef01234567",
                LocalDateTime.of(2026, 10, 30, 8, 0),
                "COMPLETED", "COMPLETED", "PUBLISHED",
                3, 2, false, 0, 0, true,
                0, 1, 1, 1, 0, 0, 0,
                1, 1, 0, 0, 0);
    }

    private static RequestPostProcessor remoteAddr(String address) {
        return request -> {
            request.setRemoteAddr(address);
            return request;
        };
    }
}
