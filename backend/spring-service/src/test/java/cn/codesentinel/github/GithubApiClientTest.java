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
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

class GithubApiClientTest {

    private static final String TEST_API_URL = "https://api.github.com";

    private MockRestServiceServer mockServer;
    private GithubApiClient client;

    @BeforeEach
    void setUp() {
        RestClient.Builder builder = RestClient.builder();
        mockServer = MockRestServiceServer.bindTo(builder).build();

        GithubAppProperties props = new GithubAppProperties(
                null, null, null, null, null, TEST_API_URL);
        client = new GithubApiClient(builder, props);
    }

    @AfterEach
    void tearDown() {
        mockServer.verify();
    }

    @Test
    void shouldUseConfiguredBaseUrl() {
        mockServer.expect(requestTo(TEST_API_URL + "/repos/owner/repo"))
                .andExpect(method(HttpMethod.GET))
                .andRespond(withSuccess("{}", MediaType.APPLICATION_JSON));

        client.getRestClient().get()
                .uri("/repos/owner/repo")
                .retrieve()
                .body(String.class);
    }

    @Test
    void shouldSendAcceptHeader() {
        mockServer.expect(requestTo(TEST_API_URL + "/test"))
                .andExpect(method(HttpMethod.GET))
                .andExpect(header("Accept", "application/vnd.github.v3+json"))
                .andRespond(withSuccess("{}", MediaType.APPLICATION_JSON));

        client.getRestClient().get()
                .uri("/test")
                .retrieve()
                .body(String.class);
    }

    @Test
    void shouldReturnResponseBodyOn200() {
        mockServer.expect(requestTo(TEST_API_URL + "/data"))
                .andRespond(withSuccess("{\"name\":\"test\"}", MediaType.APPLICATION_JSON));

        String body = client.getRestClient().get()
                .uri("/data")
                .retrieve()
                .body(String.class);

        assertEquals("{\"name\":\"test\"}", body);
    }

    @Test
    void shouldThrowGithubApiExceptionOn401() {
        mockServer.expect(requestTo(TEST_API_URL + "/protected"))
                .andRespond(withStatus(org.springframework.http.HttpStatus.UNAUTHORIZED)
                        .body("{\"message\":\"Bad credentials\"}")
                        .contentType(MediaType.APPLICATION_JSON));

        GithubApiException ex = assertThrows(GithubApiException.class, () ->
                client.getRestClient().get()
                        .uri("/protected")
                        .retrieve()
                        .body(String.class));

        assertEquals(401, ex.getStatusCode());
        assertTrue(ex.isClientError());
        assertTrue(ex.getMessage().contains("401"));
        assertTrue(ex.getMessage().contains("Bad credentials"));
    }

    @Test
    void shouldThrowGithubApiExceptionOn403() {
        mockServer.expect(requestTo(TEST_API_URL + "/forbidden"))
                .andRespond(withStatus(org.springframework.http.HttpStatus.FORBIDDEN)
                        .body("{\"message\":\"Resource not accessible\"}")
                        .contentType(MediaType.APPLICATION_JSON));

        GithubApiException ex = assertThrows(GithubApiException.class, () ->
                client.getRestClient().get()
                        .uri("/forbidden")
                        .retrieve()
                        .body(String.class));

        assertEquals(403, ex.getStatusCode());
        assertTrue(ex.isClientError());
    }

    @Test
    void shouldThrowGithubApiExceptionOn404() {
        mockServer.expect(requestTo(TEST_API_URL + "/notfound"))
                .andRespond(withStatus(org.springframework.http.HttpStatus.NOT_FOUND)
                        .body("{\"message\":\"Not Found\"}")
                        .contentType(MediaType.APPLICATION_JSON));

        GithubApiException ex = assertThrows(GithubApiException.class, () ->
                client.getRestClient().get()
                        .uri("/notfound")
                        .retrieve()
                        .body(String.class));

        assertEquals(404, ex.getStatusCode());
        assertTrue(ex.isClientError());
    }

    @Test
    void shouldThrowGithubApiExceptionOn500() {
        mockServer.expect(requestTo(TEST_API_URL + "/error"))
                .andRespond(withServerError()
                        .body("{\"message\":\"Internal error\"}")
                        .contentType(MediaType.APPLICATION_JSON));

        GithubApiException ex = assertThrows(GithubApiException.class, () ->
                client.getRestClient().get()
                        .uri("/error")
                        .retrieve()
                        .body(String.class));

        assertTrue(ex.getStatusCode() >= 500);
        assertTrue(ex.isServerError());
        assertTrue(ex.getMessage().contains("Internal error"));
    }

    @Test
    void shouldDefaultToGithubApiBaseUrlWhenNotConfigured() {
        RestClient.Builder builder = RestClient.builder();
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();

        GithubAppProperties props = new GithubAppProperties(
                null, null, null, null, null, null);
        GithubApiClient defaultClient = new GithubApiClient(builder, props);

        server.expect(requestTo("https://api.github.com/default"))
                .andRespond(withSuccess("{}", MediaType.APPLICATION_JSON));

        defaultClient.getRestClient().get()
                .uri("/default")
                .retrieve()
                .body(String.class);

        server.verify();
    }

    @Test
    void shouldPreserveResponseBodyInException() {
        String errorBody = "{\"message\":\"Validation failed\",\"errors\":[{\"code\":\"missing_field\"}]}";
        mockServer.expect(requestTo(TEST_API_URL + "/validate"))
                .andRespond(withStatus(org.springframework.http.HttpStatus.UNPROCESSABLE_ENTITY)
                        .body(errorBody)
                        .contentType(MediaType.APPLICATION_JSON));

        GithubApiException ex = assertThrows(GithubApiException.class, () ->
                client.getRestClient().get()
                        .uri("/validate")
                        .retrieve()
                        .body(String.class));

        assertEquals(422, ex.getStatusCode());
        assertTrue(ex.getMessage().contains("Validation failed"));
        assertTrue(ex.getMessage().contains("missing_field"));
    }

    @Test
    void shouldSupportPostRequests() {
        mockServer.expect(requestTo(TEST_API_URL + "/create"))
                .andExpect(method(HttpMethod.POST))
                .andRespond(withSuccess("{\"id\":1}", MediaType.APPLICATION_JSON));

        String body = client.getRestClient().post()
                .uri("/create")
                .contentType(MediaType.APPLICATION_JSON)
                .body("{\"name\":\"test\"}")
                .retrieve()
                .body(String.class);

        assertEquals("{\"id\":1}", body);
    }
}