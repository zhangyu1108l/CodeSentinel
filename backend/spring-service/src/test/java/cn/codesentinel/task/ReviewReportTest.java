package cn.codesentinel.task;

import jakarta.persistence.EnumType;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import org.junit.jupiter.api.Test;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.mapping.PropertyPath;
import org.springframework.data.mapping.PropertyReferenceException;

import java.lang.reflect.Method;
import java.time.LocalDateTime;
import java.util.Optional;

import static cn.codesentinel.task.JpaMappingTestSupport.assertColumn;
import static cn.codesentinel.task.JpaMappingTestSupport.assertNoRelationshipMappings;
import static cn.codesentinel.task.JpaMappingTestSupport.assertTable;
import static cn.codesentinel.task.JpaMappingTestSupport.assertUniqueConstraint;
import static cn.codesentinel.task.JpaMappingTestSupport.column;
import static cn.codesentinel.task.JpaMappingTestSupport.enumerated;
import static cn.codesentinel.task.JpaMappingTestSupport.field;
import static cn.codesentinel.task.JpaMappingTestSupport.generatedValue;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ReviewReportTest {

    @Test
    void shouldMapTableAndUniqueTaskConstraint() {
        assertTable(ReviewReport.class, "review_report");
        assertUniqueConstraint(ReviewReport.class, "uk_review_report_task",
                "task_id");
    }

    @Test
    void shouldMapEveryColumnAccordingToTheApprovedDdl() {
        assertColumn(ReviewReport.class, "taskId", "task_id", false);
        assertColumn(ReviewReport.class, "commitSha", "commit_sha", false);
        assertEquals(40, column(ReviewReport.class, "commitSha").length());
        assertColumn(ReviewReport.class, "aiStatus", "ai_status", false);
        assertEquals(20, column(ReviewReport.class, "aiStatus").length());
        assertColumn(ReviewReport.class, "publishStatus", "publish_status",
                false);
        assertEquals(20, column(ReviewReport.class, "publishStatus").length());
        assertEquals(EnumType.STRING,
                enumerated(ReviewReport.class, "publishStatus").value());
        assertColumn(ReviewReport.class, "findingCount", "finding_count",
                false);
        assertColumn(ReviewReport.class, "publishedCommentCount",
                "published_comment_count", false);
        assertColumn(ReviewReport.class, "summaryCommentId",
                "summary_comment_id", true);
        assertColumn(ReviewReport.class, "publishedAt", "published_at", true);
        assertColumn(ReviewReport.class, "createdAt", "created_at", false);
        assertFalse(column(ReviewReport.class, "createdAt").updatable());
        assertColumn(ReviewReport.class, "updatedAt", "updated_at", false);
        assertNotNull(field(ReviewReport.class, "id").getAnnotation(Id.class));
        assertEquals(GenerationType.IDENTITY,
                generatedValue(ReviewReport.class, "id").strategy());
    }

    @Test
    void shouldUseNoRelationshipMappings() {
        assertNoRelationshipMappings(ReviewReport.class);
    }

    @Test
    void shouldCarryAllBusinessFieldsThroughTheConstructor() {
        LocalDateTime publishedAt = LocalDateTime.of(2026, 1, 2, 3, 4, 5);
        ReviewReport report = new ReviewReport(11L, "abc123def456", "DEGRADED",
                PublishStatus.PARTIAL, 3, 2, 900L, publishedAt);

        assertEquals(11L, report.getTaskId());
        assertEquals("abc123def456", report.getCommitSha());
        assertEquals("DEGRADED", report.getAiStatus());
        assertEquals(PublishStatus.PARTIAL, report.getPublishStatus());
        assertEquals(3, report.getFindingCount());
        assertEquals(2, report.getPublishedCommentCount());
        assertEquals(900L, report.getSummaryCommentId());
        assertEquals(publishedAt, report.getPublishedAt());
    }

    @Test
    void shouldApplyTerminalPublishOutcomeWithFillOnlyFields() {
        LocalDateTime originalPublishedAt =
                LocalDateTime.of(2025, 1, 1, 0, 0);
        LocalDateTime newPublishedAt =
                LocalDateTime.of(2026, 2, 3, 4, 5);
        ReviewReport report = new ReviewReport(1L, "abc123", "COMPLETED",
                PublishStatus.PENDING, 2, 0, 900L, originalPublishedAt);

        report.applyPublishOutcome(PublishStatus.PARTIAL, 1, 901L,
                newPublishedAt);

        assertEquals(PublishStatus.PARTIAL, report.getPublishStatus());
        assertEquals(1, report.getPublishedCommentCount());
        assertEquals(900L, report.getSummaryCommentId());
        assertEquals(newPublishedAt, report.getPublishedAt());

        ReviewReport emptySummary = new ReviewReport(1L, "abc123", "COMPLETED",
                PublishStatus.PENDING, 0, 0, null, null);
        emptySummary.applyPublishOutcome(PublishStatus.PUBLISHED, 0, 902L,
                null);

        assertEquals(902L, emptySummary.getSummaryCommentId());
        assertNull(emptySummary.getPublishedAt());
    }

    @Test
    void shouldRejectNonTerminalOrNegativePublishOutcome() {
        ReviewReport report = new ReviewReport(1L, "abc123", "COMPLETED",
                PublishStatus.PENDING, 0, 0, null, null);

        assertThrows(IllegalArgumentException.class,
                () -> report.applyPublishOutcome(null, 0, null, null));
        assertThrows(IllegalArgumentException.class,
                () -> report.applyPublishOutcome(PublishStatus.PENDING, 0,
                        null, null));
        assertThrows(IllegalArgumentException.class,
                () -> report.applyPublishOutcome(PublishStatus.PUBLISHED, -1,
                        null, null));

        assertEquals(PublishStatus.PENDING, report.getPublishStatus());
        assertEquals(0, report.getPublishedCommentCount());
    }

    @Test
    void shouldInitializeTimestampsThroughLifecycleCallbacks() {
        ReviewReport report = new ReviewReport(1L, "abc123", "COMPLETED",
                PublishStatus.PENDING, 0, 0, null, null);

        assertNull(report.getCreatedAt());
        assertNull(report.getUpdatedAt());

        report.onCreate();
        LocalDateTime created = report.getCreatedAt();
        assertNotNull(created);
        assertEquals(created, report.getUpdatedAt());

        report.onUpdate();
        assertNotNull(report.getUpdatedAt());
        assertEquals(created, report.getCreatedAt());
    }

    @Test
    void repositoryShouldExposeTheTaskIdFinder() throws Exception {
        assertTrue(JpaRepository.class
                .isAssignableFrom(ReviewReportRepository.class));
        Method method = ReviewReportRepository.class
                .getMethod("findByTaskId", Long.class);
        assertEquals(Optional.class, method.getReturnType());
        assertNotNull(PropertyPath.from("taskId", ReviewReport.class));
    }

    @Test
    void propertyPathValidationShouldRejectUnknownProperties() {
        assertThrows(PropertyReferenceException.class,
                () -> PropertyPath.from("doesNotExist", ReviewReport.class));
    }
}