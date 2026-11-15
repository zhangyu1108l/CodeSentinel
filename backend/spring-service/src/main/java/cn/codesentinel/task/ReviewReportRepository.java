package cn.codesentinel.task;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDateTime;
import java.util.Optional;

public interface ReviewReportRepository extends JpaRepository<ReviewReport, Long> {

    Optional<ReviewReport> findByTaskId(Long taskId);

    /**
     * Dashboard list query (Phase 11.2.2-A).
     *
     * <p>Rooted at {@code review_report}; the {@code exists} subquery
     * supplies the owner/repo/PR/task-status filters from the logically
     * associated {@code review_task}. All params except the pageable are
     * optional. The caller fixes the sort to
     * {@code review_report.created_at DESC, id DESC}.
     */
    @Query("""
            select r from ReviewReport r
            where exists (
                select t.id from ReviewTask t
                where t.id = r.taskId
                  and (:owner is null or t.owner = :owner)
                  and (:repo is null or t.repo = :repo)
                  and (:prNumber is null or t.prNumber = :prNumber)
                  and (:taskStatus is null or t.status = :taskStatus)
            )
              and (:publishStatus is null
                   or r.publishStatus = :publishStatus)
              and (:aiStatus is null or r.aiStatus = :aiStatus)
              and (:createdFrom is null
                   or r.createdAt >= :createdFrom)
              and (:createdTo is null or r.createdAt <= :createdTo)
            """)
    Page<ReviewReport> searchHistory(
            @Param("owner") String owner,
            @Param("repo") String repo,
            @Param("prNumber") Integer prNumber,
            @Param("taskStatus") TaskStatus taskStatus,
            @Param("publishStatus") PublishStatus publishStatus,
            @Param("aiStatus") String aiStatus,
            @Param("createdFrom") LocalDateTime createdFrom,
            @Param("createdTo") LocalDateTime createdTo,
            Pageable pageable);
}
