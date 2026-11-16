package cn.codesentinel.statistics;

import java.time.LocalDateTime;

/**
 * One row of {@code GET /api/dashboard/statistics/reviews}
 * (Phase 11.2.4-B1).
 *
 * <p>{@code declaredFindingCount} / {@code actualFindingCount} and
 * {@code declaredCommentCount} / {@code actualCommentCount} are returned
 * together. The actual distribution counters always describe existing
 * rows; when a consistency flag is {@code false}, those rows are shown
 * for comparison but are excluded from the overview aggregates.
 */
public record ReviewStatisticsReviewItem(
        long taskId,
        String owner,
        String repo,
        int prNumber,
        String commitSha,
        LocalDateTime createdAt,
        String taskStatus,
        String aiStatus,
        String publishStatus,
        int declaredFindingCount,
        long actualFindingCount,
        boolean findingsConsistent,
        int declaredCommentCount,
        long actualCommentCount,
        boolean commentsConsistent,
        long criticalCount,
        long highCount,
        long highSeverityFindingCount,
        long mediumCount,
        long lowCount,
        long infoCount,
        long unknownSeverityCount,
        long bugCount,
        long securityCount,
        long performanceCount,
        long qualityCount,
        long unknownCategoryCount) {
}
