package cn.codesentinel.review;

import cn.codesentinel.persistence.UniqueKeyViolationClassifier;
import cn.codesentinel.task.PublishStatus;
import cn.codesentinel.task.ReviewHistoryService;
import cn.codesentinel.task.ReviewResultDelivery;
import cn.codesentinel.task.ReviewResultDeliveryRepository;
import cn.codesentinel.task.ReviewResultPublishResult;
import cn.codesentinel.task.ReviewResultPublishService;
import cn.codesentinel.task.ReviewResultRequest;
import cn.codesentinel.task.ReviewResultResponse;
import cn.codesentinel.task.ReviewResultService;
import cn.codesentinel.task.ReviewTask;
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
import java.util.concurrent.Callable;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.CyclicBarrier;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Phase 10.6.3 real-MySQL race verification.
 *
 * <p>Two independent threads execute the real {@link ReviewResultService}
 * reception flow with the same task id and commit SHA. A test-only
 * repository proxy lets both threads complete their first lookup before
 * either insert, then delegates the actual {@code saveAndFlush} calls to
 * the real repository. The unique-key conflict is therefore produced by
 * MySQL, not constructed by the test.
 *
 * <p>The proxy only orchestrates timing and records the real
 * {@link DataIntegrityViolationException}; it never fabricates an
 * exception. The losing thread must enter the service catch block, re-read
 * the committed winner, and return an idempotent duplicate response.
 */
class ReviewResultDeliveryMySqlRaceIT extends ReviewHistoryMySqlTestBase {

    @BeforeEach
    void clearDeliveriesBeforeTest() {
        deliveryRepository.deleteAllInBatch();
    }

    @AfterEach
    void clearDeliveriesAfterTest() {
        deliveryRepository.deleteAllInBatch();
    }

    @Test
    void twoConcurrentReceiptsProduceOneDeliveryAndOnePublish()
            throws Exception {
        long taskId = nextTaskId();
        String commitSha = commitSha(taskId);
        when(reviewTaskService.getTaskById(taskId)).thenReturn(task(taskId));

        ReviewResultPublishService publishService =
                mock(ReviewResultPublishService.class);
        when(publishService.publish(any(ReviewTask.class),
                any(ReviewResultDelivery.class)))
                .thenReturn(new ReviewResultPublishResult(
                        PublishStatus.PUBLISHED,
                        "{\"status\":\"PUBLISHED\"}",
                        LocalDateTime.now()));
        ReviewHistoryService historyService = mock(ReviewHistoryService.class);

        CyclicBarrier lookupBarrier = new CyclicBarrier(2);
        AtomicInteger lookupCount = new AtomicInteger();
        List<DataIntegrityViolationException> duplicateFailures =
                new CopyOnWriteArrayList<>();
        List<Boolean> preLookupEmpties = new CopyOnWriteArrayList<>();
        ReviewResultDeliveryRepository racingRepository = racingRepository(
                deliveryRepository, lookupBarrier, lookupCount,
                preLookupEmpties, duplicateFailures);
        ReviewResultService service = new ReviewResultService(
                reviewTaskService, racingRepository, objectMapper,
                publishService, historyService);

        ExecutorService executor = Executors.newFixedThreadPool(2);
        CountDownLatch start = new CountDownLatch(1);
        try {
            Callable<ReviewResultResponse> receipt = () -> {
                if (!start.await(10, TimeUnit.SECONDS)) {
                    throw new IllegalStateException(
                            "timed out waiting for the race start");
                }
                return service.receiveResult(taskId,
                        new ReviewResultRequest(commitSha, "COMPLETED",
                                List.of()));
            };
            Future<ReviewResultResponse> first = executor.submit(receipt);
            Future<ReviewResultResponse> second = executor.submit(receipt);
            start.countDown();

            ReviewResultResponse firstResponse = first.get(30,
                    TimeUnit.SECONDS);
            ReviewResultResponse secondResponse = second.get(30,
                    TimeUnit.SECONDS);

            assertEquals(1, deliveryRepository.count());
            // Both threads saw an empty pre-insert lookup before racing.
            assertEquals(2, preLookupEmpties.size());
            assertTrue(preLookupEmpties.stream().allMatch(Boolean::booleanValue));
            // Two pre-insert lookups plus the losing thread's catch re-read.
            assertEquals(3, lookupCount.get());
            assertEquals(1, duplicateFailures.size());
            assertMySqlUniqueViolation(duplicateFailures.get(0));
            assertTrue(firstResponse.duplicate()
                    ^ secondResponse.duplicate());
            verify(publishService, times(1)).publish(any(ReviewTask.class),
                    any(ReviewResultDelivery.class));

            ReviewResultDelivery stored = deliveryRepository
                    .findByTaskIdAndCommitSha(taskId, commitSha)
                    .orElseThrow();
            assertEquals(PublishStatus.PUBLISHED, stored.getPublishStatus());
            assertNotNull(stored.getPublishedAt());
        } finally {
            executor.shutdownNow();
        }
    }

    @SuppressWarnings("unchecked")
    private static ReviewResultDeliveryRepository racingRepository(
            ReviewResultDeliveryRepository delegate,
            CyclicBarrier lookupBarrier,
            AtomicInteger lookupCount,
            List<Boolean> preLookupEmpties,
            List<DataIntegrityViolationException> duplicateFailures) {
        return (ReviewResultDeliveryRepository) Proxy.newProxyInstance(
                ReviewResultDeliveryRepository.class.getClassLoader(),
                new Class<?>[]{ReviewResultDeliveryRepository.class},
                (proxy, method, args) -> {
                    try {
                        if ("findByTaskIdAndCommitSha".equals(
                                method.getName())) {
                            Object result = method.invoke(delegate, args);
                            if (lookupCount.incrementAndGet() <= 2) {
                                preLookupEmpties.add(result instanceof Optional<?>
                                        optional && optional.isEmpty());
                                lookupBarrier.await(10, TimeUnit.SECONDS);
                            }
                            return result;
                        }
                        return method.invoke(delegate, args);
                    } catch (InvocationTargetException error) {
                        Throwable cause = error.getCause();
                        if ("saveAndFlush".equals(method.getName())
                                && cause instanceof
                                DataIntegrityViolationException integrity) {
                            duplicateFailures.add(integrity);
                        }
                        throw cause;
                    }
                });
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
