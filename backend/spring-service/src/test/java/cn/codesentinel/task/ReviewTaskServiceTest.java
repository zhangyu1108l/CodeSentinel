package cn.codesentinel.task;

import cn.codesentinel.config.ReviewTaskProperties;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InOrder;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ReviewTaskServiceTest {

    private static final int MAX_RETRIES = 3;

    @Mock
    private ReviewTaskRepository repository;

    @Mock
    private ReviewTaskProducer producer;

    @Mock
    private ReviewTaskProperties properties;

    @InjectMocks
    private ReviewTaskService service;

    @Test
    void shouldCreateTask() {
        when(repository.findByOwnerAndRepoAndPrNumberAndCommitSha(
                "owner", "repo", 1, "abc123")).thenReturn(null);
        ReviewTask task = new ReviewTask("owner", "repo", 1, "abc123");
        when(repository.save(any(ReviewTask.class))).thenReturn(task);

        ReviewTask result = service.createTask("owner", "repo", 1, "abc123");

        assertNotNull(result);
        assertEquals("owner", result.getOwner());
        assertEquals("repo", result.getRepo());
        assertEquals(1, result.getPrNumber());
        assertEquals("abc123", result.getCommitSha());
        assertEquals(TaskStatus.PENDING, result.getStatus());
        assertEquals(0, result.getRetryCount());
        verify(repository).save(any(ReviewTask.class));
    }

    @Test
    void shouldSaveTaskWithPendingStatus() {
        when(repository.findByOwnerAndRepoAndPrNumberAndCommitSha(
                "org", "proj", 2, "def456")).thenReturn(null);
        ReviewTask task = new ReviewTask("org", "proj", 2, "def456");
        when(repository.save(any(ReviewTask.class))).thenReturn(task);

        ReviewTask result = service.createTask("org", "proj", 2, "def456");

        assertEquals(TaskStatus.PENDING, result.getStatus());
    }

    @Test
    void shouldSaveTaskWithZeroRetryCount() {
        when(repository.findByOwnerAndRepoAndPrNumberAndCommitSha(
                "org", "proj", 2, "def456")).thenReturn(null);
        ReviewTask task = new ReviewTask("org", "proj", 2, "def456");
        when(repository.save(any(ReviewTask.class))).thenReturn(task);

        ReviewTask result = service.createTask("org", "proj", 2, "def456");

        assertEquals(0, result.getRetryCount());
    }

    @Test
    void shouldPublishTaskAfterSave() {
        when(repository.findByOwnerAndRepoAndPrNumberAndCommitSha(
                "owner", "repo", 1, "abc123")).thenReturn(null);
        ReviewTask task = new ReviewTask("owner", "repo", 1, "abc123");
        when(repository.save(any(ReviewTask.class))).thenReturn(task);

        service.createTask("owner", "repo", 1, "abc123");

        InOrder inOrder = inOrder(repository, producer);
        inOrder.verify(repository).save(any(ReviewTask.class));
        inOrder.verify(producer).publish(any(ReviewTask.class));
    }

    @Test
    void shouldReturnExistingTaskOnDuplicate() {
        ReviewTask existing = new ReviewTask("owner", "repo", 1, "abc123");
        setTaskId(existing, 5L);
        when(repository.findByOwnerAndRepoAndPrNumberAndCommitSha(
                "owner", "repo", 1, "abc123")).thenReturn(existing);

        ReviewTask result = service.createTask("owner", "repo", 1, "abc123");

        assertEquals(5L, result.getId());
        assertEquals("owner", result.getOwner());
        verify(repository, never()).save(any(ReviewTask.class));
        verify(producer, never()).publish(any(ReviewTask.class));
    }

    @Test
    void shouldNotSaveOnDuplicate() {
        ReviewTask existing = new ReviewTask("owner", "repo", 1, "abc123");
        setTaskId(existing, 10L);
        when(repository.findByOwnerAndRepoAndPrNumberAndCommitSha(
                "owner", "repo", 1, "abc123")).thenReturn(existing);

        service.createTask("owner", "repo", 1, "abc123");

        verify(repository, never()).save(any(ReviewTask.class));
    }

    @Test
    void shouldNotPublishOnDuplicate() {
        ReviewTask existing = new ReviewTask("owner", "repo", 1, "abc123");
        setTaskId(existing, 10L);
        when(repository.findByOwnerAndRepoAndPrNumberAndCommitSha(
                "owner", "repo", 1, "abc123")).thenReturn(existing);

        service.createTask("owner", "repo", 1, "abc123");

        verify(producer, never()).publish(any(ReviewTask.class));
    }

    @Test
    void shouldCreateNewTaskForDifferentCommitSha() {
        when(repository.findByOwnerAndRepoAndPrNumberAndCommitSha(
                "owner", "repo", 1, "newSha")).thenReturn(null);
        ReviewTask task = new ReviewTask("owner", "repo", 1, "newSha");
        when(repository.save(any(ReviewTask.class))).thenReturn(task);

        ReviewTask result = service.createTask("owner", "repo", 1, "newSha");

        assertEquals("newSha", result.getCommitSha());
        verify(repository).save(any(ReviewTask.class));
    }

    @Test
    void shouldCreateNewTaskForDifferentRepo() {
        when(repository.findByOwnerAndRepoAndPrNumberAndCommitSha(
                "owner", "other-repo", 1, "abc123")).thenReturn(null);
        ReviewTask task = new ReviewTask("owner", "other-repo", 1, "abc123");
        when(repository.save(any(ReviewTask.class))).thenReturn(task);

        ReviewTask result = service.createTask("owner", "other-repo", 1, "abc123");

        assertEquals("other-repo", result.getRepo());
        verify(repository).save(any(ReviewTask.class));
    }

    @Test
    void shouldReportFailureAndRetry() {
        when(properties.maxRetries()).thenReturn(MAX_RETRIES);
        ReviewTask task = new ReviewTask("owner", "repo", 1, "abc123");
        task.setRetryCount(1);
        when(repository.findById(1L)).thenReturn(Optional.of(task));
        when(repository.save(any(ReviewTask.class))).thenReturn(task);

        TaskFailureResponse response = service.reportFailure(1L, "Handler error");

        assertTrue(response.retry());
        assertEquals(2, response.retryCount());
        assertEquals(TaskStatus.PENDING.name(), response.status());
        assertEquals(2, task.getRetryCount());
        assertEquals(TaskStatus.PENDING, task.getStatus());
        verify(repository).save(task);
    }

    @Test
    void shouldReportFailureAndExhaustRetries() {
        when(properties.maxRetries()).thenReturn(MAX_RETRIES);
        ReviewTask task = new ReviewTask("owner", "repo", 1, "abc123");
        task.setRetryCount(3);
        when(repository.findById(1L)).thenReturn(Optional.of(task));
        when(repository.save(any(ReviewTask.class))).thenReturn(task);

        TaskFailureResponse response = service.reportFailure(1L, "Fatal error");

        assertFalse(response.retry());
        assertEquals(3, response.retryCount());
        assertEquals(TaskStatus.FAILED.name(), response.status());
        assertEquals(TaskStatus.FAILED, task.getStatus());
        assertEquals("Fatal error", task.getErrorMessage());
        verify(repository).save(task);
    }

    @Test
    void shouldNotRetryCompletedTask() {
        ReviewTask task = new ReviewTask("owner", "repo", 1, "abc123");
        when(repository.findById(1L)).thenReturn(Optional.of(task));
        when(repository.save(any(ReviewTask.class))).thenReturn(task);

        service.updateStatus(1L, TaskStatus.COMPLETED);

        assertEquals(TaskStatus.COMPLETED, task.getStatus());
    }

    @Test
    void shouldGetTaskById() {
        ReviewTask task = new ReviewTask("owner", "repo", 1, "abc123");
        when(repository.findById(1L)).thenReturn(Optional.of(task));

        ReviewTask result = service.getTaskById(1L);

        assertNotNull(result);
        assertEquals("owner", result.getOwner());
    }

    @Test
    void shouldThrowExceptionWhenTaskNotFound() {
        when(repository.findById(99L)).thenReturn(Optional.empty());

        assertThrows(TaskNotFoundException.class,
                () -> service.getTaskById(99L));
    }

    @Test
    void shouldUpdateStatus() {
        ReviewTask task = new ReviewTask("owner", "repo", 1, "abc123");
        when(repository.findById(1L)).thenReturn(Optional.of(task));
        when(repository.save(any(ReviewTask.class))).thenReturn(task);

        ReviewTask result = service.updateStatus(1L, TaskStatus.RUNNING);

        assertEquals(TaskStatus.RUNNING, result.getStatus());
    }

    @Test
    void shouldMarkFailed() {
        ReviewTask task = new ReviewTask("owner", "repo", 1, "abc123");
        when(repository.findById(1L)).thenReturn(Optional.of(task));
        when(repository.save(any(ReviewTask.class))).thenReturn(task);

        ReviewTask result = service.markFailed(1L, "Connection timeout");

        assertEquals(TaskStatus.FAILED, result.getStatus());
        assertEquals("Connection timeout", result.getErrorMessage());
    }

    private void setTaskId(ReviewTask task, Long id) {
        try {
            var field = ReviewTask.class.getDeclaredField("id");
            field.setAccessible(true);
            field.set(task, id);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }
}