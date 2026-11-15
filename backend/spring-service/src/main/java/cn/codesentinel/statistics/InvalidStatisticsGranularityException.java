package cn.codesentinel.statistics;

/**
 * Invalid trend granularity of the Dashboard statistics API
 * (Phase 11.2.4-B1). The HTTP response exposes only the stable
 * {@code invalid_granularity} code; the message is for server-side use.
 */
public class InvalidStatisticsGranularityException extends RuntimeException {

    public InvalidStatisticsGranularityException(String message) {
        super(message);
    }
}
