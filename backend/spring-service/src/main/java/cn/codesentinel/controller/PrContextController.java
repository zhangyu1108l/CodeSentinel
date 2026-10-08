package cn.codesentinel.controller;

import cn.codesentinel.prcontext.PrContextResponse;
import cn.codesentinel.prcontext.PrContextService;
import cn.codesentinel.task.TaskNotFoundException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class PrContextController {

    private static final Logger log =
            LoggerFactory.getLogger(PrContextController.class);

    private final PrContextService prContextService;

    public PrContextController(PrContextService prContextService) {
        this.prContextService = prContextService;
    }

    @GetMapping("/api/tasks/{taskId}/pr-context")
    public ResponseEntity<PrContextResponse> getPrContext(
            @PathVariable Long taskId) {
        return ResponseEntity.ok(prContextService.buildContext(taskId));
    }

    @ExceptionHandler(TaskNotFoundException.class)
    public ResponseEntity<Void> handleTaskNotFound(TaskNotFoundException e) {
        log.warn("PR context requested for a missing task: {}", e.getMessage());
        return ResponseEntity.notFound().build();
    }
}