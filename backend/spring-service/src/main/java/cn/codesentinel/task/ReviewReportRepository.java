package cn.codesentinel.task;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface ReviewReportRepository extends JpaRepository<ReviewReport, Long> {

    Optional<ReviewReport> findByTaskId(Long taskId);
}