package cn.codesentinel.task;

import org.springframework.data.jpa.repository.JpaRepository;

public interface ReviewTaskRepository extends JpaRepository<ReviewTask, Long> {

    ReviewTask findByOwnerAndRepoAndPrNumberAndCommitSha(
            String owner, String repo, int prNumber, String commitSha);
}