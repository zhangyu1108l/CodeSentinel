package cn.codesentinel.task;

public class TaskNotFoundException extends RuntimeException {

    public TaskNotFoundException(Long taskId) {
        super("Task not found: id=" + taskId);
    }
}