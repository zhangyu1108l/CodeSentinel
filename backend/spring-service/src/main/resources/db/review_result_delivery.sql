-- ============================================================
-- CodeSentinel Phase 9.5.3B1 - review_result_delivery
-- Manual DDL (the project has no migration tool yet, consistent with
-- the manually created review_task table).
-- ============================================================
-- How to execute (run against the codesentinel database):
--
--   mysql -h <host> -P <port> -u <user> -p <database> < review_result_delivery.sql
--
-- or against the compose container (MySQL credentials are asked
-- interactively; never put a password into this file or into logs):
--
--   docker exec -i codesentinel-mysql mysql -u root -p <database> \
--       < review_result_delivery.sql
--
-- Notes:
--   * (task_id, commit_sha) is the idempotency key; it intentionally
--     does not reference review_task.status, because the worker failure
--     path may reset that status.
--   * findings_json is a replayable snapshot of the raw transport
--     payload used to retry publication; it is NOT the final Phase 10
--     structured model.
--   * Phase 10 is expected to replace this transitional table with the
--     structured review_report / review_finding tables.

CREATE TABLE IF NOT EXISTS review_result_delivery (
    id BIGINT NOT NULL AUTO_INCREMENT,
    task_id BIGINT NOT NULL,
    commit_sha CHAR(40) NOT NULL,
    ai_status VARCHAR(20) NOT NULL,
    findings_json LONGTEXT NOT NULL,
    publish_status VARCHAR(20) NOT NULL,
    publish_outcome_json TEXT NULL,
    received_at DATETIME NOT NULL,
    published_at DATETIME NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_review_result_delivery_task_commit (task_id, commit_sha)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;