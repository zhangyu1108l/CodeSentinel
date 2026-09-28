package cn.codesentinel.github;

import cn.codesentinel.config.GithubAppProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
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

class GithubAuthServiceTest {

    private static final String TEST_APP_ID = "5086582";
    private static final String TEST_INSTALLATION_ID = "12345678";
    private static final String TEST_API_URL = "https://api.github.com";
    private static final String TEST_JWT = "eyJhbGci.test.jwt";

    private MockRestServiceServer mockServer;
    private GithubAuthService service;
    private GithubJwtService jwtService;
    private ObjectMapper objectMapper;

    @BeforeEach
    void setUp() {
        jwtService = mock(GithubJwtService.class);
        when(jwtService.generateAppJwt()).thenReturn(TEST_JWT);

        objectMapper = new ObjectMapper();

        RestClient.Builder builder = RestClient.builder();
        mockServer = MockRestServiceServer.bindTo(builder).build();
    }

    @AfterEach
    void tearDown() {
        mockServer.verify();
    }

    private GithubAuthService createService(String installationId) {
        GithubAppProperties props = new GithubAppProperties(
                TEST_APP_ID, null, null, null,
                installationId, TEST_API_URL);
        return new GithubAuthService(jwtService, props, RestClient.builder(), objectMapper);
    }

    private GithubAuthService createServiceWithServer(String installationId) {
        GithubAppProperties props = new GithubAppProperties(
                TEST_APP_ID, null, null, null,
                installationId, TEST_API_URL);
        RestClient.Builder builder = RestClient.builder();
        mockServer = MockRestServiceServer.bindTo(builder).build();
        return new GithubAuthService(jwtService, props, builder, objectMapper);
    }

