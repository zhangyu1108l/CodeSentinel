package cn.codesentinel.comment;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/**
 * Deterministic Markdown generator for inline (diff) review comments
 * (structure follows the PROJECT_DESIGN.md §14.2 example).
 *
 * <p>Pure rendering: no LLM, no GitHub call, no production wiring, no
 * time or randomness. The body is built from an
 * {@link InlineCommentFinding} view:
 *
 * <ul>
 *   <li>{@code file:line} (or {@code file:start-end});</li>
 *   <li>severity line ({@code <emoji> SEVERITY Category Issue}); the
 *       §14.2 example only defines HIGH as 🔴, this implementation maps
 *       CRITICAL/HIGH → 🔴, MEDIUM → 🟠, LOW → 🟡, INFO → 🔵;</li>
 *   <li>title and description paragraphs (each rendered only when
 *       non-blank);</li>
 *   <li>{@code 原因：}, {@code 建议：} and {@code Rule:} labeled blocks
 *       (each rendered only when the value is non-blank).</li>
 * </ul>
 *
 * <p>Blank fields are skipped instead of producing empty scaffolding, a
 * blank severity or category falls back to UNKNOWN, and Markdown control
 * characters are escaped so a field can never break the document
 * structure. These are minimal extensions over the §14.2 example and are
 * recorded in the Phase 9.4 report.
 */
public final class InlineCommentMarkdownBuilder {

    private static final String LABEL_REASON = "原因：";
    private static final String LABEL_SUGGESTION = "建议：";
    private static final String LABEL_RULE = "Rule:";
    private static final String UNKNOWN = "UNKNOWN";

    /** §14.2 defines HIGH as 🔴; the other levels are a minimal extension. */
    private static final Map<String, String> SEVERITY_EMOJI;

    /** Model categories with their §14.2 display names. */
    private static final Map<String, String> CATEGORY_DISPLAY;

    private static final char[] MARKDOWN_ESCAPES = {
            '`', '*', '_', '[', ']', '<', '>', '#', '~'
    };

    static {
        Map<String, String> emoji = new LinkedHashMap<>();
        emoji.put("CRITICAL", "🔴");
        emoji.put("HIGH", "🔴");
        emoji.put("MEDIUM", "🟠");
        emoji.put("LOW", "🟡");
        emoji.put("INFO", "🔵");
        SEVERITY_EMOJI = Collections.unmodifiableMap(emoji);

        Map<String, String> display = new LinkedHashMap<>();
        display.put("BUG", "Bug");
        display.put("SECURITY", "Security");
        display.put("PERFORMANCE", "Performance");
        display.put("QUALITY", "Code Quality");
        CATEGORY_DISPLAY = Collections.unmodifiableMap(display);
    }

    private InlineCommentMarkdownBuilder() {
    }

    public static String build(InlineCommentFinding finding) {
        Objects.requireNonNull(finding, "finding");

        List<String> blocks = new ArrayList<>();
        String path = clean(finding.filePath());
        if (!path.isEmpty()
                && finding.startLine() >= 1
                && finding.endLine() >= finding.startLine()) {
            blocks.add(escapeInline(path) + ":"
                    + lineRange(finding.startLine(), finding.endLine()));
        }
        blocks.add(severityHeader(finding.severity(), finding.category()));
        addParagraph(blocks, finding.title());
        addParagraph(blocks, finding.description());
        addLabeledBlock(blocks, LABEL_REASON, finding.reason());
        addLabeledBlock(blocks, LABEL_SUGGESTION, finding.suggestion());
        addLabeledBlock(blocks, LABEL_RULE, finding.ruleId());
        return String.join("\n\n", blocks);
    }

    private static String severityHeader(String severity, String category) {
        String severityText = clean(severity);
        String emoji = severityText.isEmpty()
                ? ""
                : SEVERITY_EMOJI.getOrDefault(severityText, "");
        String severityLabel = severityText.isEmpty()
                ? UNKNOWN
                : escapeInline(severityText);
        String categoryText = clean(category);
        String categoryLabel;
        if (categoryText.isEmpty()) {
            categoryLabel = UNKNOWN;
        } else {
            categoryLabel = escapeInline(
                    CATEGORY_DISPLAY.getOrDefault(categoryText, categoryText));
        }
        String prefix = emoji.isEmpty() ? "" : emoji + " ";
        return prefix + severityLabel + " " + categoryLabel + " Issue";
    }

    private static void addParagraph(List<String> blocks, String value) {
        String text = clean(value);
        if (!text.isEmpty()) {
            blocks.add(escapeInline(text));
        }
    }

    private static void addLabeledBlock(List<String> blocks, String label,
                                        String value) {
        String text = clean(value);
        if (!text.isEmpty()) {
            blocks.add(label + "\n" + escapeInline(text));
        }
    }

    private static String lineRange(int startLine, int endLine) {
        return startLine == endLine
                ? String.valueOf(startLine)
                : startLine + "-" + endLine;
    }

    private static String clean(String value) {
        return value == null ? "" : value.trim();
    }

    private static String escapeInline(String text) {
        String escaped = text
                .replace("\r\n", " ")
                .replace("\r", " ")
                .replace("\n", " ")
                .replace("\\", "\\\\");
        for (char character : MARKDOWN_ESCAPES) {
            escaped = escaped.replace(String.valueOf(character),
                    "\\" + character);
        }
        return escaped;
    }
}