package cn.codesentinel.task;

import cn.codesentinel.config.GithubAppProperties;
import cn.codesentinel.config.ReviewContextProperties;
import cn.codesentinel.github.GithubApiClient;
import cn.codesentinel.github.GithubApiException;
import cn.codesentinel.github.GithubAuthService;
import cn.codesentinel.github.GithubIssueCommentClient;
import cn.codesentinel.github.GithubPullRequestFilesClient;
import cn.codesentinel.github.GithubReviewCommentClient;
import cn.codesentinel.github.InstallationToken;
import cn.codesentinel.github.ReviewCommentPublisher;
import com.fasterxml.jackson.databind.JsonNode;
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

import static org.hamcrest.Matchers.containsString;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

class ReviewResultPublishServiceTest {

    private static final String TEST_API_URL = "https://api.github.com";
    private static final String TEST_TOKEN = "ghs_test-token";
    private static final String FINDING_PATH = "src/A.java";
    private static final String SHA = "abc123def456";
    private static final String REVIEW_COMMENTS_URL =
            TEST_API_URL + "/repos/o/r/pulls/1/comments";
    private static final String ISSUE_COMMENT_URL =
            TEST_API_URL + "/repos/o/r/issues/1/comments";

    /** Commentable RIGHT lines 1..3 in the new file (1..2 on the left). */
    private static final String PATCH = String.join("\n",
            "@@ -1,2 +1,3 @@",
            " a",
            "+b",
            " c");

    private final ObjectMapper objectMapper = new ObjectMapper();

