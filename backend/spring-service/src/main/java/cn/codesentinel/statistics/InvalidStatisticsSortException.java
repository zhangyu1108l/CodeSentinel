package cn.codesentinel.statistics;

/**
 * Invalid sort field or direction of the Dashboard statistics reviews
 * API (Phase 11.2.4-B1). The HTTP response exposes only the stable
 * {@code invalid_sort} code; the message is for server-side use.
 */
public class InvalidStatisticsSortException extends RuntimeException {

    public InvalidStatisticsSortException(String message) {
        super(message);
    }
}
