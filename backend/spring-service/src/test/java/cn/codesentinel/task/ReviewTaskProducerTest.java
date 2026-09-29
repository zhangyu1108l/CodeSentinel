package cn.codesentinel.task;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.core.ListOperations;
import org.springframework.data.redis.core.StringRedisTemplate;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ReviewTaskProducerTest {

    private static final String TASK_QUEUE_KEY = "codesentinel:review:tasks";

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Mock
    private StringRedisTemplate redisTemplate;

    @Mock
    private ListOperations<String, String> listOperations;

    private ReviewTaskProducer producer;

    @BeforeEach
    void setUp() {
        producer = new ReviewTaskProducer(redisTemplate, objectMapper);
    }

    @Test
    void shouldPublishTaskToRedis() {
        when(redisTemplate.opsForList()).thenReturn(listOperations);
        when(listOperations.rightPush(anyString(), anyString())).thenReturn(1L);

        ReviewTask task = createTask(1L, "owner", "repo", 42, "abc123");
        producer.publish(task);

        ArgumentCaptor<String> jsonCaptor = ArgumentCaptor.forClass(String.class);
        verify(listOperations).rightPush(eq(TASK_QUEUE_KEY), jsonCaptor.capture());
        verify(redisTemplate).opsForList();

        assertNotNull(jsonCaptor.getValue());
    }

    @Test
    void shouldContainTaskIdInJson() throws Exception {
        when(redisTemplate.opsForList()).thenReturn(listOperations);
        when(listOperations.rightPush(anyString(), anyString())).thenReturn(1L);

        ReviewTask task = createTask(1L, "owner", "repo", 42, "abc123");
        producer.publish(task);

        ArgumentCaptor<String> jsonCaptor = ArgumentCaptor.forClass(String.class);
        verify(listOperations).rightPush(eq(TASK_QUEUE_KEY), jsonCaptor.capture());

        String json = jsonCaptor.getValue();
        assertTrue(json.contains("\"taskId\":1"));
        assertTrue(json.contains("\"owner\":\"owner\""));
        assertTrue(json.contains("\"repo\":\"repo\""));
        assertTrue(json.contains("\"prNumber\":42"));
        assertTrue(json.contains("\"commitSha\":\"abc123\""));
    }

    @Test
    void shouldUseCorrectRedisKey() {
        when(redisTemplate.opsForList()).thenReturn(listOperations);
        when(listOperations.rightPush(anyString(), anyString())).thenReturn(1L);

        ReviewTask task = createTask(2L, "org", "proj", 7, "def456");
        producer.publish(task);

        verify(listOperations).rightPush(eq(TASK_QUEUE_KEY), anyString());
    }

    @Test
    void shouldThrowExceptionWhenRedisFails() {
        when(redisTemplate.opsForList()).thenReturn(listOperations);
        doThrow(new RuntimeException("Redis connection failed"))
                .when(listOperations).rightPush(anyString(), anyString());

        ReviewTask task = createTask(3L, "owner", "repo", 1, "ghi789");

        RuntimeException ex = assertThrows(RuntimeException.class,
                () -> producer.publish(task));
        assertTrue(ex.getMessage().contains("Redis"));
    }

    @Test
    void shouldPublishValidJson() throws Exception {
        when(redisTemplate.opsForList()).thenReturn(listOperations);
        when(listOperations.rightPush(anyString(), anyString())).thenReturn(1L);

        ReviewTask task = createTask(5L, "testowner", "testrepo", 10, "sha12345");
        producer.publish(task);

        ArgumentCaptor<String> jsonCaptor = ArgumentCaptor.forClass(String.class);
        verify(listOperations).rightPush(eq(TASK_QUEUE_KEY), jsonCaptor.capture());

        ReviewTaskMessage parsed = objectMapper.readValue(jsonCaptor.getValue(), ReviewTaskMessage.class);
        assertEquals(5L, parsed.taskId());
        assertEquals("testowner", parsed.owner());
        assertEquals("testrepo", parsed.repo());
        assertEquals(10, parsed.prNumber());
        assertEquals("sha12345", parsed.commitSha());
    }

    private ReviewTask createTask(Long id, String owner, String repo, int prNumber, String commitSha) {
        ReviewTask task = new ReviewTask(owner, repo, prNumber, commitSha);
        task.setStatus(TaskStatus.PENDING);
        try {
            var field = ReviewTask.class.getDeclaredField("id");
            field.setAccessible(true);
            field.set(task, id);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
        return task;
    }
}