package cn.codesentinel.review;

import cn.codesentinel.persistence.UniqueKeyViolationClassifier;
import cn.codesentinel.task.PublishStatus;
import cn.codesentinel.task.ReviewComment;
import cn.codesentinel.task.ReviewFinding;
import cn.codesentinel.task.ReviewReport;
import cn.codesentinel.task.ReviewResultDelivery;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DataIntegrityViolationException;

import java.sql.SQLException;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ReviewHistoryMySqlConstraintIT extends ReviewHistoryMySqlTestBase {

    @BeforeEach
    void clearDeliveriesBeforeTest() {
        deliveryRepository.deleteAllInBatch();
    }

    @AfterEach
    void clearDeliveriesAfterTest() {
        deliveryRepository.deleteAllInBatch();
    }

    @Test
    void u1DuplicateReportTaskIdIsRejectedWithMySql1062() {
        long taskId = nextTaskId();
        reportRepository.saveAndFlush(report(taskId, commitSha(taskId),
                PublishStatus.PENDING, 0, 0, null, null));

        DataIntegrityViolationException error = assertThrows(
                DataIntegrityViolationException.class,
                () -> reportRepository.saveAndFlush(report(taskId, "b".repeat(40),
                        PublishStatus.PENDING, 0, 0, null, null)));

        assertMySqlUniqueViolation(error);
        assertEquals(1, reportRepository.count());
    }

    @Test
    void u2DuplicateFindingReportOrdinalIsRejectedWithMySql1062() {
        long taskId = nextTaskId();
        ReviewReport report = reportRepository.saveAndFlush(report(taskId,
                commitSha(taskId), PublishStatus.PENDING, 2, 0, null, null));
        findingRepository.saveAndFlush(findingRow(report.getId(), 0,
                "src/A.java"));

        DataIntegrityViolationException error = assertThrows(
                DataIntegrityViolationException.class,
                () -> findingRepository.saveAndFlush(findingRow(report.getId(),
                        0, "src/B.java")));

        assertMySqlUniqueViolation(error);
        assertEquals(1, findingRepository.count());
    }

    @Test
    void u3DuplicateCommentReportOrdinalIsRejectedWithMySql1062() {
        long taskId = nextTaskId();
        ReviewReport report = reportRepository.saveAndFlush(report(taskId,
                commitSha(taskId), PublishStatus.PARTIAL, 1, 2, null, null));
        commentRepository.saveAndFlush(commentRow(report.getId(), 0, 501L,
                "src/A.java"));

        DataIntegrityViolationException error = assertThrows(
                DataIntegrityViolationException.class,
                () -> commentRepository.saveAndFlush(commentRow(report.getId(),
                        0, 502L, "src/B.java")));

        assertMySqlUniqueViolation(error);
        assertEquals(1, commentRepository.count());
    }

    @Test
    void u4DuplicateNonNullGithubCommentIdIsRejectedWithMySql1062() {
        long firstTaskId = nextTaskId();
        long secondTaskId = nextTaskId();
        ReviewReport first = reportRepository.saveAndFlush(report(firstTaskId,
                commitSha(firstTaskId), PublishStatus.PARTIAL, 1, 1, null,
                null));
        ReviewReport second = reportRepository.saveAndFlush(report(secondTaskId,
                commitSha(secondTaskId), PublishStatus.PARTIAL, 1, 1, null,
                null));
        commentRepository.saveAndFlush(commentRow(first.getId(), 0, 501L,
                "src/A.java"));

        DataIntegrityViolationException error = assertThrows(
                DataIntegrityViolationException.class,
                () -> commentRepository.saveAndFlush(commentRow(second.getId(),
                        0, 501L, "src/B.java")));

        assertMySqlUniqueViolation(error);
        assertEquals(1, commentRepository.count());
    }

    @Test
    void u5MultipleNullGithubCommentIdsAreAllowed() {
        long taskId = nextTaskId();
        ReviewReport report = reportRepository.saveAndFlush(report(taskId,
                commitSha(taskId), PublishStatus.PARTIAL, 2, 2, null, null));

        ReviewComment first = commentRepository.saveAndFlush(
                commentRow(report.getId(), 0, null, "src/A.java"));
        ReviewComment second = commentRepository.saveAndFlush(
                commentRow(report.getId(), 1, null, "src/B.java"));

        assertEquals(2, commentRepository.count());
        assertNull(first.getGithubCommentId());
        assertNull(second.getGithubCommentId());
    }

    @Test
    void u6DuplicateDeliveryTaskCommitIsRejectedWithMySql1062() {
        long taskId = nextTaskId();
        String commitSha = commitSha(taskId);
        deliveryRepository.saveAndFlush(new ReviewResultDelivery(taskId,
                commitSha, "COMPLETED", "[]", PublishStatus.PENDING));

        DataIntegrityViolationException error = assertThrows(
                DataIntegrityViolationException.class,
                () -> deliveryRepository.saveAndFlush(new ReviewResultDelivery(
                        taskId, commitSha, "DEGRADED", "[]",
                        PublishStatus.PENDING)));

        assertMySqlUniqueViolation(error);
        assertEquals(1, deliveryRepository.count());
    }

    private static void assertMySqlUniqueViolation(
            DataIntegrityViolationException error) {
        Throwable cause = error.getMostSpecificCause();
        assertTrue(cause instanceof SQLException, cause.toString());
        SQLException sqlError = (SQLException) cause;
        assertEquals(1062, sqlError.getErrorCode());
        assertEquals("23000", sqlError.getSQLState());
        assertTrue(UniqueKeyViolationClassifier.isUniqueKeyViolation(error));
    }
}