    private MockRestServiceServer mockServer;
    private GithubAuthService authService;
    private ReviewResultPublishService service;

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
        GithubReviewCommentClient reviewClient =
                new GithubReviewCommentClient(apiClient, authService);
        GithubIssueCommentClient issueClient =
                new GithubIssueCommentClient(apiClient, authService);
        ReviewCommentPublisher publisher = new ReviewCommentPublisher(
                filesClient, reviewClient, authService);
        service = new ReviewResultPublishService(
                objectMapper, publisher, issueClient, authService);
    }

    @AfterEach
    void tearDown() {
        mockServer.verify();
    }

    @Test
    void shouldPublishInlineCommentsAndSummary() throws Exception {
        ReviewResultFinding finding =
                finding("BUG", "HIGH", FINDING_PATH, 1, 2);
        expectChangedFiles(changedFilesJson(Map.of(FINDING_PATH, PATCH)));
        expectReviewComment(501);
        expectIssueComment(900);

        ReviewResultPublishResult result = service.publish(
                task(), delivery("COMPLETED", findingsJson(finding)));

        assertEquals(PublishStatus.PUBLISHED, result.status());
        assertNotNull(result.publishedAt());

        JsonNode json = objectMapper.readTree(result.outcomeJson());
        assertEquals("PUBLISHED", json.get("status").asText());
        JsonNode summary = json.get("summary");
        assertEquals("PUBLISHED", summary.get("status").asText());
        assertTrue(summary.get("reason").isNull());
        assertEquals(900L, summary.get("commentId").asLong());

        assertEquals(1, json.get("comments").size());
        JsonNode item = json.get("comments").get(0);
        assertEquals(FINDING_PATH, item.get("filePath").asText());
        assertEquals(1, item.get("startLine").asInt());
        assertEquals(2, item.get("endLine").asInt());
        assertEquals("PUBLISHED", item.get("status").asText());
        assertTrue(item.get("reason").isNull());
        assertEquals(501L, item.get("commentId").asLong());
    }

    @Test
    void shouldMarkPartialWhenOneCommentFails() throws Exception {
        ReviewResultFinding first =
                finding("BUG", "HIGH", FINDING_PATH, 2, 2);
        ReviewResultFinding second =
                finding("SECURITY", "LOW", FINDING_PATH, 3, 3);
        expectChangedFiles(changedFilesJson(Map.of(FINDING_PATH, PATCH)));
        expectReviewComment(501);
        mockServer.expect(requestTo(REVIEW_COMMENTS_URL))
                .andExpect(method(HttpMethod.POST))
                .andRespond(withStatus(HttpStatus.UNPROCESSABLE_ENTITY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .body("{\"message\":\"line must be part of the diff\"}"));
        expectIssueComment(900);

        ReviewResultPublishResult result = service.publish(
                task(), delivery("COMPLETED", findingsJson(first, second)));

        assertEquals(PublishStatus.PARTIAL, result.status());
        assertNotNull(result.publishedAt());

        JsonNode comments = objectMapper.readTree(result.outcomeJson())
                .get("comments");
        assertEquals("PUBLISHED", comments.get(0).get("status").asText());
        assertEquals(501L, comments.get(0).get("commentId").asLong());
        assertEquals("FAILED", comments.get(1).get("status").asText());
        assertEquals("http_422", comments.get(1).get("reason").asText());
        assertTrue(comments.get(1).get("commentId").isNull());
    }

    @Test
    void shouldMarkPartialWhenOneFindingIsSkipped() throws Exception {
        ReviewResultFinding published =
                finding("BUG", "HIGH", FINDING_PATH, 2, 2);
        ReviewResultFinding skipped =
                finding("QUALITY", "INFO", FINDING_PATH, 7, 7);
        expectChangedFiles(changedFilesJson(Map.of(FINDING_PATH, PATCH)));
        expectReviewComment(501);
        expectIssueComment(900);

        ReviewResultPublishResult result = service.publish(
                task(), delivery("COMPLETED", findingsJson(published, skipped)));

        assertEquals(PublishStatus.PARTIAL, result.status());
        JsonNode comments = objectMapper.readTree(result.outcomeJson())
                .get("comments");
        assertEquals("PUBLISHED", comments.get(0).get("status").asText());
        assertEquals("SKIPPED", comments.get(1).get("status").asText());
        assertEquals("not_in_diff", comments.get(1).get("reason").asText());
    }

    @Test
    void shouldMarkFailedWhenNothingWasPublished() throws Exception {
        ReviewResultFinding finding =
                finding("BUG", "HIGH", FINDING_PATH, 2, 2);
        expectChangedFiles(changedFilesJson(Map.of(FINDING_PATH, PATCH)));
        mockServer.expect(requestTo(REVIEW_COMMENTS_URL))
                .andExpect(method(HttpMethod.POST))
                .andRespond(withStatus(HttpStatus.UNPROCESSABLE_ENTITY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .body("{\"message\":\"line must be part of the diff\"}"));
        mockServer.expect(requestTo(ISSUE_COMMENT_URL))
                .andExpect(method(HttpMethod.POST))
                .andRespond(withStatus(HttpStatus.FORBIDDEN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .body("{\"message\":\"Resource not accessible\"}"));

        ReviewResultPublishResult result = service.publish(
                task(), delivery("COMPLETED", findingsJson(finding)));

        assertEquals(PublishStatus.FAILED, result.status());
        assertNull(result.publishedAt());

        JsonNode json = objectMapper.readTree(result.outcomeJson());
        assertEquals("FAILED", json.get("status").asText());
        assertEquals("http_422",
                json.get("comments").get(0).get("reason").asText());
        assertEquals("http_403",
                json.get("summary").get("reason").asText());
    }

    @Test
    void shouldMarkPartialWhenSummaryFailsButCommentsSucceed()
            throws Exception {
        ReviewResultFinding finding =
                finding("BUG", "HIGH", FINDING_PATH, 2, 2);
        expectChangedFiles(changedFilesJson(Map.of(FINDING_PATH, PATCH)));
        expectReviewComment(501);
        mockServer.expect(requestTo(ISSUE_COMMENT_URL))
                .andExpect(method(HttpMethod.POST))
                .andRespond(withStatus(HttpStatus.INTERNAL_SERVER_ERROR)
                        .contentType(MediaType.APPLICATION_JSON)
                        .body("{\"message\":\"server error\"}"));

        ReviewResultPublishResult result = service.publish(
                task(), delivery("COMPLETED", findingsJson(finding)));

        assertEquals(PublishStatus.PARTIAL, result.status());
        assertNotNull(result.publishedAt());
        JsonNode json = objectMapper.readTree(result.outcomeJson());
        assertEquals("http_500",
                json.get("summary").get("reason").asText());
        assertEquals(501L,
                json.get("comments").get(0).get("commentId").asLong());
    }

    @Test
    void shouldMarkFailedOnSetupFailureWithoutSendingRequests()
            throws Exception {
        when(authService.getInstallationToken()).thenThrow(
                new GithubApiException(401,
                        "GitHub API error 401 for installation token"));

        ReviewResultPublishResult result = service.publish(
                task(), delivery("COMPLETED",
                        findingsJson(
                                finding("BUG", "HIGH", FINDING_PATH, 2, 2))));

        assertEquals(PublishStatus.FAILED, result.status());
        assertNull(result.publishedAt());

        JsonNode json = objectMapper.readTree(result.outcomeJson());
        assertEquals("setup_failed",
                json.get("comments").get(0).get("reason").asText());
        assertEquals("setup_failed",
                json.get("summary").get("reason").asText());
    }

    @Test
    void shouldKeepPublishedItemsWhenAnotherItemHasUncertainSideEffect()
            throws Exception {
        ReviewResultFinding first =
                finding("BUG", "HIGH", FINDING_PATH, 2, 2);
        ReviewResultFinding second =
                finding("SECURITY", "MEDIUM", FINDING_PATH, 3, 3);
        expectChangedFiles(changedFilesJson(Map.of(FINDING_PATH, PATCH)));
        expectReviewComment(501);
        mockServer.expect(requestTo(REVIEW_COMMENTS_URL))
                .andExpect(method(HttpMethod.POST))
                .andRespond(withException(
                        new IOException("connection reset")));
        expectIssueComment(900);

        ReviewResultPublishResult result = service.publish(
                task(), delivery("COMPLETED", findingsJson(first, second)));

        assertEquals(PublishStatus.PARTIAL, result.status());
        assertNotNull(result.publishedAt());

        JsonNode comments = objectMapper.readTree(result.outcomeJson())
                .get("comments");
        assertEquals("PUBLISHED", comments.get(0).get("status").asText());
        assertEquals(501L, comments.get(0).get("commentId").asLong());
        assertEquals("FAILED", comments.get(1).get("status").asText());
        assertEquals("transport_error",
                comments.get(1).get("reason").asText());
    }

    @Test
    void shouldMarkPartialWhenOnlyUncertainSideEffectsExist()
            throws Exception {
        expectChangedFiles(changedFilesJson(Map.of(FINDING_PATH, PATCH)));
        mockServer.expect(requestTo(REVIEW_COMMENTS_URL))
                .andExpect(method(HttpMethod.POST))
                .andRespond(withException(
                        new IOException("connection reset")));
        mockServer.expect(requestTo(ISSUE_COMMENT_URL))
                .andExpect(method(HttpMethod.POST))
                .andRespond(withException(
                        new IOException("connection reset")));

        ReviewResultPublishResult result = service.publish(
                task(), delivery("COMPLETED",
                        findingsJson(
                                finding("BUG", "HIGH", FINDING_PATH, 2, 2))));

        assertEquals(PublishStatus.PARTIAL, result.status());
        assertNull(result.publishedAt());

        JsonNode json = objectMapper.readTree(result.outcomeJson());
        assertEquals("transport_error",
                json.get("comments").get(0).get("reason").asText());
        assertEquals("transport_error",
                json.get("summary").get("reason").asText());
    }

    @Test
    void shouldRenderDegradedWarningInSummary() throws Exception {
        ReviewResultFinding finding =
                finding("BUG", "HIGH", FINDING_PATH, 2, 2);
        expectChangedFiles(changedFilesJson(Map.of(FINDING_PATH, PATCH)));
        expectReviewComment(501);
        mockServer.expect(requestTo(ISSUE_COMMENT_URL))
                .andExpect(method(HttpMethod.POST))
                .andExpect(content().string(
                        containsString("未完整完成（degraded）")))
                .andRespond(withSuccess(commentJson(900),
                        MediaType.APPLICATION_JSON));

        ReviewResultPublishResult result = service.publish(
                task(), delivery("DEGRADED", findingsJson(finding)));

        assertEquals(PublishStatus.PUBLISHED, result.status());
    }

    @Test
    void shouldPublishSummaryOnlyWhenNoFindings() throws Exception {
        expectIssueComment(900);

        ReviewResultPublishResult result = service.publish(
                task(), delivery("COMPLETED", "[]"));

        assertEquals(PublishStatus.PUBLISHED, result.status());
        JsonNode json = objectMapper.readTree(result.outcomeJson());
        assertEquals(0, json.get("comments").size());
        assertEquals(900L, json.get("summary").get("commentId").asLong());
    }

    @Test
    void shouldMarkFailedWhenFindingsSnapshotIsUnreadable() throws Exception {
        ReviewResultPublishResult result = service.publish(
                task(), delivery("COMPLETED", "not-json"));

        assertEquals(PublishStatus.FAILED, result.status());
        assertNull(result.publishedAt());

        JsonNode json = objectMapper.readTree(result.outcomeJson());
        assertEquals(ReviewResultPublishService.REASON_FINDINGS_PARSE_FAILED,
                json.get("summary").get("reason").asText());
        assertEquals(0, json.get("comments").size());
    }

    private static ReviewTask task() {
        return new ReviewTask("o", "r", 1, SHA);
    }

    private static ReviewResultDelivery delivery(String aiStatus,
                                                 String findingsJson) {
        return new ReviewResultDelivery(1L, SHA, aiStatus, findingsJson,
                PublishStatus.PENDING);
    }

    private String findingsJson(ReviewResultFinding... findings)
            throws Exception {
        return objectMapper.writeValueAsString(List.of(findings));
    }

    private static ReviewResultFinding finding(String category, String severity,
                                               String filePath, int start,
                                               int end) {
        return new ReviewResultFinding(category, severity, 0.9, "R-1", "title",
                filePath, start, end, "description", "reason", "suggestion",
                List.of());
    }

    private void expectChangedFiles(String json) {
        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/pulls/1/files?per_page=100&page=1"))
                .andExpect(method(HttpMethod.GET))
                .andExpect(header("Authorization", "Bearer " + TEST_TOKEN))
                .andRespond(withSuccess(json, MediaType.APPLICATION_JSON));
    }

    private void expectReviewComment(long commentId) {
        mockServer.expect(requestTo(REVIEW_COMMENTS_URL))
                .andExpect(method(HttpMethod.POST))
                .andExpect(jsonPath("$.commit_id").value(SHA))
                .andRespond(withSuccess(commentJson(commentId),
                        MediaType.APPLICATION_JSON));
    }

    private void expectIssueComment(long commentId) {
        mockServer.expect(requestTo(ISSUE_COMMENT_URL))
                .andExpect(method(HttpMethod.POST))
                .andExpect(content().string(
                        containsString("CodeSentinel AI Code Review")))
                .andRespond(withSuccess(commentJson(commentId),
                        MediaType.APPLICATION_JSON));
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

    private static String commentJson(long commentId) {
        return "{\"id\":" + commentId + ", \"body\":\"note\","
                + " \"html_url\":\"https://github.com/o/r/pull/1#discussion_r"
                + commentId + "\"}";
    }
}