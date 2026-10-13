package cn.codesentinel.github;

import cn.codesentinel.comment.InlineCommentFinding;

/**
 * One finding's publish outcome of {@link ReviewCommentPublisher}.
 *
 * <p>Status semantics:
 * <ul>
 *   <li>{@code PUBLISHED}: the comment was created;
 *       {@code commentId} carries the created id when the response
 *       provided one;</li>
 *   <li>{@code SKIPPED}: no request was sent; {@code reason} keeps the
 *       full placement reason code ({@code no_patch}, {@code parse_error},
 *       {@code invalid_range}, {@code not_in_diff}) or
 *       {@link ReviewCommentPublisher#SKIP_REASON_PATH_NOT_IN_PR};</li>
 *   <li>{@code FAILED}: the request was attempted, or its content could
 *       not be built; {@code reason} keeps a safe classification such as
 *       {@code http_422} or {@code transport_error}.</li>
 * </ul>
 */
public record ReviewCommentOutcome(
        Status status,
        String filePath,
        int startLine,
        int endLine,
        String reason,
        Long commentId) {

    public enum Status {
        PUBLISHED,
        SKIPPED,
        FAILED
    }

    public static ReviewCommentOutcome published(InlineCommentFinding finding,
                                                 Long commentId) {
        return new ReviewCommentOutcome(Status.PUBLISHED, finding.filePath(),
                finding.startLine(), finding.endLine(), null, commentId);
    }

    public static ReviewCommentOutcome skipped(InlineCommentFinding finding,
                                               String reason) {
        return new ReviewCommentOutcome(Status.SKIPPED, finding.filePath(),
                finding.startLine(), finding.endLine(), reason, null);
    }

    public static ReviewCommentOutcome failed(InlineCommentFinding finding,
                                              String reason) {
        return new ReviewCommentOutcome(Status.FAILED, finding.filePath(),
                finding.startLine(), finding.endLine(), reason, null);
    }
}