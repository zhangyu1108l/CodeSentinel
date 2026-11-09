package cn.codesentinel.controller;

import cn.codesentinel.security.InternalTokenMatcher;
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

/**
 * Durable reception of one AI review result and synchronous publication
 * of the first receipt (Phase 9.5.3B1, Phase 9.5.3C).
 *
 * <p>{@code POST /api/tasks/{taskId}/result} validates the transport
 * payload, binds it to the review task, persists the result snapshot
 * with publish_status=PENDING, and then performs one synchronous
 * publication attempt through
 * {@link cn.codesentinel.task.ReviewResultPublishService} for a first
 * receipt. The publication outcome is stored on the delivery row and
 * mirrored, best effort, into the structured history
 * (review_report / review_finding / review_comment). An identical
 * re-delivery answers 200 with {@code duplicate=true}, returns the
 * stored publish status and never publishes again; it may best-effort
 * repair missing history rows. A conflicting payload answers 409.
 *
 * <p>Structured-history writes are best effort: a history failure is
 * logged and never changes the HTTP response, so 202/200 does not
 * guarantee that history rows exist. A later identical re-delivery is
 * the only automatic repair path; there is no scheduled backfill or
 * independent retry task.
 *
 * <p>HTTP status codes follow the current implementation: 202 for a
 * first receipt, 200 for an identical duplicate, 409 for a conflicting
 * payload or task/commit mismatch, 422 for an invalid payload, 401 for
 * a missing/invalid internal token, 404 for a missing review task, and
 * 400 for malformed JSON rejected by the message converter before this
 * handler runs. A 202 means the result was accepted and the synchronous
 * publication attempt completed; it does not guarantee that GitHub
 * publication succeeded. The payload status COMPLETED is an AI status
 * and must not be read as "comments published"; check the returned
 * publish status instead.
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
        return InternalTokenMatcher.matches(internalToken, providedToken);
    }
}