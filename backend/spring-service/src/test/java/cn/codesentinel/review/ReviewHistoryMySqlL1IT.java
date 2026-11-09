package cn.codesentinel.review;

import cn.codesentinel.task.PublishStatus;
import cn.codesentinel.task.ReviewComment;
import cn.codesentinel.task.ReviewCommentRepository;
import cn.codesentinel.task.ReviewFinding;
import cn.codesentinel.task.ReviewFindingRepository;
import cn.codesentinel.task.ReviewHistoryService;
import cn.codesentinel.task.ReviewReport;
import cn.codesentinel.task.ReviewReportRepository;
import cn.codesentinel.task.ReviewResultDelivery;
import cn.codesentinel.task.ReviewResultDeliveryRepository;
import cn.codesentinel.task.ReviewResultPublishService;
import cn.codesentinel.task.ReviewResultRequest;
import cn.codesentinel.task.ReviewResultService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DataIntegrityViolationException;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Proxy;
import java.sql.SQLException;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

/**
 * Phase 10.6.3 L-1 integration verification.
 *
 * <p>All four entry points are exercised against the real Testcontainers
 * MySQL instance with a test-only repository proxy that injects a
 * non-unique-key {@link DataIntegrityViolationException}. The proxy's
 * first lookup is hidden so the service takes its insert path even though
 * the target row exists; all persistence and post-failure assertions use
 * the real database.
 *
 * <p>This is fault injection, not a naturally produced MySQL error. The
 * naturally produced 1062 cases are verified separately in
 * {@link ReviewHistoryMySqlConstraintIT}.
 */
class ReviewHistoryMySqlL1IT extends ReviewHistoryMySqlTestBase {

    @BeforeEach
    void clearDeliveries() {
        deliveryRepository.deleteAllInBatch();
    }

    @AfterEach
    void clearDeliveriesAfterTest() {
        deliveryRepository.deleteAllInBatch();
    }

    @Test
    void deliveryNonUniqueFailurePropagatesWithoutDuplicateReread() {
        long taskId = nextTaskId();
        String sha = commitSha(taskId);
        ReviewResultDelivery existing = deliveryRepository.saveAndFlush(
                new ReviewResultDelivery(taskId, sha, "COMPLETED", "[]",
                        PublishStatus.PENDING));
        when(reviewTaskService.getTaskById(taskId)).thenReturn(task(taskId));
        DataIntegrityViolationException failure = nonUniqueFailure();
        AtomicInteger lookups = new AtomicInteger();
        ReviewResultDeliveryRepository faulting = failingRepository(
                ReviewResultDeliveryRepository.class, deliveryRepository,
                "findByTaskIdAndCommitSha", lookups, failure);
        ReviewResultPublishService publishService =
                mock(ReviewResultPublishService.class);
        ReviewHistoryService historyService = mock(ReviewHistoryService.class);
        ReviewResultService service = new ReviewResultService(reviewTaskService,
                faulting, objectMapper, publishService, historyService);

        DataIntegrityViolationException thrown = assertThrows(
                DataIntegrityViolationException.class,
                () -> service.receiveResult(taskId,
                        new ReviewResultRequest(sha, "COMPLETED", List.of())));

        assertSame(failure, thrown);
        assertEquals(1, lookups.get());
        assertEquals(1, deliveryRepository.count());
        ReviewResultDelivery unchanged = deliveryRepository
                .findByTaskIdAndCommitSha(taskId, sha).orElseThrow();
        assertEquals(PublishStatus.PENDING, unchanged.getPublishStatus());
        assertNull(unchanged.getPublishedAt());
        verifyNoInteractions(publishService, historyService);
    }

    @Test
    void reportNonUniqueFailurePropagatesWithoutReread() throws Exception {
        long taskId = nextTaskId();
        ReportFixture fixture = reportOnlyFixture(taskId);
        DataIntegrityViolationException failure = nonUniqueFailure();
        AtomicInteger lookups = new AtomicInteger();
        ReviewReportRepository faulting = failingRepository(
                ReviewReportRepository.class, reportRepository,
                "findByTaskId", lookups, failure);
        ReviewHistoryService service = new ReviewHistoryService(faulting,
                findingRepository, commentRepository, objectMapper);

        DataIntegrityViolationException thrown = assertThrows(
                DataIntegrityViolationException.class,
                () -> service.ensureHistory(task(taskId),
                        delivery(taskId, List.of())));

        assertSame(failure, thrown);
        assertEquals(1, lookups.get());
        assertEquals(1, reportRepository.count());
        ReviewReport unchanged = reportRepository.findByTaskId(taskId)
                .orElseThrow();
        assertEquals(fixture.reportId(), unchanged.getId());
        assertEquals(PublishStatus.PENDING, unchanged.getPublishStatus());
        assertEquals(0, findingRepository.count());
    }

