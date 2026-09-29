package cn.codesentinel.webhook;

import cn.codesentinel.task.ReviewTaskService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

import java.nio.charset.StandardCharsets;

@RestController
public class WebhookController {

    private static final Logger log = LoggerFactory.getLogger(WebhookController.class);

    private static final String PULL_REQUEST_EVENT = "pull_request";

    private final WebhookSignatureVerifier signatureVerifier;
    private final ObjectMapper objectMapper;
    private final ReviewTaskService reviewTaskService;

    public WebhookController(WebhookSignatureVerifier signatureVerifier,
                             ObjectMapper objectMapper,
                             ReviewTaskService reviewTaskService) {
        this.signatureVerifier = signatureVerifier;
        this.objectMapper = objectMapper;
        this.reviewTaskService = reviewTaskService;
    }

    @PostMapping("/api/github/webhook")
    public ResponseEntity<Void> handleWebhook(
            @RequestHeader(value = "X-Hub-Signature-256", required = false) String signatureHeader,
            @RequestHeader(value = "X-GitHub-Event", required = false) String eventType,
            @RequestBody byte[] body) {

        if (signatureHeader == null) {
            log.warn("Rejected webhook request: missing X-Hub-Signature-256 header");
            return ResponseEntity.status(401).build();
        }

        if (!signatureVerifier.verify(body, signatureHeader)) {
            log.warn("Rejected webhook request: invalid signature");
            return ResponseEntity.status(401).build();
        }

        if (eventType == null) {
            log.warn("Rejected webhook request: missing X-GitHub-Event header");
            return ResponseEntity.status(400).build();
        }

        if (!PULL_REQUEST_EVENT.equals(eventType)) {
            log.debug("Ignored webhook event type: {}", eventType);
            return ResponseEntity.ok().build();
        }

        try {
            String payload = new String(body, StandardCharsets.UTF_8);
            JsonNode json = objectMapper.readTree(payload);

            String action = json.has("action") ? json.get("action").asText() : null;

            if (!"opened".equals(action) && !"synchronize".equals(action) && !"reopened".equals(action)) {
                log.debug("Ignored pull_request action: {}", action);
                return ResponseEntity.ok().build();
            }

            JsonNode repo = json.get("repository");
            String fullName = repo != null && repo.has("full_name")
                    ? repo.get("full_name").asText() : null;

            JsonNode pr = json.get("pull_request");
            int prNumber = pr != null && pr.has("number")
                    ? pr.get("number").asInt() : -1;
            String commitSha = null;
            if (pr != null && pr.has("head") && pr.get("head").has("sha")) {
                commitSha = pr.get("head").get("sha").asText();
            }

            if (fullName == null || commitSha == null || prNumber == -1) {
                log.error("Missing required webhook fields: fullName={}, prNumber={}, sha={}",
                        fullName, prNumber, commitSha);
                return ResponseEntity.status(400).build();
            }

            String[] parts = fullName.split("/", 2);
            if (parts.length != 2) {
                log.error("Invalid repository full_name format: {}", fullName);
                return ResponseEntity.status(400).build();
            }

            String owner = parts[0];
            String repoName = parts[1];

            reviewTaskService.createTask(owner, repoName, prNumber, commitSha);

            log.info("Created review task: owner={}, repo={}, pr={}, sha={}, action={}",
                    owner, repoName, prNumber, commitSha, action);

            return ResponseEntity.ok().build();
        } catch (Exception e) {
            log.error("Failed to process webhook request", e);
            return ResponseEntity.status(500).build();
        }
    }
}