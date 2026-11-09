package cn.codesentinel.task;

import cn.codesentinel.persistence.UniqueKeyViolationClassifier;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;

/**
 * Structured history of one received review result (Phase 10.3).
 *
 * <p>{@link #ensureHistory} idempotently writes the snapshot-derived
 * {@code review_report} and {@code review_finding} rows: the report is
 * created once per task (unique {@code task_id}) with PENDING publish
 * defaults, and every finding is written once per
 * {@code (report_id, ordinal)} with its 0-based snapshot index as the
 * ordinal. Row contents are immutable: existing rows are never updated
 * or deleted, so an interrupted or partial write is repaired by a later
 * {@code ensureHistory} call.
 *
 * <p>All length validation happens before the first INSERT; an input
 * that violates a limit, an unreadable snapshot, or a stored finding
 * count that no longer matches the snapshot raises
 * {@link ReviewHistoryConstraintException} and leaves no new rows.
 * Unique-key conflicts are only treated as idempotent success after a
 * fresh re-read confirms the target row exists; otherwise the original
 * exception propagates. Callers own the failure policy: Phase 9 keeps
 * its reception and publish semantics and logs the failure instead of
 * aborting.
 */
@Service
public class ReviewHistoryService {

    static final int MAX_RULE_ID_CHARS = 255;
    static final int MAX_TITLE_CHARS = 1000;
    static final int MAX_FILE_PATH_CHARS = 1024;
    static final int MAX_TEXT_BYTES = 65_535;

    static final String REASON_FIELD_LIMIT = "field_limit_exceeded";
    static final String REASON_PARSE_FAILED = "findings_parse_failed";
    static final String REASON_COUNT_MISMATCH = "finding_count_mismatch";
    static final String REASON_REFERENCES_SERIALIZATION =
            "references_serialization_failed";

    static final String REASON_OUTCOME_PARSE_FAILED = "outcome_parse_failed";
    static final String REASON_OUTCOME_STATUS_MISMATCH =
            "outcome_status_mismatch";
    static final String REASON_OUTCOME_STATUS_UNKNOWN =
            "outcome_status_unknown";
    static final String REASON_SUMMARY_STATUS_UNKNOWN =
            "summary_status_unknown";
    static final String REASON_OUTCOME_FINDINGS_MISMATCH =
            "outcome_findings_mismatch";
    static final String REASON_FINDING_IDENTITY_MISMATCH =
            "outcome_finding_identity_mismatch";
    static final String REASON_COMMENT_IDENTITY_MISMATCH =
            "comment_identity_mismatch";
    static final String REASON_REPORT_FINDINGS_INCOMPLETE =
            "report_findings_incomplete";
    static final String REASON_COMMIT_MISMATCH = "report_commit_mismatch";

    static final String STATUS_PUBLISHED = "PUBLISHED";
    static final String STATUS_SKIPPED = "SKIPPED";
    static final String STATUS_FAILED = "FAILED";

    private static final TypeReference<List<ReviewResultFinding>> FINDINGS_TYPE =
            new TypeReference<>() {
            };

    private static final Logger log =
            LoggerFactory.getLogger(ReviewHistoryService.class);

    private final ReviewReportRepository reportRepository;
    private final ReviewFindingRepository findingRepository;
    private final ReviewCommentRepository commentRepository;
    private final ObjectMapper objectMapper;

    public ReviewHistoryService(ReviewReportRepository reportRepository,
                                ReviewFindingRepository findingRepository,
                                ReviewCommentRepository commentRepository,
                                ObjectMapper objectMapper) {
        this.reportRepository = reportRepository;
        this.findingRepository = findingRepository;
        this.commentRepository = commentRepository;
        this.objectMapper = objectMapper;
    }

