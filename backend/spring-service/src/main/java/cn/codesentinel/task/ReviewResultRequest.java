package cn.codesentinel.task;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

/**
 * Transport payload of {@code POST /api/tasks/{taskId}/result}
 * (Phase 9.5.3B1).
 *
 * <p>Only the three fields the reception record keeps are part of this
 * contract: the reviewed commit SHA, the AI review status
 * (COMPLETED / DEGRADED) and the finding list. The free-form Python
 * {@code report} dict is deliberately not forwarded. Unknown extra
 * fields are ignored so additive contract changes do not break
 * delivery; the task id travels in the URL path, not in the body.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record ReviewResultRequest(
        @JsonProperty("commit_sha") String commitSha,
        @JsonProperty("status") String status,
        @JsonProperty("findings") List<ReviewResultFinding> findings) {
}