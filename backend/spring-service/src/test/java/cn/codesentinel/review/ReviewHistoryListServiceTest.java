package cn.codesentinel.review;

import cn.codesentinel.task.PublishStatus;
import cn.codesentinel.task.ReviewReport;
import cn.codesentinel.task.ReviewReportRepository;
import cn.codesentinel.task.ReviewTask;
import cn.codesentinel.task.ReviewTaskRepository;
import cn.codesentinel.task.TaskStatus;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.LocalDateTime;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class ReviewHistoryListServiceTest {

    private static final long TASK_ID = 7L;
    private static final long REPORT_ID = 70L;
    private static final String SHA = "abc123def456";
    private static final LocalDateTime CREATED =
            LocalDateTime.of(2026, 1, 2, 3, 0);
    private static final LocalDateTime UPDATED =
            LocalDateTime.of(2026, 1, 2, 3, 4);
    private static final LocalDateTime PUBLISHED_AT =
            LocalDateTime.of(2026, 1, 2, 3, 4, 5);

    private ReviewReportRepository reportRepository;
    private ReviewTaskRepository taskRepository;
    private ReviewHistoryListService service;

    @BeforeEach
    void setUp() {
        reportRepository = mock(ReviewReportRepository.class);
        taskRepository = mock(ReviewTaskRepository.class);
        service = new ReviewHistoryListService(reportRepository,
                taskRepository);
    }

    @Test
    void shouldUseOneBasedPageAndFixedDescendingSort() {
        when(reportRepository.searchHistory(any(), any(), any(), any(),
                any(), any(), any(), any(), any(Pageable.class)))
                .thenReturn(new PageImpl<>(List.of(),
                        PageRequest.of(1, 50), 100));

        ReviewPageResponse<ReviewReportResponse> response =
                service.search(emptyFilter(), 2, 50);

        ArgumentCaptor<Pageable> captor =
                ArgumentCaptor.forClass(Pageable.class);
        verify(reportRepository).searchHistory(any(), any(), any(), any(),
                any(), any(), any(), any(), captor.capture());

        Pageable pageable = captor.getValue();
        assertEquals(1, pageable.getPageNumber());
        assertEquals(50, pageable.getPageSize());
        assertEquals(Sort.by(
                        Sort.Order.desc("createdAt"),
                        Sort.Order.desc("id")),
                pageable.getSort());

        assertEquals(2, response.page());
        assertEquals(50, response.size());
        assertEquals(100, response.totalItems());
        assertEquals(2, response.totalPages());
        assertFalse(response.hasNext());
        verifyNoInteractions(taskRepository);
    }

    @Test
    void shouldPassAllFiltersToRepository() {
        LocalDateTime from = LocalDateTime.of(2026, 1, 1, 0, 0);
        LocalDateTime to = LocalDateTime.of(2026, 2, 1, 0, 0);
        ReviewHistoryFilter filter = new ReviewHistoryFilter(
                " owner ", " repo ", 42, TaskStatus.COMPLETED,
                PublishStatus.PUBLISHED, " degraded ", from, to);
        when(reportRepository.searchHistory(any(), any(), any(), any(),
                any(), any(), any(), any(), any(Pageable.class)))
                .thenReturn(new PageImpl<>(List.of(),
                        PageRequest.of(0, 20), 0));

        service.search(filter, 1, 20);

        verify(reportRepository).searchHistory(
                "owner", "repo", 42, TaskStatus.COMPLETED,
                PublishStatus.PUBLISHED, "DEGRADED", from, to,
                PageRequest.of(0, 20, Sort.by(
                        Sort.Order.desc("createdAt"),
                        Sort.Order.desc("id"))));
    }

    @Test
    void shouldMapReportAndTaskFields() {
        ReviewTask task = task();
        ReviewReport report = report();
        when(reportRepository.searchHistory(any(), any(), any(), any(),
                any(), any(), any(), any(), any(Pageable.class)))
                .thenReturn(new PageImpl<>(List.of(report),
                        PageRequest.of(0, 20), 1));
        when(taskRepository.findAllById(any())).thenReturn(List.of(task));

        ReviewPageResponse<ReviewReportResponse> response =
                service.search(emptyFilter(), 1, 20);

        assertEquals(1, response.items().size());
        ReviewReportResponse item = response.items().get(0);
        assertEquals(TASK_ID, item.taskId());
        assertEquals("owner", item.owner());
        assertEquals("repo", item.repo());
        assertEquals(42, item.prNumber());
        assertEquals(SHA, item.commitSha());
        assertEquals("COMPLETED", item.taskStatus());
        assertEquals("DEGRADED", item.aiStatus());
        assertEquals("PARTIAL", item.publishStatus());
        assertEquals(2, item.findingCount());
        assertEquals(1, item.publishedCommentCount());
        assertEquals(900L, item.summaryCommentId());
        assertEquals(PUBLISHED_AT, item.publishedAt());
        assertEquals(CREATED, item.createdAt());
        assertEquals(UPDATED, item.updatedAt());
        assertEquals(1, response.totalItems());
        assertEquals(1, response.totalPages());
        assertFalse(response.hasNext());
    }

    @Test
    void shouldReturnEmptyPageWithoutLoadingTasks() {
        when(reportRepository.searchHistory(any(), any(), any(), any(),
                any(), any(), any(), any(), any(Pageable.class)))
                .thenReturn(new PageImpl<>(List.of(),
                        PageRequest.of(0, 20), 0));

        ReviewPageResponse<ReviewReportResponse> response =
                service.search(emptyFilter(), 1, 20);

        assertTrue(response.items().isEmpty());
        assertEquals(1, response.page());
        assertEquals(20, response.size());
        assertEquals(0, response.totalItems());
        assertEquals(0, response.totalPages());
        assertFalse(response.hasNext());
        verifyNoInteractions(taskRepository);
    }

    @Test
    void shouldReturnEmptyItemsBeyondLastPage() {
        when(reportRepository.searchHistory(any(), any(), any(), any(),
                any(), any(), any(), any(), any(Pageable.class)))
                .thenReturn(new PageImpl<>(List.of(),
                        PageRequest.of(4, 20), 3));

        ReviewPageResponse<ReviewReportResponse> response =
                service.search(emptyFilter(), 5, 20);

        assertTrue(response.items().isEmpty());
        assertEquals(5, response.page());
        assertEquals(3, response.totalItems());
        assertEquals(1, response.totalPages());
        assertFalse(response.hasNext());
        verifyNoInteractions(taskRepository);
    }

    @Test
    void shouldRejectInvalidPaginationBeforeQuerying() {
        for (int[] pagination : List.of(
                new int[]{0, 20}, new int[]{1, 0}, new int[]{1, 101})) {
            assertThrows(InvalidReviewHistoryPaginationException.class,
                    () -> service.search(emptyFilter(), pagination[0],
                            pagination[1]));
        }

        verifyNoInteractions(reportRepository, taskRepository);
    }

    @Test
    void shouldRejectReportWhoseTaskIsMissing() {
        when(reportRepository.searchHistory(any(), any(), any(), any(),
                any(), any(), any(), any(), any(Pageable.class)))
                .thenReturn(new PageImpl<>(List.of(report()),
                        PageRequest.of(0, 20), 1));
        when(taskRepository.findAllById(any())).thenReturn(List.of());

        ReviewHistoryDataIntegrityException error = assertThrows(
                ReviewHistoryDataIntegrityException.class,
                () -> service.search(emptyFilter(), 1, 20));

        assertTrue(error.getMessage().contains("task id=" + TASK_ID));
    }

    @Test
    void shouldNormalizeBlankStringFiltersToNull() {
        ReviewHistoryFilter filter = new ReviewHistoryFilter(
                "  ", "", null, null, null, "  ", null, null);

        assertNull(filter.owner());
        assertNull(filter.repo());
        assertNull(filter.aiStatus());
    }

    private static ReviewHistoryFilter emptyFilter() {
        return new ReviewHistoryFilter(null, null, null, null, null,
                null, null, null);
    }

    private static ReviewTask task() {
        ReviewTask task = new ReviewTask("owner", "repo", 42, SHA);
        ReflectionTestUtils.setField(task, "id", TASK_ID);
        task.setStatus(TaskStatus.COMPLETED);
        return task;
    }

    private static ReviewReport report() {
        ReviewReport report = new ReviewReport(TASK_ID, SHA, "DEGRADED",
                PublishStatus.PARTIAL, 2, 1, 900L, PUBLISHED_AT);
        ReflectionTestUtils.setField(report, "id", REPORT_ID);
        ReflectionTestUtils.setField(report, "createdAt", CREATED);
        ReflectionTestUtils.setField(report, "updatedAt", UPDATED);
        return report;
    }
}
