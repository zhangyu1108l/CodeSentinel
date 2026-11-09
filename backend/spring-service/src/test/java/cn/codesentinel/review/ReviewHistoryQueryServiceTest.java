package cn.codesentinel.review;

import cn.codesentinel.task.PublishStatus;
import cn.codesentinel.task.ReviewComment;
import cn.codesentinel.task.ReviewCommentRepository;
import cn.codesentinel.task.ReviewFinding;
import cn.codesentinel.task.ReviewFindingRepository;
import cn.codesentinel.task.ReviewReport;
import cn.codesentinel.task.ReviewReportRepository;
import cn.codesentinel.task.ReviewTask;
import cn.codesentinel.task.ReviewTaskService;
import cn.codesentinel.task.TaskNotFoundException;
import cn.codesentinel.task.TaskStatus;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Transactional;

import java.lang.reflect.Method;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.verifyNoMoreInteractions;
import static org.mockito.Mockito.when;

class ReviewHistoryQueryServiceTest {

    private static final String SHA = "abc123def456";
    private static final long TASK_ID = 7L;
    private static final long REPORT_ID = 70L;
    private static final LocalDateTime CREATED =
            LocalDateTime.of(2026, 1, 2, 3, 0);
    private static final LocalDateTime UPDATED =
            LocalDateTime.of(2026, 1, 2, 3, 4);
    private static final LocalDateTime PUBLISHED_AT =
            LocalDateTime.of(2026, 1, 2, 3, 4, 5);

    private ReviewTaskService taskService;
    private ReviewReportRepository reportRepository;
    private ReviewFindingRepository findingRepository;
    private ReviewCommentRepository commentRepository;
    private ReviewHistoryQueryService service;

    @BeforeEach
    void setUp() {
        taskService = mock(ReviewTaskService.class);
        reportRepository = mock(ReviewReportRepository.class);
        findingRepository = mock(ReviewFindingRepository.class);
        commentRepository = mock(ReviewCommentRepository.class);
        service = new ReviewHistoryQueryService(taskService, reportRepository,
                findingRepository, commentRepository, new ObjectMapper());
    }

    @Test
    void shouldMapReportDetailsAndTaskContext() {
        ReviewReport report = report("DEGRADED", PublishStatus.PARTIAL, 2, 1,
                900L, PUBLISHED_AT);
        stubContext(report);
        stubDetailCounts(2, 1);

        ReviewReportResponse response = service.getReport(TASK_ID);

        assertEquals(TASK_ID, response.taskId());
        assertEquals("owner", response.owner());
        assertEquals("repo", response.repo());
        assertEquals(42, response.prNumber());
        assertEquals(SHA, response.commitSha());
        assertEquals("COMPLETED", response.taskStatus());
        assertEquals("DEGRADED", response.aiStatus());
        assertEquals("PARTIAL", response.publishStatus());
        assertEquals(2, response.findingCount());
        assertEquals(1, response.publishedCommentCount());
        assertEquals(900L, response.summaryCommentId());
        assertEquals(PUBLISHED_AT, response.publishedAt());
        assertEquals(CREATED, response.createdAt());
        assertEquals(UPDATED, response.updatedAt());
        verify(findingRepository).countByReportId(REPORT_ID);
        verify(commentRepository).countByReportId(REPORT_ID);
    }

    @Test
    void shouldMapNullSummaryAndPublishedAt() {
        ReviewReport report = report("COMPLETED", PublishStatus.FAILED, 0, 0,
                null, null);
        stubContext(report);
        stubDetailCounts(0, 0);

        ReviewReportResponse response = service.getReport(TASK_ID);

        assertNull(response.summaryCommentId());
        assertNull(response.publishedAt());
        assertEquals("COMPLETED", response.aiStatus());
        assertEquals("FAILED", response.publishStatus());
    }

    @Test
    void shouldPropagateMissingTaskWithoutQueryingHistory() {
        when(taskService.getTaskById(TASK_ID))
                .thenThrow(new TaskNotFoundException(TASK_ID));

        assertThrows(TaskNotFoundException.class,
                () -> service.getReport(TASK_ID));

        verifyNoInteractions(reportRepository, findingRepository,
                commentRepository);
    }

    @Test
    void shouldRejectMissingReportWithoutQueryingChildren() {
        when(taskService.getTaskById(TASK_ID)).thenReturn(task());
        when(reportRepository.findByTaskId(TASK_ID))
                .thenReturn(Optional.empty());

        assertThrows(ReviewHistoryNotFoundException.class,
                () -> service.getReport(TASK_ID));

        verifyNoInteractions(findingRepository, commentRepository);
    }

