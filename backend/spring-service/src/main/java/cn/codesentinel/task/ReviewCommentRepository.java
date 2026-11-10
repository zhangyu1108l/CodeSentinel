package cn.codesentinel.task;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface ReviewCommentRepository extends JpaRepository<ReviewComment, Long> {

    List<ReviewComment> findByReportIdOrderByFindingOrdinalAsc(Long reportId);

    Page<ReviewComment> findByReportId(Long reportId, Pageable pageable);

    long countByReportId(Long reportId);
}