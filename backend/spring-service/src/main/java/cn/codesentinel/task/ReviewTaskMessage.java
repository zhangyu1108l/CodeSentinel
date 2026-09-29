package cn.codesentinel.task;

import com.fasterxml.jackson.annotation.JsonProperty;

public record ReviewTaskMessage(
        @JsonProperty("taskId") Long taskId,
        @JsonProperty("owner") String owner,
        @JsonProperty("repo") String repo,
        @JsonProperty("prNumber") int prNumber,
        @JsonProperty("commitSha") String commitSha) {

    public static ReviewTaskMessage from(ReviewTask task) {
        return new ReviewTaskMessage(
                task.getId(),
                task.getOwner(),
                task.getRepo(),
                task.getPrNumber(),
                task.getCommitSha());
    }
}