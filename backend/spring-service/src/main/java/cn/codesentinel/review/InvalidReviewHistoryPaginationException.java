package cn.codesentinel.review;

/**
 * Invalid page or size of the Dashboard review history list
 * (Phase 11.2.2-A). The HTTP response exposes only the stable
 * {@code invalid_pagination} code; the message is for server-side use.
 */
public class InvalidReviewHistoryPaginationException extends RuntimeException {

    public InvalidReviewHistoryPaginationException(String message) {
        super(message);
    }
}
