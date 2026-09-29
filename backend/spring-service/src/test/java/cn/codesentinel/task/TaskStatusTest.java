package cn.codesentinel.task;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

class TaskStatusTest {

    @Test
    void shouldHaveFourStatuses() {
        assertEquals(4, TaskStatus.values().length);
    }

    @Test
    void shouldHavePending() {
        assertEquals("PENDING", TaskStatus.PENDING.name());
    }

    @Test
    void shouldHaveRunning() {
        assertEquals("RUNNING", TaskStatus.RUNNING.name());
    }

    @Test
    void shouldHaveCompleted() {
        assertEquals("COMPLETED", TaskStatus.COMPLETED.name());
    }

    @Test
    void shouldHaveFailed() {
        assertEquals("FAILED", TaskStatus.FAILED.name());
    }

    @Test
    void shouldGetEnumByName() {
        assertEquals(TaskStatus.PENDING, TaskStatus.valueOf("PENDING"));
        assertEquals(TaskStatus.RUNNING, TaskStatus.valueOf("RUNNING"));
        assertEquals(TaskStatus.COMPLETED, TaskStatus.valueOf("COMPLETED"));
        assertEquals(TaskStatus.FAILED, TaskStatus.valueOf("FAILED"));
    }
}