    public void ensureHistory(ReviewTask task, ReviewResultDelivery delivery) {
        Objects.requireNonNull(task, "task");
        Objects.requireNonNull(delivery, "delivery");

        List<PreparedFinding> prepared =
                prepareFindings(delivery.getFindingsJson());

        ReviewReport report = reportRepository.findByTaskId(task.getId())
                .orElse(null);
        boolean reportCreated = false;
        if (report == null) {
            report = insertReportSafely(task, delivery, prepared.size());
            reportCreated = true;
        } else {
            requireMatchingCommitSha(report, delivery);
            requireMatchingFindingCount(report, prepared.size());
        }

        Set<Integer> existingOrdinals = new HashSet<>();
        for (ReviewFinding row : findingRepository
                .findByReportIdOrderByOrdinalAsc(report.getId())) {
            existingOrdinals.add(row.getOrdinal());
        }

        int written = 0;
        for (PreparedFinding item : prepared) {
            if (existingOrdinals.contains(item.ordinal())) {
                continue;
            }
            insertFindingSafely(report.getId(), item);
            written++;
        }

        if (reportCreated || written > 0) {
            log.info(
                    "Review history ensured for task {} report {}: "
                            + "reportCreated={}, findingsWritten={}, "
                            + "findingsSkipped={}",
                    task.getId(), report.getId(), reportCreated, written,
                    prepared.size() - written);
        } else {
            log.debug(
                    "Review history already complete for task {} report {} "
                            + "({} findings)",
                    task.getId(), report.getId(), prepared.size());
        }
    }

    public void ensurePublishHistory(ReviewTask task,
                                     ReviewResultDelivery delivery) {
        Objects.requireNonNull(task, "task");
        Objects.requireNonNull(delivery, "delivery");
        if (delivery.getPublishStatus() == null
                || delivery.getPublishStatus() == PublishStatus.PENDING
                || delivery.getPublishOutcomeJson() == null) {
            log.debug(
                    "Publish history skipped for task {}: no terminal "
                            + "publication outcome",
                    task.getId());
            return;
        }

        PublishOutcome outcome = parsePublishOutcome(
                delivery.getPublishOutcomeJson());
        requireMatchingOutcomeStatus(outcome, delivery);

        ReviewReport report = reportRepository.findByTaskId(task.getId())
                .orElse(null);
        if (report == null) {
            log.error(
                    "Publish history skipped for task {} commit {}: "
                            + "structured report is missing",
                    task.getId(), delivery.getCommitSha());
            return;
        }
        requireMatchingCommitSha(report, delivery);

        List<ReviewFinding> findings = findingRepository
                .findByReportIdOrderByOrdinalAsc(report.getId());
        requireFindingsCoverSnapshot(report, findings, outcome);

        List<ReviewComment> existingComments = commentRepository
                .findByReportIdOrderByFindingOrdinalAsc(report.getId());
        requireExistingCommentsMatchFindings(existingComments, findings,
                outcome);

        Set<Integer> existingOrdinals = new HashSet<>();
        for (ReviewComment comment : existingComments) {
            existingOrdinals.add(comment.getFindingOrdinal());
        }

        int written = 0;
        for (int ordinal = 0;
                ordinal < outcome.comments().size(); ordinal++) {
            OutcomeComment item = outcome.comments().get(ordinal);
            if (!STATUS_PUBLISHED.equals(item.status())
                    || existingOrdinals.contains(ordinal)) {
                continue;
            }
            insertCommentSafely(report.getId(), ordinal, item);
            written++;
        }

        int commentCount = commentRepository
                .findByReportIdOrderByFindingOrdinalAsc(report.getId())
                .size();
        Long summaryCommentId = STATUS_PUBLISHED.equals(
                outcome.summary().status())
                        ? outcome.summary().commentId()
                        : null;
        report.applyPublishOutcome(delivery.getPublishStatus(),
                commentCount, summaryCommentId, delivery.getPublishedAt());
        reportRepository.save(report);
        log.info(
                "Publish history ensured for task {} report {}: status={}, "
                        + "commentsWritten={}, commentsTotal={}",
                task.getId(), report.getId(), delivery.getPublishStatus(),
                written, commentCount);
    }

