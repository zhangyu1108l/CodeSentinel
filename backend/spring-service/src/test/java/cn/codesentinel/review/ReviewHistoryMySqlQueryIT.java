package cn.codesentinel.review;

import cn.codesentinel.task.PublishStatus;
import cn.codesentinel.task.ReviewComment;
import cn.codesentinel.task.ReviewFinding;
import cn.codesentinel.task.ReviewReport;
import cn.codesentinel.task.ReviewResultDelivery;
import cn.codesentinel.task.ReviewResultFinding;
import cn.codesentinel.task.ReviewTask;
import org.hibernate.SessionFactory;
import org.hibernate.stat.Statistics;
import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.when;

class ReviewHistoryMySqlQueryIT extends ReviewHistoryMySqlTestBase {

    @Test
    void q1DetailMapsReportAndTaskContext() throws Exception {
        long taskId = nextTaskId();
        ReviewTask task = seedHistory(taskId, 2);
        List<ReviewResultFinding> findings = findings(2);
        LocalDateTime publishedAt = LocalDateTime.of(2026, 3, 4, 5, 6, 7,
                123_456_000);
        String outcome = outcome("PARTIAL", "PUBLISHED", 900L, List.of(
                new OutcomeComment("PUBLISHED", "src/File0.java", 10, 10,
                        501L),
                new OutcomeComment("SKIPPED", "src/File1.java", 11, 11,
                        null)));
        historyService.ensurePublishHistory(task,
                publishedDelivery(taskId, findings, outcome,
                        PublishStatus.PARTIAL, publishedAt));
        when(reviewTaskService.getTaskById(taskId)).thenReturn(task);

        ReviewReportResponse response = queryService.getReport(taskId);

        assertEquals(taskId, response.taskId());
        assertEquals("it-owner", response.owner());
        assertEquals("phase10-6-2", response.repo());
        assertEquals(900001, response.prNumber());
        assertEquals(commitSha(taskId), response.commitSha());
        assertEquals("COMPLETED", response.taskStatus());
        assertEquals("COMPLETED", response.aiStatus());
        assertEquals("PARTIAL", response.publishStatus());
        assertEquals(2, response.findingCount());
        assertEquals(1, response.publishedCommentCount());
        assertEquals(900L, response.summaryCommentId());
        assertEquals(publishedAt, response.publishedAt());
        assertTrue(response.createdAt() != null);
        assertTrue(response.updatedAt() != null);
    }

    @Test
    void q2FindingsPaginationUsesOrdinalOrder() throws Exception {
        long taskId = nextTaskId();
        seedHistory(taskId, 25);
        when(reviewTaskService.getTaskById(taskId)).thenReturn(task(taskId));

        ReviewPageResponse<ReviewFindingResponse> first =
                queryService.getFindings(taskId, 1, 20);
        assertEquals(20, first.items().size());
        assertEquals(1, first.page());
        assertEquals(20, first.size());
        assertEquals(25, first.totalItems());
        assertEquals(2, first.totalPages());
        assertTrue(first.hasNext());
        assertEquals(0, first.items().get(0).ordinal());
        assertEquals(19, first.items().get(19).ordinal());

        ReviewPageResponse<ReviewFindingResponse> second =
                queryService.getFindings(taskId, 2, 20);
        assertEquals(5, second.items().size());
        assertEquals(20, second.items().get(0).ordinal());
        assertEquals(24, second.items().get(4).ordinal());
        assertFalse(second.hasNext());

        ReviewPageResponse<ReviewFindingResponse> all =
                queryService.getFindings(taskId, 1, 100);
        assertEquals(25, all.items().size());
        assertEquals(1, all.totalPages());
    }

