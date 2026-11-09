package cn.codesentinel.task;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface ReviewFindingRepository extends JpaRepository<ReviewFinding, Long> {

    List<ReviewFinding> findByReportIdOrderByOrdinalAsc(Long reportId);

    Page<ReviewFinding> findByReportId(Long reportId, Pageable pageable);

    long countByReportId(Long reportId);
}