    @Test
    void shouldRejectDetailWhenFindingCountDiffers() {
        ReviewReport report = report(2, 1);
        stubContext(report);
        when(findingRepository.countByReportId(REPORT_ID)).thenReturn(1L);

        ReviewHistoryIncompleteException error = assertThrows(
                ReviewHistoryIncompleteException.class,
                () -> service.getReport(TASK_ID));

        assertTrue(error.getMessage().contains("findings"));
        verify(commentRepository, never()).countByReportId(REPORT_ID);
    }

    @Test
    void shouldRejectDetailWhenCommentCountDiffers() {
        ReviewReport report = report(2, 1);
        stubContext(report);
        stubDetailCounts(2, 0);

        ReviewHistoryIncompleteException error = assertThrows(
                ReviewHistoryIncompleteException.class,
                () -> service.getReport(TASK_ID));

        assertTrue(error.getMessage().contains("comments"));
    }

    @Test
    void shouldRejectFindingsPageWhenCountDiffers() {
        ReviewReport report = report(2, 0);
        stubContext(report);
        Page<ReviewFinding> page = new PageImpl<>(
                List.of(finding(0, "src/A.java", "[]")),
                PageRequest.of(0, 20), 1);
        when(findingRepository.findByReportId(eq(REPORT_ID),
                any(Pageable.class))).thenReturn(page);

        assertThrows(ReviewHistoryIncompleteException.class,
                () -> service.getFindings(TASK_ID, 1, 20));
    }

    @Test
    void shouldRejectCommentsPageWhenCountDiffers() {
        ReviewReport report = report(1, 2);
        stubContext(report);
        Page<ReviewComment> page = new PageImpl<>(
                List.of(comment(0, 501L)), PageRequest.of(0, 20), 1);
        when(commentRepository.findByReportId(eq(REPORT_ID),
                any(Pageable.class))).thenReturn(page);

        assertThrows(ReviewHistoryIncompleteException.class,
                () -> service.getComments(TASK_ID, 1, 20));
    }

    @Test
    void shouldReturnEmptyFindingsPage() {
        ReviewReport report = report(0, 0);
        stubContext(report);
        Page<ReviewFinding> page = new PageImpl<>(List.of(),
                PageRequest.of(0, 20), 0);
        when(findingRepository.findByReportId(eq(REPORT_ID),
                any(Pageable.class))).thenReturn(page);

        ReviewPageResponse<ReviewFindingResponse> response =
                service.getFindings(TASK_ID, 1, 20);

        assertTrue(response.items().isEmpty());
        assertEquals(1, response.page());
        assertEquals(20, response.size());
        assertEquals(0, response.totalItems());
        assertEquals(0, response.totalPages());
        assertFalse(response.hasNext());
    }

    @Test
    void shouldReturnEmptyCommentsPage() {
        ReviewReport report = report(0, 0);
        stubContext(report);
        Page<ReviewComment> page = new PageImpl<>(List.of(),
                PageRequest.of(0, 20), 0);
        when(commentRepository.findByReportId(eq(REPORT_ID),
                any(Pageable.class))).thenReturn(page);

        ReviewPageResponse<ReviewCommentResponse> response =
                service.getComments(TASK_ID, 1, 20);

        assertTrue(response.items().isEmpty());
        assertEquals(0, response.totalItems());
        assertEquals(0, response.totalPages());
        assertFalse(response.hasNext());
    }

    @Test
    void shouldMapFindingFieldsAndPreserveNullReferences() {
        ReviewReport report = report(2, 0);
        stubContext(report);
        Page<ReviewFinding> page = new PageImpl<>(
                List.of(finding(0, "src/A.java", "[\"CWE-89\",null]"),
                        finding(1, "src/B.java", "[]")),
                PageRequest.of(0, 20), 2);
        when(findingRepository.findByReportId(eq(REPORT_ID),
                any(Pageable.class))).thenReturn(page);

        ReviewPageResponse<ReviewFindingResponse> response =
                service.getFindings(TASK_ID, 1, 20);

        assertEquals(2, response.items().size());
        ReviewFindingResponse first = response.items().get(0);
        assertEquals(0, first.ordinal());
        assertEquals("SECURITY", first.category());
        assertEquals("HIGH", first.severity());
        assertEquals(0.94, first.confidence());
        assertEquals("CWE-89", first.ruleId());
        assertEquals("title", first.title());
        assertEquals("src/A.java", first.filePath());
        assertEquals(52, first.startLine());
        assertEquals(52, first.endLine());
        assertEquals("description", first.description());
        assertEquals("reason", first.reason());
        assertEquals("suggestion", first.suggestion());
        assertEquals("CWE-89", first.references().get(0));
        assertNull(first.references().get(1));
        assertTrue(response.items().get(1).references().isEmpty());
    }

