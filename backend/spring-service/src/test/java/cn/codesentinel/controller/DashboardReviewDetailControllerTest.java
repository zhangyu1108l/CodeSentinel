package cn.codesentinel.controller;

import cn.codesentinel.review.ReviewCommentResponse;
import cn.codesentinel.review.ReviewFindingResponse;
import cn.codesentinel.review.ReviewHistoryDataIntegrityException;
import cn.codesentinel.review.ReviewHistoryIncompleteException;
import cn.codesentinel.review.ReviewHistoryNotFoundException;
import cn.codesentinel.review.ReviewHistoryQueryService;
import cn.codesentinel.review.ReviewPageResponse;
import cn.codesentinel.review.ReviewReportResponse;
import cn.codesentinel.task.TaskNotFoundException;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

import java.net.URI;
import java.time.LocalDateTime;
import java.util.Arrays;
import java.util.List;

import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.not;
import static org.hamcrest.Matchers.nullValue;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(DashboardReviewDetailController.class)
@TestPropertySource(properties = "review.history.internal-token=")
class DashboardReviewDetailControllerTest {

    private static final long TASK_ID = 7L;

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private ReviewHistoryQueryService queryService;

    @Test
    void shouldReturnReportWithEveryPublicField() throws Exception {
        when(queryService.getReport(TASK_ID)).thenReturn(reportResponse());

        mockMvc.perform(get("/api/dashboard/reviews/7"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.taskId").value(7))
                .andExpect(jsonPath("$.owner").value("owner"))
                .andExpect(jsonPath("$.repo").value("repo"))
                .andExpect(jsonPath("$.prNumber").value(42))
                .andExpect(jsonPath("$.commitSha").value("abc123"))
                .andExpect(jsonPath("$.taskStatus").value("COMPLETED"))
                .andExpect(jsonPath("$.aiStatus").value("DEGRADED"))
                .andExpect(jsonPath("$.publishStatus").value("PARTIAL"))
                .andExpect(jsonPath("$.findingCount").value(2))
                .andExpect(jsonPath("$.publishedCommentCount").value(1))
                .andExpect(jsonPath("$.summaryCommentId").value(900))
                .andExpect(jsonPath("$.publishedAt").exists())
                .andExpect(jsonPath("$.createdAt").exists())
                .andExpect(jsonPath("$.updatedAt").exists())
                .andExpect(jsonPath("$.reportId").doesNotExist())
                .andExpect(jsonPath("$.id").doesNotExist());

        verify(queryService).getReport(TASK_ID);
    }

    @Test
    void shouldUseDefaultPaginationForFindingsAndComments() throws Exception {
        when(queryService.getFindings(TASK_ID, 1, 20))
                .thenReturn(findingPage(1, 20));
        when(queryService.getComments(TASK_ID, 1, 20))
                .thenReturn(commentPage(1, 20));

        mockMvc.perform(get("/api/dashboard/reviews/7/findings"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.page").value(1))
                .andExpect(jsonPath("$.size").value(20));

        mockMvc.perform(get("/api/dashboard/reviews/7/comments"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.page").value(1))
                .andExpect(jsonPath("$.size").value(20));

        verify(queryService).getFindings(TASK_ID, 1, 20);
        verify(queryService).getComments(TASK_ID, 1, 20);
    }

    @Test
    void shouldPassCustomPaginationToBothSections() throws Exception {
        when(queryService.getFindings(TASK_ID, 3, 50))
                .thenReturn(findingPage(3, 50));
        when(queryService.getComments(TASK_ID, 2, 100))
                .thenReturn(commentPage(2, 100));

        mockMvc.perform(get("/api/dashboard/reviews/7/findings")
                        .param("page", "3")
                        .param("size", "50"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.page").value(3))
                .andExpect(jsonPath("$.size").value(50));

        mockMvc.perform(get("/api/dashboard/reviews/7/comments")
                        .param("page", "2")
                        .param("size", "100"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.page").value(2))
                .andExpect(jsonPath("$.size").value(100));

        verify(queryService).getFindings(TASK_ID, 3, 50);
        verify(queryService).getComments(TASK_ID, 2, 100);
    }

    @Test
    void shouldMapFindingFieldsWithoutInternalIdentifiers() throws Exception {
        when(queryService.getFindings(TASK_ID, 1, 20))
                .thenReturn(findingPage(1, 20));

        mockMvc.perform(get("/api/dashboard/reviews/7/findings"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items.length()").value(1))
                .andExpect(jsonPath("$.items[0].ordinal").value(0))
                .andExpect(jsonPath("$.items[0].category").value("SECURITY"))
                .andExpect(jsonPath("$.items[0].severity").value("HIGH"))
                .andExpect(jsonPath("$.items[0].confidence").value(0.94))
                .andExpect(jsonPath("$.items[0].ruleId").value("CWE-89"))
                .andExpect(jsonPath("$.items[0].title").value("SQL injection"))
                .andExpect(jsonPath("$.items[0].filePath")
                        .value("src/UserRepository.java"))
                .andExpect(jsonPath("$.items[0].startLine").value(52))
                .andExpect(jsonPath("$.items[0].endLine").value(58))
                .andExpect(jsonPath("$.items[0].description")
                        .value("Externally controlled SQL."))
                .andExpect(jsonPath("$.items[0].reason")
                        .value("Input is concatenated."))
                .andExpect(jsonPath("$.items[0].suggestion")
                        .value("Use parameters."))
                .andExpect(jsonPath("$.items[0].references.length()").value(4))
                .andExpect(jsonPath("$.items[0].references[0]")
                        .value("CWE-89"))
                .andExpect(jsonPath("$.items[0].references[1]")
                        .value(nullValue()))
                .andExpect(jsonPath("$.items[0].references[2]")
                        .value(" "))
                .andExpect(jsonPath("$.items[0].id").doesNotExist())
                .andExpect(jsonPath("$.items[0].reportId").doesNotExist())
                .andExpect(jsonPath("$.totalItems").value(1))
                .andExpect(jsonPath("$.totalPages").value(1))
                .andExpect(jsonPath("$.hasNext").value(false));
    }

    @Test
    void shouldMapCommentFieldsAndNullableGithubId() throws Exception {
        when(queryService.getComments(TASK_ID, 1, 20))
                .thenReturn(commentPage(1, 20));

        mockMvc.perform(get("/api/dashboard/reviews/7/comments"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items.length()").value(1))
                .andExpect(jsonPath("$.items[0].findingOrdinal").value(0))
                .andExpect(jsonPath("$.items[0].githubCommentId")
                        .value(nullValue()))
                .andExpect(jsonPath("$.items[0].filePath")
                        .value("src/UserRepository.java"))
                .andExpect(jsonPath("$.items[0].startLine").value(52))
                .andExpect(jsonPath("$.items[0].endLine").value(58))
                .andExpect(jsonPath("$.items[0].id").doesNotExist())
                .andExpect(jsonPath("$.items[0].reportId").doesNotExist());
    }

    @Test
    void shouldReturnSameSafe404ForMissingTaskAndMissingReport()
            throws Exception {
        when(queryService.getReport(TASK_ID))
                .thenThrow(new TaskNotFoundException(TASK_ID));

        mockMvc.perform(get("/api/dashboard/reviews/7"))
                .andExpect(status().isNotFound())
                .andExpect(content().string(
                        "{\"error\":\"review_not_found\"}"))
                .andExpect(content().string(
                        not(containsString("Task not found"))));

        when(queryService.getFindings(TASK_ID, 1, 20))
                .thenThrow(new ReviewHistoryNotFoundException(TASK_ID));

        mockMvc.perform(get("/api/dashboard/reviews/7/findings"))
                .andExpect(status().isNotFound())
                .andExpect(content().string(
                        "{\"error\":\"review_not_found\"}"))
                .andExpect(content().string(
                        not(containsString("Review history not found"))));
    }

    @Test
    void shouldReturn409ForIncompleteFindingsAndComments() throws Exception {
        when(queryService.getFindings(TASK_ID, 1, 20))
                .thenThrow(new ReviewHistoryIncompleteException(
                        "Incomplete findings history for task id=7"));

        mockMvc.perform(get("/api/dashboard/reviews/7/findings"))
                .andExpect(status().isConflict())
                .andExpect(content().string(
                        "{\"error\":\"review_history_incomplete\"}"))
                .andExpect(content().string(
                        not(containsString("Incomplete findings"))));

        when(queryService.getComments(TASK_ID, 1, 20))
                .thenThrow(new ReviewHistoryIncompleteException(
                        "Incomplete comments history for task id=7"));

        mockMvc.perform(get("/api/dashboard/reviews/7/comments"))
                .andExpect(status().isConflict())
                .andExpect(content().string(
                        "{\"error\":\"review_history_incomplete\"}"));
    }

    @Test
    void shouldRejectInvalidTaskIdsBeforeCallingTheService()
            throws Exception {
        for (String taskId : new String[]{
                "abc",
                "0",
                "-7",
                "7.5",
                "99999999999999999999",
                "9223372036854775808"}) {
            mockMvc.perform(get("/api/dashboard/reviews/" + taskId))
                    .andExpect(status().isBadRequest())
                    .andExpect(jsonPath("$.error")
                            .value("invalid_task_id"));

            mockMvc.perform(get("/api/dashboard/reviews/" + taskId
                            + "/findings"))
                    .andExpect(status().isBadRequest())
                    .andExpect(jsonPath("$.error")
                            .value("invalid_task_id"));

            mockMvc.perform(get("/api/dashboard/reviews/" + taskId
                            + "/comments"))
                    .andExpect(status().isBadRequest())
                    .andExpect(jsonPath("$.error")
                            .value("invalid_task_id"));
        }

        verifyNoInteractions(queryService);
    }

    @Test
    void shouldRejectInvalidPaginationBeforeCallingTheService()
            throws Exception {
        mockMvc.perform(get("/api/dashboard/reviews/7/findings")
                        .param("page", "0"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error")
                        .value("invalid_pagination"));

        mockMvc.perform(get("/api/dashboard/reviews/7/findings")
                        .param("size", "101"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error")
                        .value("invalid_pagination"));

        mockMvc.perform(get("/api/dashboard/reviews/7/comments")
                        .param("size", "0"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error")
                        .value("invalid_pagination"));

        mockMvc.perform(get("/api/dashboard/reviews/7/findings")
                        .param("page", "abc"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error")
                        .value("invalid_pagination"));

        mockMvc.perform(get("/api/dashboard/reviews/7/comments")
                        .param("size", "99999999999999999999"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error")
                        .value("invalid_pagination"));

        verifyNoInteractions(queryService);
    }

    @Test
    void shouldNotRequireInternalToken() throws Exception {
        when(queryService.getReport(TASK_ID)).thenReturn(reportResponse());

        mockMvc.perform(get("/api/dashboard/reviews/7"))
                .andExpect(status().isOk());
    }

    @Test
    void shouldNotEchoAForgedInternalToken() throws Exception {
        when(queryService.getReport(TASK_ID)).thenReturn(reportResponse());

        mockMvc.perform(get("/api/dashboard/reviews/7")
                        .header("X-Internal-Token", "super-secret-token"))
                .andExpect(status().isOk())
                .andExpect(content().string(
                        not(containsString("super-secret-token"))));
    }

    @Test
    void shouldRejectNonLocalPeerBeforeCallingTheService()
            throws Exception {
        mockMvc.perform(get("/api/dashboard/reviews/7")
                        .with(remoteAddr("203.0.113.10")))
                .andExpect(status().isForbidden())
                .andExpect(content().string(""));

        verifyNoInteractions(queryService);
    }

    @Test
    void shouldRejectEncodedAndMatrixDetailPathsFromNonLocalPeer()
            throws Exception {
        for (String path : new String[]{
                "/api/dashboard;x/reviews/7",
                "/api/%64ashboard/reviews/7",
                "/api/dashboard%3Bx/reviews/7",
                "/api/%2564ashboard/reviews/7",
                "/api/dashboard/reviews/7/findings;x",
                "/api/dashboard/reviews/7/comments;x"}) {
            mockMvc.perform(get(URI.create(path))
                            .with(remoteAddr("203.0.113.10")))
                    .andExpect(status().isForbidden())
                    .andExpect(content().string(""));
        }

        verifyNoInteractions(queryService);
    }

    @Test
    void shouldNotTrustForwardedHeaders() throws Exception {
        mockMvc.perform(get("/api/dashboard/reviews/7")
                        .header("X-Forwarded-For", "127.0.0.1")
                        .header("Forwarded", "for=127.0.0.1")
                        .with(remoteAddr("203.0.113.10")))
                .andExpect(status().isForbidden());

        verifyNoInteractions(queryService);
    }

    @Test
    void shouldAllowIpv6Loopback() throws Exception {
        when(queryService.getReport(TASK_ID)).thenReturn(reportResponse());

        mockMvc.perform(get("/api/dashboard/reviews/7")
                        .with(remoteAddr("0:0:0:0:0:0:0:1")))
                .andExpect(status().isOk());
    }

    @Test
    void shouldReturnSafeInternalErrorForUnreadableHistory()
            throws Exception {
        when(queryService.getFindings(TASK_ID, 1, 20))
                .thenThrow(new ReviewHistoryDataIntegrityException(
                        "Unreadable references_json for report id=70"));

        mockMvc.perform(get("/api/dashboard/reviews/7/findings"))
                .andExpect(status().isInternalServerError())
                .andExpect(content().string(
                        "{\"error\":\"internal_error\"}"))
                .andExpect(content().string(
                        not(containsString("references_json"))))
                .andExpect(content().string(not(containsString("report id"))));
    }

    @Test
    void shouldReturnSafeInternalErrorForUnexpectedExceptions()
            throws Exception {
        when(queryService.getReport(TASK_ID)).thenThrow(
                new IllegalStateException(
                        "SQL select * from internal_table failed"));

        mockMvc.perform(get("/api/dashboard/reviews/7"))
                .andExpect(status().isInternalServerError())
                .andExpect(content().string(
                        "{\"error\":\"internal_error\"}"))
                .andExpect(content().string(
                        not(containsString("SQL select"))))
                .andExpect(content().string(
                        not(containsString("internal_table"))))
                .andExpect(content().string(
                        not(containsString("IllegalStateException"))));
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

    private static ReviewPageResponse<ReviewFindingResponse> findingPage(
            int page, int size) {
        ReviewFindingResponse finding = new ReviewFindingResponse(
                0, "SECURITY", "HIGH", 0.94, "CWE-89", "SQL injection",
                "src/UserRepository.java", 52, 58,
                "Externally controlled SQL.",
                "Input is concatenated.",
                "Use parameters.",
                Arrays.asList("CWE-89", null, " ", "OWASP"));
        return new ReviewPageResponse<>(
                List.of(finding), page, size, 1, 1, false);
    }

    private static ReviewPageResponse<ReviewCommentResponse> commentPage(
            int page, int size) {
        ReviewCommentResponse comment = new ReviewCommentResponse(
                0, null, "src/UserRepository.java", 52, 58);
        return new ReviewPageResponse<>(
                List.of(comment), page, size, 1, 1, false);
    }

    private static RequestPostProcessor remoteAddr(String address) {
        return request -> {
            request.setRemoteAddr(address);
            return request;
        };
    }
}
