package cn.codesentinel.comment;

/**
 * Minimal summary-only view of one reported finding.
 *
 * <p>Only the two fields the summary needs are kept: {@code severity}
 * (CRITICAL / HIGH / MEDIUM / LOW / INFO) and {@code category} (BUG /
 * SECURITY / PERFORMANCE / QUALITY), matching the review model values.
 * Values are compared exactly after trimming; anything else is handled
 * as unknown by the builder.
 *
 * <p>This is not a transport DTO: the cross-language result contract
 * does not exist on the Java side yet, and no transport DTO is defined
 * here. The future mapping layer projects the transport findings onto
 * this view.
 */
public record SummaryFinding(String category, String severity) {
}