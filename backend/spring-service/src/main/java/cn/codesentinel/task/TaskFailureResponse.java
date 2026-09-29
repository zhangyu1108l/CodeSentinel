package cn.codesentinel.task;

public record TaskFailureResponse(boolean retry, Long taskId, int retryCount, String status) {
}