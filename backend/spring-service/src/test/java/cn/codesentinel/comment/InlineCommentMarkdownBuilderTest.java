package cn.codesentinel.comment;

import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class InlineCommentMarkdownBuilderTest {

    @Test
    void shouldMatchDocumentedExampleFormat() {
        InlineCommentFinding finding = new InlineCommentFinding(
                "UserRepository.java", 52, 52, "HIGH", "SECURITY",
                null, "发现潜在 SQL Injection。", "外部输入直接参与 SQL 拼接。",
                "使用参数化查询。", "CWE-89");

        String expected = String.join("\n",
                "UserRepository.java:52", "",
                "🔴 HIGH Security Issue", "",
                "发现潜在 SQL Injection。", "",
                "原因：", "外部输入直接参与 SQL 拼接。", "",
                "建议：", "使用参数化查询。", "",
                "Rule:", "CWE-89");

        assertEquals(expected, InlineCommentMarkdownBuilder.build(finding));
    }

    @Test
    void shouldRenderTitleAndDescriptionInOrder() {
        InlineCommentFinding finding = new InlineCommentFinding(
                "src/A.java", 10, 14, "MEDIUM", "BUG",
                "Null dereference", "The value may be null.",
                "Missing null check.", "Guard the access.", "CS-001");

        String output = InlineCommentMarkdownBuilder.build(finding);

        assertTrue(output.contains("src/A.java:10-14"));
        assertTrue(output.contains("🟠 MEDIUM Bug Issue"));
        assertTrue(output.indexOf("Null dereference")
                < output.indexOf("The value may be null."));
        assertTrue(output.indexOf("The value may be null.")
                < output.indexOf("原因："));
        assertTrue(output.indexOf("原因：") < output.indexOf("建议："));
        assertTrue(output.indexOf("建议：") < output.indexOf("Rule:"));
    }

    @Test
    void shouldSkipBlankFieldsGracefully() {
        InlineCommentFinding finding = new InlineCommentFinding(
                "File.java", 7, 7, "LOW", "QUALITY",
                null, "", "   ", null, "");

        String expected = String.join("\n",
                "File.java:7", "",
                "🟡 LOW Code Quality Issue");

        String output = InlineCommentMarkdownBuilder.build(finding);
        assertEquals(expected, output);
        assertFalse(output.contains("原因："));
        assertFalse(output.contains("建议："));
        assertFalse(output.contains("Rule:"));
    }

    @Test
    void shouldFallBackToUnknownForBlankSeverityAndCategory() {
        InlineCommentFinding unknown = new InlineCommentFinding(
                "", 0, 0, "WEIRD", "", null, null, null, null, null);
        assertEquals("WEIRD UNKNOWN Issue",
                InlineCommentMarkdownBuilder.build(unknown));

        InlineCommentFinding blank = new InlineCommentFinding(
                null, 5, 5, null, null, null, null, null, null, null);
        assertEquals("UNKNOWN UNKNOWN Issue",
                InlineCommentMarkdownBuilder.build(blank));
    }

    @Test
    void shouldRenderSeverityEmojiForKnownLevels() {
        Map<String, String> expected = Map.of(
                "CRITICAL", "🔴 CRITICAL Security Issue",
                "HIGH", "🔴 HIGH Security Issue",
                "MEDIUM", "🟠 MEDIUM Security Issue",
                "LOW", "🟡 LOW Security Issue",
                "INFO", "🔵 INFO Security Issue");

        for (Map.Entry<String, String> entry : expected.entrySet()) {
            InlineCommentFinding finding = new InlineCommentFinding(
                    "", 1, 1, entry.getKey(), "SECURITY",
                    null, null, null, null, null);
            assertEquals(entry.getValue(),
                    InlineCommentMarkdownBuilder.build(finding));
        }
    }

    @Test
    void shouldEscapeMarkdownSpecialCharacters() {
        InlineCommentFinding finding = new InlineCommentFinding(
                "src/**bold**[x].java", 3, 3, "HIGH", "SECURITY",
                "Title with `code` and under_score",
                "line one\nline two # heading",
                "[link](url) <b> #tag \\ slash",
                null, "**RULE**");

        String output = InlineCommentMarkdownBuilder.build(finding);

        assertFalse(output.contains("**bold**"));
        assertFalse(output.contains("`code`"));
        assertFalse(output.contains("[link]"));
        assertFalse(output.contains("<b>"));
        assertFalse(output.contains("**RULE**"));
        assertTrue(output.contains("\\*\\*bold\\*\\*"));
        assertTrue(output.contains("\\`code\\`"));
        assertTrue(output.contains("under\\_score"));
        assertTrue(output.contains("\\[link\\](url)"));
        assertTrue(output.contains("\\<b\\>"));
        assertTrue(output.contains("\\#tag"));
        assertTrue(output.contains("\\\\ slash"));
        assertTrue(output.contains("line one line two \\# heading"));
        assertTrue(output.contains("\\*\\*RULE\\*\\*"));
        assertTrue(output.lines().noneMatch(line -> line.startsWith("#")));
    }

    @Test
    void shouldProduceIdenticalOutputForEqualInputs() {
        InlineCommentFinding first = new InlineCommentFinding(
                "A.java", 2, 4, "HIGH", "BUG", "t", "d", "r", "s", "X-1");
        InlineCommentFinding second = new InlineCommentFinding(
                "A.java", 2, 4, "HIGH", "BUG", "t", "d", "r", "s", "X-1");

        assertEquals(
                InlineCommentMarkdownBuilder.build(first),
                InlineCommentMarkdownBuilder.build(second));
    }

    @Test
    void shouldRejectNullFinding() {
        assertThrows(NullPointerException.class,
                () -> InlineCommentMarkdownBuilder.build(null));
    }
}