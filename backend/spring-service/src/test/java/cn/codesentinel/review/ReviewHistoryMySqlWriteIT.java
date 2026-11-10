package cn.codesentinel.review;

import cn.codesentinel.task.PublishStatus;
import cn.codesentinel.task.ReviewComment;
import cn.codesentinel.task.ReviewCommentRepository;
import cn.codesentinel.task.ReviewFinding;
import cn.codesentinel.task.ReviewHistoryConstraintException;
import cn.codesentinel.task.ReviewHistoryService;
import cn.codesentinel.task.ReviewReport;
import cn.codesentinel.task.ReviewResultDelivery;
import cn.codesentinel.task.ReviewResultFinding;
import cn.codesentinel.task.ReviewTask;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DataIntegrityViolationException;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Proxy;
import java.time.LocalDateTime;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ReviewHistoryMySqlWriteIT extends ReviewHistoryMySqlTestBase {

    @Test
    void h1EnsureHistoryCreatesReportAndFindings() throws Exception {
        long taskId = nextTaskId();
        ReviewTask task = task(taskId);
        List<ReviewResultFinding> findings = findings(2);

        historyService.ensureHistory(task, delivery(taskId, findings));

        ReviewReport report = reportRepository.findByTaskId(taskId).orElseThrow();
        assertEquals(taskId, report.getTaskId());
        assertEquals(commitSha(taskId), report.getCommitSha());
        assertEquals("COMPLETED", report.getAiStatus());
        assertEquals(PublishStatus.PENDING, report.getPublishStatus());
        assertEquals(2, report.getFindingCount());
        assertEquals(0, report.getPublishedCommentCount());
        assertNull(report.getSummaryCommentId());
        assertNull(report.getPublishedAt());
        assertEquals(2, findingRepository
                .findByReportIdOrderByOrdinalAsc(report.getId()).size());
        assertEquals(0, commentRepository.count());
    }

    @Test
    void h2EnsurePublishHistoryWritesOnlyPublishedComments() throws Exception {
        long taskId = nextTaskId();
        ReviewTask task = task(taskId);
        List<ReviewResultFinding> findings = findings(2);
        historyService.ensureHistory(task, delivery(taskId, findings));
        LocalDateTime publishedAt =
                LocalDateTime.of(2026, 2, 3, 4, 5, 6, 654_321_000);
        String outcome = outcome("PARTIAL", "PUBLISHED", 900L, List.of(
                new OutcomeComment("PUBLISHED", "src/File0.java", 10, 10,
                        501L),
                new OutcomeComment("SKIPPED", "src/File1.java", 11, 11,
                        null)));
        ReviewResultDelivery delivery = publishedDelivery(taskId, findings,
                outcome, PublishStatus.PARTIAL, publishedAt);

        historyService.ensurePublishHistory(task, delivery);

        ReviewReport report = reportRepository.findByTaskId(taskId).orElseThrow();
        assertEquals(PublishStatus.PARTIAL, report.getPublishStatus());
        assertEquals(1, report.getPublishedCommentCount());
        assertEquals(900L, report.getSummaryCommentId());
        assertEquals(publishedAt, report.getPublishedAt());
        List<ReviewComment> comments = commentRepository
                .findByReportIdOrderByFindingOrdinalAsc(report.getId());
        assertEquals(1, comments.size());
        assertEquals(0, comments.get(0).getFindingOrdinal());
        assertEquals(501L, comments.get(0).getGithubCommentId());
    }

    @Test
    void h3PublishedWithoutCommentIdCreatesNullIdRow() throws Exception {
        long taskId = nextTaskId();
        ReviewTask task = task(taskId);
        List<ReviewResultFinding> findings = findings(1);
        historyService.ensureHistory(task, delivery(taskId, findings));
        String outcome = outcome("PARTIAL", "FAILED", null, List.of(
                new OutcomeComment("PUBLISHED", "src/File0.java", 10, 10,
                        null)));

        historyService.ensurePublishHistory(task,
                publishedDelivery(taskId, findings, outcome,
                        PublishStatus.PARTIAL, null));

        ReviewReport report = reportRepository.findByTaskId(taskId).orElseThrow();
        ReviewComment comment = commentRepository
                .findByReportIdOrderByFindingOrdinalAsc(report.getId()).get(0);
        assertNull(comment.getGithubCommentId());
        assertEquals(1, report.getPublishedCommentCount());
    }

    @Test
    void h4FailedAndSkippedItemsDoNotCreateComments() throws Exception {
        long taskId = nextTaskId();
        ReviewTask task = task(taskId);
        List<ReviewResultFinding> findings = findings(2);
        historyService.ensureHistory(task, delivery(taskId, findings));
        String outcome = outcome("FAILED", "FAILED", null, List.of(
                new OutcomeComment("SKIPPED", "src/File0.java", 10, 10, null),
                new OutcomeComment("FAILED", "src/File1.java", 11, 11, null)));

        historyService.ensurePublishHistory(task,
                publishedDelivery(taskId, findings, outcome,
                        PublishStatus.FAILED, null));

        ReviewReport report = reportRepository.findByTaskId(taskId).orElseThrow();
        assertEquals(PublishStatus.FAILED, report.getPublishStatus());
        assertEquals(0, report.getPublishedCommentCount());
        assertEquals(0, commentRepository.count());
    }

    @Test
    void h5SummaryOnlyDoesNotIncreaseCommentCount() throws Exception {
        long taskId = nextTaskId();
        ReviewTask task = task(taskId);
        List<ReviewResultFinding> findings = List.of();
        historyService.ensureHistory(task, delivery(taskId, findings));
        String outcome = outcome("PUBLISHED", "PUBLISHED", 900L, List.of());

        historyService.ensurePublishHistory(task,
                publishedDelivery(taskId, findings, outcome,
                        PublishStatus.PUBLISHED, LocalDateTime.now()));

        ReviewReport report = reportRepository.findByTaskId(taskId).orElseThrow();
        assertEquals(PublishStatus.PUBLISHED, report.getPublishStatus());
        assertEquals(0, report.getPublishedCommentCount());
        assertEquals(900L, report.getSummaryCommentId());
        assertEquals(0, commentRepository.count());
    }

    @Test
    void h6SummaryFillOnlyAndPublishedAtNeverCleared() throws Exception {
        long taskId = nextTaskId();
        LocalDateTime oldPublishedAt = LocalDateTime.of(2025, 1, 1, 0, 0);
        ReviewReport existing = report(taskId, commitSha(taskId),
                PublishStatus.PARTIAL, 1, 0, 800L, oldPublishedAt);
        reportRepository.saveAndFlush(existing);
        ReviewTask task = task(taskId);
        List<ReviewResultFinding> findings = findings(1);
        historyService.ensureHistory(task, delivery(taskId, findings));
        String outcome = outcome("FAILED", "FAILED", null, List.of(
                new OutcomeComment("SKIPPED", "src/File0.java", 10, 10, null)));

        historyService.ensurePublishHistory(task,
                publishedDelivery(taskId, findings, outcome,
                        PublishStatus.FAILED, null));

        ReviewReport report = reportRepository.findByTaskId(taskId).orElseThrow();
        assertEquals(800L, report.getSummaryCommentId());
        assertEquals(oldPublishedAt, report.getPublishedAt());
        assertEquals(PublishStatus.FAILED, report.getPublishStatus());
    }

    @Test
    void h7EmptyFindingsAndCommentsAreRepresentable() throws Exception {
        long taskId = nextTaskId();
        ReviewTask task = task(taskId);
        List<ReviewResultFinding> findings = List.of();
        historyService.ensureHistory(task, delivery(taskId, findings));
        historyService.ensurePublishHistory(task,
                publishedDelivery(taskId, findings,
                        outcome("FAILED", "FAILED", null, List.of()),
                        PublishStatus.FAILED, null));

        ReviewReport report = reportRepository.findByTaskId(taskId).orElseThrow();
        assertEquals(0, report.getFindingCount());
        assertEquals(0, report.getPublishedCommentCount());
        assertEquals(0, findingRepository.count());
        assertEquals(0, commentRepository.count());
    }

    @Test
    void h8PublishedAtIsCopiedFromDelivery() throws Exception {
        long taskId = nextTaskId();
        ReviewTask task = task(taskId);
        List<ReviewResultFinding> findings = findings(1);
        historyService.ensureHistory(task, delivery(taskId, findings));
        LocalDateTime publishedAt =
                LocalDateTime.of(2026, 6, 7, 8, 9, 10, 777_888_000);
        String outcome = outcome("PARTIAL", "FAILED", null, List.of(
                new OutcomeComment("PUBLISHED", "src/File0.java", 10, 10,
                        501L)));

        historyService.ensurePublishHistory(task,
                publishedDelivery(taskId, findings, outcome,
                        PublishStatus.PARTIAL, publishedAt));

        ReviewReport report = reportRepository.findByTaskId(taskId).orElseThrow();
        assertEquals(publishedAt, report.getPublishedAt());
        assertEquals(777_888_000, report.getPublishedAt().getNano());
    }

    @Test
    void i1RepeatedEnsureHistoryIsIdempotent() throws Exception {
        long taskId = nextTaskId();
        ReviewTask task = task(taskId);
        ReviewResultDelivery delivery = delivery(taskId, findings(2));
        historyService.ensureHistory(task, delivery);
        ReviewReport firstReport = reportRepository.findByTaskId(taskId)
                .orElseThrow();
        List<ReviewFinding> firstRows = findingRepository
                .findByReportIdOrderByOrdinalAsc(firstReport.getId());

        historyService.ensureHistory(task, delivery);

        ReviewReport secondReport = reportRepository.findByTaskId(taskId)
                .orElseThrow();
        List<ReviewFinding> secondRows = findingRepository
                .findByReportIdOrderByOrdinalAsc(secondReport.getId());
        assertEquals(firstReport.getId(), secondReport.getId());
        assertEquals(2, secondRows.size());
        assertEquals(firstRows.get(0).getId(), secondRows.get(0).getId());
        assertEquals(firstRows.get(1).getId(), secondRows.get(1).getId());
        assertEquals(firstRows.get(0).getCreatedAt(),
                secondRows.get(0).getCreatedAt());
    }

    @Test
    void i2EnsureHistorySelfHealsOnlyMissingFindings() throws Exception {
        long taskId = nextTaskId();
        ReviewTask task = task(taskId);
        ReviewResultDelivery delivery = delivery(taskId, findings(2));
        historyService.ensureHistory(task, delivery);
        ReviewReport report = reportRepository.findByTaskId(taskId).orElseThrow();
        List<ReviewFinding> before = findingRepository
                .findByReportIdOrderByOrdinalAsc(report.getId());
        ReviewFinding ordinal0 = before.stream()
                .filter(row -> row.getOrdinal() == 0).findFirst().orElseThrow();
        ReviewFinding ordinal1 = before.stream()
                .filter(row -> row.getOrdinal() == 1).findFirst().orElseThrow();
        findingRepository.deleteById(ordinal1.getId());

        historyService.ensureHistory(task, delivery);

        List<ReviewFinding> after = findingRepository
                .findByReportIdOrderByOrdinalAsc(report.getId());
        assertEquals(2, after.size());
        ReviewFinding restored0 = after.stream()
                .filter(row -> row.getOrdinal() == 0).findFirst().orElseThrow();
        ReviewFinding restored1 = after.stream()
                .filter(row -> row.getOrdinal() == 1).findFirst().orElseThrow();
        assertEquals(ordinal0.getId(), restored0.getId());
        assertEquals(ordinal0.getCreatedAt(), restored0.getCreatedAt());
        assertNotNull(restored1.getId());
    }

    @Test
    void i3CommitShaMismatchFailsWithoutWriting() throws Exception {
        long taskId = nextTaskId();
        ReviewReport existing = report(taskId, "c".repeat(40),
                PublishStatus.PENDING, 0, 0, null, null);
        reportRepository.saveAndFlush(existing);
        ReviewTask task = task(taskId);

        assertThrows(ReviewHistoryConstraintException.class,
                () -> historyService.ensureHistory(task,
                        delivery(taskId, List.of())));

        assertEquals(0, findingRepository.count());
        assertEquals(1, reportRepository.count());
    }

    @Test
    void i4RepeatedEnsurePublishHistoryIsIdempotent() throws Exception {
        long taskId = nextTaskId();
        ReviewTask task = task(taskId);
        List<ReviewResultFinding> findings = findings(1);
        historyService.ensureHistory(task, delivery(taskId, findings));
        ReviewResultDelivery delivery = publishedDelivery(taskId, findings,
                outcome("PARTIAL", "FAILED", null, List.of(
                        new OutcomeComment("PUBLISHED", "src/File0.java", 10,
                                10, 501L))),
                PublishStatus.PARTIAL, LocalDateTime.now());

        historyService.ensurePublishHistory(task, delivery);
        ReviewReport first = reportRepository.findByTaskId(taskId).orElseThrow();
        Long firstCommentId = commentRepository
                .findByReportIdOrderByFindingOrdinalAsc(first.getId())
                .get(0).getId();

        historyService.ensurePublishHistory(task, delivery);

        ReviewReport second = reportRepository.findByTaskId(taskId).orElseThrow();
        assertEquals(1, commentRepository.count());
        assertEquals(firstCommentId, commentRepository
                .findByReportIdOrderByFindingOrdinalAsc(second.getId())
                .get(0).getId());
        assertEquals(1, second.getPublishedCommentCount());
    }

    @Test
    void i5ExistingCommentIdentityConflictFailsWithoutOverwrite() throws Exception {
        long taskId = nextTaskId();
        ReviewTask task = task(taskId);
        List<ReviewResultFinding> findings = findings(1);
        historyService.ensureHistory(task, delivery(taskId, findings));
        ReviewReport report = reportRepository.findByTaskId(taskId).orElseThrow();
        ReviewComment conflicting = commentRepository.saveAndFlush(
                commentRow(report.getId(), 0, 501L, "src/Wrong.java"));
        ReviewResultDelivery delivery = publishedDelivery(taskId, findings,
                outcome("PARTIAL", "FAILED", null, List.of(
                        new OutcomeComment("PUBLISHED", "src/File0.java", 10,
                                10, 501L))),
                PublishStatus.PARTIAL, LocalDateTime.now());

        assertThrows(ReviewHistoryConstraintException.class,
                () -> historyService.ensurePublishHistory(task, delivery));

        ReviewComment unchanged = commentRepository.findById(conflicting.getId())
                .orElseThrow();
        assertEquals("src/Wrong.java", unchanged.getFilePath());
        assertEquals(1, commentRepository.count());
        assertEquals(PublishStatus.PENDING,
                reportRepository.findByTaskId(taskId).orElseThrow()
                        .getPublishStatus());
    }

    @Test
    void i6ConcurrentEnsureHistoryCreatesOneReportAndCompleteFindings()
            throws Exception {
        long taskId = nextTaskId();
        ReviewTask task = task(taskId);
        ReviewResultDelivery delivery = delivery(taskId, findings(2));

        runConcurrently(
                () -> historyService.ensureHistory(task, delivery),
                () -> historyService.ensureHistory(task, delivery));

        ReviewReport report = reportRepository.findByTaskId(taskId).orElseThrow();
        assertEquals(1, reportRepository.count());
        assertEquals(2, findingRepository
                .findByReportIdOrderByOrdinalAsc(report.getId()).size());
    }

    @Test
    void i7ConcurrentEnsurePublishHistoryCreatesOneCommentSet()
            throws Exception {
        long taskId = nextTaskId();
        ReviewTask task = task(taskId);
        List<ReviewResultFinding> findings = findings(1);
        historyService.ensureHistory(task, delivery(taskId, findings));
        ReviewResultDelivery delivery = publishedDelivery(taskId, findings,
                outcome("PARTIAL", "FAILED", null, List.of(
                        new OutcomeComment("PUBLISHED", "src/File0.java", 10,
                                10, 501L))),
                PublishStatus.PARTIAL, LocalDateTime.now());

        runConcurrently(
                () -> historyService.ensurePublishHistory(task, delivery),
                () -> historyService.ensurePublishHistory(task, delivery));

        ReviewReport report = reportRepository.findByTaskId(taskId).orElseThrow();
        assertEquals(1, commentRepository.count());
        assertEquals(1, report.getPublishedCommentCount());
    }

    @Test
    void i8DuplicateGithubIdWithMissingTargetOrdinalRethrows()
            throws Exception {
        long otherTaskId = nextTaskId();
        long targetTaskId = nextTaskId();
        ReviewReport other = reportRepository.saveAndFlush(report(otherTaskId,
                commitSha(otherTaskId), PublishStatus.PARTIAL, 1, 1, null,
                null));
        findingRepository.saveAndFlush(findingRow(other.getId(), 0,
                "src/Other.java"));
        commentRepository.saveAndFlush(commentRow(other.getId(), 0, 501L,
                "src/Other.java"));

        ReviewTask target = task(targetTaskId);
        List<ReviewResultFinding> findings = findings(2);
        historyService.ensureHistory(target, delivery(targetTaskId, findings));
        String outcome = outcome("PARTIAL", "FAILED", null, List.of(
                new OutcomeComment("PUBLISHED", "src/File0.java", 10, 10,
                        600L),
                new OutcomeComment("PUBLISHED", "src/File1.java", 11, 11,
                        501L)));
        ReviewResultDelivery delivery = publishedDelivery(targetTaskId,
                findings, outcome, PublishStatus.PARTIAL, LocalDateTime.now());

        assertThrows(DataIntegrityViolationException.class,
                () -> historyService.ensurePublishHistory(target, delivery));

        ReviewReport targetReport = reportRepository
                .findByTaskId(targetTaskId).orElseThrow();
        assertEquals(PublishStatus.PENDING, targetReport.getPublishStatus());
        assertEquals(0, targetReport.getPublishedCommentCount());
        assertNull(targetReport.getSummaryCommentId());
        assertNull(targetReport.getPublishedAt());
        List<ReviewComment> targetComments = commentRepository
                .findByReportIdOrderByFindingOrdinalAsc(targetReport.getId());
        assertEquals(1, targetComments.size());
        ReviewComment committed = targetComments.get(0);
        assertEquals(0, committed.getFindingOrdinal());
        assertEquals(600L, committed.getGithubCommentId());
        assertEquals("src/File0.java", committed.getFilePath());
        assertEquals(10, committed.getStartLine());
        assertEquals(10, committed.getEndLine());
    }

    @Test
    void t5EnsurePublishHistoryMidFailureRetainsCommittedCommentAndRetryConverges()
            throws Exception {
        long taskId = nextTaskId();
        ReviewTask task = task(taskId);
        List<ReviewResultFinding> findings = findings(2);
        historyService.ensureHistory(task, delivery(taskId, findings));

        LocalDateTime publishedAt =
                LocalDateTime.of(2026, 7, 8, 9, 10, 11, 222_333_000);
        String outcome = outcome("PARTIAL", "FAILED", null, List.of(
                new OutcomeComment("PUBLISHED", "src/File0.java", 10, 10,
                        600L),
                new OutcomeComment("PUBLISHED", "src/File1.java", 11, 11,
                        601L)));
        ReviewResultDelivery delivery = publishedDelivery(taskId, findings,
                outcome, PublishStatus.PARTIAL, publishedAt);

        AtomicBoolean failureArmed = new AtomicBoolean(true);
        AtomicInteger saveCalls = new AtomicInteger();
        ReviewCommentRepository faultingComments =
                (ReviewCommentRepository) Proxy.newProxyInstance(
                        ReviewCommentRepository.class.getClassLoader(),
                        new Class<?>[]{ReviewCommentRepository.class},
                        (proxy, method, args) -> {
                            if ("saveAndFlush".equals(method.getName())
                                    && args != null
                                    && args.length == 1
                                    && args[0] instanceof ReviewComment
                                    && failureArmed.get()
                                    && saveCalls.incrementAndGet() == 2) {
                                throw new DataIntegrityViolationException(
                                        "injected mid-publish failure");
                            }
                            try {
                                return method.invoke(commentRepository, args);
                            } catch (InvocationTargetException error) {
                                throw error.getCause();
                            }
                        });
        ReviewHistoryService faultingHistory = new ReviewHistoryService(
                reportRepository, findingRepository, faultingComments,
                objectMapper);

        assertThrows(DataIntegrityViolationException.class,
                () -> faultingHistory.ensurePublishHistory(task, delivery));

        ReviewReport afterFailure = reportRepository.findByTaskId(taskId)
                .orElseThrow();
        assertEquals(PublishStatus.PENDING, afterFailure.getPublishStatus());
        assertEquals(0, afterFailure.getPublishedCommentCount());
        assertNull(afterFailure.getSummaryCommentId());
        assertNull(afterFailure.getPublishedAt());
        List<ReviewComment> afterFailureComments = commentRepository
                .findByReportIdOrderByFindingOrdinalAsc(afterFailure.getId());
        assertEquals(1, afterFailureComments.size());
        ReviewComment firstCommitted = afterFailureComments.get(0);
        assertEquals(0, firstCommitted.getFindingOrdinal());
        assertEquals(600L, firstCommitted.getGithubCommentId());
        assertEquals("src/File0.java", firstCommitted.getFilePath());
        assertEquals(10, firstCommitted.getStartLine());
        assertEquals(10, firstCommitted.getEndLine());

        failureArmed.set(false);
        faultingHistory.ensurePublishHistory(task, delivery);

        ReviewReport afterRetry = reportRepository.findByTaskId(taskId)
                .orElseThrow();
        assertEquals(PublishStatus.PARTIAL, afterRetry.getPublishStatus());
        assertEquals(2, afterRetry.getPublishedCommentCount());
        assertNull(afterRetry.getSummaryCommentId());
        assertEquals(publishedAt, afterRetry.getPublishedAt());
        List<ReviewComment> afterRetryComments = commentRepository
                .findByReportIdOrderByFindingOrdinalAsc(afterRetry.getId());
        assertEquals(2, afterRetryComments.size());
        assertEquals(0, afterRetryComments.get(0).getFindingOrdinal());
        assertEquals(600L, afterRetryComments.get(0).getGithubCommentId());
        assertEquals(1, afterRetryComments.get(1).getFindingOrdinal());
        assertEquals(601L, afterRetryComments.get(1).getGithubCommentId());
        assertEquals("src/File1.java", afterRetryComments.get(1).getFilePath());
        assertEquals(11, afterRetryComments.get(1).getStartLine());
        assertEquals(11, afterRetryComments.get(1).getEndLine());
    }

    private static void runConcurrently(Runnable first, Runnable second)
            throws Exception {
        ExecutorService executor = Executors.newFixedThreadPool(2);
        CountDownLatch start = new CountDownLatch(1);
        try {
            Future<?> firstFuture = executor.submit(() -> {
                await(start);
                first.run();
            });
            Future<?> secondFuture = executor.submit(() -> {
                await(start);
                second.run();
            });
            start.countDown();
            firstFuture.get(30, TimeUnit.SECONDS);
            secondFuture.get(30, TimeUnit.SECONDS);
        } finally {
            executor.shutdownNow();
        }
    }

    private static void await(CountDownLatch latch) {
        try {
            latch.await(10, TimeUnit.SECONDS);
        } catch (InterruptedException error) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException(error);
        }
    }
}