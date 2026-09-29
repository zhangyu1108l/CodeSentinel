package cn.codesentinel.controller;

import cn.codesentinel.task.ReviewTaskService;
import cn.codesentinel.task.TaskFailureResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
public class ReviewTaskController {

    private static final Logger log = LoggerFactory.getLogger(ReviewTaskController.class);

    private final ReviewTaskService reviewTaskService;

    public ReviewTaskController(ReviewTaskService reviewTaskService) {
        this.reviewTaskService = reviewTaskService;
    }

    @PostMapping("/api/tasks/{taskId}/running")
    public ResponseEntity<Void> markRunning(@PathVariable Long taskId) {
        reviewTaskService.updateStatus(taskId, cn.codesentinel.task.TaskStatus.RUNNING);
        return ResponseEntity.ok().build();
    }

    @PostMapping("/api/tasks/{taskId}/complete")
    public ResponseEntity<Void> markCompleted(@PathVariable Long taskId) {
        reviewTaskService.updateStatus(taskId, cn.codesentinel.task.TaskStatus.COMPLETED);
        return ResponseEntity.ok().build();
    }

    @PostMapping("/api/tasks/{taskId}/failure")
    public ResponseEntity<TaskFailureResponse> reportFailure(
            @PathVariable Long taskId,
            @RequestBody Map<String, String> body) {
        String errorMessage = body.getOrDefault("errorMessage", "Unknown error");
        TaskFailureResponse response = reviewTaskService.reportFailure(taskId, errorMessage);
        return ResponseEntity.ok(response);
    }
}