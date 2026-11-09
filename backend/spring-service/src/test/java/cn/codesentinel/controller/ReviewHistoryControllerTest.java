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
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import java.time.LocalDateTime;
import java.util.Arrays;
import java.util.List;

import static org.hamcrest.Matchers.nullValue;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(ReviewHistoryController.class)
@TestPropertySource(properties =
        "review.history.internal-token=test-history-token")
class ReviewHistoryControllerTest {

    private static final String TOKEN_HEADER = "X-Internal-Token";
    private static final String TOKEN = "test-history-token";
    private static final long TASK_ID = 7L;

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private ReviewHistoryQueryService queryService;

    @Test
    void shouldReturnReportWithToken() throws Exception {
        when(queryService.getReport(TASK_ID)).thenReturn(reportResponse());

        mockMvc.perform(get("/api/reviews/7").header(TOKEN_HEADER, TOKEN))
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
    }

    @Test
    void shouldReturnFindingsPage() throws Exception {
        when(queryService.getFindings(TASK_ID, 2, 50))
                .thenReturn(findingPage());

        mockMvc.perform(get("/api/reviews/7/findings")
                        .param("page", "2")
                        .param("size", "50")
                        .header(TOKEN_HEADER, TOKEN))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items.length()").value(1))
                .andExpect(jsonPath("$.items[0].ordinal").value(0))
                .andExpect(jsonPath("$.items[0].category").value("SECURITY"))
                .andExpect(jsonPath("$.items[0].severity").value("HIGH"))
                .andExpect(jsonPath("$.items[0].confidence").value(0.94))
                .andExpect(jsonPath("$.items[0].ruleId").value("CWE-89"))
                .andExpect(jsonPath("$.items[0].filePath")
                        .value("src/A.java"))
                .andExpect(jsonPath("$.items[0].startLine").value(52))
                .andExpect(jsonPath("$.items[0].references[0]")
                        .value("CWE-89"))
                .andExpect(jsonPath("$.items[0].references[1]")
                        .value(nullValue()))
                .andExpect(jsonPath("$.page").value(2))
                .andExpect(jsonPath("$.size").value(50))
                .andExpect(jsonPath("$.totalItems").value(60))
                .andExpect(jsonPath("$.totalPages").value(2))
                .andExpect(jsonPath("$.hasNext").value(false))
                .andExpect(jsonPath("$.items[0].id").doesNotExist())
                .andExpect(jsonPath("$.items[0].reportId").doesNotExist());

        verify(queryService).getFindings(TASK_ID, 2, 50);
    }

    @Test
    void shouldReturnCommentsPageWithNullableGithubId() throws Exception {
        when(queryService.getComments(TASK_ID, 1, 20))
                .thenReturn(commentPage());

        mockMvc.perform(get("/api/reviews/7/comments")
                        .header(TOKEN_HEADER, TOKEN))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items[0].findingOrdinal").value(0))
                .andExpect(jsonPath("$.items[0].githubCommentId")
                        .value(nullValue()))
                .andExpect(jsonPath("$.items[0].filePath")
                        .value("src/A.java"))
                .andExpect(jsonPath("$.items[0].startLine").value(52))
                .andExpect(jsonPath("$.items[0].endLine").value(52))
                .andExpect(jsonPath("$.items[0].id").doesNotExist())
                .andExpect(jsonPath("$.items[0].reportId").doesNotExist())
                .andExpect(jsonPath("$.page").value(1))
                .andExpect(jsonPath("$.size").value(20))
                .andExpect(jsonPath("$.totalItems").value(1))
                .andExpect(jsonPath("$.totalPages").value(1))
                .andExpect(jsonPath("$.hasNext").value(false));
    }

    @Test
    void shouldRejectMissingTokenOnEveryEndpoint() throws Exception {
        mockMvc.perform(get("/api/reviews/7"))
                .andExpect(status().isUnauthorized())
                .andExpect(content().string(""));
        mockMvc.perform(get("/api/reviews/7/findings"))
                .andExpect(status().isUnauthorized())
                .andExpect(content().string(""));
        mockMvc.perform(get("/api/reviews/7/comments"))
                .andExpect(status().isUnauthorized())
                .andExpect(content().string(""));

        verifyNoInteractions(queryService);
    }

