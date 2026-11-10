package cn.codesentinel.review;

import cn.codesentinel.task.ReviewComment;
import cn.codesentinel.task.ReviewCommentRepository;
import cn.codesentinel.task.ReviewFinding;
import cn.codesentinel.task.ReviewFindingRepository;
import cn.codesentinel.task.ReviewReport;
import cn.codesentinel.task.ReviewReportRepository;
import cn.codesentinel.task.ReviewTask;
import cn.codesentinel.task.ReviewTaskService;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;

/**
 * Read-only query service of the structured review history (Phase 10.5).
 *
 * <p>Every use case runs in one read-only transaction: task, report,
 * page content and page count are read from one database snapshot. The
 * report's absolute counts are the consistency gate - findings and
 * comments are returned only when their actual row counts match
 * {@code finding_count} / {@code published_comment_count}. A mismatch
 * raises {@link ReviewHistoryIncompleteException} instead of exposing
 * partial history.
 *
 * <p>The service never reads {@code review_result_delivery}, never
 * writes data and never creates a JPA relationship.
 */
@Service
public class ReviewHistoryQueryService {

    public static final int MAX_PAGE_SIZE = 100;

    private final ReviewTaskService reviewTaskService;
    private final ReviewReportRepository reportRepository;
    private final ReviewFindingRepository findingRepository;
    private final ReviewCommentRepository commentRepository;
    private final ObjectMapper objectMapper;

    public ReviewHistoryQueryService(ReviewTaskService reviewTaskService,
                                     ReviewReportRepository reportRepository,
                                     ReviewFindingRepository findingRepository,
                                     ReviewCommentRepository commentRepository,
                                     ObjectMapper objectMapper) {
        this.reviewTaskService = reviewTaskService;
        this.reportRepository = reportRepository;
        this.findingRepository = findingRepository;
        this.commentRepository = commentRepository;
        this.objectMapper = objectMapper;
    }

    @Transactional(readOnly = true,
            isolation = Isolation.REPEATABLE_READ)
    public ReviewReportResponse getReport(long taskId) {
        Context context = loadContext(taskId);
        ReviewReport report = context.report();
        requireMatchingCount("findings",
                findingRepository.countByReportId(report.getId()),
                report.getFindingCount(), taskId);
        requireMatchingCount("comments",
                commentRepository.countByReportId(report.getId()),
                report.getPublishedCommentCount(), taskId);
        return toReportResponse(context.task(), report);
    }

    @Transactional(readOnly = true,
            isolation = Isolation.REPEATABLE_READ)
    public ReviewPageResponse<ReviewFindingResponse> getFindings(long taskId,
                                                                  int page,
                                                                  int size) {
        Context context = loadContext(taskId);
        ReviewReport report = context.report();
        Page<ReviewFinding> result = findingRepository.findByReportId(
                report.getId(), pageRequest(page, size, "ordinal"));
        requireMatchingCount("findings", result.getTotalElements(),
                report.getFindingCount(), taskId);
        List<ReviewFindingResponse> items = result.getContent().stream()
                .map(row -> toFindingResponse(report.getId(), row))
                .toList();
        return new ReviewPageResponse<>(items, page, size,
                result.getTotalElements(), result.getTotalPages(),
                result.hasNext());
    }

    @Transactional(readOnly = true,
            isolation = Isolation.REPEATABLE_READ)
    public ReviewPageResponse<ReviewCommentResponse> getComments(long taskId,
                                                                  int page,
                                                                  int size) {
        Context context = loadContext(taskId);
        ReviewReport report = context.report();
        Page<ReviewComment> result = commentRepository.findByReportId(
                report.getId(), pageRequest(page, size, "findingOrdinal"));
        requireMatchingCount("comments", result.getTotalElements(),
                report.getPublishedCommentCount(), taskId);
        List<ReviewCommentResponse> items = result.getContent().stream()
                .map(ReviewHistoryQueryService::toCommentResponse)
                .toList();
        return new ReviewPageResponse<>(items, page, size,
                result.getTotalElements(), result.getTotalPages(),
                result.hasNext());
    }

    private Context loadContext(long taskId) {
        ReviewTask task = reviewTaskService.getTaskById(taskId);
        ReviewReport report = reportRepository.findByTaskId(taskId)
                .orElseThrow(() -> new ReviewHistoryNotFoundException(taskId));
        return new Context(task, report);
    }

    private static Pageable pageRequest(int page, int size, String property) {
        if (page < 1 || size < 1 || size > MAX_PAGE_SIZE) {
            throw new IllegalArgumentException("Invalid pagination");
        }
        return PageRequest.of(page - 1, size,
                Sort.by(Sort.Direction.ASC, property));
    }

    private static void requireMatchingCount(String section, long actual,
                                             int expected, long taskId) {
        if (actual != expected) {
            throw new ReviewHistoryIncompleteException(
                    "Incomplete " + section + " history for task id="
                            + taskId + ": actual=" + actual
                            + " expected=" + expected);
        }
    }

    private static ReviewReportResponse toReportResponse(ReviewTask task,
                                                          ReviewReport report) {
        return new ReviewReportResponse(
                task.getId(),
                task.getOwner(),
                task.getRepo(),
                task.getPrNumber(),
                task.getCommitSha(),
                task.getStatus().name(),
                report.getAiStatus(),
                report.getPublishStatus().name(),
                report.getFindingCount(),
                report.getPublishedCommentCount(),
                report.getSummaryCommentId(),
                report.getPublishedAt(),
                report.getCreatedAt(),
                report.getUpdatedAt());
    }

    private ReviewFindingResponse toFindingResponse(long reportId,
                                                     ReviewFinding row) {
        return new ReviewFindingResponse(
                row.getOrdinal(),
                row.getCategory(),
                row.getSeverity(),
                row.getConfidence(),
                row.getRuleId(),
                row.getTitle(),
                row.getFilePath(),
                row.getStartLine(),
                row.getEndLine(),
                row.getDescription(),
                row.getReason(),
                row.getSuggestion(),
                parseReferences(reportId, row.getOrdinal(),
                        row.getReferencesJson()));
    }

    private static ReviewCommentResponse toCommentResponse(ReviewComment row) {
        return new ReviewCommentResponse(
                row.getFindingOrdinal(),
                row.getGithubCommentId(),
                row.getFilePath(),
                row.getStartLine(),
                row.getEndLine());
    }

    private List<String> parseReferences(long reportId, int ordinal,
                                         String referencesJson) {
        if (referencesJson == null || referencesJson.isBlank()) {
            return List.of();
        }
        try {
            JsonNode root = objectMapper.readTree(referencesJson);
            if (root == null || root.isNull()) {
                return List.of();
            }
            if (!root.isArray()) {
                throw invalidReferences(reportId, ordinal, "not_array");
            }
            List<String> references = new ArrayList<>(root.size());
            for (JsonNode element : root) {
                if (element.isNull()) {
                    references.add(null);
                } else if (element.isTextual()) {
                    references.add(element.asText());
                } else {
                    throw invalidReferences(reportId, ordinal,
                            "non_string_element");
                }
            }
            return references;
        } catch (JsonProcessingException error) {
            throw invalidReferences(reportId, ordinal, "invalid_json");
        }
    }

    private static ReviewHistoryDataIntegrityException invalidReferences(
            long reportId, int ordinal, String reason) {
        return new ReviewHistoryDataIntegrityException(
                "Unreadable references_json for report id=" + reportId
                        + " finding ordinal=" + ordinal + " reason=" + reason);
    }

    private record Context(ReviewTask task, ReviewReport report) {
    }
}