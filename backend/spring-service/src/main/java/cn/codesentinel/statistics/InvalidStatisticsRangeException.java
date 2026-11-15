package cn.codesentinel.statistics;

/**
 * Statistics range longer than the supported maximum
 * (Phase 11.2.4-B1). The HTTP response exposes only the stable
 * {@code invalid_range} code; the message is for server-side use.
 */
public class InvalidStatisticsRangeException extends RuntimeException {

    public InvalidStatisticsRangeException(String message) {
        super(message);
    }
}
