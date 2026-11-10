package cn.codesentinel.review;

import java.util.List;

/**
 * Public finding representation of one structured history row
 * (Phase 10.5). Internal row identifiers are not exposed.
 */
public record ReviewFindingResponse(
        int ordinal,
        String category,
        String severity,
        Double confidence,
        String ruleId,
        String title,
        String filePath,
        int startLine,
        int endLine,
        String description,
        String reason,
        String suggestion,
        List<String> references) {
}