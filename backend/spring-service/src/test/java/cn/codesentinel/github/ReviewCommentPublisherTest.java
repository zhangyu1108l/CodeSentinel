package cn.codesentinel.github;

import cn.codesentinel.comment.InlineCommentFinding;
import cn.codesentinel.comment.InlineCommentMarkdownBuilder;
import cn.codesentinel.comment.PatchCommentableLines;
import cn.codesentinel.config.GithubAppProperties;
import cn.codesentinel.config.ReviewContextProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import java.io.IOException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

class ReviewCommentPublisherTest {

    private static final String TEST_API_URL = "https://api.github.com";
    private static final String TEST_TOKEN = "ghs_test-token";
    private static final String FINDING_PATH = "src/A.java";

    /** Commentable RIGHT lines 1..3 in the new file (1..2 on the left). */
    private static final String PATCH = String.join("\n",
            "@@ -1,2 +1,3 @@",
            " a",
            "+b",
            " c");

    private final ObjectMapper objectMapper = new ObjectMapper();

    private MockRestServiceServer mockServer;
    private GithubAuthService authService;
    private ReviewCommentPublisher publisher;

    @BeforeEach
    void setUp() {
        authService = mock(GithubAuthService.class);
        when(authService.getInstallationToken()).thenReturn(
                new InstallationToken(TEST_TOKEN, "2025-01-01T00:00:00Z"));

        RestClient.Builder apiBuilder = RestClient.builder();
        mockServer = MockRestServiceServer.bindTo(apiBuilder).build();

        GithubAppProperties appProps = new GithubAppProperties(
                null, null, null, null, null, TEST_API_URL);
        GithubApiClient apiClient = new GithubApiClient(apiBuilder, appProps);
        GithubPullRequestFilesClient filesClient =
                new GithubPullRequestFilesClient(apiClient, authService,
                        new ReviewContextProperties(50, 262_144, 5,
                                List.of("java", "py")));
        GithubReviewCommentClient commentClient =
                new GithubReviewCommentClient(apiClient, authService);
        publisher = new ReviewCommentPublisher(
                filesClient, commentClient, authService);
    }

    @AfterEach
    void tearDown() {
        mockServer.verify();
    }

