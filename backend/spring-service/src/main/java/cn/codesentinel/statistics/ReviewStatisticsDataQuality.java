package cn.codesentinel.statistics;

/**
 * Data-quality disclosure of one statistics snapshot (Phase 11.2.4-B1).
 *
 * <p>Inconsistent reports remain in report-level metrics but are excluded
 * from Finding or comment aggregates. These counters make the exclusion
 * explicit instead of silently under-counting.
 */
public record ReviewStatisticsDataQuality(
        long totalReportCount,
        long findingsConsistentReportCount,
        long commentsConsistentReportCount,
        long reportsExcludedFromFindingStats,
        long reportsExcludedFromCommentStats,
        long unknownCategoryFindingCount,
        long unknownSeverityFindingCount,
        long unknownAiStatusReportCount,
        long unknownPublishStatusReportCount) {
}
