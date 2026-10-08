package cn.codesentinel.github;

import cn.codesentinel.config.GithubAppProperties;
import cn.codesentinel.config.ReviewContextProperties;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

class GithubPullRequestFilesClientTest {

    private static final String TEST_API_URL = "https://api.github.com";
    private static final String TEST_TOKEN = "ghs_test-token";
    private static final InstallationToken TOKEN =
            new InstallationToken(TEST_TOKEN, "2025-01-01T00:00:00Z");

    private MockRestServiceServer mockServer;
    private GithubApiClient apiClient;
    private GithubAuthService authService;

    @BeforeEach
    void setUp() {
        authService = mock(GithubAuthService.class);
        when(authService.getInstallationToken()).thenReturn(TOKEN);

        RestClient.Builder apiBuilder = RestClient.builder();
        mockServer = MockRestServiceServer.bindTo(apiBuilder).build();

        GithubAppProperties props = new GithubAppProperties(
                null, null, null, null, null, TEST_API_URL);
        apiClient = new GithubApiClient(apiBuilder, props);
    }

    @AfterEach
    void tearDown() {
        mockServer.verify();
    }

    private GithubPullRequestFilesClient filesClient(int maxFiles, int maxFetchPages) {
        return filesClient(new ReviewContextProperties(
                maxFiles, 262_144, maxFetchPages, List.of("java", "py")));
    }

    private GithubPullRequestFilesClient filesClient(ReviewContextProperties properties) {
        return new GithubPullRequestFilesClient(apiClient, authService, properties);
    }

    private static String linkHeader(String url, String rel) {
        return "<" + url + ">; rel=\"" + rel + "\"";
    }

    private static HttpHeaders linkHeaders(String linkValue) {
        HttpHeaders headers = new HttpHeaders();
        headers.add(HttpHeaders.LINK, linkValue);
        return headers;
    }

    @Test
    void shouldGetSinglePageOfChangedFiles() {
        String responseBody = """
                [
                  {
                    "filename": "src/App.java",
                    "status": "modified",
                    "additions": 3,
                    "deletions": 1,
                    "changes": 4,
                    "patch": "@@ -1 +1 @@",
                    "blob_url": "https://github.com/owner/repo/blob/abc/src/App.java"
                  },
                  {
                    "filename": "src/renamed.py",
                    "previous_filename": "src/old.py",
                    "status": "renamed",
                    "additions": 0,
                    "deletions": 0,
                    "changes": 0,
                    "patch": null,
                    "blob_url": "https://github.com/owner/repo/blob/abc/src/renamed.py"
                  }
                ]""";

        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/owner/repo/pulls/42/files?per_page=100&page=1"))
                .andExpect(method(HttpMethod.GET))
                .andExpect(header("Authorization", "Bearer " + TEST_TOKEN))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        List<PullRequestFile> files = filesClient(50, 5)
                .getChangedFiles("owner", "repo", 42, TOKEN);

        assertEquals(2, files.size());
        assertEquals("src/App.java", files.get(0).path());
        assertEquals("modified", files.get(0).status());
        assertEquals(3, files.get(0).additions());
        assertEquals(1, files.get(0).deletions());
        assertEquals(4, files.get(0).changes());
        assertEquals("@@ -1 +1 @@", files.get(0).patch());
        assertNull(files.get(0).previousPath());
        assertEquals("src/renamed.py", files.get(1).path());
        assertEquals("src/old.py", files.get(1).previousPath());
        assertEquals("renamed", files.get(1).status());
        assertNull(files.get(1).patch());
        assertEquals("https://github.com/owner/repo/blob/abc/src/renamed.py",
                files.get(1).blobUrl());
    }

    @Test
    void shouldFollowLinkHeaderToTheNextPage() {
        String pageOne = """
                [
                  { "filename": "a/A.java", "status": "modified", "patch": "p1" }
                ]""";
        String pageTwo = """
                [
                  { "filename": "b/B.py", "status": "added", "patch": "p2" }
                ]""";

        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/owner/repo/pulls/42/files?per_page=100&page=1"))
                .andExpect(method(HttpMethod.GET))
                .andRespond(withSuccess(pageOne, MediaType.APPLICATION_JSON)
                        .headers(linkHeaders(linkHeader(
                                TEST_API_URL + "/repos/owner/repo/pulls/42/files?per_page=100&page=2",
                                "next"))));

        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/owner/repo/pulls/42/files?per_page=100&page=2"))
                .andExpect(method(HttpMethod.GET))
                .andRespond(withSuccess(pageTwo, MediaType.APPLICATION_JSON));

        List<PullRequestFile> files = filesClient(50, 5)
                .getChangedFiles("owner", "repo", 42, TOKEN);

        assertEquals(List.of("a/A.java", "b/B.py"),
                files.stream().map(PullRequestFile::path).toList());
    }

    @Test
    void shouldUsePerPage100() {
        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/pulls/1/files?per_page=100&page=1"))
                .andRespond(withSuccess("[]", MediaType.APPLICATION_JSON));

        filesClient(50, 5).getChangedFiles("o", "r", 1, TOKEN);
    }

    @Test
    void shouldStopAtMaxFilesWithoutAnotherRequest() {
        String responseBody = """
                [
                  { "filename": "a.java" },
                  { "filename": "b.java" },
                  { "filename": "c.java" }
                ]""";

        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/pulls/1/files?per_page=100&page=1"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON)
                        .headers(linkHeaders(linkHeader(
                                TEST_API_URL + "/repos/o/r/pulls/1/files?per_page=100&page=2",
                                "next"))));

        List<PullRequestFile> files = filesClient(2, 5)
                .getChangedFiles("o", "r", 1, TOKEN);

