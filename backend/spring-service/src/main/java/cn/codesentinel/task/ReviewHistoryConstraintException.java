package cn.codesentinel.task;

/**
 * A deterministic refusal to write structured review history
 * (Phase 10.3).
 *
 * <p>Raised for inputs that must not be stored: a field over its
 * approved limit, an unreadable findings snapshot, or a stored finding
 * count that no longer matches the snapshot. The message contains only
 * a safe error code and, where applicable, the field name, its limit
 * and the actual length - never finding content, full JSON, tokens or
 * SQL parameters.
 */
public class ReviewHistoryConstraintException extends RuntimeException {

    public ReviewHistoryConstraintException(String message) {
        super(message);
    }
}