    @Test
    void shouldGetInstallationTokenSuccessfully() {
        service = createServiceWithServer(TEST_INSTALLATION_ID);

        mockServer.expect(requestTo(TEST_API_URL
                        + "/app/installations/" + TEST_INSTALLATION_ID + "/access_tokens"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(header("Authorization", "Bearer " + TEST_JWT))
                .andExpect(header("Accept", "application/vnd.github.v3+json"))
                .andRespond(withSuccess(
                        "{\"token\":\"ghs_testtoken\","
                                + "\"expires_at\":\"2024-01-01T00:00:00Z\"}",
                        MediaType.APPLICATION_JSON));

        InstallationToken result = service.getInstallationToken(TEST_INSTALLATION_ID);
        assertEquals("ghs_testtoken", result.token());
        assertEquals("2024-01-01T00:00:00Z", result.expiresAt());
    }

    @Test
    void shouldUseJwtInAuthorizationHeader() {
        service = createServiceWithServer(TEST_INSTALLATION_ID);

        mockServer.expect(requestTo(TEST_API_URL
                        + "/app/installations/" + TEST_INSTALLATION_ID + "/access_tokens"))
                .andExpect(header("Authorization", "Bearer " + TEST_JWT))
                .andRespond(withSuccess(
                        "{\"token\":\"ghs_any\"}",
                        MediaType.APPLICATION_JSON));

        service.getInstallationToken(TEST_INSTALLATION_ID);
    }

    @Test
    void shouldPostToCorrectUrl() {
        service = createServiceWithServer(TEST_INSTALLATION_ID);

        mockServer.expect(requestTo(TEST_API_URL
                        + "/app/installations/" + TEST_INSTALLATION_ID + "/access_tokens"))
                .andExpect(method(HttpMethod.POST))
                .andRespond(withSuccess(
                        "{\"token\":\"ghs_any\"}",
                        MediaType.APPLICATION_JSON));

        service.getInstallationToken(TEST_INSTALLATION_ID);
    }

    @Test
    void shouldGetInstallationTokenFromConfig() {
        service = createServiceWithServer(TEST_INSTALLATION_ID);

        mockServer.expect(requestTo(TEST_API_URL
                        + "/app/installations/" + TEST_INSTALLATION_ID + "/access_tokens"))
                .andExpect(method(HttpMethod.POST))
                .andRespond(withSuccess(
                        "{\"token\":\"ghs_from_config\"}",
                        MediaType.APPLICATION_JSON));

        InstallationToken token = service.getInstallationToken();
        assertEquals("ghs_from_config", token.token());
    }

    @Test
    void shouldThrowWhenInstallationIdNotConfigured() {
        service = createService(null);

        assertThrows(IllegalStateException.class, service::getInstallationToken);
    }

    @Test
    void shouldThrowWhenInstallationIdIsBlank() {
        service = createService("  ");

        assertThrows(IllegalStateException.class, service::getInstallationToken);
    }

    @Test
    void shouldThrowWhenGitHubReturns401() {
        service = createServiceWithServer(TEST_INSTALLATION_ID);

        mockServer.expect(requestTo(TEST_API_URL
                        + "/app/installations/" + TEST_INSTALLATION_ID + "/access_tokens"))
                .andRespond(withStatus(org.springframework.http.HttpStatus.UNAUTHORIZED)
                        .body("{\"message\":\"Bad credentials\"}")
                        .contentType(MediaType.APPLICATION_JSON));

        GithubApiException ex = assertThrows(GithubApiException.class,
                () -> service.getInstallationToken(TEST_INSTALLATION_ID));
        assertEquals(401, ex.getStatusCode());
        assertTrue(ex.isClientError());
    }

    @Test
    void shouldThrowWhenGitHubReturns403() {
        service = createServiceWithServer(TEST_INSTALLATION_ID);

        mockServer.expect(requestTo(TEST_API_URL
                        + "/app/installations/" + TEST_INSTALLATION_ID + "/access_tokens"))
                .andRespond(withStatus(org.springframework.http.HttpStatus.FORBIDDEN)
                        .body("{\"message\":\"Resource not accessible by integration\"}")
                        .contentType(MediaType.APPLICATION_JSON));

        GithubApiException ex = assertThrows(GithubApiException.class,
                () -> service.getInstallationToken(TEST_INSTALLATION_ID));
        assertEquals(403, ex.getStatusCode());
    }

    @Test
    void shouldThrowWhenGitHubReturns500() {
        service = createServiceWithServer(TEST_INSTALLATION_ID);

        mockServer.expect(requestTo(TEST_API_URL
                        + "/app/installations/" + TEST_INSTALLATION_ID + "/access_tokens"))
                .andRespond(withServerError()
                        .body("{\"message\":\"Internal error\"}")
                        .contentType(MediaType.APPLICATION_JSON));

        GithubApiException ex = assertThrows(GithubApiException.class,
                () -> service.getInstallationToken(TEST_INSTALLATION_ID));
        assertTrue(ex.getStatusCode() >= 500);
        assertTrue(ex.isServerError());
    }

    @Test
    void shouldThrowWhenResponseIsInvalidJson() {
        service = createServiceWithServer(TEST_INSTALLATION_ID);

        mockServer.expect(requestTo(TEST_API_URL
                        + "/app/installations/" + TEST_INSTALLATION_ID + "/access_tokens"))
                .andRespond(withSuccess("not valid json", MediaType.APPLICATION_JSON));

        assertThrows(GithubApiException.class,
                () -> service.getInstallationToken(TEST_INSTALLATION_ID));
    }

    @Test
    void shouldThrowWhenResponseMissingTokenField() {
        service = createServiceWithServer(TEST_INSTALLATION_ID);

        mockServer.expect(requestTo(TEST_API_URL
                        + "/app/installations/" + TEST_INSTALLATION_ID + "/access_tokens"))
                .andRespond(withSuccess(
                        "{\"expires_at\":\"2024-01-01T00:00:00Z\"}",
                        MediaType.APPLICATION_JSON));

        GithubApiException ex = assertThrows(GithubApiException.class,
                () -> service.getInstallationToken(TEST_INSTALLATION_ID));
        assertTrue(ex.getMessage().contains("missing token"));
    }

    @Test
    void shouldGenerateJwtForEachRequest() {
        service = createServiceWithServer(TEST_INSTALLATION_ID);

        mockServer.expect(requestTo(TEST_API_URL
                        + "/app/installations/" + TEST_INSTALLATION_ID + "/access_tokens"))
                .andExpect(header("Authorization", "Bearer " + TEST_JWT))
                .andRespond(withSuccess(
                        "{\"token\":\"ghs_first\"}",
                        MediaType.APPLICATION_JSON));

        service.getInstallationToken(TEST_INSTALLATION_ID);
    }

    @Test
    void shouldAcceptValidExpiresAtInResponse() {
        service = createServiceWithServer(TEST_INSTALLATION_ID);

        mockServer.expect(requestTo(TEST_API_URL
                        + "/app/installations/" + TEST_INSTALLATION_ID + "/access_tokens"))
                .andRespond(withSuccess(
                        "{\"token\":\"ghs_test\","
                                + "\"expires_at\":\"2026-01-01T12:00:00Z\"}",
                        MediaType.APPLICATION_JSON));

        InstallationToken token = service.getInstallationToken(TEST_INSTALLATION_ID);
        assertEquals("ghs_test", token.token());
        assertEquals("2026-01-01T12:00:00Z", token.expiresAt());
    }
}