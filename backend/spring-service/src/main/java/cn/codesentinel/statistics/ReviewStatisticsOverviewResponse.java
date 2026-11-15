package cn.codesentinel.statistics;

import java.time.LocalDateTime;

/**
 * Response of {@code GET /api/dashboard/statistics/overview}
 * (Phase 11.2.4-B1). Summary, trend and data quality are read from one
 * repeatable-read transaction, so their totals cannot disagree.
 */
public record ReviewStatisticsOverviewResponse(
        ReviewStatisticsRange range,
        LocalDateTime generatedAt,
        ReviewStatisticsSummary summary,
        ReviewStatisticsTrend trend,
        ReviewStatisticsDataQuality dataQuality) {
}
