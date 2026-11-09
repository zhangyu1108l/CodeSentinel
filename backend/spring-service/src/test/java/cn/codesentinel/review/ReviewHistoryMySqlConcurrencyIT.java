package cn.codesentinel.review;

import cn.codesentinel.task.PublishStatus;
import cn.codesentinel.task.ReviewReport;
import cn.codesentinel.task.ReviewResultDelivery;
import cn.codesentinel.task.ReviewTask;
import org.junit.jupiter.api.Test;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.TransactionTemplate;

import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.when;

class ReviewHistoryMySqlConcurrencyIT extends ReviewHistoryMySqlTestBase {

    @Test
    void t1TestDatabaseUsesRepeatableRead() {
        assertEquals("REPEATABLE-READ", jdbcTemplate.queryForObject(
                "SELECT @@transaction_isolation", String.class));
    }

    @Test
    void t2RepeatableReadKeepsAStableSnapshotAcrossConcurrentInsert()
            throws Exception {
        long taskId = nextTaskId();
        ReviewReport report = reportRepository.saveAndFlush(report(taskId,
                commitSha(taskId), PublishStatus.PENDING, 1, 0, null, null));
        findingRepository.saveAndFlush(findingRow(report.getId(), 0,
                "src/File0.java"));
        ReviewTask task = task(taskId);
        when(reviewTaskService.getTaskById(taskId)).thenReturn(task);

        CountDownLatch firstRead = new CountDownLatch(1);
        CountDownLatch inserted = new CountDownLatch(1);
        ExecutorService executor = Executors.newSingleThreadExecutor();
        Future<?> writer = executor.submit(() -> {
            await(firstRead);
            findingRepository.saveAndFlush(findingRow(report.getId(), 1,
                    "src/File1.java"));
            inserted.countDown();
        });

        TransactionTemplate template =
                new TransactionTemplate(transactionManager);
        template.setIsolationLevel(
                TransactionDefinition.ISOLATION_REPEATABLE_READ);
        template.setReadOnly(true);
        AtomicInteger firstTotal = new AtomicInteger(-1);
        AtomicInteger secondTotal = new AtomicInteger(-1);
        try {
            template.executeWithoutResult(status -> {
                ReviewPageResponse<ReviewFindingResponse> first =
                        queryService.getFindings(taskId, 1, 20);
                firstTotal.set((int) first.totalItems());
                firstRead.countDown();
                await(inserted);
                ReviewPageResponse<ReviewFindingResponse> second =
                        queryService.getFindings(taskId, 1, 20);
                secondTotal.set((int) second.totalItems());
                assertEquals(first.totalItems(), second.totalItems());
                assertEquals(first.items().size(), second.items().size());
            });
            writer.get(30, TimeUnit.SECONDS);
        } finally {
            executor.shutdownNow();
        }

        assertEquals(1, firstTotal.get());
        assertEquals(1, secondTotal.get());
        assertEquals(2, findingRepository.count());
    }

    @Test
    void t3ReaderNeverObservesPartialFindingsDuringSelfHeal() throws Exception {
        long taskId = nextTaskId();
        ReviewTask task = task(taskId);
        ReviewReport report = reportRepository.saveAndFlush(report(taskId,
                commitSha(taskId), PublishStatus.PENDING, 2, 0, null, null));
        findingRepository.saveAndFlush(findingRow(report.getId(), 0,
                "src/File0.java"));
        ReviewResultDelivery delivery = delivery(taskId, findings(2));
        when(reviewTaskService.getTaskById(taskId)).thenReturn(task);

        ExecutorService executor = Executors.newFixedThreadPool(2);
        CountDownLatch start = new CountDownLatch(1);
        try {
            Future<?> writer = executor.submit(() -> {
                await(start);
                historyService.ensureHistory(task, delivery);
            });
            Future<Void> reader = executor.submit(() -> {
                await(start);
                for (int i = 0; i < 20; i++) {
                    try {
                        ReviewPageResponse<ReviewFindingResponse> page =
                                queryService.getFindings(taskId, 1, 20);
                        assertEquals(2, page.totalItems());
                        assertEquals(2, page.items().size());
                    } catch (ReviewHistoryIncompleteException expected) {
                        // The self-heal has not committed yet; 409/exception
                        // is the safe observable state.
                    }
                }
                return null;
            });
            start.countDown();
            writer.get(30, TimeUnit.SECONDS);
            reader.get(30, TimeUnit.SECONDS);
        } finally {
            executor.shutdownNow();
        }

        ReviewPageResponse<ReviewFindingResponse> finalPage =
                queryService.getFindings(taskId, 1, 20);
        assertEquals(2, finalPage.totalItems());
        assertEquals(2, finalPage.items().size());
        assertFalse(finalPage.items().isEmpty());
        assertTrue(finalPage.totalPages() >= 1);
    }

    private static void await(CountDownLatch latch) {
        try {
            if (!latch.await(10, TimeUnit.SECONDS)) {
                throw new IllegalStateException("timed out waiting for latch");
            }
        } catch (InterruptedException error) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException(error);
        }
    }
}