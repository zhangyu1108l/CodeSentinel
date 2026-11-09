package cn.codesentinel.controller;

import cn.codesentinel.review.ReviewCommentResponse;
import cn.codesentinel.review.ReviewFindingResponse;
import cn.codesentinel.review.ReviewHistoryDataIntegrityException;
import cn.codesentinel.review.ReviewHistoryError;
import cn.codesentinel.review.ReviewHistoryIncompleteException;
import cn.codesentinel.review.ReviewHistoryNotFoundException;
import cn.codesentinel.review.ReviewHistoryQueryService;
import cn.codesentinel.review.ReviewPageResponse;
import cn.codesentinel.review.ReviewReportResponse;
import cn.codesentinel.security.InternalTokenMatcher;
import cn.codesentinel.task.TaskNotFoundException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * Read-only structured review history API (Phase 10.5).
 *
 * <p>All endpoints require the independent service-level credential
 * {@code review.history.internal-token} in {@code X-Internal-Token}.
 * Authentication happens before any service/database call; a blank
 * configuration rejects every request. This is a shared service
 * credential, not user-level authorization - the API must not be
 * exposed to a browser frontend.
 *
 * <p>Unknown task and unknown report deliberately share the same empty
 * 404 response so resource existence is not disclosed. Incomplete
 * history answers 409 with a safe error code; unreadable
 * {@code references_json} answers 500 with an empty body.
 */
@RestController
public class ReviewHistoryController {

    public static final String INTERNAL_TOKEN_HEADER = "X-Internal-Token";

    private static final int DEFAULT_PAGE = 1;
    private static final int MAX_SIZE = ReviewHistoryQueryService.MAX_PAGE_SIZE;
    private static final String ERROR_INVALID_PAGINATION = "invalid_pagination";
    private static final String ERROR_INCOMPLETE = "review_history_incomplete";

    private static final Logger log =
            LoggerFactory.getLogger(ReviewHistoryController.class);

    private final ReviewHistoryQueryService queryService;
    private final String internalToken;

    public ReviewHistoryController(ReviewHistoryQueryService queryService,
                                   @Value("${review.history.internal-token:}")
                                   String internalToken) {
        this.queryService = queryService;
        this.internalToken = internalToken;
    }

    @GetMapping("/api/reviews/{taskId}")
    public ResponseEntity<?> getReport(
            @PathVariable Long taskId,
            @RequestHeader(value = INTERNAL_TOKEN_HEADER, required = false)
            String token) {
        if (!isAuthorized(token)) {
            return unauthorized();
        }
        return ResponseEntity.ok(queryService.getReport(taskId));
    }

    @GetMapping("/api/reviews/{taskId}/findings")
    public ResponseEntity<?> getFindings(
            @PathVariable Long taskId,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestHeader(value = INTERNAL_TOKEN_HEADER, required = false)
            String token) {
        if (!isAuthorized(token)) {
            return unauthorized();
        }
        if (!isValidPagination(page, size)) {
            return ResponseEntity.badRequest()
                    .body(new ReviewHistoryError(ERROR_INVALID_PAGINATION));
        }
        ReviewPageResponse<ReviewFindingResponse> response =
                queryService.getFindings(taskId, page, size);
        return ResponseEntity.ok(response);
    }

    @GetMapping("/api/reviews/{taskId}/comments")
    public ResponseEntity<?> getComments(
            @PathVariable Long taskId,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestHeader(value = INTERNAL_TOKEN_HEADER, required = false)
            String token) {
        if (!isAuthorized(token)) {
            return unauthorized();
        }
        if (!isValidPagination(page, size)) {
            return ResponseEntity.badRequest()
                    .body(new ReviewHistoryError(ERROR_INVALID_PAGINATION));
        }
        ReviewPageResponse<ReviewCommentResponse> response =
                queryService.getComments(taskId, page, size);
        return ResponseEntity.ok(response);
    }

    @ExceptionHandler({TaskNotFoundException.class,
            ReviewHistoryNotFoundException.class})
    public ResponseEntity<Void> handleNotFound(RuntimeException error) {
        log.warn("Review history requested for a missing resource: {}",
                error.getMessage());
        return ResponseEntity.notFound().build();
    }

    @ExceptionHandler(ReviewHistoryIncompleteException.class)
    public ResponseEntity<ReviewHistoryError> handleIncomplete(
            ReviewHistoryIncompleteException error) {
        log.warn("Review history is incomplete: {}", error.getMessage());
        return ResponseEntity.status(HttpStatus.CONFLICT)
                .body(new ReviewHistoryError(ERROR_INCOMPLETE));
    }

    @ExceptionHandler(ReviewHistoryDataIntegrityException.class)
    public ResponseEntity<Void> handleUnreadableHistory(
            ReviewHistoryDataIntegrityException error) {
        // The exception message contains only ids and a safe reason.
        log.error("Review history data is unreadable: {}", error.getMessage());
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
    }

    private boolean isAuthorized(String providedToken) {
        if (internalToken == null || internalToken.isBlank()) {
            log.warn("Review history internal token is not configured, "
                    + "rejecting all requests");
            return false;
        }
        boolean matched = InternalTokenMatcher.matches(internalToken,
                providedToken);
        if (!matched) {
            log.warn("Rejected review history request: invalid or missing "
                    + "internal token");
        }
        return matched;
    }

    private static boolean isValidPagination(int page, int size) {
        return page >= DEFAULT_PAGE && size >= 1 && size <= MAX_SIZE;
    }

    private static ResponseEntity<Void> unauthorized() {
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
    }
}