package cn.codesentinel.statistics;

import java.util.List;

/**
 * Aggregate counters of one statistics snapshot (Phase 11.2.4-B1).
 *
 * <p>Report-level counters include every report in the effective range.
 * Finding counters only include reports whose actual {@code review_finding}
 * row count equals {@code finding_count}; comment counters only include
 * reports whose actual {@code review_comment} row count equals
 * {@code published_comment_count}. Ratios and averages with a zero
 * denominator are {@code null}, never {@code NaN} or infinity.
 */
public record ReviewStatisticsSummary(
        long reviewCount,
        long findingStatsReviewCount,
        long findingCount,
        Double averageFindingsPerReview,
        Double medianFindingsPerReview,
        Long maxFindingsInReview,
        long reviewsWithFindings,
        Double reviewsWithFindingsRatio,
        long highSeverityFindingCount,
        Double highSeverityRatio,
        long commentStatsReviewCount,
        long publishedInlineCommentCount,
        long reviewsWithInlineComments,
        Double reviewsWithInlineCommentsRatio,
        long summaryCommentIdPresentCount,
        List<ReviewStatisticsCount> categoryCounts,
        List<ReviewStatisticsCount> severityCounts,
        List<ReviewStatisticsCount> publishStatusCounts,
        List<ReviewStatisticsCount> aiStatusCounts) {
}
