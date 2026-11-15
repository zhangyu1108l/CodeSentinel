package cn.codesentinel.controller;

import cn.codesentinel.review.ReviewHistoryDataIntegrityException;
import cn.codesentinel.review.ReviewHistoryFilter;
import cn.codesentinel.review.ReviewHistoryListService;
import cn.codesentinel.review.ReviewPageResponse;
import cn.codesentinel.review.ReviewReportResponse;
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
import java.time.LocalDateTime;
import java.util.List;

import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.not;
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

@WebMvcTest(DashboardReviewController.class)
@TestPropertySource(properties = "review.history.internal-token=")
class DashboardReviewControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private ReviewHistoryListService listService;

    @Test
    void shouldUseDefaultPaginationAndReturnEmptyEnvelope() throws Exception {
        when(listService.search(any(ReviewHistoryFilter.class), eq(1), eq(20)))
                .thenReturn(emptyPage(1, 20));

        mockMvc.perform(get("/api/dashboard/reviews"))
                .andExpect(status().isOk())
                .andExpect(content().json("""
                        {"items":[],"page":1,"size":20,
                         "totalItems":0,"totalPages":0,"hasNext":false}
                        """, true));

        ArgumentCaptor<ReviewHistoryFilter> filterCaptor =
                ArgumentCaptor.forClass(ReviewHistoryFilter.class);
        verify(listService).search(filterCaptor.capture(), eq(1), eq(20));

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
    void shouldPassAllFiltersAndTrimAndNormalize() throws Exception {
        when(listService.search(any(ReviewHistoryFilter.class), eq(2), eq(50)))
                .thenReturn(emptyPage(2, 50));

        mockMvc.perform(get("/api/dashboard/reviews")
                        .param("page", "2")
                        .param("size", "50")
                        .param("owner", " owner ")
                        .param("repo", "repo")
                        .param("prNumber", "42")
                        .param("taskStatus", "COMPLETED")
                        .param("publishStatus", "PUBLISHED")
                        .param("aiStatus", "degraded")
                        .param("createdFrom", "2026-01-01T00:00:00")
                        .param("createdTo", "2026-02-01T00:00:00"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.page").value(2))
                .andExpect(jsonPath("$.size").value(50));

        ArgumentCaptor<ReviewHistoryFilter> filterCaptor =
                ArgumentCaptor.forClass(ReviewHistoryFilter.class);
        verify(listService).search(filterCaptor.capture(), eq(2), eq(50));

        ReviewHistoryFilter filter = filterCaptor.getValue();
        assertEquals("owner", filter.owner());
        assertEquals("repo", filter.repo());
        assertEquals(42, filter.prNumber());
        assertEquals(TaskStatus.COMPLETED, filter.taskStatus());
        assertEquals(PublishStatus.PUBLISHED, filter.publishStatus());
        assertEquals("DEGRADED", filter.aiStatus());
        assertEquals(LocalDateTime.of(2026, 1, 1, 0, 0),
                filter.createdFrom());
        assertEquals(LocalDateTime.of(2026, 2, 1, 0, 0),
                filter.createdTo());
    }

    @Test
    void shouldMapReviewReportResponseFields() throws Exception {
        when(listService.search(any(ReviewHistoryFilter.class), eq(1), eq(20)))
                .thenReturn(new ReviewPageResponse<>(
                        List.of(reportResponse()), 1, 20, 1, 1, false));

        mockMvc.perform(get("/api/dashboard/reviews"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items.length()").value(1))
                .andExpect(jsonPath("$.items[0].taskId").value(7))
                .andExpect(jsonPath("$.items[0].owner").value("owner"))
                .andExpect(jsonPath("$.items[0].repo").value("repo"))
                .andExpect(jsonPath("$.items[0].prNumber").value(42))
                .andExpect(jsonPath("$.items[0].commitSha").value("abc123"))
                .andExpect(jsonPath("$.items[0].taskStatus")
                        .value("COMPLETED"))
                .andExpect(jsonPath("$.items[0].aiStatus").value("DEGRADED"))
                .andExpect(jsonPath("$.items[0].publishStatus")
                        .value("PARTIAL"))
                .andExpect(jsonPath("$.items[0].findingCount").value(2))
                .andExpect(jsonPath("$.items[0].publishedCommentCount")
                        .value(1))
                .andExpect(jsonPath("$.items[0].summaryCommentId")
                        .value(900))
                .andExpect(jsonPath("$.items[0].publishedAt").exists())
                .andExpect(jsonPath("$.items[0].createdAt").exists())
                .andExpect(jsonPath("$.items[0].updatedAt").exists())
                .andExpect(jsonPath("$.items[0].reportId").doesNotExist());
    }

    @Test
    void shouldNotRequireInternalToken() throws Exception {
        when(listService.search(any(ReviewHistoryFilter.class), eq(1), eq(20)))
                .thenReturn(emptyPage(1, 20));

        mockMvc.perform(get("/api/dashboard/reviews"))
                .andExpect(status().isOk());
    }

    @Test
    void shouldNotEchoInternalToken() throws Exception {
        when(listService.search(any(ReviewHistoryFilter.class), eq(1), eq(20)))
                .thenReturn(emptyPage(1, 20));

        mockMvc.perform(get("/api/dashboard/reviews")
                        .header("X-Internal-Token", "super-secret-token"))
                .andExpect(status().isOk())
                .andExpect(content().string(
                        not(containsString("super-secret-token"))));
    }

    @Test
    void shouldRejectNonLocalPeer() throws Exception {
        mockMvc.perform(get("/api/dashboard/reviews")
                        .with(remoteAddr("203.0.113.10")))
                .andExpect(status().isForbidden())
                .andExpect(content().string(""));

        verifyNoInteractions(listService);
    }

    @Test
    void shouldRejectEncodedAndMatrixDashboardPathsFromNonLocalPeer()
            throws Exception {
        for (String path : new String[]{
                "/api/dashboard;x/reviews",
                "/api/%64ashboard/reviews",
                "/api/dashboard%3Bx/reviews",
                "/api/%2564ashboard/reviews"}) {
            mockMvc.perform(get(URI.create(path))
                            .with(remoteAddr("203.0.113.10")))
                    .andExpect(status().isForbidden())
                    .andExpect(content().string(""));
        }

        verifyNoInteractions(listService);
    }

    @Test
    void shouldNotTrustForwardedHeaders() throws Exception {
        mockMvc.perform(get("/api/dashboard/reviews")
                        .header("X-Forwarded-For", "127.0.0.1")
                        .header("Forwarded", "for=127.0.0.1")
                        .with(remoteAddr("203.0.113.10")))
                .andExpect(status().isForbidden());

        verifyNoInteractions(listService);
    }

    @Test
    void shouldAllowIpv6Loopback() throws Exception {
        when(listService.search(any(ReviewHistoryFilter.class), eq(1), eq(20)))
                .thenReturn(emptyPage(1, 20));

        mockMvc.perform(get("/api/dashboard/reviews")
                        .with(remoteAddr("0:0:0:0:0:0:0:1")))
                .andExpect(status().isOk());
    }

    @Test
    void shouldRejectInvalidPagination() throws Exception {
        mockMvc.perform(get("/api/dashboard/reviews")
                        .param("page", "0"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error")
                        .value("invalid_pagination"));

        mockMvc.perform(get("/api/dashboard/reviews")
                        .param("size", "101"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error")
                        .value("invalid_pagination"));

        mockMvc.perform(get("/api/dashboard/reviews")
                        .param("page", "abc"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error")
                        .value("invalid_pagination"));

        verifyNoInteractions(listService);
    }

    @Test
    void shouldRejectInvalidFilters() throws Exception {
        mockMvc.perform(get("/api/dashboard/reviews")
                        .param("prNumber", "0"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("invalid_filter"));

        mockMvc.perform(get("/api/dashboard/reviews")
                        .param("aiStatus", "UNKNOWN"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("invalid_filter"));

        mockMvc.perform(get("/api/dashboard/reviews")
                        .param("taskStatus", "UNKNOWN"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("invalid_filter"));

        mockMvc.perform(get("/api/dashboard/reviews")
                        .param("createdFrom", "not-a-date"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("invalid_filter"));

        mockMvc.perform(get("/api/dashboard/reviews")
                        .param("createdFrom", "2026-02-01T00:00:00")
                        .param("createdTo", "2026-01-01T00:00:00"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("invalid_filter"));

        verifyNoInteractions(listService);
    }

    @Test
    void shouldReturnSafeInternalErrorForUnreadableHistory() throws Exception {
        when(listService.search(any(ReviewHistoryFilter.class), eq(1), eq(20)))
                .thenThrow(new ReviewHistoryDataIntegrityException(
                        "Missing review_task for report task id=7"));

        mockMvc.perform(get("/api/dashboard/reviews"))
                .andExpect(status().isInternalServerError())
                .andExpect(content().string(
                        "{\"error\":\"internal_error\"}"));
    }

    private static ReviewPageResponse<ReviewReportResponse> emptyPage(
            int page, int size) {
        return new ReviewPageResponse<>(List.of(), page, size, 0, 0, false);
    }

    private static ReviewReportResponse reportResponse() {
        return new ReviewReportResponse(
                7L, "owner", "repo", 42, "abc123",
                "COMPLETED", "DEGRADED", "PARTIAL",
                2, 1, 900L,
                LocalDateTime.of(2026, 1, 2, 3, 4, 5),
                LocalDateTime.of(2026, 1, 2, 3, 0),
                LocalDateTime.of(2026, 1, 2, 3, 4));
    }

    private static RequestPostProcessor remoteAddr(String address) {
        return request -> {
            request.setRemoteAddr(address);
            return request;
        };
    }
}