        assertEquals(2, files.size());
        assertEquals(List.of("a.java", "b.java"),
                files.stream().map(PullRequestFile::path).toList());
    }

    @Test
    void shouldRespectMaxFetchPages() {
        String pageOne = """
                [ { "filename": "a.java" } ]""";
        String pageTwo = """
                [ { "filename": "b.java" } ]""";

        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/pulls/1/files?per_page=100&page=1"))
                .andRespond(withSuccess(pageOne, MediaType.APPLICATION_JSON)
                        .headers(linkHeaders(linkHeader(
                                TEST_API_URL + "/repos/o/r/pulls/1/files?per_page=100&page=2",
                                "next"))));
        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/pulls/1/files?per_page=100&page=2"))
                .andRespond(withSuccess(pageTwo, MediaType.APPLICATION_JSON)
                        .headers(linkHeaders(linkHeader(
                                TEST_API_URL + "/repos/o/r/pulls/1/files?per_page=100&page=3",
                                "next"))));

        List<PullRequestFile> files = filesClient(50, 2)
                .getChangedFiles("o", "r", 1, TOKEN);

        assertEquals(2, files.size());
    }

    @Test
    void shouldReturnEmptyListForEmptyArray() {
        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/pulls/1/files?per_page=100&page=1"))
                .andRespond(withSuccess("[]", MediaType.APPLICATION_JSON));

        assertTrue(filesClient(50, 5).getChangedFiles("o", "r", 1, TOKEN).isEmpty());
    }

    @Test
    void shouldIgnoreLinkWithoutNextRelation() {
        String responseBody = """
                [ { "filename": "a.java" } ]""";

        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/pulls/1/files?per_page=100&page=1"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON)
                        .headers(linkHeaders(linkHeader(
                                TEST_API_URL + "/repos/o/r/pulls/1/files?per_page=100&page=9",
                                "last"))));

        assertEquals(1, filesClient(50, 5)
                .getChangedFiles("o", "r", 1, TOKEN).size());
    }

    @Test
    void shouldIgnoreMalformedLinkUrl() {
        String responseBody = """
                [ { "filename": "a.java" } ]""";

        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/pulls/1/files?per_page=100&page=1"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON)
                        .headers(linkHeaders("<http://bad url with spaces/>; rel=\"next\"")));

        assertEquals(1, filesClient(50, 5)
                .getChangedFiles("o", "r", 1, TOKEN).size());
    }

    @Test
    void shouldIgnoreGarbageLinkHeader() {
        String responseBody = """
                [ { "filename": "a.java" } ]""";

        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/pulls/1/files?per_page=100&page=1"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON)
                        .headers(linkHeaders("not-a-link-header")));

        assertEquals(1, filesClient(50, 5)
                .getChangedFiles("o", "r", 1, TOKEN).size());
    }

    @Test
    void shouldThrowOn404() {
        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/pulls/999/files?per_page=100&page=1"))
                .andRespond(withStatus(HttpStatus.NOT_FOUND)
                        .body("{\"message\":\"Not Found\"}")
                        .contentType(MediaType.APPLICATION_JSON));

        GithubApiException ex = assertThrows(GithubApiException.class, () ->
                filesClient(50, 5).getChangedFiles("o", "r", 999, TOKEN));

        assertEquals(404, ex.getStatusCode());
        assertTrue(ex.isClientError());
    }

    @Test
    void shouldThrowOn403() {
        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/pulls/1/files?per_page=100&page=1"))
                .andRespond(withStatus(HttpStatus.FORBIDDEN)
                        .body("{\"message\":\"Forbidden\"}")
                        .contentType(MediaType.APPLICATION_JSON));

        GithubApiException ex = assertThrows(GithubApiException.class, () ->
                filesClient(50, 5).getChangedFiles("o", "r", 1, TOKEN));

        assertEquals(403, ex.getStatusCode());
        assertTrue(ex.isClientError());
    }

    @Test
    void shouldKeepGitHubOrderAcrossPages() {
        String pageOne = """
                [ { "filename": "z.java" }, { "filename": "a.java" } ]""";
        String pageTwo = """
                [ { "filename": "m.java" } ]""";

        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/pulls/1/files?per_page=100&page=1"))
                .andRespond(withSuccess(pageOne, MediaType.APPLICATION_JSON)
                        .headers(linkHeaders(linkHeader(
                                TEST_API_URL + "/repos/o/r/pulls/1/files?per_page=100&page=2",
                                "next"))));
        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/pulls/1/files?per_page=100&page=2"))
                .andRespond(withSuccess(pageTwo, MediaType.APPLICATION_JSON));

        List<PullRequestFile> files = filesClient(50, 5)
                .getChangedFiles("o", "r", 1, TOKEN);

        assertEquals(List.of("z.java", "a.java", "m.java"),
                files.stream().map(PullRequestFile::path).toList());
    }

    @Test
    void shouldNotAskAuthServiceWhenTokenIsProvided() {
        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/pulls/1/files?per_page=100&page=1"))
                .andRespond(withSuccess("[]", MediaType.APPLICATION_JSON));

        filesClient(50, 5).getChangedFiles("o", "r", 1, TOKEN);

        verifyNoInteractions(authService);
    }

    @Test
    void shouldFetchTokenWhenNotProvided() {
        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/pulls/1/files?per_page=100&page=1"))
                .andExpect(header("Authorization", "Bearer " + TEST_TOKEN))
                .andRespond(withSuccess("[]", MediaType.APPLICATION_JSON));

        assertTrue(filesClient(50, 5).getChangedFiles("o", "r", 1).isEmpty());
    }
}