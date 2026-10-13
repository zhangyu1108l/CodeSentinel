package cn.codesentinel.task;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.time.LocalDateTime;

/**
 * Reception response of {@code POST /api/tasks/{taskId}/result}.
 *
 * <p>{@code publishStatus} states whether the stored result has been
 * published. Phase 9.5.3B1 always answers PENDING on a first receipt and
 * never claims that comments were published; the review task status is
 * not touched by this endpoint, so COMPLETED must not be read as
 * "comments published".
 */
public record ReviewResultResponse(
        @JsonProperty("task_id") Long taskId,
        @JsonProperty("commit_sha") String commitSha,
        @JsonProperty("duplicate") boolean duplicate,
        @JsonProperty("publish_status") String publishStatus,
        @JsonProperty("received_at") LocalDateTime receivedAt) {
}