    @Test
    void shouldPublishSingleLineComment() throws Exception {
        InlineCommentFinding finding = finding(2, 2);
        expectChangedFiles(changedFilesJson(Map.of(FINDING_PATH, PATCH)));

        mockServer.expect(requestTo(TEST_API_URL + "/repos/o/r/pulls/1/comments"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(header("Authorization", "Bearer " + TEST_TOKEN))
                .andExpect(jsonPath("$.body").value(
                        InlineCommentMarkdownBuilder.build(finding)))
                .andExpect(jsonPath("$.commit_id").value("abc123def456"))
                .andExpect(jsonPath("$.path").value(FINDING_PATH))
                .andExpect(jsonPath("$.line").value(2))
                .andExpect(jsonPath("$.side").value("RIGHT"))
                .andRespond(withSuccess(commentJson(501),
                        MediaType.APPLICATION_JSON));

        List<ReviewCommentOutcome> outcomes = publisher.publish(
                "o", "r", 1, "abc123def456", List.of(finding));

        assertEquals(1, outcomes.size());
        ReviewCommentOutcome outcome = outcomes.get(0);
        assertEquals(ReviewCommentOutcome.Status.PUBLISHED, outcome.status());
        assertEquals(FINDING_PATH, outcome.filePath());
        assertEquals(2, outcome.startLine());
        assertEquals(2, outcome.endLine());
        assertNull(outcome.reason());
        assertEquals(Long.valueOf(501), outcome.commentId());
        verify(authService).getInstallationToken();
    }

    @Test
    void shouldPublishMultiLineComment() throws Exception {
        InlineCommentFinding finding = finding(1, 3);
        expectChangedFiles(changedFilesJson(Map.of(FINDING_PATH, PATCH)));

        mockServer.expect(requestTo(TEST_API_URL + "/repos/o/r/pulls/1/comments"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(jsonPath("$.line").value(3))
                .andExpect(jsonPath("$.side").value("RIGHT"))
                .andExpect(jsonPath("$.start_line").value(1))
                .andExpect(jsonPath("$.start_side").value("RIGHT"))
                .andRespond(withSuccess(commentJson(502),
                        MediaType.APPLICATION_JSON));

        List<ReviewCommentOutcome> outcomes = publisher.publish(
                "o", "r", 1, "abc123def456", List.of(finding));

        assertEquals(ReviewCommentOutcome.Status.PUBLISHED,
                outcomes.get(0).status());
        assertEquals(Long.valueOf(502), outcomes.get(0).commentId());
    }

    @Test
    void shouldSkipFindingOutsideTheDiffAndKeepTheReason() throws Exception {
        InlineCommentFinding finding = finding(7, 7);
        expectChangedFiles(changedFilesJson(Map.of(FINDING_PATH, PATCH)));

        List<ReviewCommentOutcome> outcomes = publisher.publish(
                "o", "r", 1, "abc123def456", List.of(finding));

        assertEquals(1, outcomes.size());
        ReviewCommentOutcome outcome = outcomes.get(0);
        assertEquals(ReviewCommentOutcome.Status.SKIPPED, outcome.status());
        assertEquals(PatchCommentableLines.REASON_NOT_IN_DIFF,
                outcome.reason());
        assertNull(outcome.commentId());
    }

    @Test
    void shouldSkipWhenPatchIsMissing() throws Exception {
        InlineCommentFinding finding = finding(2, 2);
        Map<String, String> files = new LinkedHashMap<>();
        files.put(FINDING_PATH, null);
        expectChangedFiles(changedFilesJson(files));

        List<ReviewCommentOutcome> outcomes = publisher.publish(
                "o", "r", 1, "abc123def456", List.of(finding));

        assertEquals(ReviewCommentOutcome.Status.SKIPPED,
                outcomes.get(0).status());
        assertEquals(PatchCommentableLines.REASON_NO_PATCH,
                outcomes.get(0).reason());
    }

    @Test
    void shouldSkipWhenPatchIsUnparsable() throws Exception {
        InlineCommentFinding finding = finding(2, 2);
        expectChangedFiles(
                changedFilesJson(Map.of(FINDING_PATH, "not a diff")));

        List<ReviewCommentOutcome> outcomes = publisher.publish(
                "o", "r", 1, "abc123def456", List.of(finding));

        assertEquals(ReviewCommentOutcome.Status.SKIPPED,
                outcomes.get(0).status());
        assertEquals(PatchCommentableLines.REASON_PARSE_ERROR,
                outcomes.get(0).reason());
    }

    @Test
    void shouldSkipWhenPathIsNotInTheChangedFiles() throws Exception {
        InlineCommentFinding blankPath = new InlineCommentFinding(
                "", 2, 2, "HIGH", "SECURITY", null, null, "r", "s", "CWE-1");
        InlineCommentFinding missingPath = new InlineCommentFinding(
                "src/Missing.java", 2, 2, "HIGH", "SECURITY",
                null, null, "r", "s", "CWE-2");
        expectChangedFiles(changedFilesJson(Map.of(FINDING_PATH, PATCH)));

        List<ReviewCommentOutcome> outcomes = publisher.publish(
                "o", "r", 1, "abc123def456",
                List.of(blankPath, missingPath));

        assertEquals(2, outcomes.size());
        for (ReviewCommentOutcome outcome : outcomes) {
            assertEquals(ReviewCommentOutcome.Status.SKIPPED, outcome.status());
            assertEquals(ReviewCommentPublisher.SKIP_REASON_PATH_NOT_IN_PR,
                    outcome.reason());
        }
    }

    @Test
    void shouldFailOneCommentAndContinueWithTheNext() throws Exception {
        InlineCommentFinding first = finding(2, 2);
        InlineCommentFinding second = finding(3, 3);
        expectChangedFiles(changedFilesJson(Map.of(FINDING_PATH, PATCH)));

        mockServer.expect(requestTo(TEST_API_URL + "/repos/o/r/pulls/1/comments"))
                .andExpect(method(HttpMethod.POST))
                .andRespond(withStatus(HttpStatus.UNPROCESSABLE_ENTITY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .body("{\"message\":\"line must be part of the diff\"}"));
        mockServer.expect(requestTo(TEST_API_URL + "/repos/o/r/pulls/1/comments"))
                .andExpect(method(HttpMethod.POST))
                .andRespond(withSuccess(commentJson(503),
                        MediaType.APPLICATION_JSON));

        List<ReviewCommentOutcome> outcomes = publisher.publish(
                "o", "r", 1, "abc123def456", List.of(first, second));

        assertEquals(2, outcomes.size());
        assertEquals(ReviewCommentOutcome.Status.FAILED,
                outcomes.get(0).status());
        assertEquals("http_422", outcomes.get(0).reason());
        assertNull(outcomes.get(0).commentId());
        assertEquals(ReviewCommentOutcome.Status.PUBLISHED,
                outcomes.get(1).status());
        assertEquals(Long.valueOf(503), outcomes.get(1).commentId());
    }

    @Test
    void shouldReportTransportFailureAsFailed() throws Exception {
        expectChangedFiles(changedFilesJson(Map.of(FINDING_PATH, PATCH)));

        mockServer.expect(requestTo(TEST_API_URL + "/repos/o/r/pulls/1/comments"))
                .andExpect(method(HttpMethod.POST))
                .andRespond(withException(new IOException("connection reset")));

        List<ReviewCommentOutcome> outcomes = publisher.publish(
                "o", "r", 1, "abc123def456", List.of(finding(2, 2)));

        assertEquals(ReviewCommentOutcome.Status.FAILED,
                outcomes.get(0).status());
        assertEquals(ReviewCommentPublisher.FAILURE_REASON_TRANSPORT,
                outcomes.get(0).reason());
    }

    @Test
    void shouldRejectBlankTaskInputs() {
        InlineCommentFinding finding = finding(2, 2);

        assertThrows(IllegalArgumentException.class,
                () -> publisher.publish(" ", "r", 1, "abc", List.of(finding)));
        assertThrows(IllegalArgumentException.class,
                () -> publisher.publish("o", "", 1, "abc", List.of(finding)));
        assertThrows(IllegalArgumentException.class,
                () -> publisher.publish("o", "r", 1, "  ", List.of(finding)));
        assertThrows(IllegalArgumentException.class,
                () -> publisher.publish("o", "r", 0, "abc", List.of(finding)));
        verify(authService, never()).getInstallationToken();
    }

    @Test
    void shouldReturnEmptyOutcomesWithoutAnyRequest() {
        assertTrue(publisher.publish(
                "o", "r", 1, "abc123def456", List.of()).isEmpty());
        assertTrue(publisher.publish(
                "o", "r", 1, "abc123def456", null).isEmpty());
        verify(authService, never()).getInstallationToken();
    }

    private static InlineCommentFinding finding(int startLine, int endLine) {
        return new InlineCommentFinding(FINDING_PATH, startLine, endLine,
                "HIGH", "SECURITY", null, null,
                "external input", "use binding", "CWE-89");
    }

    private static String commentJson(long commentId) {
        return "{\"id\":" + commentId + ", \"body\":\"note\","
                + " \"html_url\":\"https://github.com/o/r/pull/1#discussion_r"
                + commentId + "\"}";
    }

    private String changedFilesJson(Map<String, String> pathToPatch)
            throws Exception {
        List<Map<String, Object>> files = new ArrayList<>();
        for (Map.Entry<String, String> entry : pathToPatch.entrySet()) {
            Map<String, Object> file = new LinkedHashMap<>();
            file.put("filename", entry.getKey());
            file.put("status", "modified");
            if (entry.getValue() != null) {
                file.put("patch", entry.getValue());
            }
            files.add(file);
        }
        return objectMapper.writeValueAsString(files);
    }

    private void expectChangedFiles(String json) {
        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/pulls/1/files?per_page=100&page=1"))
                .andExpect(method(HttpMethod.GET))
                .andExpect(header("Authorization", "Bearer " + TEST_TOKEN))
                .andRespond(withSuccess(json, MediaType.APPLICATION_JSON));
    }
}