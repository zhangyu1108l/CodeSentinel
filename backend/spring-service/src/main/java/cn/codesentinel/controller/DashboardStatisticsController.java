package cn.codesentinel.controller;

import cn.codesentinel.review.InvalidReviewHistoryFilterException;
import cn.codesentinel.review.InvalidReviewHistoryPaginationException;
import cn.codesentinel.review.ReviewHistoryDataIntegrityException;
import cn.codesentinel.review.ReviewHistoryError;
import cn.codesentinel.review.ReviewHistoryFilter;
import cn.codesentinel.review.ReviewPageResponse;
import cn.codesentinel.statistics.InvalidStatisticsGranularityException;
import cn.codesentinel.statistics.InvalidStatisticsRangeException;
import cn.codesentinel.statistics.InvalidStatisticsSortException;
import cn.codesentinel.statistics.ReviewStatisticsOverviewResponse;
import cn.codesentinel.statistics.ReviewStatisticsReviewItem;
import cn.codesentinel.statistics.ReviewStatisticsService;
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
 * Browser-facing Dashboard statistics BFF (Phase 11.2.4-B1).
 *
 * <p>Both endpoints only read structured review history: the root table is
 * {@code review_report}, with {@code review_task} used for logical
 * association and filters. The controller never reads
 * {@code review_result_delivery}, never calls GitHub / Python / LLM, and
 * never reads or forwards {@code REVIEW_HISTORY_INTERNAL_TOKEN}.
 *
 * <p>Every path is under {@code /api/dashboard/**}, so the existing
 * {@code DashboardLocalAccessFilter} loopback boundary applies without
 * modification.
 */
@RestController
public class DashboardStatisticsController {

    private static final Logger log =
            LoggerFactory.getLogger(DashboardStatisticsController.class);

    private static final String ERROR_INVALID_PAGINATION =
            "invalid_pagination";
    private static final String ERROR_INVALID_FILTER = "invalid_filter";
    private static final String ERROR_INVALID_GRANULARITY =
            "invalid_granularity";
    private static final String ERROR_INVALID_SORT = "invalid_sort";
    private static final String ERROR_INVALID_RANGE = "invalid_range";
    private static final String ERROR_INTERNAL = "internal_error";

    private final ReviewStatisticsService statisticsService;

    public DashboardStatisticsController(
            ReviewStatisticsService statisticsService) {
        this.statisticsService = statisticsService;
    }

    @GetMapping("/api/dashboard/statistics/overview")
    public ReviewStatisticsOverviewResponse overview(
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
            LocalDateTime createdTo,
            @RequestParam(defaultValue = "DAY") String granularity) {
        ReviewHistoryFilter filter = new ReviewHistoryFilter(owner, repo,
                prNumber, taskStatus, publishStatus, aiStatus,
                createdFrom, createdTo);
        return statisticsService.overview(filter, granularity);
    }

    @GetMapping("/api/dashboard/statistics/reviews")
    public ReviewPageResponse<ReviewStatisticsReviewItem> reviews(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(defaultValue = "createdAt") String sort,
            @RequestParam(defaultValue = "desc") String direction,
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
        return statisticsService.reviews(filter, page, size,
                sort, direction);
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

    @ExceptionHandler(InvalidStatisticsGranularityException.class)
    public ResponseEntity<ReviewHistoryError> handleInvalidGranularity(
            InvalidStatisticsGranularityException error) {
        return ResponseEntity.badRequest()
                .body(new ReviewHistoryError(ERROR_INVALID_GRANULARITY));
    }

    @ExceptionHandler(InvalidStatisticsSortException.class)
    public ResponseEntity<ReviewHistoryError> handleInvalidSort(
            InvalidStatisticsSortException error) {
        return ResponseEntity.badRequest()
                .body(new ReviewHistoryError(ERROR_INVALID_SORT));
    }

    @ExceptionHandler(InvalidStatisticsRangeException.class)
    public ResponseEntity<ReviewHistoryError> handleInvalidRange(
            InvalidStatisticsRangeException error) {
        return ResponseEntity.badRequest()
                .body(new ReviewHistoryError(ERROR_INVALID_RANGE));
    }

    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    public ResponseEntity<ReviewHistoryError> handleTypeMismatch(
            MethodArgumentTypeMismatchException error) {
        String code = "page".equals(error.getName())
                || "size".equals(error.getName())
                ? ERROR_INVALID_PAGINATION
                : "granularity".equals(error.getName())
                ? ERROR_INVALID_GRANULARITY
                : ERROR_INVALID_FILTER;
        return ResponseEntity.badRequest()
                .body(new ReviewHistoryError(code));
    }

    @ExceptionHandler(ReviewHistoryDataIntegrityException.class)
    public ResponseEntity<ReviewHistoryError> handleDataIntegrity(
            ReviewHistoryDataIntegrityException error) {
        log.error("Dashboard statistics history is unreadable: {}",
                error.getMessage());
        return ResponseEntity.internalServerError()
                .body(new ReviewHistoryError(ERROR_INTERNAL));
    }

    /**
     * The response intentionally contains only the stable error code.
     * Logging the exception class (not its message or a stack trace) avoids
     * writing SQL, bind values or credentials to the application log.
     */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ReviewHistoryError> handleUnexpected(
            Exception error) {
        log.error("Dashboard statistics request failed: {}",
                error.getClass().getSimpleName());
        return ResponseEntity.internalServerError()
                .body(new ReviewHistoryError(ERROR_INTERNAL));
    }

    private static void validatePagination(int page, int size) {
        if (page < 1 || size < 1
                || size > ReviewStatisticsService.MAX_PAGE_SIZE) {
            throw new InvalidReviewHistoryPaginationException(
                    "Invalid dashboard statistics pagination");
        }
    }
}
