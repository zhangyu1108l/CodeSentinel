package cn.codesentinel.github;

import cn.codesentinel.config.GithubAppProperties;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

class GithubPullRequestClientTest {

    private static final String TEST_API_URL = "https://api.github.com";
    private static final String TEST_TOKEN = "ghs_test-token";

    private MockRestServiceServer mockServer;
    private GithubPullRequestClient pullRequestClient;

    @BeforeEach
    void setUp() {
        GithubAuthService authService = mock(GithubAuthService.class);
        when(authService.getInstallationToken())
                .thenReturn(new InstallationToken(TEST_TOKEN, "2025-01-01T00:00:00Z"));

        RestClient.Builder apiBuilder = RestClient.builder();
        mockServer = MockRestServiceServer.bindTo(apiBuilder).build();

        GithubAppProperties props = new GithubAppProperties(
                null, null, null, null, null, TEST_API_URL);
        GithubApiClient apiClient = new GithubApiClient(apiBuilder, props);

        pullRequestClient = new GithubPullRequestClient(apiClient, authService);
    }

    @AfterEach
    void tearDown() {
        mockServer.verify();
    }

    @Test
    void shouldGetPullRequest() {
        String responseBody = """
                {
                    "number": 42,
                    "title": "Add webhook verification",
                    "state": "open",
                    "head": {
                        "sha": "abc123def456",
                        "ref": "feature/webhook"
                    },
                    "base": {
                        "ref": "main"
                    }
                }""";

        mockServer.expect(requestTo(TEST_API_URL + "/repos/owner/repo/pulls/42"))
                .andExpect(method(HttpMethod.GET))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        PullRequest pr = pullRequestClient.getPullRequest("owner", "repo", 42);

        assertNotNull(pr);
        assertEquals(42, pr.number());
        assertEquals("Add webhook verification", pr.title());
        assertEquals("open", pr.state());
        assertEquals("abc123def456", pr.head().sha());
        assertEquals("feature/webhook", pr.head().ref());
        assertEquals("main", pr.base().ref());
    }

    @Test
    void shouldSetAuthorizationHeader() {
        String responseBody = """
                {
                    "number": 1,
                    "title": "test",
                    "state": "open",
                    "head": {
                        "sha": "aaa",
                        "ref": "dev"
                    },
                    "base": {
                        "ref": "main"
                    }
                }""";

        mockServer.expect(requestTo(TEST_API_URL + "/repos/org/repo/pulls/1"))
                .andExpect(method(HttpMethod.GET))
                .andExpect(header("Authorization", "Bearer " + TEST_TOKEN))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        pullRequestClient.getPullRequest("org", "repo", 1);
    }

    @Test
    void shouldReturnNumber() {
        String responseBody = """
                {
                    "number": 99,
                    "title": "t",
                    "state": "open",
                    "head": { "sha": "s", "ref": "r" },
                    "base": { "ref": "b" }
                }""";

        mockServer.expect(requestTo(TEST_API_URL + "/repos/o/r/pulls/99"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        PullRequest pr = pullRequestClient.getPullRequest("o", "r", 99);
        assertEquals(99, pr.number());
    }

    @Test
    void shouldReturnTitle() {
        String responseBody = """
                {
                    "number": 1,
                    "title": "Fix null pointer in user service",
                    "state": "open",
                    "head": { "sha": "s", "ref": "r" },
                    "base": { "ref": "b" }
                }""";

        mockServer.expect(requestTo(TEST_API_URL + "/repos/o/r/pulls/1"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        PullRequest pr = pullRequestClient.getPullRequest("o", "r", 1);
        assertEquals("Fix null pointer in user service", pr.title());
    }

    @Test
    void shouldReturnState() {
        String responseBody = """
                {
                    "number": 3,
                    "title": "t",
                    "state": "closed",
                    "head": { "sha": "s", "ref": "r" },
                    "base": { "ref": "b" }
                }""";

        mockServer.expect(requestTo(TEST_API_URL + "/repos/o/r/pulls/3"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        PullRequest pr = pullRequestClient.getPullRequest("o", "r", 3);
        assertEquals("closed", pr.state());
    }

    @Test
    void shouldReturnHeadSha() {
        String responseBody = """
                {
                    "number": 1,
                    "title": "t",
                    "state": "open",
                    "head": {
                        "sha": "e7b9534c8a2f1d6b3e5a7c9d0f1e2a3b4c5d6e7f",
                        "ref": "feature/x"
                    },
                    "base": { "ref": "main" }
                }""";

        mockServer.expect(requestTo(TEST_API_URL + "/repos/o/r/pulls/1"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        PullRequest pr = pullRequestClient.getPullRequest("o", "r", 1);
        assertEquals("e7b9534c8a2f1d6b3e5a7c9d0f1e2a3b4c5d6e7f", pr.head().sha());
    }

    @Test
    void shouldReturnHeadRef() {
        String responseBody = """
                {
                    "number": 1,
                    "title": "t",
                    "state": "open",
                    "head": { "sha": "s", "ref": "feature/new-api" },
                    "base": { "ref": "main" }
                }""";

        mockServer.expect(requestTo(TEST_API_URL + "/repos/o/r/pulls/1"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        PullRequest pr = pullRequestClient.getPullRequest("o", "r", 1);
        assertEquals("feature/new-api", pr.head().ref());
    }

    @Test
    void shouldReturnBaseRef() {
        String responseBody = """
                {
                    "number": 1,
                    "title": "t",
                    "state": "open",
                    "head": { "sha": "s", "ref": "r" },
                    "base": { "ref": "develop" }
                }""";

        mockServer.expect(requestTo(TEST_API_URL + "/repos/o/r/pulls/1"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        PullRequest pr = pullRequestClient.getPullRequest("o", "r", 1);
        assertEquals("develop", pr.base().ref());
    }

    @Test
    void shouldThrowOn404() {
        mockServer.expect(requestTo(TEST_API_URL + "/repos/owner/repo/pulls/999"))
                .andRespond(withStatus(org.springframework.http.HttpStatus.NOT_FOUND)
                        .body("{\"message\":\"Not Found\"}")
                        .contentType(MediaType.APPLICATION_JSON));

        GithubApiException ex = assertThrows(GithubApiException.class, () ->
                pullRequestClient.getPullRequest("owner", "repo", 999));

        assertEquals(404, ex.getStatusCode());
        assertTrue(ex.isClientError());
    }

    @Test
    void shouldIgnoreUnknownFields() {
        String responseBody = """
                {
                    "number": 7,
                    "title": "Keep only needed fields",
                    "state": "open",
                    "head": {
                        "sha": "abc",
                        "ref": "feature/x",
                        "label": "owner:feature/x",
                        "repo": { "id": 1, "name": "repo" }
                    },
                    "base": {
                        "ref": "main",
                        "label": "owner:main",
                        "repo": { "id": 1, "name": "repo" }
                    },
                    "body": "This should be ignored",
                    "html_url": "https://github.com/owner/repo/pull/7",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "labels": [{"name": "bug"}],
                    "draft": false,
                    "mergeable": true
                }""";

        mockServer.expect(requestTo(TEST_API_URL + "/repos/owner/repo/pulls/7"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        PullRequest pr = pullRequestClient.getPullRequest("owner", "repo", 7);

        assertEquals(7, pr.number());
        assertEquals("Keep only needed fields", pr.title());
        assertEquals("open", pr.state());
        assertEquals("abc", pr.head().sha());
        assertEquals("feature/x", pr.head().ref());
        assertEquals("main", pr.base().ref());
    }
}