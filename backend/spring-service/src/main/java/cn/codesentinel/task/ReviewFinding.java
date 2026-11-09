package cn.codesentinel.task;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;

import java.time.LocalDateTime;

/**
 * Structured history row of one finding of a stored review snapshot
 * (Phase 10.2; DDL Phase 10.1).
 *
 * <p>{@code ordinal} is the 0-based index of this finding inside the
 * stored {@code review_result_delivery.findings_json} array and is the
 * stable identity for idempotent writes. {@code references_json} keeps
 * the snapshot JSON array as TEXT (elements may be null). Flat entity:
 * no relationship mappings and no physical foreign keys, matching the
 * existing entity style.
 *
 * <p>{@code created_at} is set at construction time (write-once row,
 * {@link ReviewResultDelivery} convention).
 */
@Entity
@Table(
        name = "review_finding",
        uniqueConstraints = @UniqueConstraint(
                name = "uk_review_finding_report_ordinal",
                columnNames = {"report_id", "ordinal"}))
public class ReviewFinding {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "report_id", nullable = false)
    private Long reportId;

    @Column(name = "ordinal", nullable = false)
    private int ordinal;

    @Column(name = "category", nullable = false, length = 20)
    private String category;

    @Column(name = "severity", nullable = false, length = 20)
    private String severity;

    @Column(name = "confidence", nullable = false)
    private Double confidence;

    @Column(name = "rule_id", nullable = false, length = 255)
    private String ruleId;

    @Column(name = "title", nullable = false, length = 1000)
    private String title;

    @Column(name = "file_path", nullable = false, length = 1024)
    private String filePath;

    @Column(name = "start_line", nullable = false)
    private int startLine;

    @Column(name = "end_line", nullable = false)
    private int endLine;

    @Column(name = "description", nullable = false, columnDefinition = "TEXT")
    private String description;

    @Column(name = "reason", nullable = false, columnDefinition = "TEXT")
    private String reason;

    @Column(name = "suggestion", nullable = false, columnDefinition = "TEXT")
    private String suggestion;

    @Column(name = "references_json", columnDefinition = "TEXT")
    private String referencesJson;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    protected ReviewFinding() {
    }

    public ReviewFinding(Long reportId, int ordinal, String category,
                         String severity, Double confidence, String ruleId,
                         String title, String filePath, int startLine,
                         int endLine, String description, String reason,
                         String suggestion, String referencesJson) {
        this.reportId = reportId;
        this.ordinal = ordinal;
        this.category = category;
        this.severity = severity;
        this.confidence = confidence;
        this.ruleId = ruleId;
        this.title = title;
        this.filePath = filePath;
        this.startLine = startLine;
        this.endLine = endLine;
        this.description = description;
        this.reason = reason;
        this.suggestion = suggestion;
        this.referencesJson = referencesJson;
        this.createdAt = LocalDateTime.now();
    }

    public Long getId() {
        return id;
    }

    public Long getReportId() {
        return reportId;
    }

    public int getOrdinal() {
        return ordinal;
    }

    public String getCategory() {
        return category;
    }

    public String getSeverity() {
        return severity;
    }

    public Double getConfidence() {
        return confidence;
    }

    public String getRuleId() {
        return ruleId;
    }

    public String getTitle() {
        return title;
    }

    public String getFilePath() {
        return filePath;
    }

    public int getStartLine() {
        return startLine;
    }

    public int getEndLine() {
        return endLine;
    }

    public String getDescription() {
        return description;
    }

    public String getReason() {
        return reason;
    }

    public String getSuggestion() {
        return suggestion;
    }

    public String getReferencesJson() {
        return referencesJson;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }
}