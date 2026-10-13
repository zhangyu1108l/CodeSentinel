package cn.codesentinel.comment;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class PatchCommentableLinesTest {

    @Test
    void shouldMapAddedRemovedAndContextLines() {
        PatchCommentableLines lines = PatchCommentableLines.parse(
                String.join("\n",
                        "@@ -1,5 +1,6 @@",
                        " line1",
                        " line2",
                        "-removed3",
                        "+added3",
                        "+added4",
                        " line5",
                        " line6"));

        assertTrue(lines.isCommentable("RIGHT", 3));
        assertTrue(lines.isCommentable("RIGHT", 4));
        assertTrue(lines.isCommentable("RIGHT", 5));
        assertTrue(lines.isCommentable("RIGHT", 6));
        assertTrue(lines.isCommentable("LEFT", 1));
        assertTrue(lines.isCommentable("LEFT", 3));
        assertTrue(lines.isCommentable("LEFT", 5));
        assertFalse(lines.isCommentable("RIGHT", 7));
        assertFalse(lines.isCommentable("LEFT", 6));

        assertEquals(
                InlineCommentPlacement.placed("RIGHT", 4, 3, "RIGHT"),
                lines.placeRight(3, 4));
        assertEquals(
                InlineCommentPlacement.placed("RIGHT", 5, null, null),
                lines.placeRight(5, 5));
    }

    @Test
    void shouldTreatRemovedLinesAsLeftOnly() {
        PatchCommentableLines lines = PatchCommentableLines.parse(
                String.join("\n",
                        "@@ -10,3 +10,2 @@",
                        " context10",
                        "-removed11",
                        " context12"));

        assertTrue(lines.isCommentable("LEFT", 11));
        assertTrue(lines.isCommentable("LEFT", 12));
        assertFalse(lines.isCommentable("RIGHT", 12));
        assertTrue(lines.isCommentable("RIGHT", 11));

        assertEquals(
                InlineCommentPlacement.notCommentable(
                        PatchCommentableLines.REASON_NOT_IN_DIFF),
                lines.placeRight(12, 12));
        assertEquals(
                InlineCommentPlacement.placed("RIGHT", 11, null, null),
                lines.placeRight(11, 11));
    }

    @Test
    void shouldHandleNewFilePatch() {
        PatchCommentableLines lines = PatchCommentableLines.parse(
                String.join("\n",
                        "@@ -0,0 +1,3 @@",
                        "+line1",
                        "+line2",
                        "+line3"));

        assertTrue(lines.isCommentable("RIGHT", 1));
        assertTrue(lines.isCommentable("RIGHT", 3));
        assertFalse(lines.isCommentable("RIGHT", 4));
        assertFalse(lines.isCommentable("LEFT", 1));

        assertEquals(
                InlineCommentPlacement.placed("RIGHT", 2, null, null),
                lines.placeRight(2, 2));
    }

    @Test
    void shouldHandleDeletedFilePatch() {
        PatchCommentableLines lines = PatchCommentableLines.parse(
                String.join("\n",
                        "@@ -1,3 +0,0 @@",
                        "-line1",
                        "-line2",
                        "-line3"));

        assertTrue(lines.isCommentable("LEFT", 1));
        assertTrue(lines.isCommentable("LEFT", 3));
        assertFalse(lines.isCommentable("LEFT", 4));
        assertFalse(lines.isCommentable("RIGHT", 1));

        assertEquals(
                InlineCommentPlacement.notCommentable(
                        PatchCommentableLines.REASON_NOT_IN_DIFF),
                lines.placeRight(2, 2));
    }

    @Test
    void shouldPlaceRangesAcrossMultipleHunks() {
        PatchCommentableLines lines = PatchCommentableLines.parse(
                String.join("\n",
                        "@@ -1,2 +1,3 @@",
                        " a",
                        "+b",
                        " c",
                        "@@ -10,2 +11,2 @@",
                        " x",
                        "-y",
                        "+z"));

        assertEquals(
                InlineCommentPlacement.placed("RIGHT", 3, 1, "RIGHT"),
                lines.placeRight(1, 3));
        assertEquals(
                InlineCommentPlacement.placed("RIGHT", 11, null, null),
                lines.placeRight(3, 11));
        assertEquals(
                InlineCommentPlacement.placed("RIGHT", 12, null, null),
                lines.placeRight(12, 15));
        assertEquals(
                InlineCommentPlacement.notCommentable(
                        PatchCommentableLines.REASON_NOT_IN_DIFF),
                lines.placeRight(4, 5));

        assertTrue(lines.isCommentable("LEFT", 11));
        assertFalse(lines.isCommentable("LEFT", 12));
        assertTrue(lines.isCommentable("RIGHT", 12));
    }

    @Test
    void shouldReportNotInDiffForLineOutsideHunks() {
        PatchCommentableLines lines = PatchCommentableLines.parse(
                String.join("\n",
                        "@@ -1,2 +1,2 @@",
                        " a",
                        " b"));

        assertFalse(lines.isCommentable("RIGHT", 3));
        assertFalse(lines.isCommentable("LEFT", 3));

        assertEquals(
                InlineCommentPlacement.notCommentable(
                        PatchCommentableLines.REASON_NOT_IN_DIFF),
                lines.placeRight(3, 3));
        assertEquals(
                InlineCommentPlacement.notCommentable(
                        PatchCommentableLines.REASON_NOT_IN_DIFF),
                lines.placeRight(3, 8));
    }

    @Test
    void shouldReportNoPatchForMissingOrBlankPatch() {
        for (String patch : new String[]{null, "", "   ", "\n"}) {
            PatchCommentableLines lines = PatchCommentableLines.parse(patch);
            assertFalse(lines.isCommentable("RIGHT", 1));
            assertEquals(
                    InlineCommentPlacement.notCommentable(
                            PatchCommentableLines.REASON_NO_PATCH),
                    lines.placeRight(1, 1));
        }
    }

    @Test
    void shouldReportParseErrorForMalformedPatches() {
        List<String> malformed = List.of(
                "not a diff at all",
                String.join("\n",
                        "@@ -1,3 +1,3 @@",
                        "+a",
                        "+b"),
                String.join("\n",
                        "@@ -1,1 +1,1 @@",
                        "-a",
                        "-b"),
                String.join("\n",
                        "@@ -1,2 +1,2 @@",
                        "?junk",
                        " a",
                        " b"),
                String.join("\n",
                        "@@ -1,2 +1,2 @@",
                        " a",
                        "@@ -5,2 +5,2 @@",
                        " x",
                        " y"));

        for (String patch : malformed) {
            PatchCommentableLines lines = PatchCommentableLines.parse(patch);
            assertFalse(lines.isCommentable("RIGHT", 1));
            assertFalse(lines.isCommentable("LEFT", 1));
            assertEquals(
                    InlineCommentPlacement.notCommentable(
                            PatchCommentableLines.REASON_PARSE_ERROR),
                    lines.placeRight(1, 1));
        }
    }

    @Test
    void shouldTreatEmptyLineAsContextInsideHunk() {
        PatchCommentableLines lines = PatchCommentableLines.parse(
                String.join("\n",
                        "@@ -1,3 +1,3 @@",
                        " a",
                        "",
                        " c"));

        assertTrue(lines.isCommentable("RIGHT", 2));
        assertTrue(lines.isCommentable("LEFT", 2));
        assertEquals(
                InlineCommentPlacement.placed("RIGHT", 2, null, null),
                lines.placeRight(2, 2));
    }

    @Test
    void shouldIgnoreNoNewlineMarker() {
        PatchCommentableLines lines = PatchCommentableLines.parse(
                String.join("\n",
                        "@@ -1,1 +1,1 @@",
                        "-a",
                        "+b",
                        "\\ No newline at end of file"));

        assertTrue(lines.isCommentable("LEFT", 1));
        assertTrue(lines.isCommentable("RIGHT", 1));
        assertFalse(lines.isCommentable("RIGHT", 2));
    }

    @Test
    void shouldRejectInvalidRangeRequests() {
        PatchCommentableLines lines = PatchCommentableLines.parse(
                String.join("\n",
                        "@@ -1,1 +1,1 @@",
                        " a"));

        assertEquals(
                InlineCommentPlacement.notCommentable(
                        PatchCommentableLines.REASON_INVALID_RANGE),
                lines.placeRight(0, 1));
        assertEquals(
                InlineCommentPlacement.notCommentable(
                        PatchCommentableLines.REASON_INVALID_RANGE),
                lines.placeRight(5, 3));
    }

    @Test
    void shouldRejectUnknownSide() {
        PatchCommentableLines lines = PatchCommentableLines.parse(
                String.join("\n",
                        "@@ -1,1 +1,1 @@",
                        " a"));

        assertThrows(IllegalArgumentException.class,
                () -> lines.isCommentable("MIDDLE", 1));
        assertThrows(IllegalArgumentException.class,
                () -> lines.isCommentable(null, 1));
    }
}