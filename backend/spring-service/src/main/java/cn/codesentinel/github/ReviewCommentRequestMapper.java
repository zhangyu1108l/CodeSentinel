package cn.codesentinel.github;

import cn.codesentinel.comment.InlineCommentPlacement;
import cn.codesentinel.comment.PatchCommentableLines;

import java.util.Objects;
import java.util.Optional;

/**
 * Maps one finding's diff placement onto the GitHub review comment
 * request (Phase 9.5.2). Pure and deterministic: no I/O, no client call,
 * no production wiring.
 *
 * <p>A placement that cannot be posted on the diff ({@code no_patch},
 * {@code parse_error}, {@code invalid_range} or {@code not_in_diff})
 * yields an empty result: no request is fabricated, and the caller keeps
 * the placement for the degraded path because the reason is already
 * carried by {@link InlineCommentPlacement#reason()}.
 *
 * <p>A commentable placement is mapped as a whole: a single-line
 * placement maps {@code side} / {@code line}; a multi-line placement
 * maps {@code line}, {@code side}, {@code startLine} and
 * {@code startSide} together. A commentable placement with broken
 * invariants (missing or invalid side / line, a half multi-line state,
 * or {@code startLine >= line}) raises
 * {@link IllegalArgumentException}: a half multi-line request is never
 * built and no value is ever rewritten.
 *
 * <p>{@code body}, {@code commitId} and {@code path} are passed through
 * unchanged; validating them stays with the caller and the thin
 * {@link ReviewCommentRequest} contract, following the existing client
 * style.
 */
public final class ReviewCommentRequestMapper {

    private ReviewCommentRequestMapper() {
    }

    public static Optional<ReviewCommentRequest> map(
            String body, String commitId, String path,
            InlineCommentPlacement placement) {
        Objects.requireNonNull(placement, "placement");
        if (!placement.commentable()) {
            return Optional.empty();
        }

        String side = placement.side();
        if (!PatchCommentableLines.SIDE_LEFT.equals(side)
                && !PatchCommentableLines.SIDE_RIGHT.equals(side)) {
            throw new IllegalArgumentException(
                    "commentable placement requires side LEFT or RIGHT: "
                            + side);
        }

        Integer line = placement.line();
        if (line == null || line < 1) {
            throw new IllegalArgumentException(
                    "commentable placement requires a positive line: " + line);
        }

        Integer startLine = placement.startLine();
        String startSide = placement.startSide();
        if ((startLine == null) != (startSide == null)) {
            throw new IllegalArgumentException(
                    "startLine and startSide must be provided together");
        }
        if (startLine != null) {
            if (!PatchCommentableLines.SIDE_LEFT.equals(startSide)
                    && !PatchCommentableLines.SIDE_RIGHT.equals(startSide)) {
                throw new IllegalArgumentException(
                        "startSide must be LEFT or RIGHT: " + startSide);
            }
            if (startLine < 1 || startLine >= line) {
                throw new IllegalArgumentException(
                        "startLine must be a positive line smaller than line"
                                + " (startLine=" + startLine
                                + ", line=" + line + ")");
            }
        }

        return Optional.of(new ReviewCommentRequest(
                body, commitId, path, line, side, startLine, startSide));
    }
}