    @Test
    void findingNonUniqueFailurePropagatesWithoutReread() throws Exception {
        long taskId = nextTaskId();
        ReportFixture fixture = reportFixture(taskId, 1);
        DataIntegrityViolationException failure = nonUniqueFailure();
        AtomicInteger lookups = new AtomicInteger();
        ReviewFindingRepository faulting = failingRepository(
                ReviewFindingRepository.class, findingRepository,
                "findByReportIdOrderByOrdinalAsc", lookups, failure);
        ReviewHistoryService service = new ReviewHistoryService(reportRepository,
                faulting, commentRepository, objectMapper);

        DataIntegrityViolationException thrown = assertThrows(
                DataIntegrityViolationException.class,
                () -> service.ensureHistory(task(taskId),
                        delivery(taskId, findings(1))));

        assertSame(failure, thrown);
        assertEquals(1, lookups.get());
        assertEquals(1, findingRepository.count());
        ReviewFinding unchanged = findingRepository
                .findByReportIdOrderByOrdinalAsc(fixture.reportId()).get(0);
        assertEquals(0, unchanged.getOrdinal());
        assertEquals("src/File0.java", unchanged.getFilePath());
    }

    @Test
    void commentNonUniqueFailurePropagatesWithoutRereadOrReportUpdate()
            throws Exception {
        long taskId = nextTaskId();
        ReportFixture fixture = reportFixture(taskId, 1);
        ReviewComment existing = commentRepository.saveAndFlush(commentRow(
                fixture.reportId(), 0, 600L, "src/File0.java"));
        DataIntegrityViolationException failure = nonUniqueFailure();
        AtomicInteger lookups = new AtomicInteger();
        ReviewCommentRepository faulting = failingRepository(
                ReviewCommentRepository.class, commentRepository,
                "findByReportIdOrderByFindingOrdinalAsc", lookups, failure);
        ReviewHistoryService service = new ReviewHistoryService(reportRepository,
                findingRepository, faulting, objectMapper);
        ReviewResultDelivery delivery = publishedDelivery(taskId, findings(1),
                outcome("PARTIAL", "FAILED", null, List.of(
                        new OutcomeComment("PUBLISHED", "src/File0.java", 10,
                                10, 600L))),
                PublishStatus.PARTIAL, LocalDateTime.now());

        DataIntegrityViolationException thrown = assertThrows(
                DataIntegrityViolationException.class,
                () -> service.ensurePublishHistory(task(taskId), delivery));

        assertSame(failure, thrown);
        assertEquals(1, lookups.get());
        assertEquals(1, commentRepository.count());
        ReviewComment unchanged = commentRepository
                .findByReportIdOrderByFindingOrdinalAsc(fixture.reportId())
                .get(0);
        assertEquals(existing.getId(), unchanged.getId());
        assertEquals(0, unchanged.getFindingOrdinal());
        assertEquals(600L, unchanged.getGithubCommentId());
        assertEquals("src/File0.java", unchanged.getFilePath());
        ReviewReport report = reportRepository.findByTaskId(taskId)
                .orElseThrow();
        assertEquals(PublishStatus.PENDING, report.getPublishStatus());
        assertEquals(0, report.getPublishedCommentCount());
        assertNull(report.getPublishedAt());
        assertNull(report.getSummaryCommentId());
    }

    private ReportFixture reportOnlyFixture(long taskId) {
        ReviewReport report = reportRepository.saveAndFlush(report(taskId,
                commitSha(taskId), PublishStatus.PENDING, 0, 0, null, null));
        return new ReportFixture(report.getId());
    }

    private ReportFixture reportFixture(long taskId, int findingCount) {
        ReviewReport report = reportRepository.saveAndFlush(report(taskId,
                commitSha(taskId), PublishStatus.PENDING, findingCount, 0,
                null, null));
        findingRepository.saveAndFlush(findingRow(report.getId(), 0,
                "src/File0.java"));
        return new ReportFixture(report.getId());
    }

    @SuppressWarnings("unchecked")
    private static <T> T failingRepository(Class<T> type, T delegate,
                                           String lookupMethod,
                                           AtomicInteger lookups,
                                           DataIntegrityViolationException failure) {
        return (T) Proxy.newProxyInstance(type.getClassLoader(),
                new Class<?>[]{type},
                (proxy, method, args) -> {
                    if ("saveAndFlush".equals(method.getName())) {
                        throw failure;
                    }
                    if (lookupMethod.equals(method.getName())
                            && lookups.incrementAndGet() == 1) {
                        if (Optional.class.equals(method.getReturnType())) {
                            return Optional.empty();
                        }
                        if (List.class.isAssignableFrom(
                                method.getReturnType())) {
                            return List.of();
                        }
                    }
                    try {
                        return method.invoke(delegate, args);
                    } catch (InvocationTargetException error) {
                        throw error.getCause();
                    }
                });
    }

    private static DataIntegrityViolationException nonUniqueFailure() {
        return new DataIntegrityViolationException("not null",
                new SQLException("not null", "23000", 1048));
    }

    private record ReportFixture(long reportId) {
    }
}