package cn.codesentinel.review;

/**
 * The stored report counts and the actual child rows do not match
 * (Phase 10.5). This is a transient or corrupt-history condition; the
 * API answers 409 without returning partial data.
 */
public class ReviewHistoryIncompleteException extends RuntimeException {

    public ReviewHistoryIncompleteException(String message) {
        super(message);
    }
}