    private void insertCommentSafely(Long reportId, int ordinal,
                                     OutcomeComment item) {
        ReviewComment row = new ReviewComment(reportId, ordinal,
                item.commentId(), item.filePath(), item.startLine(),
                item.endLine());
        try {
            commentRepository.saveAndFlush(row);
        } catch (DataIntegrityViolationException error) {
            if (!UniqueKeyViolationClassifier.isUniqueKeyViolation(error)) {
                throw error;
            }
            // A fresh re-read must find the same ordinal AND the same
            // identity that this call tried to insert. Finding only the
            // ordinal is not enough: a concurrent winner with a
            // different file/line identity must never be accepted as
            // this row's idempotent success.
            boolean identityConfirmed = commentRepository
                    .findByReportIdOrderByFindingOrdinalAsc(reportId)
                    .stream()
                    .anyMatch(existing -> existing.getFindingOrdinal()
                            == ordinal
                            && Objects.equals(existing.getFilePath(),
                                    item.filePath())
                            && existing.getStartLine() == item.startLine()
                            && existing.getEndLine() == item.endLine());
            if (!identityConfirmed) {
                throw error;
            }
        }
    }

    private void insertFindingSafely(Long reportId, PreparedFinding item) {
        ReviewFinding row = new ReviewFinding(reportId, item.ordinal(),
                item.finding().category(), item.finding().severity(),
                item.finding().confidence(), item.finding().ruleId(),
                item.finding().title(), item.finding().filePath(),
                item.finding().startLine(), item.finding().endLine(),
                item.finding().description(), item.finding().reason(),
                item.finding().suggestion(), item.referencesJson());
        try {
            findingRepository.saveAndFlush(row);
        } catch (DataIntegrityViolationException error) {
            if (!UniqueKeyViolationClassifier.isUniqueKeyViolation(error)) {
                throw error;
            }
            // Only a fresh re-read that finds the concurrent winner with
            // the complete identity may turn the unique-key conflict into
            // idempotent success. Ordinal alone is not sufficient.
            ReviewFinding existing = findingRepository
                    .findByReportIdOrderByOrdinalAsc(reportId).stream()
                    .filter(candidate -> candidate.getOrdinal()
                            == item.ordinal())
                    .findFirst()
                    .orElse(null);
            if (existing == null
                    || !hasSameFindingIdentity(existing, item)) {
                throw error;
            }
        }
    }

    private ReviewReport insertReportSafely(ReviewTask task,
                                            ReviewResultDelivery delivery,
                                            int findingCount) {
        ReviewReport report = new ReviewReport(task.getId(),
                delivery.getCommitSha(), delivery.getAiStatus(),
                PublishStatus.PENDING, findingCount, 0, null, null);
        try {
            return reportRepository.saveAndFlush(report);
        } catch (DataIntegrityViolationException error) {
            if (!UniqueKeyViolationClassifier.isUniqueKeyViolation(error)) {
                throw error;
            }
            ReviewReport existing = reportRepository.findByTaskId(
                    task.getId()).orElse(null);
            if (existing == null) {
                throw error;
            }
            requireMatchingCommitSha(existing, delivery);
            requireMatchingFindingCount(existing, findingCount);
            return existing;
        }
    }

    private List<PreparedFinding> prepareFindings(String findingsJson) {
        List<ReviewResultFinding> findings = parseFindings(findingsJson);
        List<PreparedFinding> prepared = new ArrayList<>(findings.size());
        for (int ordinal = 0; ordinal < findings.size(); ordinal++) {
            ReviewResultFinding finding = findings.get(ordinal);
            if (finding == null) {
                throw new ReviewHistoryConstraintException(
                        REASON_PARSE_FAILED + ": findings[ordinal=" + ordinal
                                + "] is null");
            }
            requireCharLimit(ordinal, "rule_id", finding.ruleId(),
                    MAX_RULE_ID_CHARS);
            requireCharLimit(ordinal, "title", finding.title(),
                    MAX_TITLE_CHARS);
            requireCharLimit(ordinal, "file_path", finding.filePath(),
                    MAX_FILE_PATH_CHARS);
            requireByteLimit(ordinal, "description", finding.description());
            requireByteLimit(ordinal, "reason", finding.reason());
            requireByteLimit(ordinal, "suggestion", finding.suggestion());
            String referencesJson = serializeReferences(finding.references());
            requireByteLimit(ordinal, "references_json", referencesJson);
            prepared.add(new PreparedFinding(ordinal, finding,
                    referencesJson));
        }
        return prepared;
    }

