package cn.codesentinel.statistics;

import java.util.List;

/**
 * Trend series of one statistics snapshot (Phase 11.2.4-B1).
 *
 * <p>When the effective range contains no reports, {@code hasData} is
 * {@code false} and {@code points} is empty. When it contains reports,
 * every bucket in the effective range is returned, including zero-count
 * buckets.
 */
public record ReviewStatisticsTrend(
        StatisticsGranularity granularity,
        boolean hasData,
        List<ReviewStatisticsTrendPoint> points) {
}