    @Test
    void q3CommentsPaginationUsesFindingOrdinalOrder() throws Exception {
        long taskId = nextTaskId();
        ReviewTask task = seedHistory(taskId, 3);
        List<OutcomeComment> comments = new ArrayList<>();
        for (int i = 0; i < 3; i++) {
            comments.add(new OutcomeComment("PUBLISHED", "src/File" + i + ".java",
                    10 + i, 10 + i, i == 1 ? null : 500L + i));
        }
        historyService.ensurePublishHistory(task,
                publishedDelivery(taskId, findings(3),
                        outcome("PARTIAL", "FAILED", null, comments),
                        PublishStatus.PARTIAL, LocalDateTime.now()));
        when(reviewTaskService.getTaskById(taskId)).thenReturn(task);

        ReviewPageResponse<ReviewCommentResponse> first =
                queryService.getComments(taskId, 1, 2);
        assertEquals(2, first.items().size());
        assertEquals(0, first.items().get(0).findingOrdinal());
        assertEquals(1, first.items().get(1).findingOrdinal());
        assertNull(first.items().get(1).githubCommentId());
        assertEquals(3, first.totalItems());
        assertTrue(first.hasNext());

        ReviewPageResponse<ReviewCommentResponse> second =
                queryService.getComments(taskId, 2, 2);
        assertEquals(1, second.items().size());
        assertEquals(2, second.items().get(0).findingOrdinal());
        assertFalse(second.hasNext());
    }

    @Test
    void q4BeyondLastPageIsEmptyWithCorrectMetadata() throws Exception {
        long taskId = nextTaskId();
        seedHistory(taskId, 3);
        when(reviewTaskService.getTaskById(taskId)).thenReturn(task(taskId));

        ReviewPageResponse<ReviewFindingResponse> response =
                queryService.getFindings(taskId, 5, 20);

        assertTrue(response.items().isEmpty());
        assertEquals(5, response.page());
        assertEquals(3, response.totalItems());
        assertEquals(1, response.totalPages());
        assertFalse(response.hasNext());
    }

    @Test
    void q5EmptyFindingsAndCommentsAreReturnedAsEmptyPages() throws Exception {
        long taskId = nextTaskId();
        seedHistory(taskId, 0);
        when(reviewTaskService.getTaskById(taskId)).thenReturn(task(taskId));

        ReviewPageResponse<ReviewFindingResponse> findings =
                queryService.getFindings(taskId, 1, 20);
        ReviewPageResponse<ReviewCommentResponse> comments =
                queryService.getComments(taskId, 1, 20);
        ReviewReportResponse detail = queryService.getReport(taskId);

        assertTrue(findings.items().isEmpty());
        assertEquals(0, findings.totalItems());
        assertTrue(comments.items().isEmpty());
        assertEquals(0, comments.totalItems());
        assertEquals(0, detail.findingCount());
        assertEquals(0, detail.publishedCommentCount());
    }

    @Test
    void q6FindingCountMismatchIsRejected() throws Exception {
        long taskId = nextTaskId();
        ReviewReport report = reportRepository.saveAndFlush(report(taskId,
                commitSha(taskId), PublishStatus.PENDING, 2, 0, null, null));
        findingRepository.saveAndFlush(findingRow(report.getId(), 0,
                "src/A.java"));
        when(reviewTaskService.getTaskById(taskId)).thenReturn(task(taskId));

        assertThrows(ReviewHistoryIncompleteException.class,
                () -> queryService.getReport(taskId));
        assertThrows(ReviewHistoryIncompleteException.class,
                () -> queryService.getFindings(taskId, 1, 20));
    }

    @Test
    void q7CommentCountMismatchIsRejected() throws Exception {
        long taskId = nextTaskId();
        ReviewReport report = reportRepository.saveAndFlush(report(taskId,
                commitSha(taskId), PublishStatus.PARTIAL, 0, 1, null, null));
        when(reviewTaskService.getTaskById(taskId)).thenReturn(task(taskId));

        assertThrows(ReviewHistoryIncompleteException.class,
                () -> queryService.getReport(taskId));
        assertThrows(ReviewHistoryIncompleteException.class,
                () -> queryService.getComments(taskId, 1, 20));
    }