    private List<ReviewResultFinding> parseFindings(String findingsJson) {
        try {
            List<ReviewResultFinding> findings =
                    objectMapper.readValue(findingsJson, FINDINGS_TYPE);
            if (findings == null) {
                throw new ReviewHistoryConstraintException(
                        REASON_PARSE_FAILED);
            }
            return findings;
        } catch (JsonProcessingException error) {
            throw new ReviewHistoryConstraintException(
                    REASON_PARSE_FAILED);
        }
    }

    private String serializeReferences(List<String> references) {
        try {
            return objectMapper.writeValueAsString(references);
        } catch (JsonProcessingException error) {
            throw new ReviewHistoryConstraintException(
                    REASON_REFERENCES_SERIALIZATION);
        }
    }

    private static boolean hasSameFindingIdentity(ReviewFinding existing,
                                              PreparedFinding item) {
        ReviewResultFinding finding = item.finding();
        return existing.getOrdinal() == item.ordinal()
                && Objects.equals(existing.getCategory(), finding.category())
                && Objects.equals(existing.getSeverity(), finding.severity())
                && Objects.equals(existing.getConfidence(),
                        finding.confidence())
                && Objects.equals(existing.getRuleId(), finding.ruleId())
                && Objects.equals(existing.getTitle(), finding.title())
                && Objects.equals(existing.getFilePath(), finding.filePath())
                && Objects.equals(existing.getStartLine(),
                        finding.startLine())
                && Objects.equals(existing.getEndLine(), finding.endLine())
                && Objects.equals(existing.getDescription(),
                        finding.description())
                && Objects.equals(existing.getReason(), finding.reason())
                && Objects.equals(existing.getSuggestion(),
                        finding.suggestion())
                && Objects.equals(existing.getReferencesJson(),
                        item.referencesJson());
    }

    private static void requireMatchingFindingCount(ReviewReport report,
                                                    int expected) {
        if (report.getFindingCount() != expected) {
            throw new ReviewHistoryConstraintException(
                    REASON_COUNT_MISMATCH + ": report=" + report.getId()
                            + " stored=" + report.getFindingCount()
                            + " snapshot=" + expected);
        }
    }

    private static void requireCharLimit(int ordinal, String field,
                                         String value, int limit) {
        int length = value == null ? 0 : value.length();
        if (length > limit) {
            throw limitExceeded(ordinal, field, "chars", length, limit);
        }
    }

    private static void requireByteLimit(int ordinal, String field,
                                         String value) {
        int bytes = value == null
                ? 0
                : value.getBytes(StandardCharsets.UTF_8).length;
        if (bytes > MAX_TEXT_BYTES) {
            throw limitExceeded(ordinal, field, "utf8_bytes", bytes,
                    MAX_TEXT_BYTES);
        }
    }

    private static ReviewHistoryConstraintException limitExceeded(
            int ordinal, String field, String unit, int actual, int limit) {
        return new ReviewHistoryConstraintException(
                REASON_FIELD_LIMIT + ": findings[ordinal=" + ordinal + "]."
                        + field + " " + unit + "=" + actual
                        + " limit=" + limit);
    }

