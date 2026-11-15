package cn.codesentinel.statistics;

import cn.codesentinel.task.ReviewReport;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.query.Param;

import java.time.LocalDateTime;
import java.util.List;

/**
 * Read-only native SQL access of the Dashboard statistics API
 * (Phase 11.2.4-B1).
 *
 * <p>The root table is {@code review_report}. {@code review_task} is used
 * only for logical association, filtering and display. The repository
 * never reads {@code review_result_delivery}, never parses
 * {@code review_finding.references_json}, and has no write methods.
 *
 * <p>Every user-supplied value is a named parameter. The two queries share
 * exactly the same filter block so report-level and Finding-level results
 * use the same population.
 */
public interface ReviewStatisticsRepository
        extends Repository<ReviewReport, Long> {

    @Query(value = """
            SELECT
                r.id AS reportId,
                r.task_id AS taskId,
                t.owner AS owner,
                t.repo AS repo,
                t.pr_number AS prNumber,
                t.commit_sha AS commitSha,
                t.status AS taskStatus,
                r.ai_status AS aiStatus,
                r.publish_status AS publishStatus,
                r.created_at AS createdAt,
                r.finding_count AS declaredFindingCount,
                (SELECT COUNT(*) FROM review_finding f
                  WHERE f.report_id = r.id) AS actualFindingCount,
                r.published_comment_count AS declaredCommentCount,
                (SELECT COUNT(*) FROM review_comment c
                  WHERE c.report_id = r.id) AS actualCommentCount,
                CASE WHEN r.summary_comment_id IS NULL THEN 0 ELSE 1 END
                    AS summaryCommentIdPresent
            FROM review_report r
            LEFT JOIN review_task t ON t.id = r.task_id
            WHERE (:owner IS NULL OR t.owner = :owner)
              AND (:repo IS NULL OR t.repo = :repo)
              AND (:prNumber IS NULL OR t.pr_number = :prNumber)
              AND (:taskStatus IS NULL OR t.status = :taskStatus)
              AND (:publishStatus IS NULL OR r.publish_status = :publishStatus)
              AND (:aiStatus IS NULL OR r.ai_status = :aiStatus)
              AND r.created_at >= :createdFrom
              AND r.created_at <= :createdTo
            """, nativeQuery = true)
    List<ReportStatisticsRow> findReportStatistics(
            @Param("owner") String owner,
            @Param("repo") String repo,
            @Param("prNumber") Integer prNumber,
            @Param("taskStatus") String taskStatus,
            @Param("publishStatus") String publishStatus,
            @Param("aiStatus") String aiStatus,
            @Param("createdFrom") LocalDateTime createdFrom,
            @Param("createdTo") LocalDateTime createdTo);

    /**
     * Per-report Finding counters. Known enum values are counted exactly;
     * every other stored value is counted into the corresponding
     * {@code UNKNOWN} counter. The query does not read any Finding text or
     * JSON column.
     */
    @Query(value = """
            SELECT
                f.report_id AS reportId,
                COUNT(*) AS actualFindingCount,
                COUNT(CASE WHEN f.severity = 'CRITICAL' THEN 1 END)
                    AS criticalCount,
                COUNT(CASE WHEN f.severity = 'HIGH' THEN 1 END)
                    AS highCount,
                COUNT(CASE WHEN f.severity = 'MEDIUM' THEN 1 END)
                    AS mediumCount,
                COUNT(CASE WHEN f.severity = 'LOW' THEN 1 END)
                    AS lowCount,
                COUNT(CASE WHEN f.severity = 'INFO' THEN 1 END)
                    AS infoCount,
                COUNT(CASE WHEN f.severity NOT IN
                    ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO') THEN 1 END)
                    AS unknownSeverityCount,
                COUNT(CASE WHEN f.category = 'BUG' THEN 1 END)
                    AS bugCount,
                COUNT(CASE WHEN f.category = 'SECURITY' THEN 1 END)
                    AS securityCount,
                COUNT(CASE WHEN f.category = 'PERFORMANCE' THEN 1 END)
                    AS performanceCount,
                COUNT(CASE WHEN f.category = 'QUALITY' THEN 1 END)
                    AS qualityCount,
                COUNT(CASE WHEN f.category NOT IN
                    ('BUG', 'SECURITY', 'PERFORMANCE', 'QUALITY') THEN 1 END)
                    AS unknownCategoryCount
            FROM review_finding f
            JOIN review_report r ON r.id = f.report_id
            LEFT JOIN review_task t ON t.id = r.task_id
            WHERE (:owner IS NULL OR t.owner = :owner)
              AND (:repo IS NULL OR t.repo = :repo)
              AND (:prNumber IS NULL OR t.pr_number = :prNumber)
              AND (:taskStatus IS NULL OR t.status = :taskStatus)
              AND (:publishStatus IS NULL OR r.publish_status = :publishStatus)
              AND (:aiStatus IS NULL OR r.ai_status = :aiStatus)
              AND r.created_at >= :createdFrom
              AND r.created_at <= :createdTo
            GROUP BY f.report_id
            """, nativeQuery = true)
    List<FindingAggregateRow> findFindingAggregates(
            @Param("owner") String owner,
            @Param("repo") String repo,
            @Param("prNumber") Integer prNumber,
            @Param("taskStatus") String taskStatus,
            @Param("publishStatus") String publishStatus,
            @Param("aiStatus") String aiStatus,
            @Param("createdFrom") LocalDateTime createdFrom,
            @Param("createdTo") LocalDateTime createdTo);

    /**
     * One report row with its declared and actual row counts. Task fields
     * are nullable at the projection level so the service can fail closed
     * on an orphan report instead of silently dropping it.
     */
    interface ReportStatisticsRow {

        Long getReportId();

        Long getTaskId();

        String getOwner();

        String getRepo();

        Integer getPrNumber();

        String getCommitSha();

        String getTaskStatus();

        String getAiStatus();

        String getPublishStatus();

        LocalDateTime getCreatedAt();

        Integer getDeclaredFindingCount();

        Long getActualFindingCount();

        Integer getDeclaredCommentCount();

        Long getActualCommentCount();

        Integer getSummaryCommentIdPresent();
    }

    /**
     * Per-report Finding counters used by both the overview distributions
     * and the review comparison table.
     */
    interface FindingAggregateRow {

        Long getReportId();

        Long getActualFindingCount();

        Long getCriticalCount();

        Long getHighCount();

        Long getMediumCount();

        Long getLowCount();

        Long getInfoCount();

        Long getUnknownSeverityCount();

        Long getBugCount();

        Long getSecurityCount();

        Long getPerformanceCount();

        Long getQualityCount();

        Long getUnknownCategoryCount();
    }
}