    @Test
    void shouldTreatNullJsonNullAndBlankReferencesAsEmpty() {
        ReviewReport report = report(3, 0);
        stubContext(report);
        Page<ReviewFinding> page = new PageImpl<>(
                List.of(finding(0, "src/A.java", null),
                        finding(1, "src/B.java", "null"),
                        finding(2, "src/C.java", "")),
                PageRequest.of(0, 20), 3);
        when(findingRepository.findByReportId(eq(REPORT_ID),
                any(Pageable.class))).thenReturn(page);

        ReviewPageResponse<ReviewFindingResponse> response =
                service.getFindings(TASK_ID, 1, 20);

        assertTrue(response.items().get(0).references().isEmpty());
        assertTrue(response.items().get(1).references().isEmpty());
        assertTrue(response.items().get(2).references().isEmpty());
    }

    @Test
    void shouldRejectUnreadableReferences() {
        for (String invalid : List.of("not-json", "{}", "[1]", "\"text\"")) {
            ReviewReport report = report(1, 0);
            stubContext(report);
            Page<ReviewFinding> page = new PageImpl<>(
                    List.of(finding(0, "src/A.java", invalid)),
                    PageRequest.of(0, 20), 1);
            when(findingRepository.findByReportId(eq(REPORT_ID),
                    any(Pageable.class))).thenReturn(page);

            ReviewHistoryDataIntegrityException error = assertThrows(
                    ReviewHistoryDataIntegrityException.class,
                    () -> service.getFindings(TASK_ID, 1, 20));

            assertFalse(error.getMessage().contains(invalid));
            assertTrue(error.getMessage().contains("references_json"));
        }
    }

    @Test
    void shouldMapCommentWithNullGithubCommentId() {
        ReviewReport report = report(1, 1);
        stubContext(report);
        Page<ReviewComment> page = new PageImpl<>(
                List.of(comment(0, null)), PageRequest.of(0, 20), 1);
        when(commentRepository.findByReportId(eq(REPORT_ID),
                any(Pageable.class))).thenReturn(page);

        ReviewPageResponse<ReviewCommentResponse> response =
                service.getComments(TASK_ID, 1, 20);

        ReviewCommentResponse item = response.items().get(0);
        assertEquals(0, item.findingOrdinal());
        assertNull(item.githubCommentId());
        assertEquals("src/A.java", item.filePath());
        assertEquals(52, item.startLine());
        assertEquals(52, item.endLine());
        assertEquals(1, response.page());
        assertEquals(20, response.size());
        assertEquals(1, response.totalItems());
        assertEquals(1, response.totalPages());
        assertFalse(response.hasNext());
    }

    @Test
    void shouldUseOneBasedPageAndFixedOrdinalSort() {
        ReviewReport report = report(100, 0);
        stubContext(report);
        Page<ReviewFinding> page = new PageImpl<>(
                List.of(finding(2, "src/C.java", "[]")),
                PageRequest.of(1, 50), 100);
        when(findingRepository.findByReportId(eq(REPORT_ID),
                any(Pageable.class))).thenReturn(page);

        ReviewPageResponse<ReviewFindingResponse> response =
                service.getFindings(TASK_ID, 2, 50);

        ArgumentCaptor<Pageable> captor =
                ArgumentCaptor.forClass(Pageable.class);
        verify(findingRepository).findByReportId(eq(REPORT_ID),
                captor.capture());
        Pageable pageable = captor.getValue();
        assertEquals(1, pageable.getPageNumber());
        assertEquals(50, pageable.getPageSize());
        assertEquals(Sort.Direction.ASC,
                pageable.getSort().getOrderFor("ordinal").getDirection());

        assertEquals(2, response.page());
        assertEquals(50, response.size());
        assertEquals(100, response.totalItems());
        assertEquals(2, response.totalPages());
        assertFalse(response.hasNext());
    }

    @Test
    void shouldUseFixedFindingOrdinalSortForComments() {
        ReviewReport report = report(0, 1);
        stubContext(report);
        Page<ReviewComment> page = new PageImpl<>(
                List.of(comment(0, 501L)), PageRequest.of(0, 20), 1);
        when(commentRepository.findByReportId(eq(REPORT_ID),
                any(Pageable.class))).thenReturn(page);

        service.getComments(TASK_ID, 1, 20);

        ArgumentCaptor<Pageable> captor =
                ArgumentCaptor.forClass(Pageable.class);
        verify(commentRepository).findByReportId(eq(REPORT_ID),
                captor.capture());
        assertEquals(Sort.Direction.ASC,
                captor.getValue().getSort().getOrderFor("findingOrdinal")
                        .getDirection());
    }

