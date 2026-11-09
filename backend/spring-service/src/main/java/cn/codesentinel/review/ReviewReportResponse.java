package cn.codesentinel.review;

import java.time.LocalDateTime;

/**
 * Public report metadata of one review task (Phase 10.5).
 *
 * <p>The three status fields are deliberately separate:
 * {@code taskStatus} is the review task lifecycle, {@code aiStatus} is
 * the received AI result status (COMPLETED / DEGRADED), and
 * {@code publishStatus} is the GitHub publication status
 * (PENDING / PUBLISHED / PARTIAL / FAILED).
 */
public record ReviewReportResponse(
        long taskId,
        String owner,
        String repo,
        int prNumber,
        String commitSha,
        String taskStatus,
        String aiStatus,
        String publishStatus,
        int findingCount,
        int publishedCommentCount,
        Long summaryCommentId,
        LocalDateTime publishedAt,
        LocalDateTime createdAt,
        LocalDateTime updatedAt) {
}