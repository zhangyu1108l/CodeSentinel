package cn.codesentinel.task;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;

import java.time.LocalDateTime;

/**
 * Structured history row of one review (Phase 10.2; DDL Phase 10.1).
 *
 * <p>One row per review task (unique {@code task_id}). The structured
 * columns mirror the terminal publication state of
 * {@code review_result_delivery} so history queries never read the
 * replay buffers. Flat entity: no relationship mappings and no physical
 * foreign keys, matching the existing entity style.
 *
 * <p>{@code created_at} / {@code updated_at} follow the
 * {@link ReviewTask} lifecycle-callback convention (DATETIME(6)).
 */
@Entity
@Table(
        name = "review_report",
        uniqueConstraints = @UniqueConstraint(
                name = "uk_review_report_task",
                columnNames = {"task_id"}))
public class ReviewReport {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "task_id", nullable = false)
    private Long taskId;

    @Column(name = "commit_sha", nullable = false, length = 40)
    private String commitSha;

    @Column(name = "ai_status", nullable = false, length = 20)
    private String aiStatus;

    @Enumerated(EnumType.STRING)
    @Column(name = "publish_status", nullable = false, length = 20)
    private PublishStatus publishStatus;

    @Column(name = "finding_count", nullable = false)
    private int findingCount;

    @Column(name = "published_comment_count", nullable = false)
    private int publishedCommentCount;

    @Column(name = "summary_comment_id")
    private Long summaryCommentId;

    @Column(name = "published_at")
    private LocalDateTime publishedAt;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

    protected ReviewReport() {
    }

    public ReviewReport(Long taskId, String commitSha, String aiStatus,
                        PublishStatus publishStatus, int findingCount,
                        int publishedCommentCount, Long summaryCommentId,
                        LocalDateTime publishedAt) {
        this.taskId = taskId;
        this.commitSha = commitSha;
        this.aiStatus = aiStatus;
        this.publishStatus = publishStatus;
        this.findingCount = findingCount;
        this.publishedCommentCount = publishedCommentCount;
        this.summaryCommentId = summaryCommentId;
        this.publishedAt = publishedAt;
    }

    /**
     * Mirrors the terminal publication outcome of the delivery
     * (Phase 10.4). Controlled update: the status converges to the
     * delivery's terminal status, the comment count is the absolute
     * inline-comment row count, the summary id is only filled when it
     * is still missing, and publishedAt is only written when non-null
     * (never cleared).
     */
    public void applyPublishOutcome(PublishStatus publishStatus,
                                    int publishedCommentCount,
                                    Long summaryCommentId,
                                    LocalDateTime publishedAt) {
        if (publishStatus == null || publishStatus == PublishStatus.PENDING) {
            throw new IllegalArgumentException(
                    "publishStatus must be a terminal status: "
                            + publishStatus);
        }
        if (publishedCommentCount < 0) {
            throw new IllegalArgumentException(
                    "publishedCommentCount must not be negative: "
                            + publishedCommentCount);
        }
        this.publishStatus = publishStatus;
        this.publishedCommentCount = publishedCommentCount;
        if (this.summaryCommentId == null && summaryCommentId != null) {
            this.summaryCommentId = summaryCommentId;
        }
        if (publishedAt != null) {
            this.publishedAt = publishedAt;
        }
    }

    @PrePersist
    protected void onCreate() {
        LocalDateTime now = LocalDateTime.now();
        this.createdAt = now;
        this.updatedAt = now;
    }

    @PreUpdate
    protected void onUpdate() {
        this.updatedAt = LocalDateTime.now();
    }

    public Long getId() {
        return id;
    }

    public Long getTaskId() {
        return taskId;
    }

    public String getCommitSha() {
        return commitSha;
    }

    public String getAiStatus() {
        return aiStatus;
    }

    public PublishStatus getPublishStatus() {
        return publishStatus;
    }

    public int getFindingCount() {
        return findingCount;
    }

    public int getPublishedCommentCount() {
        return publishedCommentCount;
    }

    public Long getSummaryCommentId() {
        return summaryCommentId;
    }

    public LocalDateTime getPublishedAt() {
        return publishedAt;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }

    public LocalDateTime getUpdatedAt() {
        return updatedAt;
    }
}