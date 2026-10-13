package cn.codesentinel.task;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Set;

/**
 * Reception of one AI review result (Phase 9.5.3B1) with synchronous
 * publication of the first receipt (Phase 9.5.3C).
 *
 * <p>Responsibilities: structural validation of the transport payload,
 * binding to the review task (the task must exist and the payload commit
 * SHA must match the task's SHA; owner/repo/PR are never taken from the
 * payload), durable idempotent persistence of the result snapshot, and
 * duplicate/conflict semantics on the (taskId, commitSha) idempotency
 * key. Only the successful first insert triggers one synchronous
 * publication attempt (see {@link ReviewResultPublishService}); a
 * duplicate receipt never publishes again and answers the stored
 * {@code publish_status}. The review task status is never changed here.
 *
 * <p>Publication failure semantics: the GitHub side effects of one
 * attempt are not transactional and are never considered rolled back by
 * this class; the publish orchestration contains its own failures and
 * records them on the delivery row. Only the delivery update itself may
 * still fail after external side effects happened. The unique key is
 * the single-flight guard, so a concurrent duplicate can never reach
 * the publish call; the publish attempt itself runs outside any service
 * level transaction.
 *
 * <p>Deliberately not wrapped in one service-level transaction: each
 * repository call is transactional on its own, so a unique-key race
 * ({@link DataIntegrityViolationException}) is caught after its own
 * transaction has rolled back cleanly and can be answered
 * deterministically instead of contaminating a rollback-only
 * transaction. The duplicate pre-check and the insert are therefore two
 * transactions by design; the unique key is the real guard.
 *
 * <p>Known offline-test limitation: the unique-key / transaction /
 * concurrency semantics cannot be verified without a real MySQL (no
 * H2/Testcontainers); unit tests cover the service branches only.
 */
@Service
public class ReviewResultService {

    static final String STATUS_COMPLETED = "COMPLETED";
    static final String STATUS_DEGRADED = "DEGRADED";

    private static final Set<String> ALLOWED_STATUSES =
            Set.of(STATUS_COMPLETED, STATUS_DEGRADED);
    private static final Set<String> ALLOWED_CATEGORIES = Set.of(
            "BUG", "SECURITY", "PERFORMANCE", "QUALITY");
    private static final Set<String> ALLOWED_SEVERITIES = Set.of(
            "CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO");

    private static final Logger log =
            LoggerFactory.getLogger(ReviewResultService.class);

    private final ReviewTaskService reviewTaskService;
    private final ReviewResultDeliveryRepository repository;
    private final ObjectMapper objectMapper;
    private final ReviewResultPublishService publishService;

    public ReviewResultService(ReviewTaskService reviewTaskService,
                               ReviewResultDeliveryRepository repository,
                               ObjectMapper objectMapper,
                               ReviewResultPublishService publishService) {
        this.reviewTaskService = reviewTaskService;
        this.repository = repository;
        this.objectMapper = objectMapper;
        this.publishService = publishService;
    }

    public ReviewResultResponse receiveResult(Long taskId,
                                              ReviewResultRequest request) {
        validateRequest(request);
        ReviewTask task = reviewTaskService.getTaskById(taskId);
        if (!task.getCommitSha().equals(request.commitSha())) {
            throw new ReviewResultRejectedException(
                    409, "commitSha does not match the review task");
        }

        String findingsJson = serializeFindings(request.findings());
        ReviewResultDelivery existing = repository
                .findByTaskIdAndCommitSha(taskId, request.commitSha())
                .orElse(null);
        if (existing != null) {
            return duplicateOrConflict(existing, request.status(),
                    findingsJson);
        }

        ReviewResultDelivery delivery = new ReviewResultDelivery(
                taskId, request.commitSha(), request.status(), findingsJson,
                PublishStatus.PENDING);
        ReviewResultDelivery saved;
        try {
            saved = repository.saveAndFlush(delivery);
        } catch (DataIntegrityViolationException e) {
            log.warn(
                    "Concurrent duplicate result delivery for task {} commit {}",
                    taskId, request.commitSha());
            return repository
                    .findByTaskIdAndCommitSha(taskId, request.commitSha())
                    .map(other -> duplicateOrConflict(other, request.status(),
                            findingsJson))
                    .orElseThrow(() -> new ReviewResultRejectedException(
                            409,
                            "a concurrent result delivery is in progress; "
                                    + "retry"));
        }
        log.info(
                "Stored review result for task {} commit {}: status={}, findings={}",
                taskId, request.commitSha(), request.status(),
                request.findings().size());
        return publishFirstReceipt(task, saved);
    }