    @Test
    void q8ReferencesWithNullElementsArePreserved() throws Exception {
        long taskId = nextTaskId();
        seedHistory(taskId, 1);
        when(reviewTaskService.getTaskById(taskId)).thenReturn(task(taskId));

        ReviewPageResponse<ReviewFindingResponse> response =
                queryService.getFindings(taskId, 1, 20);
        ReviewFindingResponse finding = response.items().get(0);

        assertEquals("CWE-0", finding.references().get(0));
        assertNull(finding.references().get(1));
    }

    @Test
    void q9NullAndEmptyReferencesBecomeEmptyLists() throws Exception {
        long taskId = nextTaskId();
        ReviewReport report = reportRepository.saveAndFlush(report(taskId,
                commitSha(taskId), PublishStatus.PENDING, 2, 0, null, null));
        findingRepository.saveAndFlush(new ReviewFinding(report.getId(), 0,
                "BUG", "LOW", 0.5, "R-1", "title", "src/A.java", 1, 1,
                "d", "r", "s", null));
        findingRepository.saveAndFlush(new ReviewFinding(report.getId(), 1,
                "BUG", "LOW", 0.5, "R-2", "title", "src/B.java", 1, 1,
                "d", "r", "s", "[]"));
        when(reviewTaskService.getTaskById(taskId)).thenReturn(task(taskId));

        ReviewPageResponse<ReviewFindingResponse> response =
                queryService.getFindings(taskId, 1, 20);

        assertTrue(response.items().get(0).references().isEmpty());
        assertTrue(response.items().get(1).references().isEmpty());
    }

    @Test
    void q10InvalidAndNonArrayReferencesAreRejectedWithoutRawJson() {
        long taskId = nextTaskId();
        ReviewReport report = reportRepository.saveAndFlush(report(taskId,
                commitSha(taskId), PublishStatus.PENDING, 1, 0, null, null));
        String invalid = "{\"not\":\"an-array\"}";
        findingRepository.saveAndFlush(new ReviewFinding(report.getId(), 0,
                "BUG", "LOW", 0.5, "R-1", "title", "src/A.java", 1, 1,
                "d", "r", "s", invalid));
        when(reviewTaskService.getTaskById(taskId)).thenReturn(task(taskId));

        ReviewHistoryDataIntegrityException error = assertThrows(
                ReviewHistoryDataIntegrityException.class,
                () -> queryService.getFindings(taskId, 1, 20));

        assertFalse(error.getMessage().contains(invalid));
        assertTrue(error.getMessage().contains("references_json"));
    }

    @Test
    void q11PendingPublishStatusIsVisibleAndCommentsAreEmpty() throws Exception {
        long taskId = nextTaskId();
        seedHistory(taskId, 1);
        when(reviewTaskService.getTaskById(taskId)).thenReturn(task(taskId));

        ReviewReportResponse detail = queryService.getReport(taskId);
        ReviewPageResponse<ReviewCommentResponse> comments =
                queryService.getComments(taskId, 1, 20);

        assertEquals("PENDING", detail.publishStatus());
        assertNull(detail.publishedAt());
        assertTrue(comments.items().isEmpty());
    }

    @Test
    void q12FindingsPageDoesNotUsePerRowQueries() throws Exception {
        long taskId = nextTaskId();
        seedHistory(taskId, 25);
        when(reviewTaskService.getTaskById(taskId)).thenReturn(task(taskId));
        Statistics statistics = entityManagerFactory
                .unwrap(SessionFactory.class).getStatistics();
        statistics.clear();

        queryService.getFindings(taskId, 1, 20);

        long queryCount = statistics.getQueryExecutionCount();
        assertTrue(queryCount > 0, "expected at least one query");
        assertTrue(queryCount <= 4,
                "expected a bounded query count, actual=" + queryCount);
    }

    private ReviewTask seedHistory(long taskId, int findingCount)
            throws Exception {
        ReviewTask task = task(taskId);
        historyService.ensureHistory(task,
                delivery(taskId, findings(findingCount)));
        return task;
    }
}