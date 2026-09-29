package cn.codesentinel.webhook;

import cn.codesentinel.task.ReviewTaskService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.util.HexFormat;

import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(WebhookController.class)
@Import(WebhookSignatureVerifier.class)
@TestPropertySource(properties = {
        "github.app.webhook-secret=test-webhook-secret"
})
class WebhookControllerTest {

    private static final String TEST_SECRET = "test-webhook-secret";
    private static final String HMAC_ALGORITHM = "HmacSHA256";

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private ReviewTaskService reviewTaskService;

    @Test
    void shouldReturn401WhenSignatureHeaderMissing() throws Exception {
        mockMvc.perform(post("/api/github/webhook")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isUnauthorized());

        verify(reviewTaskService, never()).createTask(anyString(), anyString(), anyInt(), anyString());
    }

    @Test
    void shouldReturn401WhenSignatureInvalid() throws Exception {
        String body = "{}";
        String signature = "sha256=" + "a".repeat(64);

        mockMvc.perform(post("/api/github/webhook")
                        .contentType(MediaType.APPLICATION_JSON)
                        .header("X-Hub-Signature-256", signature)
                        .header("X-GitHub-Event", "pull_request")
                        .content(body))
                .andExpect(status().isUnauthorized());

        verify(reviewTaskService, never()).createTask(anyString(), anyString(), anyInt(), anyString());
    }

    @Test
    void shouldReturn400WhenEventHeaderMissing() throws Exception {
        String body = "{}";
        String signature = makeSignature(body.getBytes(StandardCharsets.UTF_8), TEST_SECRET);

        mockMvc.perform(post("/api/github/webhook")
                        .contentType(MediaType.APPLICATION_JSON)
                        .header("X-Hub-Signature-256", signature)
                        .content(body))
                .andExpect(status().isBadRequest());
    }

    @Test
    void shouldReturn200WhenPushEventIgnored() throws Exception {
        String body = "{}";
        String signature = makeSignature(body.getBytes(StandardCharsets.UTF_8), TEST_SECRET);

        mockMvc.perform(post("/api/github/webhook")
                        .contentType(MediaType.APPLICATION_JSON)
                        .header("X-Hub-Signature-256", signature)
                        .header("X-GitHub-Event", "push")
                        .content(body))
                .andExpect(status().isOk());

        verify(reviewTaskService, never()).createTask(anyString(), anyString(), anyInt(), anyString());
    }

    @Test
    void shouldCreateTaskWhenPullRequestOpened() throws Exception {
        String body = """
                {
                    "action": "opened",
                    "pull_request": {
                        "number": 42,
                        "head": {
                            "sha": "abc123def456"
                        }
                    },
                    "repository": {
                        "full_name": "owner/test-repo"
                    },
                    "sender": {
                        "login": "developer1"
                    }
                }""";
        String signature = makeSignature(body.getBytes(StandardCharsets.UTF_8), TEST_SECRET);

        mockMvc.perform(post("/api/github/webhook")
                        .contentType(MediaType.APPLICATION_JSON)
                        .header("X-Hub-Signature-256", signature)
                        .header("X-GitHub-Event", "pull_request")
                        .content(body))
                .andExpect(status().isOk());

        verify(reviewTaskService).createTask("owner", "test-repo", 42, "abc123def456");
    }

    @Test
    void shouldCreateTaskWhenPullRequestSynchronize() throws Exception {
        String body = """
                {
                    "action": "synchronize",
                    "pull_request": {
                        "number": 7,
                        "head": {
                            "sha": "def789abc"
                        }
                    },
                    "repository": {
                        "full_name": "owner/repo"
                    },
                    "sender": {
                        "login": "dev"
                    }
                }""";
        String signature = makeSignature(body.getBytes(StandardCharsets.UTF_8), TEST_SECRET);

        mockMvc.perform(post("/api/github/webhook")
                        .contentType(MediaType.APPLICATION_JSON)
                        .header("X-Hub-Signature-256", signature)
                        .header("X-GitHub-Event", "pull_request")
                        .content(body))
                .andExpect(status().isOk());

        verify(reviewTaskService).createTask("owner", "repo", 7, "def789abc");
    }

    @Test
    void shouldCreateTaskWhenPullRequestReopened() throws Exception {
        String body = """
                {
                    "action": "reopened",
                    "pull_request": {
                        "number": 99,
                        "head": {
                            "sha": "ghi012xyz"
                        }
                    },
                    "repository": {
                        "full_name": "org/project"
                    },
                    "sender": {
                        "login": "reviewer"
                    }
                }""";
        String signature = makeSignature(body.getBytes(StandardCharsets.UTF_8), TEST_SECRET);

        mockMvc.perform(post("/api/github/webhook")
                        .contentType(MediaType.APPLICATION_JSON)
                        .header("X-Hub-Signature-256", signature)
                        .header("X-GitHub-Event", "pull_request")
                        .content(body))
                .andExpect(status().isOk());

        verify(reviewTaskService).createTask("org", "project", 99, "ghi012xyz");
    }

