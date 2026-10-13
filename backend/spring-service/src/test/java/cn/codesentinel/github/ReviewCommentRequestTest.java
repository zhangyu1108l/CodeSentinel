package cn.codesentinel.github;

import cn.codesentinel.config.GithubAppProperties;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.mock;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

class ReviewCommentRequestTest {

    private static final String TEST_API_URL = "https://api.github.com";
    private static final String TEST_TOKEN = "ghs_test-token";

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void shouldOmitStartFieldsForSingleLineRequest() throws Exception {
        ReviewCommentRequest request = new ReviewCommentRequest(
                "note", "abc123def456", "src/A.java", 7, "RIGHT");

        String raw = objectMapper.writeValueAsString(request);
        assertFalse(raw.contains("start_line"));
        assertFalse(raw.contains("start_side"));

        JsonNode json = objectMapper.readTree(raw);
        assertEquals("note", json.get("body").asText());
        assertEquals("abc123def456", json.get("commit_id").asText());
        assertEquals("src/A.java", json.get("path").asText());
        assertEquals(7, json.get("line").asInt());
        assertEquals("RIGHT", json.get("side").asText());
    }

    @Test
    void shouldSerializeStartFieldsForMultiLineRequest() throws Exception {
        ReviewCommentRequest request = new ReviewCommentRequest(
                "note", "abc123def456", "src/A.java", 12, "RIGHT", 10, "RIGHT");

        JsonNode json = objectMapper.readTree(
                objectMapper.writeValueAsString(request));

        assertTrue(json.has("start_line"));
        assertTrue(json.has("start_side"));
        assertEquals(10, json.get("start_line").asInt());
        assertEquals("RIGHT", json.get("start_side").asText());
        assertEquals(12, json.get("line").asInt());
        assertEquals("RIGHT", json.get("side").asText());
    }

    @Test
    void shouldPreserveSideValuesForBothLines() throws Exception {
        ReviewCommentRequest request = new ReviewCommentRequest(
                "note", "abc123def456", "src/A.java", 9, "LEFT", 8, "LEFT");

        JsonNode json = objectMapper.readTree(
                objectMapper.writeValueAsString(request));

        assertEquals("LEFT", json.get("side").asText());
        assertEquals("LEFT", json.get("start_side").asText());
        assertEquals(8, json.get("start_line").asInt());
        assertEquals(9, json.get("line").asInt());
    }

    @Test
    void shouldKeepFiveArgumentConstructorCompatible() {
        ReviewCommentRequest request = new ReviewCommentRequest(
                "note", "abc123def456", "src/A.java", 7, "RIGHT");

        assertEquals("note", request.body());
        assertEquals("abc123def456", request.commitId());
        assertEquals("src/A.java", request.path());
        assertEquals(7, request.line());
        assertEquals("RIGHT", request.side());
        assertNull(request.startLine());
        assertNull(request.startSide());
    }

    @Test
    void shouldSendMultiLineFieldsThroughClient() {
        GithubAuthService authService = mock(GithubAuthService.class);
        RestClient.Builder apiBuilder = RestClient.builder();
        MockRestServiceServer mockServer =
                MockRestServiceServer.bindTo(apiBuilder).build();

        GithubAppProperties props = new GithubAppProperties(
                null, null, null, null, null, TEST_API_URL);
        GithubApiClient apiClient = new GithubApiClient(apiBuilder, props);
        GithubReviewCommentClient client =
                new GithubReviewCommentClient(apiClient, authService);

        mockServer.expect(requestTo(TEST_API_URL + "/repos/o/r/pulls/1/comments"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(header("Authorization", "Bearer " + TEST_TOKEN))
                .andExpect(jsonPath("$.start_line").value(10))
                .andExpect(jsonPath("$.start_side").value("RIGHT"))
                .andExpect(jsonPath("$.line").value(12))
                .andExpect(jsonPath("$.side").value("RIGHT"))
                .andExpect(jsonPath("$.path").value("src/A.java"))
                .andRespond(withSuccess("""
                        {"id": 5, "body": "note",
                         "html_url": "https://github.com/o/r/pull/1#discussion_r5"}
                        """, MediaType.APPLICATION_JSON));

        ReviewCommentResponse response = client.createComment("o", "r", 1,
                new ReviewCommentRequest(
                        "note", "cafebabe", "src/A.java", 12, "RIGHT", 10, "RIGHT"),
                new InstallationToken(TEST_TOKEN, "2025-01-01T00:00:00Z"));

        assertEquals(5L, response.id());
        mockServer.verify();
    }
}