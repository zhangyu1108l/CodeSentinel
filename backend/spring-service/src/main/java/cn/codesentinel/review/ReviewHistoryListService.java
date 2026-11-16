package cn.codesentinel.review;

import cn.codesentinel.task.ReviewReport;
import cn.codesentinel.task.ReviewReportRepository;
import cn.codesentinel.task.ReviewTask;
import cn.codesentinel.task.ReviewTaskRepository;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * Read-only Dashboard list query of stored review history
 * (Phase 11.2.2-A).
 *
 * <p>The query is rooted at {@code review_report}, so only reviews with a
 * structured history row are listed. Owner/repo/PR/task status come from
 * the logically associated {@code review_task}; the response mapping reuses
 * the Phase 10 {@link ReviewReportResponse} contract.
 *
 * <p>The fixed sort {@code createdAt DESC, id DESC} keeps pagination
 * deterministic. This service never reads or writes
 * {@code review_result_delivery}.
 */
@Service
public class ReviewHistoryListService {

    private final ReviewReportRepository reportRepository;
    private final ReviewTaskRepository taskRepository;

    public ReviewHistoryListService(ReviewReportRepository reportRepository,
                                    ReviewTaskRepository taskRepository) {
        this.reportRepository = reportRepository;
        this.taskRepository = taskRepository;
    }

    @Transactional(readOnly = true,
            isolation = Isolation.REPEATABLE_READ)
    public ReviewPageResponse<ReviewReportResponse> search(
            ReviewHistoryFilter filter, int page, int size) {
        validatePagination(page, size);
        Pageable pageable = PageRequest.of(page - 1, size,
                Sort.by(Sort.Order.desc("createdAt"), Sort.Order.desc("id")));
        Page<ReviewReport> result = reportRepository.searchHistory(
                filter.owner(), filter.repo(), filter.prNumber(),
                filter.taskStatus(), filter.publishStatus(), filter.aiStatus(),
                filter.createdFrom(), filter.createdTo(), pageable);
        Map<Long, ReviewTask> tasks = loadTasks(result.getContent());
        List<ReviewReportResponse> items = result.getContent().stream()
                .map(report -> toResponse(report, tasks.get(report.getTaskId())))
                .toList();
        return new ReviewPageResponse<>(items, page, size,
                result.getTotalElements(), result.getTotalPages(),
                result.hasNext());
    }

    private Map<Long, ReviewTask> loadTasks(List<ReviewReport> reports) {
        if (reports.isEmpty()) {
            return Map.of();
        }
        List<Long> taskIds = reports.stream()
                .map(ReviewReport::getTaskId)
                .distinct()
                .toList();
        Map<Long, ReviewTask> tasks = taskRepository.findAllById(taskIds)
                .stream()
                .collect(Collectors.toMap(ReviewTask::getId,
                        Function.identity()));
        for (Long taskId : taskIds) {
            if (!tasks.containsKey(taskId)) {
                throw new ReviewHistoryDataIntegrityException(
                        "Missing review_task for report task id=" + taskId);
            }
        }
        return tasks;
    }

    private static ReviewReportResponse toResponse(ReviewReport report,
                                                   ReviewTask task) {
        return ReviewHistoryQueryService.toReportResponse(task, report);
    }

    private static void validatePagination(int page, int size) {
        if (page < 1 || size < 1
                || size > ReviewHistoryQueryService.MAX_PAGE_SIZE) {
            throw new InvalidReviewHistoryPaginationException(
                    "page must be >= 1 and size must be between 1 and "
                            + ReviewHistoryQueryService.MAX_PAGE_SIZE);
        }
    }
}
