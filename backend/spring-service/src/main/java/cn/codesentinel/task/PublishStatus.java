package cn.codesentinel.task;

/**
 * Publication state of one received review result
 * (review_result_delivery.publish_status).
 *
 * <p>Phase 9.5.3B1 only ever writes {@link #PENDING}; the remaining
 * values exist for the later publish stage and are never set by the
 * reception endpoint.
 */
public enum PublishStatus {
    PENDING,
    PUBLISHED,
    PARTIAL,
    FAILED
}