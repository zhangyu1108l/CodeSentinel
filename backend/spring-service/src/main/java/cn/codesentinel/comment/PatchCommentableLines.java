package cn.codesentinel.comment;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Commentable-line oracle for one file's GitHub `patch` field.
 *
 * <p>The patch is the per-file unified diff returned by the GitHub API:
 * only {@code @@} hunk sections, no {@code ---} / {@code +++} header. The
 * parser mirrors the Phase 6 Python semantics (omitted hunk count means
 * 1; an empty line inside a hunk is a context line; the
 * {@code \ No newline at end of file} marker is skipped) but is
 * fail-closed: a truncated, over-long or otherwise inconsistent hunk
 * yields {@link #REASON_PARSE_ERROR} and no commentable lines, instead of
 * a partially trusted mapping.
 *
 * <p>Commentable lines follow the GitHub review comment contract: a
 * {@code RIGHT} comment uses a new-file line number that appears in the
 * diff (added or context lines of a hunk), a {@code LEFT} comment uses an
 * old-file line number (removed or context lines). Lines outside the
 * hunks are never commentable, removed lines have no {@code RIGHT}
 * position, and a missing patch (binary file, pure rename, oversized
 * diff) yields {@link #REASON_NO_PATCH}. Findings carry new-file side
 * line numbers (Phase 6 contract), so {@link #placeRight} is the
 * finding-level entry point.
 */
public final class PatchCommentableLines {

    public static final String SIDE_LEFT = "LEFT";
    public static final String SIDE_RIGHT = "RIGHT";

    public static final String REASON_NO_PATCH = "no_patch";
    public static final String REASON_PARSE_ERROR = "parse_error";
    public static final String REASON_INVALID_RANGE = "invalid_range";
    public static final String REASON_NOT_IN_DIFF = "not_in_diff";

    private static final Pattern HUNK_HEADER = Pattern.compile(
            "^@@\\s+-(\\d+)(?:,(\\d+))?\\s+\\+(\\d+)(?:,(\\d+))?\\s+@@(.*)$");

    private static final String NO_NEWLINE_MARKER = "\\";

    private final List<Hunk> hunks;
    private final String failureReason;

    private PatchCommentableLines(List<Hunk> hunks, String failureReason) {
        this.hunks = hunks;
        this.failureReason = failureReason;
    }

    /**
     * Parse a GitHub per-file patch. Null / blank input is
     * {@link #REASON_NO_PATCH}; a non-empty input that yields no
     * consistent hunk is {@link #REASON_PARSE_ERROR}.
     */
    public static PatchCommentableLines parse(String patch) {
        if (patch == null || patch.isBlank()) {
            return new PatchCommentableLines(List.of(), REASON_NO_PATCH);
        }

        String[] rawLines = patch
                .replace("\r\n", "\n")
                .replace("\r", "\n")
                .split("\n", -1);
        int lineCount = rawLines.length;
        if (lineCount > 0 && rawLines[lineCount - 1].isEmpty()) {
            lineCount--;
        }

        List<Hunk> hunks = new ArrayList<>();
        String failure = null;
        boolean inHunk = false;
        int oldCount = 0;
        int newCount = 0;
        int oldSeen = 0;
        int newSeen = 0;

        for (int index = 0; index < lineCount; index++) {
            String line = rawLines[index];
            Matcher matcher = HUNK_HEADER.matcher(line);
            if (matcher.matches()) {
                if (inHunk && (oldSeen < oldCount || newSeen < newCount)) {
                    failure = REASON_PARSE_ERROR;
                    break;
                }
                oldCount = count(matcher, 2);
                newCount = count(matcher, 4);
                hunks.add(new Hunk(
                        Integer.parseInt(matcher.group(1)), oldCount,
                        Integer.parseInt(matcher.group(3)), newCount));
                oldSeen = 0;
                newSeen = 0;
                inHunk = oldCount > 0 || newCount > 0;
                continue;
            }
            if (!inHunk) {
                // Tolerate full-diff headers and padding outside hunks.
                continue;
            }
            if (line.startsWith(NO_NEWLINE_MARKER)) {
                continue;
            }
            if (line.isEmpty() || line.startsWith(" ")) {
                oldSeen++;
                newSeen++;
            } else if (line.startsWith("+")) {
                newSeen++;
            } else if (line.startsWith("-")) {
                oldSeen++;
            } else {
                failure = REASON_PARSE_ERROR;
                break;
            }
            if (oldSeen > oldCount || newSeen > newCount) {
                failure = REASON_PARSE_ERROR;
                break;
            }
            if (oldSeen == oldCount && newSeen == newCount) {
                inHunk = false;
            }
        }

        if (failure == null && inHunk
                && (oldSeen < oldCount || newSeen < newCount)) {
            failure = REASON_PARSE_ERROR;
        }
        if (failure == null && hunks.isEmpty()) {
            failure = REASON_PARSE_ERROR;
        }
        if (failure != null) {
            return new PatchCommentableLines(List.of(), failure);
        }
        return new PatchCommentableLines(List.copyOf(hunks), null);
    }

    private static int count(Matcher matcher, int group) {
        return matcher.group(group) == null
                ? 1
                : Integer.parseInt(matcher.group(group));
    }

    /**
     * Whether the given line can be targeted by a GitHub review comment
     * on the given side.
     *
     * @param side {@link #SIDE_LEFT} or {@link #SIDE_RIGHT}
     * @param line 1-based line number on that side
     */
    public boolean isCommentable(String side, int line) {
        boolean right = requireSide(side);
        if (failureReason != null || line < 1) {
            return false;
        }
        for (Hunk hunk : hunks) {
            if (right ? hunk.coversNew(line) : hunk.coversOld(line)) {
                return true;
            }
        }
        return false;
    }

    /**
     * Place one finding range on the diff. Findings carry new-file side
     * line numbers (Phase 6 contract), so only RIGHT placements are
     * produced: a single line when the range is a point or when only one
     * endpoint is commentable, and a multi-line placement when both
     * endpoints are commentable inside the same hunk. No line is ever
     * invented: a range that cannot be placed yields a non-commentable
     * result with {@link #REASON_NOT_IN_DIFF}.
     */
    public InlineCommentPlacement placeRight(int startLine, int endLine) {
        if (startLine < 1 || endLine < 1 || startLine > endLine) {
            return InlineCommentPlacement.notCommentable(REASON_INVALID_RANGE);
        }
        if (failureReason != null) {
            return InlineCommentPlacement.notCommentable(failureReason);
        }
        boolean startCommentable = isCommentable(SIDE_RIGHT, startLine);
        boolean endCommentable = isCommentable(SIDE_RIGHT, endLine);
        if (startLine == endLine) {
            return endCommentable
                    ? InlineCommentPlacement.placed(
                            SIDE_RIGHT, endLine, null, null)
                    : InlineCommentPlacement.notCommentable(
                            REASON_NOT_IN_DIFF);
        }
        if (startCommentable && endCommentable
                && sharesRightHunk(startLine, endLine)) {
            return InlineCommentPlacement.placed(
                    SIDE_RIGHT, endLine, startLine, SIDE_RIGHT);
        }
        if (endCommentable) {
            return InlineCommentPlacement.placed(
                    SIDE_RIGHT, endLine, null, null);
        }
        if (startCommentable) {
            return InlineCommentPlacement.placed(
                    SIDE_RIGHT, startLine, null, null);
        }
        return InlineCommentPlacement.notCommentable(REASON_NOT_IN_DIFF);
    }

    private boolean sharesRightHunk(int first, int second) {
        for (Hunk hunk : hunks) {
            if (hunk.coversNew(first) && hunk.coversNew(second)) {
                return true;
            }
        }
        return false;
    }

    private static boolean requireSide(String side) {
        if (SIDE_RIGHT.equals(side)) {
            return true;
        }
        if (SIDE_LEFT.equals(side)) {
            return false;
        }
        throw new IllegalArgumentException(
                "side must be " + SIDE_LEFT + " or " + SIDE_RIGHT + ": "
                        + Objects.toString(side, "null"));
    }

    private record Hunk(int oldStart, int oldCount,
                        int newStart, int newCount) {

        boolean coversOld(int line) {
            return oldCount > 0
                    && line >= oldStart
                    && line <= oldStart + oldCount - 1;
        }

        boolean coversNew(int line) {
            return newCount > 0
                    && line >= newStart
                    && line <= newStart + newCount - 1;
        }
    }
}