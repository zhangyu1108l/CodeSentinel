package cn.codesentinel.review;

/**
 * A stored history field cannot be represented safely, for example an
 * unreadable {@code references_json} value (Phase 10.5). The message
 * contains only identifiers and a safe reason; it never contains the
 * raw JSON or finding content.
 */
public class ReviewHistoryDataIntegrityException extends RuntimeException {

    public ReviewHistoryDataIntegrityException(String message) {
        super(message);
    }
}