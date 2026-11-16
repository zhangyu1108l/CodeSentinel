package cn.codesentinel.review;

import cn.codesentinel.task.PublishStatus;
import cn.codesentinel.task.TaskStatus;

import java.time.LocalDateTime;
import java.util.Locale;
import java.util.Set;

/**
 * Optional server-side filters of the Dashboard review history list
 * (Phase 11.2.2-A).
 *
 * <p>All filters are exact matches. String filters are trimmed and blank
 * values are treated as absent. {@code createdFrom} and {@code createdTo}
 * are inclusive bounds on {@code review_report.created_at}.
 */
public record ReviewHistoryFilter(
        String owner,
        String repo,
        Integer prNumber,
        TaskStatus taskStatus,
        PublishStatus publishStatus,
        String aiStatus,
        LocalDateTime createdFrom,
        LocalDateTime createdTo) {

    private static final int MAX_OWNER_LENGTH = 255;
    private static final int MAX_REPO_LENGTH = 255;
    private static final Set<String> AI_STATUSES =
            Set.of("COMPLETED", "DEGRADED");

    public ReviewHistoryFilter {
        owner = normalize(owner, "owner", MAX_OWNER_LENGTH);
        repo = normalize(repo, "repo", MAX_REPO_LENGTH);
        if (prNumber != null && prNumber <= 0) {
            throw new InvalidReviewHistoryFilterException(
                    "prNumber must be positive");
        }
        if (aiStatus != null) {
            String normalized = aiStatus.trim();
            if (normalized.isEmpty()) {
                aiStatus = null;
            } else {
                normalized = normalized.toUpperCase(Locale.ROOT);
                if (!AI_STATUSES.contains(normalized)) {
                    throw new InvalidReviewHistoryFilterException(
                            "aiStatus must be COMPLETED or DEGRADED");
                }
                aiStatus = normalized;
            }
        }
        if (createdFrom != null && createdTo != null
                && createdFrom.isAfter(createdTo)) {
            throw new InvalidReviewHistoryFilterException(
                    "createdFrom must not be after createdTo");
        }
    }

    private static String normalize(String value, String field, int maxLength) {
        if (value == null) {
            return null;
        }
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            return null;
        }
        if (normalized.length() > maxLength) {
            throw new InvalidReviewHistoryFilterException(
                    field + " must not exceed " + maxLength + " characters");
        }
        return normalized;
    }
}
