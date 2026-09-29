package cn.codesentinel.task;

import cn.codesentinel.config.ReviewTaskProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ReviewTaskService {

    private static final Logger log = LoggerFactory.getLogger(ReviewTaskService.class);

    private final ReviewTaskRepository repository;
    private final ReviewTaskProducer producer;
    private final ReviewTaskProperties properties;

    public ReviewTaskService(ReviewTaskRepository repository,
                             ReviewTaskProducer producer,
                             ReviewTaskProperties properties) {
        this.repository = repository;
        this.producer = producer;
        this.properties = properties;
    }

    @Transactional
    public ReviewTask createTask(String owner, String repo, int prNumber, String commitSha) {
        ReviewTask existing = repository.findByOwnerAndRepoAndPrNumberAndCommitSha(
                owner, repo, prNumber, commitSha);
        if (existing != null) {
            log.info("Task already exists for owner={}, repo={}, pr={}, sha={}, taskId={}",
                    owner, repo, prNumber, commitSha, existing.getId());
            return existing;
        }

        ReviewTask task = new ReviewTask(owner, repo, prNumber, commitSha);
        ReviewTask saved = repository.save(task);
        log.info("Created review task: id={}, owner={}, repo={}, pr={}, sha={}",
                saved.getId(), owner, repo, prNumber, commitSha);
        producer.publish(saved);
        return saved;
    }

    public ReviewTask getTaskById(Long taskId) {
        return repository.findById(taskId)
                .orElseThrow(() -> new TaskNotFoundException(taskId));
    }

    @Transactional
    public ReviewTask updateStatus(Long taskId, TaskStatus status) {
        ReviewTask task = getTaskById(taskId);
        task.setStatus(status);
        ReviewTask saved = repository.save(task);
        log.info("Updated task {} status to {}", taskId, status);
        return saved;
    }

    @Transactional
    public ReviewTask markFailed(Long taskId, String errorMessage) {
        ReviewTask task = getTaskById(taskId);
        task.setStatus(TaskStatus.FAILED);
        task.setErrorMessage(errorMessage);
        ReviewTask saved = repository.save(task);
        log.info("Marked task {} as FAILED: {}", taskId, errorMessage);
        return saved;
    }

    @Transactional
    public TaskFailureResponse reportFailure(Long taskId, String errorMessage) {
        ReviewTask task = getTaskById(taskId);
        int currentRetry = task.getRetryCount();

        if (currentRetry < properties.maxRetries()) {
            task.setRetryCount(currentRetry + 1);
            task.setStatus(TaskStatus.PENDING);
            task.setErrorMessage(errorMessage);
            repository.save(task);
            log.info("Task {} retry: retryCount={}/{}, error={}",
                    taskId, task.getRetryCount(), properties.maxRetries(), errorMessage);
            return new TaskFailureResponse(true, taskId, task.getRetryCount(), TaskStatus.PENDING.name());
        }

        task.setStatus(TaskStatus.FAILED);
        task.setErrorMessage(errorMessage);
        repository.save(task);
        log.info("Task {} FAILED after {} retries: {}",
                taskId, task.getRetryCount(), errorMessage);
        return new TaskFailureResponse(false, taskId, task.getRetryCount(), TaskStatus.FAILED.name());
    }
}