    /**
     * One synchronous publication attempt for the just-inserted first
     * receipt. The publish service contains its own failures; only the
     * delivery update can still fail here, after external side effects
     * may already exist (they are never pretended to be rolled back).
     */
    private ReviewResultResponse publishFirstReceipt(ReviewTask task,
                                                     ReviewResultDelivery saved) {
        ReviewResultPublishResult publishResult =
                publishService.publish(task, saved);
        saved.recordPublishOutcome(publishResult.status(),
                publishResult.outcomeJson(), publishResult.publishedAt());
        repository.save(saved);
        log.info(
                "Review result for task {} commit {} finalized: publishStatus={}",
                saved.getTaskId(), saved.getCommitSha(),
                saved.getPublishStatus());
        return new ReviewResultResponse(saved.getTaskId(),
                saved.getCommitSha(), false,
                saved.getPublishStatus().name(), saved.getReceivedAt());
    }

    private ReviewResultResponse duplicateOrConflict(
            ReviewResultDelivery existing, String requestStatus,
            String findingsJson) {
        if (!existing.getAiStatus().equals(requestStatus)
                || !existing.getFindingsJson().equals(findingsJson)) {
            throw new ReviewResultRejectedException(409,
                    "a different result already exists for this task and "
                            + "commit");
        }
        log.info(
                "Duplicate review result for task {} commit {}: publishStatus={}",
                existing.getTaskId(), existing.getCommitSha(),
                existing.getPublishStatus());
        return new ReviewResultResponse(existing.getTaskId(),
                existing.getCommitSha(), true,
                existing.getPublishStatus().name(),
                existing.getReceivedAt());
    }

    private void validateRequest(ReviewResultRequest request) {
        if (request == null) {
            throw new ReviewResultRejectedException(422,
                    "request body is required");
        }
        if (request.commitSha() == null || request.commitSha().isBlank()) {
            throw new ReviewResultRejectedException(422,
                    "commit_sha must not be blank");
        }
        if (request.status() == null
                || !ALLOWED_STATUSES.contains(request.status())) {
            throw new ReviewResultRejectedException(422,
                    "status must be COMPLETED or DEGRADED");
        }
        List<ReviewResultFinding> findings = request.findings();
        if (findings == null) {
            throw new ReviewResultRejectedException(422,
                    "findings must not be null");
        }
        for (int index = 0; index < findings.size(); index++) {
            validateFinding(index, findings.get(index));
        }
    }

    private void validateFinding(int index, ReviewResultFinding finding) {
        if (finding == null) {
            throw rejectFinding(index, "entry must not be null");
        }
        if (finding.category() == null
                || !ALLOWED_CATEGORIES.contains(finding.category())) {
            throw rejectFinding(index,
                    "category must be BUG, SECURITY, PERFORMANCE or QUALITY");
        }
        if (finding.severity() == null
                || !ALLOWED_SEVERITIES.contains(finding.severity())) {
            throw rejectFinding(index,
                    "severity must be CRITICAL, HIGH, MEDIUM, LOW or INFO");
        }
        if (finding.confidence() == null
                || finding.confidence() < 0.0
                || finding.confidence() > 1.0) {
            throw rejectFinding(index,
                    "confidence must be between 0.0 and 1.0");
        }
        requireText(index, "rule_id", finding.ruleId());
        requireText(index, "title", finding.title());
        requireText(index, "file_path", finding.filePath());
        requireText(index, "description", finding.description());
        requireText(index, "reason", finding.reason());
        requireText(index, "suggestion", finding.suggestion());
        if (finding.startLine() == null || finding.startLine() < 1) {
            throw rejectFinding(index,
                    "start_line must be a positive line number");
        }
        if (finding.endLine() == null
                || finding.endLine() < finding.startLine()) {
            throw rejectFinding(index,
                    "end_line must not be smaller than start_line");
        }
        if (finding.references() == null) {
            throw rejectFinding(index,
                    "references must be a list (possibly empty)");
        }
    }

    private static ReviewResultRejectedException rejectFinding(int index,
                                                               String reason) {
        return new ReviewResultRejectedException(422,
                "findings[" + index + "] " + reason);
    }

    private static void requireText(int index, String field, String value) {
        if (value == null || value.isBlank()) {
            throw rejectFinding(index, field + " must not be blank");
        }
    }

    /**
     * Canonical serialization of the finding list: it doubles as the
     * stored replay snapshot and as the deterministic comparison value
     * for "same idempotency key, same payload" duplicate detection.
     */
    private String serializeFindings(List<ReviewResultFinding> findings) {
        try {
            return objectMapper.writeValueAsString(findings);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException(
                    "Failed to serialize result findings", e);
        }
    }
}