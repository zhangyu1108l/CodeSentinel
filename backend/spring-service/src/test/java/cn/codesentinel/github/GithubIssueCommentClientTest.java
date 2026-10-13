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

class GithubIssueCommentClientTest {

    private static final String TEST_API_URL = "https://api.github.com";
    private static final String TEST_TOKEN = "ghs_test-token";

    private MockRestServiceServer mockServer;
    private GithubAuthService authService;
    private GithubIssueCommentClient issueCommentClient;

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

        issueCommentClient = new GithubIssueCommentClient(apiClient, authService);
    }

    @AfterEach
    void tearDown() {
        mockServer.verify();
    }

    @Test
    void shouldCreateIssueComment() {
        String responseBody = """
                {
                    "id": 123456789,
                    "body": "CodeSentinel review summary",
                    "html_url": "https://github.com/owner/repo/issues/42#issuecomment-123456789",
                    "user": { "login": "codesentinel-lab" }
                }""";

        mockServer.expect(requestTo(TEST_API_URL + "/repos/owner/repo/issues/42/comments"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(header("Authorization", "Bearer " + TEST_TOKEN))
                .andExpect(jsonPath("$.body").value("CodeSentinel review summary"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        IssueCommentResponse response = issueCommentClient.createComment(
                "owner", "repo", 42,
                new IssueCommentRequest("CodeSentinel review summary"),
                new InstallationToken(TEST_TOKEN, "2025-01-01T00:00:00Z"));

        assertNotNull(response);
        assertEquals(123456789L, response.id());
        assertEquals("CodeSentinel review summary", response.body());
        assertEquals(
                "https://github.com/owner/repo/issues/42#issuecomment-123456789",
                response.htmlUrl());
    }

    @Test
    void shouldObtainInstallationTokenWhenNotProvided() {
        String responseBody = """
                {
                    "id": 1,
                    "body": "summary",
                    "html_url": "https://github.com/o/r/issues/7#issuecomment-1"
                }""";

        mockServer.expect(requestTo(TEST_API_URL + "/repos/o/r/issues/7/comments"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(header("Authorization", "Bearer " + TEST_TOKEN))
                .andExpect(jsonPath("$.body").value("summary"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        IssueCommentResponse response = issueCommentClient.createComment(
                "o", "r", 7, new IssueCommentRequest("summary"));

        assertNotNull(response);
        assertEquals(1L, response.id());
        verify(authService).getInstallationToken();
    }

    @Test
    void shouldThrowGithubApiExceptionOnUnprocessableEntity() {
        mockServer.expect(requestTo(TEST_API_URL + "/repos/o/r/issues/7/comments"))
                .andExpect(method(HttpMethod.POST))
                .andRespond(withStatus(HttpStatus.UNPROCESSABLE_ENTITY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .body("{\"message\":\"Validation Failed\"}"));

        InstallationToken token =
                new InstallationToken(TEST_TOKEN, "2025-01-01T00:00:00Z");
        IssueCommentRequest request = new IssueCommentRequest("summary");

        GithubApiException error = assertThrows(GithubApiException.class,
                () -> issueCommentClient.createComment("o", "r", 7, request, token));
        assertEquals(422, error.getStatusCode());
    }
}