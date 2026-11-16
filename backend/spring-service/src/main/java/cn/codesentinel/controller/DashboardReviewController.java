package cn.codesentinel.controller;

import cn.codesentinel.review.InvalidReviewHistoryFilterException;
import cn.codesentinel.review.InvalidReviewHistoryPaginationException;
import cn.codesentinel.review.ReviewHistoryDataIntegrityException;
import cn.codesentinel.review.ReviewHistoryError;
import cn.codesentinel.review.ReviewHistoryFilter;
import cn.codesentinel.review.ReviewHistoryListService;
import cn.codesentinel.review.ReviewHistoryQueryService;
import cn.codesentinel.review.ReviewPageResponse;
import cn.codesentinel.review.ReviewReportResponse;
import cn.codesentinel.task.PublishStatus;
import cn.codesentinel.task.TaskStatus;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

import java.time.LocalDateTime;

/**
 * Browser-facing Dashboard BFF for the review history list
 * (Phase 11.2.2-A).
 *
 * <p>This controller deliberately does not read
 * {@code review.history.internal-token} and does not accept or forward
 * {@code X-Internal-Token}. The Phase 10 service-to-service endpoints keep
 * their existing authentication contract.
 *
 * <p>The sibling {@code DashboardLocalAccessFilter} rejects every request
 * whose TCP peer is not a loopback address. Forwarded headers are not
 * trusted for this boundary.
 */
@RestController
public class DashboardReviewController {

    private static final Logger log =
            LoggerFactory.getLogger(DashboardReviewController.class);

    private static final String ERROR_INVALID_PAGINATION =
            "invalid_pagination";
    private static final String ERROR_INVALID_FILTER = "invalid_filter";
    private static final String ERROR_INTERNAL = "internal_error";

    private final ReviewHistoryListService listService;

    public DashboardReviewController(ReviewHistoryListService listService) {
        this.listService = listService;
    }

    @GetMapping("/api/dashboard/reviews")
    public ReviewPageResponse<ReviewReportResponse> list(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) String owner,
            @RequestParam(required = false) String repo,
            @RequestParam(required = false) Integer prNumber,
            @RequestParam(required = false) TaskStatus taskStatus,
            @RequestParam(required = false) PublishStatus publishStatus,
            @RequestParam(required = false) String aiStatus,
            @RequestParam(required = false)
            @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME)
            LocalDateTime createdFrom,
            @RequestParam(required = false)
            @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME)
            LocalDateTime createdTo) {
        validatePagination(page, size);
        ReviewHistoryFilter filter = new ReviewHistoryFilter(owner, repo,
                prNumber, taskStatus, publishStatus, aiStatus,
                createdFrom, createdTo);
        return listService.search(filter, page, size);
    }

    @ExceptionHandler(InvalidReviewHistoryPaginationException.class)
    public ResponseEntity<ReviewHistoryError> handleInvalidPagination(
            InvalidReviewHistoryPaginationException error) {
        return ResponseEntity.badRequest()
                .body(new ReviewHistoryError(ERROR_INVALID_PAGINATION));
    }

    @ExceptionHandler(InvalidReviewHistoryFilterException.class)
    public ResponseEntity<ReviewHistoryError> handleInvalidFilter(
            InvalidReviewHistoryFilterException error) {
        return ResponseEntity.badRequest()
                .body(new ReviewHistoryError(ERROR_INVALID_FILTER));
    }

    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    public ResponseEntity<ReviewHistoryError> handleTypeMismatch(
            MethodArgumentTypeMismatchException error) {
        String code = "page".equals(error.getName())
                || "size".equals(error.getName())
                ? ERROR_INVALID_PAGINATION
                : ERROR_INVALID_FILTER;
        return ResponseEntity.badRequest()
                .body(new ReviewHistoryError(code));
    }

    @ExceptionHandler(ReviewHistoryDataIntegrityException.class)
    public ResponseEntity<ReviewHistoryError> handleDataIntegrity(
            ReviewHistoryDataIntegrityException error) {
        log.error("Dashboard review history is unreadable: {}",
                error.getMessage());
        return ResponseEntity.internalServerError()
                .body(new ReviewHistoryError(ERROR_INTERNAL));
    }

    private static void validatePagination(int page, int size) {
        if (page < 1 || size < 1
                || size > ReviewHistoryQueryService.MAX_PAGE_SIZE) {
            throw new InvalidReviewHistoryPaginationException(
                    "Invalid dashboard review history pagination");
        }
    }
}
