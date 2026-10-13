package cn.codesentinel.task;

import java.time.LocalDateTime;

/**
 * Terminal result of one publication attempt (Phase 9.5.3C).
 *
 * <p>{@code status} is {@code PUBLISHED} / {@code PARTIAL} /
 * {@code FAILED}; {@code outcomeJson} is the stable per-item outcome
 * snapshot stored in {@code publish_outcome_json}; {@code publishedAt}
 * is set only when at least one external item was confirmed published
 * and stays null otherwise (no claim is made about unknown side
 * effects).
 */
public record ReviewResultPublishResult(
        PublishStatus status,
        String outcomeJson,
        LocalDateTime publishedAt) {
}