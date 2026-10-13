package cn.codesentinel.comment;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/**
 * Deterministic Markdown generator for the PR review summary comment
 * (format follows the PROJECT_DESIGN.md §14.1 example).
 *
 * <p>Pure rendering: the output depends only on the given findings and
 * status. The generator never calls GitHub, never reads time or
 * randomness, and never claims completeness: a degraded review always
 * carries an explicit warning line.
 *
 * <p>Inputs are the minimal summary views {@link SummaryFinding} and
 * {@link ReviewSummaryStatus}; the cross-language transport DTOs do not
 * exist on the Java side yet, so no transport DTO is defined here.
 *
 * <p>Rules:
 * <ul>
 *   <li>severity is counted strictly from the model values (CRITICAL /
 *       HIGH / MEDIUM / LOW / INFO); a value outside the model,
 *       including blank or missing, is bucketed as UNKNOWN so the total
 *       stays consistent with the rendered rows;</li>
 *   <li>only severities with a non-zero count are rendered, in model
 *       order;</li>
 *   <li>dimension lines list the model categories that have findings
 *       (BUG / SECURITY / PERFORMANCE / QUALITY, in model order with the
 *       §14.1 display names); when no known category can be derived
 *       (empty findings or only unknown categories), the four standard
 *       dimensions are listed instead;</li>
 *   <li>degraded notes are rendered as a flat bullet list; Markdown
 *       control characters and line breaks are escaped so a note can
 *       never break the document structure.</li>
 * </ul>
 */
public final class ReviewSummaryMarkdownBuilder {

    private static final String TITLE = "🤖 CodeSentinel AI Code Review";
    private static final String DEGRADED_WARNING =
            "⚠ 本次审查未完整完成（degraded），结果可能不完整，请谨慎参考。";
    private static final String CLOSING = "请查看具体代码行评论。";
    private static final String DIMENSIONS_HEADING = "审查维度：";
    private static final String UNKNOWN_SEVERITY_LABEL = "UNKNOWN:";

    private static final List<String> SEVERITY_ORDER = List.of(
            "CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO");

    /** Model categories in §14.1 display order, with their summary names. */
    private static final Map<String, String> REVIEW_DIMENSIONS;

    private static final char[] MARKDOWN_ESCAPES = {
            '`', '*', '_', '[', ']', '<', '>', '#', '~'
    };

    static {
        Map<String, String> dimensions = new LinkedHashMap<>();
        dimensions.put("BUG", "Bug");
        dimensions.put("SECURITY", "Security");
        dimensions.put("PERFORMANCE", "Performance");
        dimensions.put("QUALITY", "Code Quality");
        REVIEW_DIMENSIONS = Collections.unmodifiableMap(dimensions);
    }

    private ReviewSummaryMarkdownBuilder() {
    }

    public static String build(List<SummaryFinding> findings,
                               ReviewSummaryStatus status) {
        Objects.requireNonNull(status, "status");

        List<SummaryFinding> safeFindings =
                findings == null ? List.of() : findings;
        int total = safeFindings.size();

        Map<String, Integer> severityCounts = new LinkedHashMap<>();
        for (String severity : SEVERITY_ORDER) {
            severityCounts.put(severity, 0);
        }
        int unknownSeverityCount = 0;
        List<String> presentCategories = new ArrayList<>();
        for (SummaryFinding finding : safeFindings) {
            String severity = finding == null || finding.severity() == null
                    ? ""
                    : finding.severity().trim();
            if (severityCounts.containsKey(severity)) {
                severityCounts.merge(severity, 1, Integer::sum);
            } else {
                unknownSeverityCount++;
            }
            if (finding != null) {
                String category = finding.category() == null
                        ? ""
                        : finding.category().trim();
                if (REVIEW_DIMENSIONS.containsKey(category)
                        && !presentCategories.contains(category)) {
                    presentCategories.add(category);
                }
            }
        }

        List<String> lines = new ArrayList<>();
        lines.add(TITLE);
        lines.add("");
        if (status.degraded()) {
            lines.add(DEGRADED_WARNING);
            List<String> notes = renderableNotes(status.notes());
            if (!notes.isEmpty()) {
                lines.add("");
                for (String note : notes) {
                    lines.add("- " + escapeInline(note));
                }
            }
            lines.add("");
        }

        if (total == 0) {
            lines.add("本次审查共发现 0 个问题。");
        } else {
            lines.add("本次审查共发现 " + total + " 个问题：");
            lines.add("");
            lines.addAll(severityRows(severityCounts, unknownSeverityCount));
        }

        lines.add("");
        lines.add(DIMENSIONS_HEADING);
        lines.add("");
        lines.addAll(dimensionLines(presentCategories));
        lines.add("");
        lines.add(CLOSING);
        return String.join("\n", lines);
    }

    private static List<String> severityRows(Map<String, Integer> severityCounts,
                                             int unknownSeverityCount) {
        List<String> labels = new ArrayList<>();
        List<Integer> counts = new ArrayList<>();
        for (String severity : SEVERITY_ORDER) {
            int count = severityCounts.get(severity);
            if (count > 0) {
                labels.add(severity + ":");
                counts.add(count);
            }
        }
        if (unknownSeverityCount > 0) {
            labels.add(UNKNOWN_SEVERITY_LABEL);
            counts.add(unknownSeverityCount);
        }
        int width = 1;
        for (String label : labels) {
            width = Math.max(width, label.length() + 1);
        }
        List<String> rows = new ArrayList<>(labels.size());
        for (int i = 0; i < labels.size(); i++) {
            rows.add(String.format("%-" + width + "s%d",
                    labels.get(i), counts.get(i)));
        }
        return rows;
    }

    private static List<String> dimensionLines(List<String> presentCategories) {
        List<String> lines = new ArrayList<>();
        for (Map.Entry<String, String> dimension
                : REVIEW_DIMENSIONS.entrySet()) {
            if (presentCategories.isEmpty()
                    || presentCategories.contains(dimension.getKey())) {
                lines.add("✓ " + dimension.getValue());
            }
        }
        return lines;
    }

    private static List<String> renderableNotes(List<String> notes) {
        if (notes == null) {
            return List.of();
        }
        List<String> rendered = new ArrayList<>();
        for (String note : notes) {
            if (note != null && !note.isBlank()) {
                rendered.add(note);
            }
        }
        return rendered;
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