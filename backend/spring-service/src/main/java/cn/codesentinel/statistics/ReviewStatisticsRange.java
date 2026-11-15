package cn.codesentinel.statistics;

import java.time.LocalDateTime;

/**
 * Effective, inclusive wall-clock range of a statistics response
 * (Phase 11.2.4-B1). The bounds are application-local {@link LocalDateTime}
 * values, matching the storage semantics of {@code review_report.created_at}.
 */
public record ReviewStatisticsRange(
        LocalDateTime createdFrom,
        LocalDateTime createdTo,
        String zoneId,
        StatisticsGranularity granularity) {
}
