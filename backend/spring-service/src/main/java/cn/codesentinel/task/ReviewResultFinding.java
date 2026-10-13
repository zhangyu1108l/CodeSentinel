package cn.codesentinel.task;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

/**
 * One finding of the AI review result transport payload (Phase 9.5.3B1).
 *
 * <p>Field names and types mirror the Python {@code ReviewFinding} model
 * ({@code agent/app/schemas/review.py} L29-41) with snake_case JSON keys.
 * The nullable component types are intentional: a missing JSON field
 * must be detectable during validation instead of silently becoming a
 * default value. Unknown extra fields are ignored so later additive
 * contract changes do not break delivery.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record ReviewResultFinding(
        @JsonProperty("category") String category,
        @JsonProperty("severity") String severity,
        @JsonProperty("confidence") Double confidence,
        @JsonProperty("rule_id") String ruleId,
        @JsonProperty("title") String title,
        @JsonProperty("file_path") String filePath,
        @JsonProperty("start_line") Integer startLine,
        @JsonProperty("end_line") Integer endLine,
        @JsonProperty("description") String description,
        @JsonProperty("reason") String reason,
        @JsonProperty("suggestion") String suggestion,
        @JsonProperty("references") List<String> references) {
}