package cn.codesentinel.controller;

import cn.codesentinel.task.ReviewResultRejectedException;
import cn.codesentinel.task.ReviewResultRequest;
import cn.codesentinel.task.ReviewResultResponse;
import cn.codesentinel.task.ReviewResultService;
import cn.codesentinel.task.TaskNotFoundException;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import java.time.LocalDateTime;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(ReviewResultController.class)
@TestPropertySource(properties = "review.result.internal-token=test-internal-token")
class ReviewResultControllerTest {

    private static final String PATH = "/api/tasks/1/result";
    private static final String TOKEN_HEADER = "X-Internal-Token";
    private static final String TOKEN = "test-internal-token";
    private static final String SHA = "abc123def456";
    private static final String BODY = "{\"commit_sha\":\"" + SHA
            + "\",\"status\":\"COMPLETED\",\"findings\":[]}";

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private ReviewResultService reviewResultService;

    @Test
    void shouldAcceptFirstReceiptWithAccepted() throws Exception {
        when(reviewResultService.receiveResult(eq(1L), any()))
                .thenReturn(new ReviewResultResponse(1L, SHA, false, "PENDING",
                        LocalDateTime.of(2026, 1, 1, 0, 0)));

        mockMvc.perform(post(PATH).header(TOKEN_HEADER, TOKEN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(BODY))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.task_id").value(1))
                .andExpect(jsonPath("$.commit_sha").value(SHA))
                .andExpect(jsonPath("$.duplicate").value(false))
                .andExpect(jsonPath("$.publish_status").value("PENDING"))
                .andExpect(jsonPath("$.received_at").exists());

        ArgumentCaptor<ReviewResultRequest> captor =
                ArgumentCaptor.forClass(ReviewResultRequest.class);
        verify(reviewResultService).receiveResult(eq(1L), captor.capture());
        assertEquals(SHA, captor.getValue().commitSha());
        assertEquals("COMPLETED", captor.getValue().status());
        assertTrue(captor.getValue().findings().isEmpty());
    }

    @Test
    void shouldReturnFinalPublishStatusOnFirstReceipt() throws Exception {
        when(reviewResultService.receiveResult(eq(1L), any()))
                .thenReturn(new ReviewResultResponse(1L, SHA, false, "PARTIAL",
                        LocalDateTime.of(2026, 1, 1, 0, 0)));

        mockMvc.perform(post(PATH).header(TOKEN_HEADER, TOKEN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(BODY))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.task_id").value(1))
                .andExpect(jsonPath("$.commit_sha").value(SHA))
                .andExpect(jsonPath("$.duplicate").value(false))
                .andExpect(jsonPath("$.publish_status").value("PARTIAL"))
                .andExpect(jsonPath("$.received_at").exists());
    }

    @Test
    void shouldReturnDuplicateWithOk() throws Exception {
        when(reviewResultService.receiveResult(eq(1L), any()))
                .thenReturn(new ReviewResultResponse(1L, SHA, true, "PUBLISHED",
                        LocalDateTime.of(2026, 1, 1, 0, 0)));

        mockMvc.perform(post(PATH).header(TOKEN_HEADER, TOKEN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(BODY))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.duplicate").value(true))
                .andExpect(jsonPath("$.publish_status").value("PUBLISHED"));
    }

    @Test
    void shouldRejectMissingToken() throws Exception {
        mockMvc.perform(post(PATH)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(BODY))
                .andExpect(status().isUnauthorized());

        verify(reviewResultService, never()).receiveResult(any(), any());
    }

    @Test
    void shouldRejectWrongToken() throws Exception {
        mockMvc.perform(post(PATH).header(TOKEN_HEADER, "wrong-token")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(BODY))
                .andExpect(status().isUnauthorized());

        verify(reviewResultService, never()).receiveResult(any(), any());
    }

    @Test
    void shouldReturnNotFoundForMissingTask() throws Exception {
        when(reviewResultService.receiveResult(eq(1L), any()))
                .thenThrow(new TaskNotFoundException(1L));

        mockMvc.perform(post(PATH).header(TOKEN_HEADER, TOKEN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(BODY))
                .andExpect(status().isNotFound());
    }

    @Test
    void shouldReturnConflictForRejectedResult() throws Exception {
        when(reviewResultService.receiveResult(eq(1L), any()))
                .thenThrow(new ReviewResultRejectedException(409,
                        "commitSha does not match the review task"));

        mockMvc.perform(post(PATH).header(TOKEN_HEADER, TOKEN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(BODY))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.error").value(
                        "commitSha does not match the review task"));
    }

    @Test
    void shouldReturnUnprocessableForRejectedValidation() throws Exception {
        when(reviewResultService.receiveResult(eq(1L), any()))
                .thenThrow(new ReviewResultRejectedException(422,
                        "findings[0] severity must be CRITICAL, HIGH, "
                                + "MEDIUM, LOW or INFO"));

        mockMvc.perform(post(PATH).header(TOKEN_HEADER, TOKEN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(BODY))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.error").value(
                        "findings[0] severity must be CRITICAL, HIGH, "
                                + "MEDIUM, LOW or INFO"));
    }

    @Test
    void shouldReturnBadRequestForMalformedJson() throws Exception {
        mockMvc.perform(post(PATH).header(TOKEN_HEADER, TOKEN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("not-json"))
                .andExpect(status().isBadRequest());

        verify(reviewResultService, never()).receiveResult(any(), any());
    }

    @Test
    void shouldRejectAllRequestsWhenTokenIsNotConfigured() {
        ReviewResultController controller =
                new ReviewResultController(reviewResultService, "");

        ResponseEntity<ReviewResultResponse> response =
                controller.receiveResult(1L, TOKEN, new ReviewResultRequest(
                        SHA, "COMPLETED", List.of()));

        assertEquals(HttpStatus.UNAUTHORIZED, response.getStatusCode());
        verify(reviewResultService, never()).receiveResult(any(), any());
    }
}