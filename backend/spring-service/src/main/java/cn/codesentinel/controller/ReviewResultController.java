package cn.codesentinel.controller;

import cn.codesentinel.task.ReviewResultError;
import cn.codesentinel.task.ReviewResultRejectedException;
import cn.codesentinel.task.ReviewResultRequest;
import cn.codesentinel.task.ReviewResultResponse;
import cn.codesentinel.task.ReviewResultService;
import cn.codesentinel.task.TaskNotFoundException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/**
 * Durable reception of one AI review result (Phase 9.5.3B1).
 *
 * <p>{@code POST /api/tasks/{taskId}/result} persists the transport
 * payload snapshot with publish_status=PENDING and answers 202 on a
 * first receipt; an identical re-delivery answers 200 with
 * {@code duplicate=true} and the stored publish status; a conflicting
 * payload answers 409. The endpoint never publishes comments and never
 * marks the review task COMPLETED, so COMPLETED must not be read as
 * "comments published".
 *
 * <p>Authentication: minimal configurable internal token
 * ({@code review.result.internal-token}, environment
 * {@code REVIEW_RESULT_INTERNAL_TOKEN}, header
 * {@code X-Internal-Token}, constant-time comparison). A blank/unset
 * token rejects every request (fail closed) and the token value is never
 * logged. While no valid token is presented, no payload is processed -
 * note that a syntactically invalid JSON body is rejected by the message
 * converter (400) before this handler runs. The existing task endpoints
 * (running/complete/failure) keep their current unauthenticated
 * behavior; hardening them is out of this phase's scope.
 */
@RestController
public class ReviewResultController {

    public static final String INTERNAL_TOKEN_HEADER = "X-Internal-Token";

    private static final Logger log =
            LoggerFactory.getLogger(ReviewResultController.class);

    private final ReviewResultService reviewResultService;
    private final String internalToken;

    public ReviewResultController(
            ReviewResultService reviewResultService,
            @Value("${review.result.internal-token:}") String internalToken) {
        this.reviewResultService = reviewResultService;
        this.internalToken = internalToken;
    }

    @PostMapping("/api/tasks/{taskId}/result")
    public ResponseEntity<ReviewResultResponse> receiveResult(
            @PathVariable Long taskId,
            @RequestHeader(value = INTERNAL_TOKEN_HEADER, required = false)
            String token,
            @RequestBody ReviewResultRequest request) {
        if (!isInternalRequest(token)) {
            log.warn("Rejected review result delivery: invalid or missing "
                    + "internal token");
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
        }
        ReviewResultResponse response =
                reviewResultService.receiveResult(taskId, request);
        HttpStatus status = response.duplicate()
                ? HttpStatus.OK
                : HttpStatus.ACCEPTED;
        return ResponseEntity.status(status).body(response);
    }

    @ExceptionHandler(TaskNotFoundException.class)
    public ResponseEntity<Void> handleTaskNotFound(TaskNotFoundException e) {
        log.warn("Review result delivered for a missing task: {}",
                e.getMessage());
        return ResponseEntity.notFound().build();
    }

    @ExceptionHandler(ReviewResultRejectedException.class)
    public ResponseEntity<ReviewResultError> handleRejected(
            ReviewResultRejectedException e) {
        log.warn("Review result rejected ({}): {}", e.getStatus(),
                e.getMessage());
        return ResponseEntity.status(e.getStatus())
                .body(new ReviewResultError(e.getMessage()));
    }

    private boolean isInternalRequest(String providedToken) {
        if (internalToken == null || internalToken.isBlank()) {
            log.warn("Review result internal token is not configured, "
                    + "rejecting all result delivery requests");
            return false;
        }
        if (providedToken == null) {
            return false;
        }
        return MessageDigest.isEqual(
                internalToken.getBytes(StandardCharsets.UTF_8),
                providedToken.getBytes(StandardCharsets.UTF_8));
    }
}