    @Test
    void shouldRejectWrongToken() throws Exception {
        mockMvc.perform(get("/api/reviews/7")
                        .header(TOKEN_HEADER, "wrong-token"))
                .andExpect(status().isUnauthorized())
                .andExpect(content().string(""));

        verifyNoInteractions(queryService);
    }

    @Test
    void shouldRejectEmptyTokenHeader() throws Exception {
        mockMvc.perform(get("/api/reviews/7").header(TOKEN_HEADER, ""))
                .andExpect(status().isUnauthorized())
                .andExpect(content().string(""));

        verifyNoInteractions(queryService);
    }

    @Test
    void shouldRejectAllRequestsWhenTokenIsNotConfigured() {
        ReviewHistoryController controller =
                new ReviewHistoryController(queryService, "");

        ResponseEntity<?> response = controller.getReport(TASK_ID, TOKEN);

        assertEquals(HttpStatus.UNAUTHORIZED, response.getStatusCode());
        verifyNoInteractions(queryService);
    }

    @Test
    void shouldReturnSameEmpty404ForMissingTaskAndReport() throws Exception {
        when(queryService.getReport(TASK_ID))
                .thenThrow(new TaskNotFoundException(TASK_ID));
        mockMvc.perform(get("/api/reviews/7").header(TOKEN_HEADER, TOKEN))
                .andExpect(status().isNotFound())
                .andExpect(content().string(""));

        when(queryService.getReport(8L))
                .thenThrow(new ReviewHistoryNotFoundException(8L));
        mockMvc.perform(get("/api/reviews/8").header(TOKEN_HEADER, TOKEN))
                .andExpect(status().isNotFound())
                .andExpect(content().string(""));
    }

    @Test
    void shouldReturnConflictForIncompleteHistory() throws Exception {
        when(queryService.getFindings(TASK_ID, 1, 20))
                .thenThrow(new ReviewHistoryIncompleteException(
                        "Incomplete findings history"));

        mockMvc.perform(get("/api/reviews/7/findings")
                        .header(TOKEN_HEADER, TOKEN))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.error")
                        .value("review_history_incomplete"))
                .andExpect(content().string(
                        "{\"error\":\"review_history_incomplete\"}"));
    }

    @Test
    void shouldReturnBadRequestForInvalidPagination() throws Exception {
        mockMvc.perform(get("/api/reviews/7/findings")
                        .param("page", "0")
                        .header(TOKEN_HEADER, TOKEN))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("invalid_pagination"));

        mockMvc.perform(get("/api/reviews/7/findings")
                        .param("size", "0")
                        .header(TOKEN_HEADER, TOKEN))
                .andExpect(status().isBadRequest());

        mockMvc.perform(get("/api/reviews/7/comments")
                        .param("size", "101")
                        .header(TOKEN_HEADER, TOKEN))
                .andExpect(status().isBadRequest());

        verifyNoInteractions(queryService);
    }

    @Test
    void shouldReturnBadRequestForNonNumericTaskId() throws Exception {
        mockMvc.perform(get("/api/reviews/not-a-number")
                        .header(TOKEN_HEADER, TOKEN))
                .andExpect(status().isBadRequest());

        verifyNoInteractions(queryService);
    }

    @Test
    void shouldReturnEmpty500ForUnreadableReferences() throws Exception {
        when(queryService.getFindings(TASK_ID, 1, 20))
                .thenThrow(new ReviewHistoryDataIntegrityException(
                        "Unreadable references_json for report id=70"));

        mockMvc.perform(get("/api/reviews/7/findings")
                        .header(TOKEN_HEADER, TOKEN))
                .andExpect(status().isInternalServerError())
                .andExpect(content().string(""));
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

    private static ReviewPageResponse<ReviewFindingResponse> findingPage() {
        ReviewFindingResponse finding = new ReviewFindingResponse(
                0, "SECURITY", "HIGH", 0.94, "CWE-89", "title",
                "src/A.java", 52, 52, "description", "reason", "suggestion",
                Arrays.asList("CWE-89", null));
        return new ReviewPageResponse<>(List.of(finding), 2, 50, 60, 2, false);
    }

    private static ReviewPageResponse<ReviewCommentResponse> commentPage() {
        ReviewCommentResponse comment = new ReviewCommentResponse(
                0, null, "src/A.java", 52, 52);
        return new ReviewPageResponse<>(List.of(comment), 1, 20, 1, 1, false);
    }
}