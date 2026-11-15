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
import cn.codesentinel.task.TaskNotFoundException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

import java.util.regex.Pattern;

/**
 * Browser-facing Dashboard BFF for one review history detail
 * (Phase 11.2.3-B).
 *
 * <p>The three read-only endpoints reuse
 * {@link ReviewHistoryQueryService} directly. They deliberately do not
 * read {@code review.history.internal-token} and do not accept or
 * forward {@code X-Internal-Token}: the internal credential stays on the
 * Phase 10 service-to-service API.
 *
 * <p>The sibling {@code DashboardLocalAccessFilter} rejects every
 * {@code /api/dashboard/**} request whose TCP peer is not a loopback
 * address. Forwarded headers are not trusted for this boundary.
 *
 * <p>All error bodies are fixed safe codes. Exception messages, SQL,
 * stack traces, tokens and internal paths never reach the response.
 */
@RestController
public class DashboardReviewDetailController {

    private static final Logger log =
            LoggerFactory.getLogger(DashboardReviewDetailController.class);

    private static final String ERROR_INVALID_TASK_ID = "invalid_task_id";
    private static final String ERROR_INVALID_PAGINATION =
            "invalid_pagination";
    private static final String ERROR_NOT_FOUND = "review_not_found";
    private static final String ERROR_INCOMPLETE =
            "review_history_incomplete";
    private static final String ERROR_INTERNAL = "internal_error";

    private static final int DEFAULT_PAGE = 1;

    private static final Pattern TASK_ID_PATTERN = Pattern.compile("\\d+");

    private final ReviewHistoryQueryService queryService;

    public DashboardReviewDetailController(
            ReviewHistoryQueryService queryService) {
        this.queryService = queryService;
    }

    @GetMapping("/api/dashboard/reviews/{taskId}")
    public ReviewReportResponse getReport(@PathVariable String taskId) {
        return queryService.getReport(parseTaskId(taskId));
    }

    @GetMapping("/api/dashboard/reviews/{taskId}/findings")
    public ReviewPageResponse<ReviewFindingResponse> getFindings(
            @PathVariable String taskId,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {
        long id = parseTaskId(taskId);
        validatePagination(page, size);
        return queryService.getFindings(id, page, size);
    }

    @GetMapping("/api/dashboard/reviews/{taskId}/comments")
    public ReviewPageResponse<ReviewCommentResponse> getComments(
            @PathVariable String taskId,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {
        long id = parseTaskId(taskId);
        validatePagination(page, size);
        return queryService.getComments(id, page, size);
    }

    @ExceptionHandler(InvalidDashboardTaskIdException.class)
    public ResponseEntity<ReviewHistoryError> handleInvalidTaskId(
            InvalidDashboardTaskIdException error) {
        return ResponseEntity.badRequest()
                .body(new ReviewHistoryError(ERROR_INVALID_TASK_ID));
    }

    @ExceptionHandler(InvalidDashboardPaginationException.class)
    public ResponseEntity<ReviewHistoryError> handleInvalidPagination(
            InvalidDashboardPaginationException error) {
        return ResponseEntity.badRequest()
                .body(new ReviewHistoryError(ERROR_INVALID_PAGINATION));
    }

    /**
     * Spring binds {@code page}/{@code size} before the handler runs, so
     * non-numeric values and integer overflow never reach the explicit
     * validation above. Both cases still map to the agreed pagination
     * error instead of a framework 400 with an internal message.
     */
    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    public ResponseEntity<ReviewHistoryError> handleTypeMismatch(
            MethodArgumentTypeMismatchException error) {
        if ("page".equals(error.getName()) || "size".equals(error.getName())) {
            return ResponseEntity.badRequest()
                    .body(new ReviewHistoryError(ERROR_INVALID_PAGINATION));
        }
        log.warn("Unexpected dashboard review detail argument type mismatch");
        return ResponseEntity.internalServerError()
                .body(new ReviewHistoryError(ERROR_INTERNAL));
    }

    @ExceptionHandler({TaskNotFoundException.class,
            ReviewHistoryNotFoundException.class})
    public ResponseEntity<ReviewHistoryError> handleNotFound(
            RuntimeException error) {
        // Both exceptions carry only a task id in their message.
        log.warn("Dashboard review detail requested for a missing resource: {}",
                error.getMessage());
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(new ReviewHistoryError(ERROR_NOT_FOUND));
    }

    @ExceptionHandler(ReviewHistoryIncompleteException.class)
    public ResponseEntity<ReviewHistoryError> handleIncomplete(
            ReviewHistoryIncompleteException error) {
        log.warn("Dashboard review history is incomplete: {}",
                error.getMessage());
        return ResponseEntity.status(HttpStatus.CONFLICT)
                .body(new ReviewHistoryError(ERROR_INCOMPLETE));
    }

    @ExceptionHandler(ReviewHistoryDataIntegrityException.class)
    public ResponseEntity<ReviewHistoryError> handleDataIntegrity(
            ReviewHistoryDataIntegrityException error) {
        // The message contains only ids and a safe reason.
        log.error("Dashboard review history is unreadable: {}",
                error.getMessage());
        return ResponseEntity.internalServerError()
                .body(new ReviewHistoryError(ERROR_INTERNAL));
    }

    /**
     * Last-resort handler. Only the exception type is logged: a message
     * could contain a SQL fragment, file path or stored content.
     */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ReviewHistoryError> handleUnexpected(
            Exception error) {
        log.error("Unexpected dashboard review detail error: type={}",
                error.getClass().getSimpleName());
        return ResponseEntity.internalServerError()
                .body(new ReviewHistoryError(ERROR_INTERNAL));
    }

    private static long parseTaskId(String value) {
        if (value == null || !TASK_ID_PATTERN.matcher(value).matches()) {
            throw new InvalidDashboardTaskIdException();
        }
        try {
            long taskId = Long.parseLong(value);
            if (taskId <= 0) {
                throw new InvalidDashboardTaskIdException();
            }
            return taskId;
        } catch (NumberFormatException overflow) {
            throw new InvalidDashboardTaskIdException();
        }
    }

    private static void validatePagination(int page, int size) {
        if (page < DEFAULT_PAGE || size < 1
                || size > ReviewHistoryQueryService.MAX_PAGE_SIZE) {
            throw new InvalidDashboardPaginationException();
        }
    }

    private static final class InvalidDashboardTaskIdException
            extends RuntimeException {
        private InvalidDashboardTaskIdException() {
            super("Invalid dashboard review task id");
        }
    }

    private static final class InvalidDashboardPaginationException
            extends RuntimeException {
        private InvalidDashboardPaginationException() {
            super("Invalid dashboard review detail pagination");
        }
    }
}
