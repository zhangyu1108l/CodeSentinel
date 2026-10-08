package cn.codesentinel.github;

import cn.codesentinel.config.GithubAppProperties;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import java.nio.charset.StandardCharsets;
import java.util.Base64;

import org.springframework.web.util.UriUtils;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

class GithubFileContentClientTest {

    private static final String TEST_API_URL = "https://api.github.com";
    private static final String TEST_TOKEN = "ghs_test-token";
    private static final InstallationToken TOKEN =
            new InstallationToken(TEST_TOKEN, "2025-01-01T00:00:00Z");

    private MockRestServiceServer mockServer;
    private GithubAuthService authService;
    private GithubFileContentClient fileContentClient;

    @BeforeEach
    void setUp() {
        authService = mock(GithubAuthService.class);
        when(authService.getInstallationToken()).thenReturn(TOKEN);

        RestClient.Builder apiBuilder = RestClient.builder();
        mockServer = MockRestServiceServer.bindTo(apiBuilder).build();

        GithubAppProperties props = new GithubAppProperties(
                null, null, null, null, null, TEST_API_URL);
        GithubApiClient apiClient = new GithubApiClient(apiBuilder, props);

        fileContentClient = new GithubFileContentClient(apiClient, authService);
    }

    @AfterEach
    void tearDown() {
        mockServer.verify();
    }

    @Test
    void shouldGetFileContent() {
        String originalText = "public class App {\n    public static void main(String[] args) {\n        System.out.println(\"Hello\");\n    }\n}\n";
        String encoded = encodeGitHubStyle(originalText);

        String responseBody = """
                {
                    "type": "file",
                    "encoding": "base64",
                    "size": 123,
                    "name": "App.java",
                    "path": "src/App.java",
                    "content": "%s",
                    "sha": "abc123"
                }""".formatted(encoded);

        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/owner/repo/contents/src/App.java?ref=head123"))
                .andExpect(method(HttpMethod.GET))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        FileContent result = fileContentClient.getFileContent(
                "owner", "repo", "src/App.java", "head123");

        assertNotNull(result);
        assertEquals("src/App.java", result.path());
        assertEquals(originalText, result.content());
    }

    @Test
    void shouldSetAuthorizationHeader() {
        String encoded = encodeGitHubStyle("test");
        String responseBody = """
                {
                    "type": "file",
                    "encoding": "base64",
                    "content": "%s",
                    "path": "test.txt"
                }""".formatted(encoded);

        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/contents/test.txt?ref=abc"))
                .andExpect(method(HttpMethod.GET))
                .andExpect(header("Authorization", "Bearer " + TEST_TOKEN))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        fileContentClient.getFileContent("o", "r", "test.txt", "abc");
    }

    @Test
    void shouldPassRefAsQueryParameter() {
        String encoded = encodeGitHubStyle("x");
        String responseBody = """
                {
                    "type": "file",
                    "encoding": "base64",
                    "content": "%s",
                    "path": "f"
                }""".formatted(encoded);

        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/contents/f?ref=e7b9534c"))
                .andExpect(method(HttpMethod.GET))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        FileContent result = fileContentClient.getFileContent(
                "o", "r", "f", "e7b9534c");
        assertEquals("x", result.content());
    }

    @Test
    void shouldDecodeBase64ContentWithNewlines() {
        String originalText = "line1\nline2\nline3";
        String encoded = encodeGitHubStyle(originalText);

        String responseBody = """
                {
                    "type": "file",
                    "encoding": "base64",
                    "content": "%s",
                    "path": "file.txt"
                }""".formatted(encoded);

        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/contents/file.txt?ref=abc"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        FileContent result = fileContentClient.getFileContent(
                "o", "r", "file.txt", "abc");

