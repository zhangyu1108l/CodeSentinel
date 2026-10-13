package cn.codesentinel.comment;

/**
 * Result of placing one finding range on the pull request diff.
 *
 * <p>When {@code commentable} is true, {@code side} is {@code LEFT} or
 * {@code RIGHT} (the GitHub review comment sides), {@code line} is the
 * anchor line on that side, and {@code startLine} / {@code startSide}
 * are set only for a multi-line placement. When {@code commentable} is
 * false all location fields are null and {@code reason} is a short,
 * log-safe code ({@link PatchCommentableLines#REASON_NO_PATCH},
 * {@link PatchCommentableLines#REASON_PARSE_ERROR},
 * {@link PatchCommentableLines#REASON_INVALID_RANGE},
 * {@link PatchCommentableLines#REASON_NOT_IN_DIFF}).
 */
public record InlineCommentPlacement(
        boolean commentable,
        String side,
        Integer line,
        Integer startLine,
        String startSide,
        String reason) {

    public static InlineCommentPlacement placed(String side, int line,
                                                Integer startLine,
                                                String startSide) {
        return new InlineCommentPlacement(
                true, side, line, startLine, startSide, null);
    }

    public static InlineCommentPlacement notCommentable(String reason) {
        return new InlineCommentPlacement(
                false, null, null, null, null, reason);
    }
}