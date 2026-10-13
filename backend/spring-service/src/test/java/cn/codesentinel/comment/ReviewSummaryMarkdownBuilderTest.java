package cn.codesentinel.comment;

import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class ReviewSummaryMarkdownBuilderTest {

    private static SummaryFinding finding(String category, String severity) {
        return new SummaryFinding(category, severity);
    }

    private static ReviewSummaryStatus completed() {
        return new ReviewSummaryStatus(false, List.of());
    }

    @Test
    void shouldMatchDocumentedExampleFormat() {
        List<SummaryFinding> findings = List.of(
                finding("BUG", "HIGH"),
                finding("BUG", "MEDIUM"),
                finding("SECURITY", "MEDIUM"),
                finding("PERFORMANCE", "LOW"),
                finding("PERFORMANCE", "LOW"),
                finding("QUALITY", "LOW"));

        String expected = String.join("\n",
                "🤖 CodeSentinel AI Code Review",
                "",
                "本次审查共发现 6 个问题：",
                "",
                "HIGH:   1",
                "MEDIUM: 2",
                "LOW:    3",
                "",
                "审查维度：",
                "",
                "✓ Bug",
                "✓ Security",
                "✓ Performance",
                "✓ Code Quality",
                "",
                "请查看具体代码行评论。");

        String output = ReviewSummaryMarkdownBuilder.build(findings, completed());
        assertEquals(expected, output);
        assertFalse(output.contains("⚠"));
    }

    @Test
    void shouldCountEachSeverityStrictlyFromModelValues() {
        String output = ReviewSummaryMarkdownBuilder.build(List.of(
                finding("BUG", "CRITICAL"),
                finding("BUG", "HIGH"),
                finding("BUG", "MEDIUM"),
                finding("BUG", "LOW"),
                finding("BUG", "INFO")), completed());

        assertTrue(output.contains("本次审查共发现 5 个问题："));
        assertTrue(output.contains("CRITICAL: 1"));
        assertTrue(output.contains("HIGH:     1"));
        assertTrue(output.contains("MEDIUM:   1"));
        assertTrue(output.contains("LOW:      1"));
        assertTrue(output.contains("INFO:     1"));
        assertTrue(output.contains("✓ Bug"));
        assertFalse(output.contains("✓ Security"));
    }

    @Test
    void shouldOmitSeveritiesWithZeroCount() {
        String output = ReviewSummaryMarkdownBuilder.build(List.of(
                finding("BUG", "MEDIUM"),
                finding("SECURITY", "HIGH")), completed());

        assertTrue(output.contains("HIGH:   1"));
        assertTrue(output.contains("MEDIUM: 1"));
        assertFalse(output.contains("CRITICAL"));
        assertFalse(output.contains("LOW"));
        assertFalse(output.contains("INFO"));
        assertFalse(output.contains("UNKNOWN"));
    }

    @Test
    void shouldListOnlyDimensionsPresentInFindings() {
        String output = ReviewSummaryMarkdownBuilder.build(List.of(
                finding("BUG", "LOW"),
                finding("SECURITY", "LOW")), completed());

        assertTrue(output.contains("✓ Bug"));
        assertTrue(output.contains("✓ Security"));
        assertFalse(output.contains("✓ Performance"));
        assertFalse(output.contains("✓ Code Quality"));
    }

    @Test
    void shouldRenderEmptyFindingsCleanly() {
        String expected = String.join("\n",
                "🤖 CodeSentinel AI Code Review",
                "",
                "本次审查共发现 0 个问题。",
                "",
                "审查维度：",
                "",
                "✓ Bug",
                "✓ Security",
                "✓ Performance",
                "✓ Code Quality",
                "",
                "请查看具体代码行评论。");

        String output = ReviewSummaryMarkdownBuilder.build(List.of(), completed());
        assertEquals(expected, output);
        assertFalse(output.contains("⚠"));
        assertEquals(expected,
                ReviewSummaryMarkdownBuilder.build(null, completed()));
    }

    @Test
    void shouldBucketUnknownAndBlankSeverities() {
        String output = ReviewSummaryMarkdownBuilder.build(List.of(
                finding("BUG", "WEIRD"),
                finding("QUALITY", null),
                finding("BUG", "  ")), completed());

        assertTrue(output.contains("本次审查共发现 3 个问题："));
        assertTrue(output.contains("UNKNOWN: 3"));
        assertTrue(output.contains("✓ Bug"));
        assertTrue(output.contains("✓ Code Quality"));
        assertFalse(output.contains("HIGH"));
        assertFalse(output.contains("CRITICAL"));
        assertFalse(output.contains("INFO"));
    }

    @Test
    void shouldIgnoreUnknownCategoriesInDimensions() {
        String output = ReviewSummaryMarkdownBuilder.build(List.of(
                finding("BUG", "HIGH"),
                finding("WEIRD", "HIGH")), completed());

        assertTrue(output.contains("本次审查共发现 2 个问题："));
        assertTrue(output.contains("HIGH: 2"));
        assertTrue(output.contains("✓ Bug"));
        assertFalse(output.contains("✓ Security"));
        assertFalse(output.contains("✓ Performance"));
        assertFalse(output.contains("✓ Code Quality"));
        assertFalse(output.contains("WEIRD"));
    }

    @Test
    void shouldTolerateNullFindingElements() {
        List<SummaryFinding> findings = new ArrayList<>();
        findings.add(null);
        findings.add(finding("BUG", "HIGH"));

        String output = ReviewSummaryMarkdownBuilder.build(findings, completed());

        assertTrue(output.contains("本次审查共发现 2 个问题："));
        assertTrue(output.contains("HIGH:    1"));
        assertTrue(output.contains("UNKNOWN: 1"));
    }

    @Test
    void shouldRenderDegradedWarningWithNotes() {
        ReviewSummaryStatus status = new ReviewSummaryStatus(true, List.of(
                "PR context unavailable: http_error:500",
                "static analysis degraded"));

        String output = ReviewSummaryMarkdownBuilder.build(
                List.of(finding("BUG", "HIGH")), status);

        assertTrue(output.contains(
                "⚠ 本次审查未完整完成（degraded），结果可能不完整，请谨慎参考。"));
        assertTrue(output.contains("- PR context unavailable: http\\_error:500"));
        assertTrue(output.contains("- static analysis degraded"));
        assertTrue(output.contains("本次审查共发现 1 个问题："));
        assertTrue(output.indexOf("⚠") < output.indexOf("本次审查共发现"));
    }

    @Test
    void shouldRenderDegradedWarningWithoutNotes() {
        String output = ReviewSummaryMarkdownBuilder.build(
                List.of(), new ReviewSummaryStatus(true, List.of()));

        assertTrue(output.contains(
                "⚠ 本次审查未完整完成（degraded），结果可能不完整，请谨慎参考。"));
        assertFalse(output.contains("\n- "));
        assertTrue(output.contains("本次审查共发现 0 个问题。"));

        String withNullNotes = ReviewSummaryMarkdownBuilder.build(
                List.of(), new ReviewSummaryStatus(true, null));
        assertEquals(output, withNullNotes);
    }

    @Test
    void shouldEscapeMarkdownSpecialCharactersInNotes() {
        String note = "**bold** and `code` and [link](url) <b> #tag "
                + "\\ slash and under_score\nsecond line";

        String output = ReviewSummaryMarkdownBuilder.build(
                List.of(), new ReviewSummaryStatus(true, List.of(note)));

        assertFalse(output.contains("**bold**"));
        assertFalse(output.contains("`code`"));
        assertFalse(output.contains("[link]"));
        assertFalse(output.contains("<b>"));
        assertTrue(output.contains("\\*\\*bold\\*\\*"));
        assertTrue(output.contains("\\`code\\`"));
        assertTrue(output.contains("\\[link\\](url)"));
        assertTrue(output.contains("\\<b\\>"));
        assertTrue(output.contains("\\#tag"));
        assertTrue(output.contains("\\\\ slash"));
        assertTrue(output.contains("under\\_score"));
        assertTrue(output.contains("second line"));
        assertTrue(output.lines().noneMatch(line -> line.startsWith("#")));
    }

    @Test
    void shouldProduceIdenticalOutputForEqualInputs() {
        List<SummaryFinding> firstFindings = List.of(
                finding("BUG", "HIGH"),
                finding("SECURITY", "LOW"));
        List<SummaryFinding> secondFindings = List.of(
                finding("BUG", "HIGH"),
                finding("SECURITY", "LOW"));
        ReviewSummaryStatus status =
                new ReviewSummaryStatus(true, List.of("note"));

        assertEquals(
                ReviewSummaryMarkdownBuilder.build(firstFindings, status),
                ReviewSummaryMarkdownBuilder.build(secondFindings,
                        new ReviewSummaryStatus(true, List.of("note"))));
    }

    @Test
    void shouldRejectNullStatus() {
        assertThrows(NullPointerException.class,
                () -> ReviewSummaryMarkdownBuilder.build(List.of(), null));
    }
}