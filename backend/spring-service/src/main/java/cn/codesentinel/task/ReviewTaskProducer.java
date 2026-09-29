package cn.codesentinel.task;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

@Component
public class ReviewTaskProducer {

    private static final Logger log = LoggerFactory.getLogger(ReviewTaskProducer.class);

    private static final String TASK_QUEUE_KEY = "codesentinel:review:tasks";

    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;

    public ReviewTaskProducer(StringRedisTemplate redisTemplate, ObjectMapper objectMapper) {
        this.redisTemplate = redisTemplate;
        this.objectMapper = objectMapper;
    }

    public void publish(ReviewTask task) {
        ReviewTaskMessage message = ReviewTaskMessage.from(task);
        try {
            String json = objectMapper.writeValueAsString(message);
            redisTemplate.opsForList().rightPush(TASK_QUEUE_KEY, json);
            log.info("Published task to Redis: taskId={}, key={}", task.getId(), TASK_QUEUE_KEY);
        } catch (Exception e) {
            log.error("Failed to publish task {} to Redis", task.getId(), e);
            throw new RuntimeException("Failed to publish task to Redis: " + task.getId(), e);
        }
    }
}