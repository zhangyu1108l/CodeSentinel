package cn.codesentinel.github;

import cn.codesentinel.comment.InlineCommentPlacement;
import cn.codesentinel.comment.PatchCommentableLines;
import org.junit.jupiter.api.Test;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;

class ReviewCommentRequestMapperTest {

    @Test
    void shouldMapSingleLinePlacement() {
        InlineCommentPlacement placement =
                InlineCommentPlacement.placed("RIGHT", 52, null, null);

        Optional<ReviewCommentRequest> mapped = ReviewCommentRequestMapper.map(
                "body", "abc123def456", "src/UserRepository.java", placement);

        assertTrue(mapped.isPresent());
        ReviewCommentRequest request = mapped.get();
        assertEquals("body", request.body());
        assertEquals("abc123def456", request.commitId());
        assertEquals("src/UserRepository.java", request.path());
        assertEquals(52, request.line());
        assertEquals("RIGHT", request.side());
        assertNull(request.startLine());
        assertNull(request.startSide());
    }

    @Test
    void shouldMapMultiLinePlacement() {
        InlineCommentPlacement placement =
                InlineCommentPlacement.placed("RIGHT", 12, 10, "RIGHT");

        ReviewCommentRequest request = ReviewCommentRequestMapper.map(
                "body", "abc123def456", "src/A.java", placement).orElseThrow();

        assertEquals(12, request.line());
        assertEquals("RIGHT", request.side());
        assertNotNull(request.startLine());
        assertEquals(10, request.startLine().intValue());
        assertEquals("RIGHT", request.startSide());
        assertTrue(request.startLine() < request.line());
    }

    @Test
    void shouldPreserveLeftAndRightSides() {
        ReviewCommentRequest leftSingle = ReviewCommentRequestMapper.map(
                "body", "abc", "src/A.java",
                InlineCommentPlacement.placed("LEFT", 8, null, null))
                .orElseThrow();
        assertEquals("LEFT", leftSingle.side());
        assertEquals(8, leftSingle.line());
        assertNull(leftSingle.startLine());

        ReviewCommentRequest leftMulti = ReviewCommentRequestMapper.map(
                "body", "abc", "src/A.java",
                InlineCommentPlacement.placed("LEFT", 9, 8, "LEFT"))
                .orElseThrow();
        assertEquals("LEFT", leftMulti.side());
        assertEquals("LEFT", leftMulti.startSide());
        assertEquals(9, leftMulti.line());
        assertNotNull(leftMulti.startLine());
        assertEquals(8, leftMulti.startLine().intValue());
    }

    @Test
    void shouldReturnEmptyForNonCommentablePlacement() {
        for (String reason : new String[]{
                PatchCommentableLines.REASON_NO_PATCH,
                PatchCommentableLines.REASON_PARSE_ERROR,
                PatchCommentableLines.REASON_INVALID_RANGE,
                PatchCommentableLines.REASON_NOT_IN_DIFF}) {
            Optional<ReviewCommentRequest> mapped =
                    ReviewCommentRequestMapper.map(
                            "body", "abc", "src/A.java",
                            InlineCommentPlacement.notCommentable(reason));
            assertTrue(mapped.isEmpty());
        }
    }

    @Test
    void shouldRejectNullPlacement() {
        assertThrows(NullPointerException.class,
                () -> ReviewCommentRequestMapper.map(
                        "body", "abc", "src/A.java", null));
    }

    @Test
    void shouldRejectCommentablePlacementWithMissingOrInvalidFields() {
        assertThrows(IllegalArgumentException.class,
                () -> ReviewCommentRequestMapper.map("body", "abc", "src/A.java",
                        new InlineCommentPlacement(
                                true, null, 7, null, null, null)));
        assertThrows(IllegalArgumentException.class,
                () -> ReviewCommentRequestMapper.map("body", "abc", "src/A.java",
                        new InlineCommentPlacement(
                                true, " ", 7, null, null, null)));
        assertThrows(IllegalArgumentException.class,
                () -> ReviewCommentRequestMapper.map("body", "abc", "src/A.java",
                        new InlineCommentPlacement(
                                true, "MIDDLE", 7, null, null, null)));
        assertThrows(IllegalArgumentException.class,
                () -> ReviewCommentRequestMapper.map("body", "abc", "src/A.java",
                        new InlineCommentPlacement(
                                true, "RIGHT", null, null, null, null)));
        assertThrows(IllegalArgumentException.class,
                () -> ReviewCommentRequestMapper.map("body", "abc", "src/A.java",
                        new InlineCommentPlacement(
                                true, "RIGHT", 0, null, null, null)));
    }

    @Test
    void shouldRejectHalfMultiLinePlacement() {
        assertThrows(IllegalArgumentException.class,
                () -> ReviewCommentRequestMapper.map("body", "abc", "src/A.java",
                        new InlineCommentPlacement(
                                true, "RIGHT", 12, 10, null, null)));
        assertThrows(IllegalArgumentException.class,
                () -> ReviewCommentRequestMapper.map("body", "abc", "src/A.java",
                        new InlineCommentPlacement(
                                true, "RIGHT", 12, null, "RIGHT", null)));
    }

    @Test
    void shouldRejectInvalidMultiLineRange() {
        assertThrows(IllegalArgumentException.class,
                () -> ReviewCommentRequestMapper.map("body", "abc", "src/A.java",
                        new InlineCommentPlacement(
                                true, "RIGHT", 10, 10, "RIGHT", null)));
        assertThrows(IllegalArgumentException.class,
                () -> ReviewCommentRequestMapper.map("body", "abc", "src/A.java",
                        new InlineCommentPlacement(
                                true, "RIGHT", 10, 12, "RIGHT", null)));
        assertThrows(IllegalArgumentException.class,
                () -> ReviewCommentRequestMapper.map("body", "abc", "src/A.java",
                        new InlineCommentPlacement(
                                true, "RIGHT", 10, -1, "RIGHT", null)));
        assertThrows(IllegalArgumentException.class,
                () -> ReviewCommentRequestMapper.map("body", "abc", "src/A.java",
                        new InlineCommentPlacement(
                                true, "RIGHT", 10, 5, "MIDDLE", null)));
    }
}