    @Test
    void shouldNotCreateTaskWhenPullRequestClosedActionIgnored() throws Exception {
        String body = """
                {
                    "action": "closed",
                    "pull_request": {
                        "number": 1,
                        "head": {
                            "sha": "abc123"
                        }
                    },
                    "repository": {
                        "full_name": "owner/repo"
                    }
                }""";
        String signature = makeSignature(body.getBytes(StandardCharsets.UTF_8), TEST_SECRET);

        mockMvc.perform(post("/api/github/webhook")
                        .contentType(MediaType.APPLICATION_JSON)
                        .header("X-Hub-Signature-256", signature)
                        .header("X-GitHub-Event", "pull_request")
                        .content(body))
                .andExpect(status().isOk());

        verify(reviewTaskService, never()).createTask(anyString(), anyString(), anyInt(), anyString());
    }

    @Test
    void shouldReturn500WhenBodyIsInvalidJson() throws Exception {
        String body = "not valid json";
        String signature = makeSignature(body.getBytes(StandardCharsets.UTF_8), TEST_SECRET);

        mockMvc.perform(post("/api/github/webhook")
                        .contentType(MediaType.APPLICATION_JSON)
                        .header("X-Hub-Signature-256", signature)
                        .header("X-GitHub-Event", "pull_request")
                        .content(body))
                .andExpect(status().isInternalServerError());
    }

    @Test
    void shouldReturn500WhenServiceThrowsException() throws Exception {
        String body = """
                {
                    "action": "opened",
                    "pull_request": {
                        "number": 42,
                        "head": {
                            "sha": "abc123"
                        }
                    },
                    "repository": {
                        "full_name": "owner/repo"
                    }
                }""";
        String signature = makeSignature(body.getBytes(StandardCharsets.UTF_8), TEST_SECRET);

        doThrow(new RuntimeException("Database error"))
                .when(reviewTaskService)
                .createTask("owner", "repo", 42, "abc123");

        mockMvc.perform(post("/api/github/webhook")
                        .contentType(MediaType.APPLICATION_JSON)
                        .header("X-Hub-Signature-256", signature)
                        .header("X-GitHub-Event", "pull_request")
                        .content(body))
                .andExpect(status().isInternalServerError());

        verify(reviewTaskService).createTask("owner", "repo", 42, "abc123");
    }

    @Test
    void shouldReturn400WhenCommitShaMissing() throws Exception {
        String body = """
                {
                    "action": "opened",
                    "pull_request": {
                        "number": 42
                    },
                    "repository": {
                        "full_name": "owner/repo"
                    }
                }""";
        String signature = makeSignature(body.getBytes(StandardCharsets.UTF_8), TEST_SECRET);

        mockMvc.perform(post("/api/github/webhook")
                        .contentType(MediaType.APPLICATION_JSON)
                        .header("X-Hub-Signature-256", signature)
                        .header("X-GitHub-Event", "pull_request")
                        .content(body))
                .andExpect(status().isBadRequest());

        verify(reviewTaskService, never()).createTask(anyString(), anyString(), anyInt(), anyString());
    }

    @Test
    void shouldReturn400WhenRepositoryMissing() throws Exception {
        String body = """
                {
                    "action": "opened",
                    "pull_request": {
                        "number": 42,
                        "head": {
                            "sha": "abc123"
                        }
                    }
                }""";
        String signature = makeSignature(body.getBytes(StandardCharsets.UTF_8), TEST_SECRET);

        mockMvc.perform(post("/api/github/webhook")
                        .contentType(MediaType.APPLICATION_JSON)
                        .header("X-Hub-Signature-256", signature)
                        .header("X-GitHub-Event", "pull_request")
                        .content(body))
                .andExpect(status().isBadRequest());

        verify(reviewTaskService, never()).createTask(anyString(), anyString(), anyInt(), anyString());
    }

    private static String makeSignature(byte[] payload, String secret) {
        return "sha256=" + makeHexSignature(payload, secret);
    }

    private static String makeHexSignature(byte[] payload, String secret) {
        try {
            Mac mac = Mac.getInstance(HMAC_ALGORITHM);
            SecretKeySpec keySpec = new SecretKeySpec(
                    secret.getBytes(StandardCharsets.UTF_8),
                    HMAC_ALGORITHM
            );
            mac.init(keySpec);
            byte[] hmac = mac.doFinal(payload);
            return HexFormat.of().formatHex(hmac);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }
}