    @Test
    void shouldReturnEmptyPageBeyondTheLastPage() {
        ReviewReport report = report(3, 0);
        stubContext(report);
        Page<ReviewFinding> page = new PageImpl<>(List.of(),
                PageRequest.of(4, 20), 3);
        when(findingRepository.findByReportId(eq(REPORT_ID),
                any(Pageable.class))).thenReturn(page);

        ReviewPageResponse<ReviewFindingResponse> response =
                service.getFindings(TASK_ID, 5, 20);

        assertTrue(response.items().isEmpty());
        assertEquals(5, response.page());
        assertEquals(3, response.totalItems());
        assertEquals(1, response.totalPages());
        assertFalse(response.hasNext());
    }

    @Test
    void shouldExposePendingPublishStatus() {
        ReviewReport report = report("COMPLETED", PublishStatus.PENDING, 1, 0,
                null, null);
        stubContext(report);
        stubDetailCounts(1, 0);

        ReviewReportResponse response = service.getReport(TASK_ID);

        assertEquals("PENDING", response.publishStatus());
    }

    @Test
    void shouldNotAddPerFindingQueries() {
        ReviewReport report = report(2, 0);
        stubContext(report);
        Page<ReviewFinding> page = new PageImpl<>(
                List.of(finding(0, "src/A.java", "[]"),
                        finding(1, "src/B.java", "[]")),
                PageRequest.of(0, 20), 2);
        when(findingRepository.findByReportId(eq(REPORT_ID),
                any(Pageable.class))).thenReturn(page);

        service.getFindings(TASK_ID, 1, 20);

        verify(findingRepository, times(1)).findByReportId(eq(REPORT_ID),
                any(Pageable.class));
        verifyNoMoreInteractions(findingRepository);
        verifyNoInteractions(commentRepository);
    }

    @Test
    void shouldUseRepeatableReadForEveryHistoryQuery() throws Exception {
        assertQueryIsolation("getReport", long.class);
        assertQueryIsolation("getFindings", long.class, int.class, int.class);
        assertQueryIsolation("getComments", long.class, int.class, int.class);
    }

    private static void assertQueryIsolation(String methodName,
                                             Class<?>... parameterTypes)
            throws Exception {
        Method method = ReviewHistoryQueryService.class
                .getMethod(methodName, parameterTypes);
        Transactional annotation = method.getAnnotation(Transactional.class);
        assertNotNull(annotation);
        assertTrue(annotation.readOnly());
        assertEquals(Isolation.REPEATABLE_READ, annotation.isolation());
    }

    private void stubContext(ReviewReport report) {
        when(taskService.getTaskById(TASK_ID)).thenReturn(task());
        when(reportRepository.findByTaskId(TASK_ID))
                .thenReturn(Optional.of(report));
    }

    private void stubDetailCounts(int findings, int comments) {
        when(findingRepository.countByReportId(REPORT_ID))
                .thenReturn((long) findings);
        when(commentRepository.countByReportId(REPORT_ID))
                .thenReturn((long) comments);
    }

    private static ReviewTask task() {
        ReviewTask task = new ReviewTask("owner", "repo", 42, SHA);
        ReflectionTestUtils.setField(task, "id", TASK_ID);
        task.setStatus(TaskStatus.COMPLETED);
        return task;
    }

    private static ReviewReport report(String aiStatus,
                                       PublishStatus publishStatus,
                                       int findingCount,
                                       int publishedCommentCount,
                                       Long summaryCommentId,
                                       LocalDateTime publishedAt) {
        ReviewReport report = new ReviewReport(TASK_ID, SHA, aiStatus,
                publishStatus, findingCount, publishedCommentCount,
                summaryCommentId, publishedAt);
        ReflectionTestUtils.setField(report, "id", REPORT_ID);
        ReflectionTestUtils.setField(report, "createdAt", CREATED);
        ReflectionTestUtils.setField(report, "updatedAt", UPDATED);
        return report;
    }

    private static ReviewReport report(int findingCount,
                                       int publishedCommentCount) {
        return report("COMPLETED", PublishStatus.PARTIAL, findingCount,
                publishedCommentCount, 900L, PUBLISHED_AT);
    }

    private static ReviewFinding finding(int ordinal, String filePath,
                                         String referencesJson) {
        return new ReviewFinding(REPORT_ID, ordinal, "SECURITY", "HIGH", 0.94,
                "CWE-89", "title", filePath, 52, 52, "description", "reason",
                "suggestion", referencesJson);
    }

    private static ReviewComment comment(int findingOrdinal,
                                         Long githubCommentId) {
        return new ReviewComment(REPORT_ID, findingOrdinal, githubCommentId,
                "src/A.java", 52, 52);
    }
}