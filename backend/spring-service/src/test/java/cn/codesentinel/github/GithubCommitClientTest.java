package cn.codesentinel.github;

import cn.codesentinel.config.GithubAppProperties;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

class GithubCommitClientTest {

    private static final String TEST_API_URL = "https://api.github.com";
    private static final String TEST_TOKEN = "ghs_test-token";

    private MockRestServiceServer mockServer;
    private GithubCommitClient commitClient;

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

        commitClient = new GithubCommitClient(apiClient, authService);
    }

    @AfterEach
    void tearDown() {
        mockServer.verify();
    }

    @Test
    void shouldGetCommit() {
        String responseBody = """
                {
                    "sha": "abc123def456",
                    "commit": {
                        "message": "Fix null pointer in UserService"
                    },
                    "files": [
                        {
                            "filename": "src/UserService.java",
                            "status": "modified",
                            "additions": 5,
                            "deletions": 3,
                            "patch": "@@ -1,2 +1,3 @@"
                        }
                    ]
                }""";

        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/owner/repo/commits/abc123def456"))
                .andExpect(method(HttpMethod.GET))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        Commit commit = commitClient.getCommit("owner", "repo", "abc123def456");

        assertNotNull(commit);
        assertEquals("abc123def456", commit.sha());
        assertEquals("Fix null pointer in UserService", commit.commit().message());
        assertEquals(1, commit.files().size());
        assertEquals("src/UserService.java", commit.files().get(0).filename());
        assertEquals("modified", commit.files().get(0).status());
        assertEquals(5, commit.files().get(0).additions());
        assertEquals(3, commit.files().get(0).deletions());
        assertEquals("@@ -1,2 +1,3 @@", commit.files().get(0).patch());
    }

    @Test
    void shouldSetAuthorizationHeader() {
        String responseBody = """
                {
                    "sha": "abc",
                    "commit": { "message": "test" },
                    "files": []
                }""";

        mockServer.expect(requestTo(TEST_API_URL + "/repos/o/r/commits/abc"))
                .andExpect(method(HttpMethod.GET))
                .andExpect(header("Authorization", "Bearer " + TEST_TOKEN))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        commitClient.getCommit("o", "r", "abc");
    }

    @Test
    void shouldReturnSha() {
        String responseBody = """
                {
                    "sha": "e7b9534c8a2f1d6b3e5a7c9d0f1e2a3b4c5d6e7f",
                    "commit": { "message": "t" },
                    "files": []
                }""";

        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/commits/e7b9534c8a2f1d6b3e5a7c9d0f1e2a3b4c5d6e7f"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        Commit commit = commitClient.getCommit("o", "r",
                "e7b9534c8a2f1d6b3e5a7c9d0f1e2a3b4c5d6e7f");
        assertEquals("e7b9534c8a2f1d6b3e5a7c9d0f1e2a3b4c5d6e7f", commit.sha());
    }

    @Test
    void shouldReturnMessage() {
        String responseBody = """
                {
                    "sha": "abc",
                    "commit": { "message": "Add webhook signature verification" },
                    "files": []
                }""";

        mockServer.expect(requestTo(TEST_API_URL + "/repos/o/r/commits/abc"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        Commit commit = commitClient.getCommit("o", "r", "abc");
        assertEquals("Add webhook signature verification",
                commit.commit().message());
    }

    @Test
    void shouldReturnFileList() {
        String responseBody = """
                {
                    "sha": "abc",
                    "commit": { "message": "t" },
                    "files": [
                        { "filename": "a.java", "status": "added",
                          "additions": 10, "deletions": 0, "patch": "@@" },
                        { "filename": "b.java", "status": "modified",
                          "additions": 2, "deletions": 1, "patch": "@@" },
                        { "filename": "c.java", "status": "removed",
                          "additions": 0, "deletions": 5, "patch": "@@" }
                    ]
                }""";

        mockServer.expect(requestTo(TEST_API_URL + "/repos/o/r/commits/abc"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        Commit commit = commitClient.getCommit("o", "r", "abc");

        List<Commit.CommitFile> files = commit.files();
        assertEquals(3, files.size());
    }

    @Test
    void shouldReturnFileName() {
        String responseBody = """
                {
                    "sha": "abc",
                    "commit": { "message": "t" },
                    "files": [
                        {
                            "filename": "src/main/java/cn/codesentinel/App.java",
                            "status": "modified",
                            "additions": 1,
                            "deletions": 0,
                            "patch": "@@"
                        }
                    ]
                }""";

        mockServer.expect(requestTo(TEST_API_URL + "/repos/o/r/commits/abc"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        Commit commit = commitClient.getCommit("o", "r", "abc");
        assertEquals("src/main/java/cn/codesentinel/App.java",
                commit.files().get(0).filename());
    }

    @Test
    void shouldReturnFileStatus() {
        String responseBody = """
                {
                    "sha": "abc",
                    "commit": { "message": "t" },
                    "files": [
                        { "filename": "f", "status": "renamed",
                          "additions": 0, "deletions": 0, "patch": null }
                    ]
                }""";

        mockServer.expect(requestTo(TEST_API_URL + "/repos/o/r/commits/abc"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        Commit commit = commitClient.getCommit("o", "r", "abc");
        assertEquals("renamed", commit.files().get(0).status());
    }

    @Test
    void shouldReturnFilePatch() {
        String diffPatch = """
                @@ -10,7 +10,9 @@ public class UserService {
                         return user;
                     }
                -    private User findById(Long id) {
                +    public User findById(Long id) {
                         return repository.findById(id).orElse(null);
                     }
                +    public void deleteUser(Long id) {""";

        String responseBody = """
                {
                    "sha": "abc",
                    "commit": { "message": "Refactor UserService" },
                    "files": [
                        {
                            "filename": "src/UserService.java",
                            "status": "modified",
                            "additions": 3,
                            "deletions": 1,
                            "patch": "%s"
                        }
                    ]
                }""".formatted(diffPatch.replace("\n", "\\n").replace("\"", "\\\""));

        // Build clean JSON without escape issues
        String json = """
                {
                    "sha": "abc",
                    "commit": { "message": "Refactor UserService" },
                    "files": [
                        {
                            "filename": "src/UserService.java",
                            "status": "modified",
                            "additions": 3,
                            "deletions": 1,
                            "patch": "@@ -10,7 +10,9 @@ public class UserService {\\n         return user;\\n     }\\n-    private User findById(Long id) {\\n+    public User findById(Long id) {\\n         return repository.findById(id).orElse(null);\\n     }\\n+    public void deleteUser(Long id) {"
                        }
                    ]
                }""";

        mockServer.expect(requestTo(TEST_API_URL + "/repos/o/r/commits/abc"))
                .andRespond(withSuccess(json, MediaType.APPLICATION_JSON));

        Commit commit = commitClient.getCommit("o", "r", "abc");
        String patch = commit.files().get(0).patch();
        assertNotNull(patch);
        assertTrue(patch.contains("@@"));
        assertTrue(patch.contains("findById"));
    }

    @Test
    void shouldThrowOn404() {
        mockServer.expect(requestTo(TEST_API_URL + "/repos/o/r/commits/nonexistent"))
                .andRespond(withStatus(org.springframework.http.HttpStatus.NOT_FOUND)
                        .body("{\"message\":\"Not Found\"}")
                        .contentType(MediaType.APPLICATION_JSON));

        GithubApiException ex = assertThrows(GithubApiException.class, () ->
                commitClient.getCommit("o", "r", "nonexistent"));

        assertEquals(404, ex.getStatusCode());
        assertTrue(ex.isClientError());
    }

    @Test
    void shouldAllowNullPatch() {
        String responseBody = """
                {
                    "sha": "abc",
                    "commit": { "message": "Binary file update" },
                    "files": [
                        {
                            "filename": "assets/logo.png",
                            "status": "modified",
                            "additions": 0,
                            "deletions": 0,
                            "patch": null
                        }
                    ]
                }""";

        mockServer.expect(requestTo(TEST_API_URL + "/repos/o/r/commits/abc"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        Commit commit = commitClient.getCommit("o", "r", "abc");
        assertNull(commit.files().get(0).patch());
    }

    @Test
    void shouldIgnoreUnknownFields() {
        String responseBody = """
                {
                    "sha": "abc",
                    "commit": {
                        "message": "test",
                        "author": { "name": "Dev", "date": "2024-01-01T00:00:00Z" },
                        "committer": { "name": "GitHub" },
                        "tree": { "sha": "tree-sha" },
                        "comment_count": 0,
                        "verification": { "verified": true }
                    },
                    "files": [
                        {
                            "filename": "app.java",
                            "status": "modified",
                            "additions": 1,
                            "deletions": 0,
                            "patch": "@@",
                            "sha": "file-sha",
                            "blob_url": "https://...",
                            "raw_url": "https://...",
                            "contents_url": "https://...",
                            "changes": 1
                        }
                    ],
                    "stats": { "additions": 1, "deletions": 0, "total": 1 },
                    "parents": [{ "sha": "parent-sha" }],
                    "url": "https://...",
                    "html_url": "https://..."
                }""";

        mockServer.expect(requestTo(TEST_API_URL + "/repos/o/r/commits/abc"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        Commit commit = commitClient.getCommit("o", "r", "abc");

        assertEquals("abc", commit.sha());
        assertEquals("test", commit.commit().message());
        assertEquals(1, commit.files().size());
        assertEquals("app.java", commit.files().get(0).filename());
    }
}