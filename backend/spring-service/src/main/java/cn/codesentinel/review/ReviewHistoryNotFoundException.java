package cn.codesentinel.review;

/**
 * No structured review history exists for a task yet (Phase 10.5).
 * The message is used for server-side logs only; the HTTP response never
 * exposes it.
 */
public class ReviewHistoryNotFoundException extends RuntimeException {

    public ReviewHistoryNotFoundException(long taskId) {
        super("Review history not found for task id=" + taskId);
    }
}