    private PublishOutcome parsePublishOutcome(String outcomeJson) {
        try {
            JsonNode root = objectMapper.readTree(outcomeJson);
            if (root == null || !root.isObject()) {
                throw new ReviewHistoryConstraintException(
                        REASON_OUTCOME_PARSE_FAILED);
            }
            String status = requireTextNode(root, "status");
            JsonNode summaryNode = root.get("summary");
            if (summaryNode == null || !summaryNode.isObject()) {
                throw new ReviewHistoryConstraintException(
                        REASON_OUTCOME_PARSE_FAILED);
            }
            String summaryStatus = requireTextNode(summaryNode, "status");
            validateSummaryStatus(summaryStatus);
            Long summaryCommentId = optionalLongNode(summaryNode,
                    "commentId");
            JsonNode commentsNode = root.get("comments");
            if (commentsNode == null || !commentsNode.isArray()) {
                throw new ReviewHistoryConstraintException(
                        REASON_OUTCOME_PARSE_FAILED);
            }
            List<OutcomeComment> comments =
                    new ArrayList<>(commentsNode.size());
            for (JsonNode node : commentsNode) {
                comments.add(parseOutcomeComment(node));
            }
            return new PublishOutcome(status,
                    new OutcomeSummary(summaryStatus, summaryCommentId),
                    comments);
        } catch (JsonProcessingException error) {
            throw new ReviewHistoryConstraintException(
                    REASON_OUTCOME_PARSE_FAILED);
        }
    }

    private static OutcomeComment parseOutcomeComment(JsonNode node) {
        if (node == null || !node.isObject()) {
            throw new ReviewHistoryConstraintException(
                    REASON_OUTCOME_PARSE_FAILED);
        }
        String status = requireTextNode(node, "status");
        if (!STATUS_PUBLISHED.equals(status)
                && !STATUS_SKIPPED.equals(status)
                && !STATUS_FAILED.equals(status)) {
            throw new ReviewHistoryConstraintException(
                    REASON_OUTCOME_STATUS_UNKNOWN + ": " + status);
        }
        return new OutcomeComment(status, requireTextNode(node, "filePath"),
                requireIntNode(node, "startLine"),
                requireIntNode(node, "endLine"),
                optionalLongNode(node, "commentId"));
    }

    private static String requireTextNode(JsonNode node, String field) {
        JsonNode value = node.get(field);
        if (value == null || !value.isTextual()) {
            throw new ReviewHistoryConstraintException(
                    REASON_OUTCOME_PARSE_FAILED);
        }
        return value.asText();
    }

    private static int requireIntNode(JsonNode node, String field) {
        JsonNode value = node.get(field);
        if (value == null || !value.isInt()) {
            throw new ReviewHistoryConstraintException(
                    REASON_OUTCOME_PARSE_FAILED);
        }
        return value.asInt();
    }

    private static Long optionalLongNode(JsonNode node, String field) {
        JsonNode value = node.get(field);
        if (value == null || value.isNull()) {
            return null;
        }
        if (!value.isIntegralNumber() || !value.canConvertToLong()) {
            throw new ReviewHistoryConstraintException(
                    REASON_OUTCOME_PARSE_FAILED);
        }
        return value.asLong();
    }

    private static void validateSummaryStatus(String status) {
        if (!STATUS_PUBLISHED.equals(status)
                && !STATUS_FAILED.equals(status)) {
            throw new ReviewHistoryConstraintException(
                    REASON_SUMMARY_STATUS_UNKNOWN + ": " + status);
        }
    }

    private static void requireMatchingOutcomeStatus(
            PublishOutcome outcome, ReviewResultDelivery delivery) {
        if (!delivery.getPublishStatus().name().equals(outcome.status())) {
            throw new ReviewHistoryConstraintException(
                    REASON_OUTCOME_STATUS_MISMATCH + ": outcome="
                            + outcome.status() + " delivery="
                            + delivery.getPublishStatus().name());
        }
    }

    private static void requireMatchingCommitSha(ReviewReport report,
                                                 ReviewResultDelivery delivery) {
        if (!Objects.equals(report.getCommitSha(),
                delivery.getCommitSha())) {
            throw new ReviewHistoryConstraintException(
                    REASON_COMMIT_MISMATCH + ": report="
                            + report.getCommitSha() + " delivery="
                            + delivery.getCommitSha());
        }
    }

