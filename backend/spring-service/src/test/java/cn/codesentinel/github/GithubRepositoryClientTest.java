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

class GithubRepositoryClientTest {

    private static final String TEST_API_URL = "https://api.github.com";
    private static final String TEST_TOKEN = "ghs_test-token";

    private MockRestServiceServer mockServer;
    private GithubRepositoryClient repositoryClient;

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

        repositoryClient = new GithubRepositoryClient(apiClient, authService);
    }

    @AfterEach
    void tearDown() {
        mockServer.verify();
    }

    @Test
    void shouldGetRepository() {
        String responseBody = """
                {
                    "id": 12345,
                    "full_name": "owner/test-repo",
                    "name": "test-repo"
                }""";

        mockServer.expect(requestTo(TEST_API_URL + "/repos/owner/test-repo"))
                .andExpect(method(HttpMethod.GET))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        Repository repo = repositoryClient.getRepository("owner", "test-repo");

        assertNotNull(repo);
        assertEquals(12345L, repo.id());
        assertEquals("owner/test-repo", repo.fullName());
        assertEquals("test-repo", repo.name());
    }

    @Test
    void shouldSetAuthorizationHeader() {
        String responseBody = """
                {
                    "id": 1,
                    "full_name": "org/repo",
                    "name": "repo"
                }""";

        mockServer.expect(requestTo(TEST_API_URL + "/repos/org/repo"))
                .andExpect(method(HttpMethod.GET))
                .andExpect(header("Authorization", "Bearer " + TEST_TOKEN))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        repositoryClient.getRepository("org", "repo");
    }

    @Test
    void shouldReturnRepositoryId() {
        String responseBody = """
                {
                    "id": 99999,
                    "full_name": "a/b",
                    "name": "b"
                }""";

        mockServer.expect(requestTo(TEST_API_URL + "/repos/a/b"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        Repository repo = repositoryClient.getRepository("a", "b");
        assertEquals(99999L, repo.id());
    }

    @Test
    void shouldReturnRepositoryFullName() {
        String responseBody = """
                {
                    "id": 1,
                    "full_name": "zhangyu1108l/CodeSentinel",
                    "name": "CodeSentinel"
                }""";

        mockServer.expect(requestTo(TEST_API_URL + "/repos/zhangyu1108l/CodeSentinel"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        Repository repo = repositoryClient.getRepository("zhangyu1108l", "CodeSentinel");
        assertEquals("zhangyu1108l/CodeSentinel", repo.fullName());
    }

    @Test
    void shouldReturnRepositoryName() {
        String responseBody = """
                {
                    "id": 1,
                    "full_name": "owner/repo",
                    "name": "repo"
                }""";

        mockServer.expect(requestTo(TEST_API_URL + "/repos/owner/repo"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        Repository repo = repositoryClient.getRepository("owner", "repo");
        assertEquals("repo", repo.name());
    }

    @Test
    void shouldThrowOn404() {
        mockServer.expect(requestTo(TEST_API_URL + "/repos/owner/missing"))
                .andRespond(withStatus(org.springframework.http.HttpStatus.NOT_FOUND)
                        .body("{\"message\":\"Not Found\"}")
                        .contentType(MediaType.APPLICATION_JSON));

        GithubApiException ex = assertThrows(GithubApiException.class, () ->
                repositoryClient.getRepository("owner", "missing"));

        assertEquals(404, ex.getStatusCode());
        assertTrue(ex.isClientError());
    }

    @Test
    void shouldThrowOn403() {
        mockServer.expect(requestTo(TEST_API_URL + "/repos/owner/private"))
                .andRespond(withStatus(org.springframework.http.HttpStatus.FORBIDDEN)
                        .body("{\"message\":\"Resource not accessible by integration\"}")
                        .contentType(MediaType.APPLICATION_JSON));

        GithubApiException ex = assertThrows(GithubApiException.class, () ->
                repositoryClient.getRepository("owner", "private"));

        assertEquals(403, ex.getStatusCode());
        assertTrue(ex.isClientError());
    }

    @Test
    void shouldIgnoreUnknownFields() {
        String responseBody = """
                {
                    "id": 42,
                    "full_name": "owner/repo",
                    "name": "repo",
                    "description": "should be ignored",
                    "private": false,
                    "html_url": "https://github.com/owner/repo",
                    "language": "Java",
                    "stargazers_count": 100
                }""";

        mockServer.expect(requestTo(TEST_API_URL + "/repos/owner/repo"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        Repository repo = repositoryClient.getRepository("owner", "repo");

        assertEquals(42L, repo.id());
        assertEquals("owner/repo", repo.fullName());
        assertEquals("repo", repo.name());
    }
}