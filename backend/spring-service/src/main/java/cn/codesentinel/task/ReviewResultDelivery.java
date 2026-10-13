package cn.codesentinel.task;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;

import java.time.LocalDateTime;

/**
 * Transitional reception record of one AI review result (Phase 9.5.3B1).
 *
 * <p>{@code findingsJson} is a replayable snapshot of the raw transport
 * payload, kept so that publication can be retried after a crash; it is
 * deliberately NOT the final structured Phase 10 model. The unique key
 * (task_id, commit_sha) is the idempotency key and is independent of
 * {@link ReviewTask#getStatus()}: the worker failure path may reset the
 * task status, which must never affect deduplication.
 *
 * <p>Structured columns (task id, commit sha, status, publish status,
 * timestamps) are the queryable state; the JSON columns are retry
 * buffers only.
 */
@Entity
@Table(
        name = "review_result_delivery",
        uniqueConstraints = @UniqueConstraint(
                name = "uk_review_result_delivery_task_commit",
                columnNames = {"task_id", "commit_sha"}))
public class ReviewResultDelivery {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "task_id", nullable = false)
    private Long taskId;

    @Column(name = "commit_sha", nullable = false, length = 40)
    private String commitSha;

    @Column(name = "ai_status", nullable = false, length = 20)
    private String aiStatus;

    @Column(name = "findings_json", nullable = false,
            columnDefinition = "LONGTEXT")
    private String findingsJson;

    @Enumerated(EnumType.STRING)
    @Column(name = "publish_status", nullable = false, length = 20)
    private PublishStatus publishStatus;

    @Column(name = "publish_outcome_json", columnDefinition = "TEXT")
    private String publishOutcomeJson;

    @Column(name = "received_at", nullable = false, updatable = false)
    private LocalDateTime receivedAt;

    @Column(name = "published_at")
    private LocalDateTime publishedAt;

    protected ReviewResultDelivery() {
    }

    public ReviewResultDelivery(Long taskId, String commitSha, String aiStatus,
                                String findingsJson,
                                PublishStatus publishStatus) {
        this.taskId = taskId;
        this.commitSha = commitSha;
        this.aiStatus = aiStatus;
        this.findingsJson = findingsJson;
        this.publishStatus = publishStatus;
        this.receivedAt = LocalDateTime.now();
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

    public String getFindingsJson() {
        return findingsJson;
    }

    public PublishStatus getPublishStatus() {
        return publishStatus;
    }

    public String getPublishOutcomeJson() {
        return publishOutcomeJson;
    }

    public LocalDateTime getReceivedAt() {
        return receivedAt;
    }

    public LocalDateTime getPublishedAt() {
        return publishedAt;
    }

    /**
     * Records the terminal publication outcome (Phase 9.5.3C). The B1
     * reception fields (task, commit SHA, AI status, findings snapshot)
     * stay frozen; only the publication columns change.
     */
    public void recordPublishOutcome(PublishStatus publishStatus,
                                     String publishOutcomeJson,
                                     LocalDateTime publishedAt) {
        if (publishStatus == null || publishStatus == PublishStatus.PENDING) {
            throw new IllegalArgumentException(
                    "publishStatus must be a terminal status: "
                            + publishStatus);
        }
        if (publishOutcomeJson == null) {
            throw new IllegalArgumentException(
                    "publishOutcomeJson must not be null");
        }
        this.publishStatus = publishStatus;
        this.publishOutcomeJson = publishOutcomeJson;
        this.publishedAt = publishedAt;
    }
}