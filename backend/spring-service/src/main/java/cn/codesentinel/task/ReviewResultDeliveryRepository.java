package cn.codesentinel.task;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface ReviewResultDeliveryRepository
        extends JpaRepository<ReviewResultDelivery, Long> {

    Optional<ReviewResultDelivery> findByTaskIdAndCommitSha(
            Long taskId, String commitSha);
}