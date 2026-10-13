package cn.codesentinel.comment;

/**
 * Minimal inline-comment view of one reported finding.
 *
 * <p>Carries exactly the fields the §14.2 comment body renders: the file
 * location and the finding's severity, category and text fields. It is
 * NOT a transport DTO: the cross-language result contract does not exist
 * on the Java side yet, and no transport DTO is defined here.
 */
public record InlineCommentFinding(
        String filePath,
        int startLine,
        int endLine,
        String severity,
        String category,
        String title,
        String description,
        String reason,
        String suggestion,
        String ruleId) {
}