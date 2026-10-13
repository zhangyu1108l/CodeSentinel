package cn.codesentinel.github;

import cn.codesentinel.config.GithubAppProperties;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

class GithubReviewCommentClientTest {

    private static final String TEST_API_URL = "https://api.github.com";
    private static final String TEST_TOKEN = "ghs_test-token";

    private MockRestServiceServer mockServer;
    private GithubAuthService authService;
    private GithubReviewCommentClient reviewCommentClient;

    @BeforeEach
    void setUp() {
        authService = mock(GithubAuthService.class);
        when(authService.getInstallationToken())
                .thenReturn(new InstallationToken(TEST_TOKEN, "2025-01-01T00:00:00Z"));

        RestClient.Builder apiBuilder = RestClient.builder();
        mockServer = MockRestServiceServer.bindTo(apiBuilder).build();

        GithubAppProperties props = new GithubAppProperties(
                null, null, null, null, null, TEST_API_URL);
        GithubApiClient apiClient = new GithubApiClient(apiBuilder, props);

        reviewCommentClient = new GithubReviewCommentClient(apiClient, authService);
    }

    @AfterEach
    void tearDown() {
        mockServer.verify();
    }

    @Test
    void shouldCreateReviewComment() {
        String responseBody = """
                {
                    "id": 987654321,
                    "body": "Use parameterized queries.",
                    "html_url": "https://github.com/owner/repo/pull/42#discussion_r987654321",
                    "path": "src/UserRepository.java",
                    "line": 52,
                    "side": "RIGHT"
                }""";

        mockServer.expect(requestTo(TEST_API_URL + "/repos/owner/repo/pulls/42/comments"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(header("Authorization", "Bearer " + TEST_TOKEN))
                .andExpect(jsonPath("$.body").value("Use parameterized queries."))
                .andExpect(jsonPath("$.commit_id").value("abc123def456"))
                .andExpect(jsonPath("$.path").value("src/UserRepository.java"))
                .andExpect(jsonPath("$.line").value(52))
                .andExpect(jsonPath("$.side").value("RIGHT"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        ReviewCommentRequest request = new ReviewCommentRequest(
                "Use parameterized queries.",
                "abc123def456",
                "src/UserRepository.java",
                52,
                "RIGHT");

        ReviewCommentResponse response = reviewCommentClient.createComment(
                "owner", "repo", 42, request,
                new InstallationToken(TEST_TOKEN, "2025-01-01T00:00:00Z"));

        assertNotNull(response);
        assertEquals(987654321L, response.id());
        assertEquals("Use parameterized queries.", response.body());
        assertEquals(
                "https://github.com/owner/repo/pull/42#discussion_r987654321",
                response.htmlUrl());
    }

    @Test
    void shouldPassThroughLineAndSideUnchanged() {
        String responseBody = """
                {
                    "id": 5,
                    "body": "note",
                    "html_url": "https://github.com/o/r/pull/1#discussion_r5"
                }""";

        mockServer.expect(requestTo(TEST_API_URL + "/repos/o/r/pulls/1/comments"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(jsonPath("$.commit_id").value("cafebabe"))
                .andExpect(jsonPath("$.line").value(7))
                .andExpect(jsonPath("$.side").value("LEFT"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        ReviewCommentRequest request = new ReviewCommentRequest(
                "note", "cafebabe", "src/A.java", 7, "LEFT");

        ReviewCommentResponse response = reviewCommentClient.createComment(
                "o", "r", 1, request,
                new InstallationToken(TEST_TOKEN, "2025-01-01T00:00:00Z"));

        assertNotNull(response);
        assertEquals(5L, response.id());
    }

    @Test
    void shouldObtainInstallationTokenWhenNotProvided() {
        String responseBody = """
                {
                    "id": 6,
                    "body": "note",
                    "html_url": "https://github.com/o/r/pull/1#discussion_r6"
                }""";

        mockServer.expect(requestTo(TEST_API_URL + "/repos/o/r/pulls/1/comments"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(header("Authorization", "Bearer " + TEST_TOKEN))
                .andExpect(jsonPath("$.side").value("RIGHT"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        ReviewCommentResponse response = reviewCommentClient.createComment(
                "o", "r", 1,
                new ReviewCommentRequest(
                        "note", "cafebabe", "src/A.java", 7, "RIGHT"));

        assertNotNull(response);
        assertEquals(6L, response.id());
        verify(authService).getInstallationToken();
    }

    @Test
    void shouldThrowGithubApiExceptionOnUnprocessableEntity() {
        mockServer.expect(requestTo(TEST_API_URL + "/repos/o/r/pulls/1/comments"))
                .andExpect(method(HttpMethod.POST))
                .andRespond(withStatus(HttpStatus.UNPROCESSABLE_ENTITY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .body("{\"message\":\"Pull request review thread line must be part of the diff\"}"));

        ReviewCommentRequest request = new ReviewCommentRequest(
                "note", "cafebabe", "src/A.java", 7, "RIGHT");

        GithubApiException error = assertThrows(GithubApiException.class,
                () -> reviewCommentClient.createComment("o", "r", 1, request,
                        new InstallationToken(TEST_TOKEN, "2025-01-01T00:00:00Z")));
        assertEquals(422, error.getStatusCode());
    }
}