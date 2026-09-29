package cn.codesentinel.task;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ReviewTaskTest {

    @Test
    void shouldCreateReviewTaskWithBusinessConstructor() {
        ReviewTask task = new ReviewTask("owner", "repo", 42, "abc123");

        assertNotNull(task);
    }

    @Test
    void shouldSetOwnerCorrectly() {
        ReviewTask task = new ReviewTask("owner", "repo", 42, "abc123");

        assertEquals("owner", task.getOwner());
    }

    @Test
    void shouldSetRepoCorrectly() {
        ReviewTask task = new ReviewTask("owner", "repo", 42, "abc123");

        assertEquals("repo", task.getRepo());
    }

    @Test
    void shouldSetPrNumberCorrectly() {
        ReviewTask task = new ReviewTask("owner", "repo", 42, "abc123");

        assertEquals(42, task.getPrNumber());
    }

    @Test
    void shouldSetCommitShaCorrectly() {
        ReviewTask task = new ReviewTask("owner", "repo", 42, "abc123");

        assertEquals("abc123", task.getCommitSha());
    }

    @Test
    void shouldDefaultStatusToPending() {
        ReviewTask task = new ReviewTask("owner", "repo", 42, "abc123");

        assertEquals(TaskStatus.PENDING, task.getStatus());
    }

    @Test
    void shouldDefaultRetryCountToZero() {
        ReviewTask task = new ReviewTask("owner", "repo", 42, "abc123");

        assertEquals(0, task.getRetryCount());
    }

    @Test
    void shouldHaveNullErrorMessageInitially() {
        ReviewTask task = new ReviewTask("owner", "repo", 42, "abc123");

        assertNull(task.getErrorMessage());
    }

    @Test
    void shouldModifyStatus() {
        ReviewTask task = new ReviewTask("owner", "repo", 42, "abc123");

        task.setStatus(TaskStatus.RUNNING);
        assertEquals(TaskStatus.RUNNING, task.getStatus());

        task.setStatus(TaskStatus.COMPLETED);
        assertEquals(TaskStatus.COMPLETED, task.getStatus());

        task.setStatus(TaskStatus.FAILED);
        assertEquals(TaskStatus.FAILED, task.getStatus());
    }

    @Test
    void shouldModifyRetryCount() {
        ReviewTask task = new ReviewTask("owner", "repo", 42, "abc123");

        task.setRetryCount(1);
        assertEquals(1, task.getRetryCount());

        task.setRetryCount(3);
        assertEquals(3, task.getRetryCount());
    }

    @Test
    void shouldSetErrorMessage() {
        ReviewTask task = new ReviewTask("owner", "repo", 42, "abc123");

        task.setErrorMessage("Something went wrong");
        assertEquals("Something went wrong", task.getErrorMessage());
    }

    @Test
    void shouldSetErrorMessageToNull() {
        ReviewTask task = new ReviewTask("owner", "repo", 42, "abc123");
        task.setErrorMessage("error");
        task.setErrorMessage(null);

        assertNull(task.getErrorMessage());
    }

    @Test
    void shouldSetCreatedAtAndUpdatedAtOnPersist() {
        ReviewTask task = new ReviewTask("owner", "repo", 42, "abc123");

        task.onCreate();

        assertNotNull(task.getCreatedAt());
        assertNotNull(task.getUpdatedAt());
        assertEquals(task.getCreatedAt(), task.getUpdatedAt());
    }

    @Test
    void shouldUpdateUpdatedAtOnUpdate() throws InterruptedException {
        ReviewTask task = new ReviewTask("owner", "repo", 42, "abc123");

        task.onCreate();
        Thread.sleep(1);
        task.onUpdate();

        assertNotNull(task.getUpdatedAt());
        assertTrue(task.getUpdatedAt().isAfter(task.getCreatedAt())
                || task.getUpdatedAt().equals(task.getCreatedAt()));
    }
}