        assertEquals(originalText, result.content());
    }

    @Test
    void shouldHandleNullContent() {
        String responseBody = """
                {
                    "type": "file",
                    "encoding": "base64",
                    "content": null,
                    "path": "large-file.bin"
                }""";

        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/contents/large-file.bin?ref=abc"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        FileContent result = fileContentClient.getFileContent(
                "o", "r", "large-file.bin", "abc");

        assertEquals("large-file.bin", result.path());
        assertNull(result.content());
    }

    @Test
    void shouldHandleDirectory() {
        String responseBody = """
                {
                    "type": "dir",
                    "encoding": null,
                    "content": null,
                    "path": "src/main"
                }""";

        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/contents/src/main?ref=abc"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        FileContent result = fileContentClient.getFileContent(
                "o", "r", "src/main", "abc");

        assertEquals("src/main", result.path());
        assertNull(result.content());
    }

    @Test
    void shouldHandleEmptyContent() {
        String responseBody = """
                {
                    "type": "file",
                    "encoding": "base64",
                    "content": "",
                    "path": "empty.txt"
                }""";

        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/contents/empty.txt?ref=abc"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        FileContent result = fileContentClient.getFileContent(
                "o", "r", "empty.txt", "abc");

        assertEquals("empty.txt", result.path());
        assertEquals("", result.content());
    }

    @Test
    void shouldThrowOn404() {
        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/contents/missing.java?ref=abc"))
                .andRespond(withStatus(org.springframework.http.HttpStatus.NOT_FOUND)
                        .body("{\"message\":\"Not Found\"}")
                        .contentType(MediaType.APPLICATION_JSON));

        GithubApiException ex = assertThrows(GithubApiException.class, () ->
                fileContentClient.getFileContent("o", "r", "missing.java", "abc"));

        assertEquals(404, ex.getStatusCode());
        assertTrue(ex.isClientError());
    }

    @Test
    void shouldIgnoreUnknownFields() {
        String encoded = encodeGitHubStyle("content");
        String responseBody = """
                {
                    "type": "file",
                    "encoding": "base64",
                    "size": 100,
                    "name": "Hello.java",
                    "path": "src/Hello.java",
                    "content": "%s",
                    "sha": "blob-sha",
                    "url": "https://api.github.com/repos/...",
                    "html_url": "https://github.com/...",
                    "git_url": "https://api.github.com/...",
                    "download_url": "https://raw.githubusercontent.com/..."
                }""".formatted(encoded);

        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/contents/src/Hello.java?ref=abc"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        FileContent result = fileContentClient.getFileContent(
                "o", "r", "src/Hello.java", "abc");

        assertEquals("src/Hello.java", result.path());
        assertEquals("content", result.content());
    }

    @Test
    void shouldHandleBase64WithCrLf() {
        String originalText = "test with CRLF";
        byte[] raw = originalText.getBytes(StandardCharsets.UTF_8);
        String b64 = Base64.getEncoder().encodeToString(raw);
        String withCrLf = b64.replaceAll("(.{60})", "$1\r\n")
                .replace("\r", "\\r").replace("\n", "\\n");

        String responseBody = """
                {
                    "type": "file",
                    "encoding": "base64",
                    "content": "%s",
                    "path": "crlf.txt"
                }""".formatted(withCrLf);

        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/contents/crlf.txt?ref=abc"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        FileContent result = fileContentClient.getFileContent(
                "o", "r", "crlf.txt", "abc");

        assertEquals(originalText, result.content());
    }

    @Test
    void shouldFallbackToRequestPathWhenResponsePathNull() {
        String encoded = encodeGitHubStyle("fallback");
        String responseBody = """
                {
                    "type": "file",
                    "encoding": "base64",
                    "content": "%s",
                    "path": null
                }""".formatted(encoded);

        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/contents/requested/path.java?ref=abc"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        FileContent result = fileContentClient.getFileContent(
                "o", "r", "requested/path.java", "abc");

        assertEquals("requested/path.java", result.path());
        assertEquals("fallback", result.content());
    }

    private static String encodeGitHubStyle(String text) {
        byte[] raw = text.getBytes(StandardCharsets.UTF_8);
        String b64 = Base64.getEncoder().encodeToString(raw);
        return b64.replaceAll("(.{60})", "$1\n").replace("\n", "\\n");
    }

    @Test
    void shouldRejectEncodingNone() {
        String responseBody = """
                {
                    "type": "file",
                    "encoding": "none",
                    "size": 2000000,
                    "content": "",
                    "path": "big.bin"
                }""";

        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/contents/big.bin?ref=abc"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        FileContent result = fileContentClient.getFileContent(
                "o", "r", "big.bin", "abc");

        assertNull(result.content());
        assertEquals(FileContent.REASON_TOO_LARGE, result.contentReason());
    }

    @Test
    void shouldRejectContentLargerThanMaxBytes() {
        String encoded = encodeGitHubStyle("small text");
        String responseBody = """
                {
                    "type": "file",
                    "encoding": "base64",
                    "size": 5000,
                    "content": "%s",
                    "path": "big.java"
                }""".formatted(encoded);

        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/contents/big.java?ref=abc"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        FileContent result = fileContentClient.getFileContent(
                "o", "r", "big.java", "abc", TOKEN, 1000);

        assertNull(result.content());
        assertEquals(FileContent.REASON_TOO_LARGE, result.contentReason());
    }

    @Test
    void shouldRejectContentWhoseDecodedSizeExceedsMaxBytes() {
        String encoded = Base64.getEncoder().encodeToString(
                "x".repeat(200).getBytes(StandardCharsets.UTF_8));
        String responseBody = """
                {
                    "type": "file",
                    "encoding": "base64",
                    "content": "%s",
                    "path": "unknown-size.java"
                }""".formatted(encoded);

        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/contents/unknown-size.java?ref=abc"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        FileContent result = fileContentClient.getFileContent(
                "o", "r", "unknown-size.java", "abc", TOKEN, 100);

        assertNull(result.content());
        assertEquals(FileContent.REASON_TOO_LARGE, result.contentReason());
    }

    @Test
    void shouldRejectBinaryContentWithNulByte() {
        byte[] raw = new byte[] {65, 0, 66};
        String encoded = Base64.getEncoder().encodeToString(raw);
        String responseBody = """
                {
                    "type": "file",
                    "encoding": "base64",
                    "content": "%s",
                    "path": "binary.dat"
                }""".formatted(encoded);

        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/contents/binary.dat?ref=abc"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        FileContent result = fileContentClient.getFileContent(
                "o", "r", "binary.dat", "abc");

        assertNull(result.content());
        assertEquals(FileContent.REASON_BINARY, result.contentReason());
    }

    @Test
    void shouldRejectNonBase64Encoding() {
        String responseBody = """
                {
                    "type": "file",
                    "encoding": "utf-8",
                    "content": "plain",
                    "path": "odd.txt"
                }""";

        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/contents/odd.txt?ref=abc"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        FileContent result = fileContentClient.getFileContent(
                "o", "r", "odd.txt", "abc");

        assertNull(result.content());
        assertEquals(FileContent.REASON_BINARY, result.contentReason());
    }

    @Test
    void shouldKeepLegitimateEmptyFileAvailable() {
        String responseBody = """
                {
                    "type": "file",
                    "encoding": "base64",
                    "size": 0,
                    "content": "",
                    "path": "empty.txt"
                }""";

        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/contents/empty.txt?ref=abc"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        FileContent result = fileContentClient.getFileContent(
                "o", "r", "empty.txt", "abc");

        assertEquals("", result.content());
        assertNull(result.contentReason());
    }

    @Test
    void shouldEncodeSpecialCharactersInPath() {
        String path = "docs/src file#1/中文.java";
        String content = "class Comment {}";
        String encoded = Base64.getEncoder().encodeToString(
                content.getBytes(StandardCharsets.UTF_8));
        String responseBody = """
                {
                    "type": "file",
                    "encoding": "base64",
                    "content": "%s",
                    "path": "%s"
                }""".formatted(encoded, path);

        String expectedUri = TEST_API_URL + "/repos/o/r/contents/docs/"
                + UriUtils.encodePathSegment("src file#1", StandardCharsets.UTF_8)
                + "/"
                + UriUtils.encodePathSegment("中文.java", StandardCharsets.UTF_8)
                + "?ref=abc";

        mockServer.expect(request -> assertEquals(expectedUri,
                        request.getURI().toString()))
                .andExpect(method(HttpMethod.GET))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        FileContent result = fileContentClient.getFileContent(
                "o", "r", path, "abc");

        assertEquals(path, result.path());
        assertEquals(content, result.content());
        assertNull(result.contentReason());
    }

    @Test
    void shouldThrowOn403() {
        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/contents/secret.java?ref=abc"))
                .andRespond(withStatus(org.springframework.http.HttpStatus.FORBIDDEN)
                        .body("{\"message\":\"Forbidden\"}")
                        .contentType(MediaType.APPLICATION_JSON));

        GithubApiException ex = assertThrows(GithubApiException.class, () ->
                fileContentClient.getFileContent("o", "r", "secret.java", "abc"));

        assertEquals(403, ex.getStatusCode());
        assertTrue(ex.isClientError());
    }

    @Test
    void shouldNotAskAuthServiceWhenTokenProvided() {
        String encoded = encodeGitHubStyle("x");
        String responseBody = """
                {
                    "type": "file",
                    "encoding": "base64",
                    "content": "%s",
                    "path": "f.java"
                }""".formatted(encoded);

        mockServer.expect(requestTo(TEST_API_URL
                        + "/repos/o/r/contents/f.java?ref=abc"))
                .andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));

        fileContentClient.getFileContent("o", "r", "f.java", "abc", TOKEN, 1000);

        verifyNoInteractions(authService);
    }
}