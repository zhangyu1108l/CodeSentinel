package cn.codesentinel.review;

/**
 * Invalid optional filter of the Dashboard review history list
 * (Phase 11.2.2-A). The HTTP response exposes only the stable
 * {@code invalid_filter} code; the message is for server-side use.
 */
public class InvalidReviewHistoryFilterException extends RuntimeException {

    public InvalidReviewHistoryFilterException(String message) {
        super(message);
    }
}