    private static void requireFindingsCoverSnapshot(
            ReviewReport report, List<ReviewFinding> findings,
            PublishOutcome outcome) {
        if (findings.size() != report.getFindingCount()) {
            throw new ReviewHistoryConstraintException(
                    REASON_REPORT_FINDINGS_INCOMPLETE + ": report="
                            + report.getId() + " rows=" + findings.size()
                            + " stored=" + report.getFindingCount());
        }
        if (outcome.comments().size() != findings.size()) {
            throw new ReviewHistoryConstraintException(
                    REASON_OUTCOME_FINDINGS_MISMATCH + ": comments="
                            + outcome.comments().size() + " findings="
                            + findings.size());
        }
        for (int ordinal = 0; ordinal < findings.size(); ordinal++) {
            ReviewFinding finding = findings.get(ordinal);
            if (finding.getOrdinal() != ordinal) {
                throw new ReviewHistoryConstraintException(
                        REASON_OUTCOME_FINDINGS_MISMATCH
                                + ": ordinal gap at index=" + ordinal
                                + " actual=" + finding.getOrdinal());
            }
            OutcomeComment item = outcome.comments().get(ordinal);
            if (!Objects.equals(item.filePath(), finding.getFilePath())
                    || item.startLine() != finding.getStartLine()
                    || item.endLine() != finding.getEndLine()) {
                throw new ReviewHistoryConstraintException(
                        REASON_FINDING_IDENTITY_MISMATCH + ": ordinal="
                                + ordinal);
            }
            // Deterministic validation must finish before the first
            // INSERT, so an overlong path on any item cannot leave a
            // partial set of comment rows behind.
            requireCommentPathLimit(ordinal, item.filePath());
        }
    }

    private void requireExistingCommentsMatchFindings(
            List<ReviewComment> comments, List<ReviewFinding> findings,
            PublishOutcome outcome) {
        Set<Integer> seen = new HashSet<>();
        for (ReviewComment comment : comments) {
            int ordinal = comment.getFindingOrdinal();
            if (ordinal < 0 || ordinal >= findings.size()
                    || !seen.add(ordinal)) {
                throw new ReviewHistoryConstraintException(
                        REASON_COMMENT_IDENTITY_MISMATCH + ": ordinal="
                                + ordinal);
            }
            ReviewFinding finding = findings.get(ordinal);
            if (!Objects.equals(comment.getFilePath(),
                            finding.getFilePath())
                    || comment.getStartLine() != finding.getStartLine()
                    || comment.getEndLine() != finding.getEndLine()) {
                throw new ReviewHistoryConstraintException(
                        REASON_COMMENT_IDENTITY_MISMATCH + ": ordinal="
                                + ordinal);
            }
            if (!STATUS_PUBLISHED.equals(
                    outcome.comments().get(ordinal).status())) {
                log.warn(
                        "Existing review comment for report {} ordinal {} "
                                + "does not match a published outcome item",
                        comment.getReportId(), ordinal);
            }
        }
    }

    private static void requireCommentPathLimit(int ordinal,
                                                 String filePath) {
        int length = filePath == null ? 0 : filePath.length();
        if (length > MAX_FILE_PATH_CHARS) {
            throw new ReviewHistoryConstraintException(
                    REASON_FIELD_LIMIT + ": comments[ordinal=" + ordinal
                            + "].file_path chars=" + length
                            + " limit=" + MAX_FILE_PATH_CHARS);
        }
    }

    private record PublishOutcome(String status, OutcomeSummary summary,
                                  List<OutcomeComment> comments) {
    }

    private record OutcomeSummary(String status, Long commentId) {
    }

    private record OutcomeComment(String status, String filePath,
                                  int startLine, int endLine,
                                  Long commentId) {
    }

    private record PreparedFinding(int ordinal, ReviewResultFinding finding,
                                   String referencesJson) {
    }
}