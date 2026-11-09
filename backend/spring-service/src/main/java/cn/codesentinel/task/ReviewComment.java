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
 * Structured history row of one successfully created inline review
 * comment (Phase 10.2; DDL Phase 10.1).
 *
 * <p>Links to a finding through {@code (report_id, finding_ordinal)},
 * the same logical key shape as
 * {@code review_finding(report_id, ordinal)}; skipped and failed items
 * stay in {@code review_result_delivery.publish_outcome_json}.
 * {@code github_comment_id} is NULL only for the defensive
 * "confirmed published without an id" outcome. Flat entity: no
 * relationship mappings and no physical foreign keys.
 *
 * <p>{@code created_at} is set at construction time (write-once row,
 * {@link ReviewResultDelivery} convention).
 */
@Entity
@Table(
        name = "review_comment",
        uniqueConstraints = {
                @UniqueConstraint(
                        name = "uk_review_comment_report_finding",
                        columnNames = {"report_id", "finding_ordinal"}),
                @UniqueConstraint(
                        name = "uk_review_comment_github_id",
                        columnNames = {"github_comment_id"})})
public class ReviewComment {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "report_id", nullable = false)
    private Long reportId;

    @Column(name = "finding_ordinal", nullable = false)
    private int findingOrdinal;

    @Column(name = "github_comment_id")
    private Long githubCommentId;

    @Column(name = "file_path", nullable = false, length = 1024)
    private String filePath;

    @Column(name = "start_line", nullable = false)
    private int startLine;

    @Column(name = "end_line", nullable = false)
    private int endLine;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    protected ReviewComment() {
    }

    public ReviewComment(Long reportId, int findingOrdinal,
                         Long githubCommentId, String filePath,
                         int startLine, int endLine) {
        this.reportId = reportId;
        this.findingOrdinal = findingOrdinal;
        this.githubCommentId = githubCommentId;
        this.filePath = filePath;
        this.startLine = startLine;
        this.endLine = endLine;
        this.createdAt = LocalDateTime.now();
    }

    public Long getId() {
        return id;
    }

    public Long getReportId() {
        return reportId;
    }

    public int getFindingOrdinal() {
        return findingOrdinal;
    }

    public Long getGithubCommentId() {
        return githubCommentId;
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

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }
}