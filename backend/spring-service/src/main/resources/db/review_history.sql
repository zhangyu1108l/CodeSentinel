-- ============================================================
-- CodeSentinel Phase 10.1 最终批准 DDL
-- 来源：Phase 10.1 最终复核报告第⑤节。
-- 本文件用于人工审查和执行。
-- 不代表数据库已经执行这些 DDL。
-- ============================================================

-- ============================================================
-- CodeSentinel Phase 10.1 - review history (manual DDL, no migration tool)
-- review_result_delivery keeps its reception/replay contract unchanged.
-- ============================================================

CREATE TABLE IF NOT EXISTS review_report (
    id                      BIGINT       NOT NULL AUTO_INCREMENT,
    task_id                 BIGINT       NOT NULL,
    commit_sha              CHAR(40)     NOT NULL,
    ai_status               VARCHAR(20)  NOT NULL,  -- COMPLETED / DEGRADED
    publish_status          VARCHAR(20)  NOT NULL,  -- PENDING / PUBLISHED / PARTIAL / FAILED
    finding_count           INT          NOT NULL,  -- = review_finding rows for this report
    published_comment_count INT          NOT NULL,  -- = review_comment rows (inline only)
    summary_comment_id      BIGINT       NULL,      -- NULL = no usable summary id (see docs)
    published_at            DATETIME(6)  NULL,      -- non-null iff >=1 item confirmed published
    created_at              DATETIME(6)  NOT NULL,
    updated_at              DATETIME(6)  NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_review_report_task (task_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

CREATE TABLE IF NOT EXISTS review_finding (
    id              BIGINT        NOT NULL AUTO_INCREMENT,
    report_id       BIGINT        NOT NULL,
    ordinal         INT           NOT NULL,  -- 0-based index in the findings snapshot
    category        VARCHAR(20)   NOT NULL,
    severity        VARCHAR(20)   NOT NULL,
    confidence      DOUBLE        NOT NULL,
    rule_id         VARCHAR(255)  NOT NULL,
    title           VARCHAR(1000) NOT NULL,
    file_path       VARCHAR(1024) NOT NULL,
    start_line      INT           NOT NULL,
    end_line        INT           NOT NULL,
    description     TEXT          NOT NULL,
    reason          TEXT          NOT NULL,
    suggestion      TEXT          NOT NULL,
    references_json TEXT          NULL,      -- JSON array, elements may be null (snapshot fidelity)
    created_at      DATETIME(6)   NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_review_finding_report_ordinal (report_id, ordinal)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

CREATE TABLE IF NOT EXISTS review_comment (
    id                BIGINT        NOT NULL AUTO_INCREMENT,
    report_id         BIGINT        NOT NULL,
    finding_ordinal   INT           NOT NULL,  -- links (report_id, ordinal) of review_finding
    github_comment_id BIGINT        NULL,      -- NULL only for confirmed PUBLISHED without id
    file_path         VARCHAR(1024) NOT NULL,
    start_line        INT           NOT NULL,
    end_line          INT           NOT NULL,
    created_at        DATETIME(6)   NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_review_comment_report_finding (report_id, finding_ordinal),
    UNIQUE KEY uk_review_comment_github_id (github_comment_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;