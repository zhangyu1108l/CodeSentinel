package cn.codesentinel.review;

import cn.codesentinel.task.PublishStatus;
import cn.codesentinel.task.ReviewComment;
import cn.codesentinel.task.ReviewFinding;
import cn.codesentinel.task.ReviewReport;
import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;

class ReviewHistoryMySqlMappingIT extends ReviewHistoryMySqlTestBase {

    @Test
    void m1Char40RoundTripsThroughRealMySql() {
        long taskId = nextTaskId();
        String sha = commitSha(taskId);
        ReviewReport saved = reportRepository.saveAndFlush(report(taskId, sha,
                PublishStatus.PARTIAL, 0, 0, null, null));

        ReviewReport read = reportRepository.findById(saved.getId()).orElseThrow();

        assertEquals(40, sha.length());
        assertEquals("char(40)", columnType("review_report", "commit_sha"));
        assertEquals(sha, read.getCommitSha());
    }

    @Test
    void m2Datetime6PreservesMicroseconds() {
        long taskId = nextTaskId();
        LocalDateTime publishedAt =
                LocalDateTime.of(2026, 1, 2, 3, 4, 5, 123_456_000);
        ReviewReport saved = reportRepository.saveAndFlush(report(taskId,
                commitSha(taskId), PublishStatus.PARTIAL, 0, 0, null,
                publishedAt));

        LocalDateTime read = jdbcTemplate.queryForObject(
                "SELECT published_at FROM review_report WHERE id = ?",
                LocalDateTime.class, saved.getId());

        assertEquals(publishedAt, read);
        assertEquals(123_456_000, read.getNano());
        assertEquals(6, datetimePrecision("review_report", "published_at"));
        assertEquals(6, datetimePrecision("review_report", "created_at"));
        assertEquals(6, datetimePrecision("review_report", "updated_at"));
    }

    @Test
    void m3TextAndNullReferencesRoundTrip() {
        long taskId = nextTaskId();
        String text = "x".repeat(60_000);
        ReviewReport report = reportRepository.saveAndFlush(report(taskId,
                commitSha(taskId), PublishStatus.PENDING, 2, 0, null, null));
        ReviewFinding withText = findingRepository.saveAndFlush(
                new ReviewFinding(report.getId(), 0, "BUG", "LOW", 0.5,
                        "R-1", "title", "src/A.java", 1, 1, "d", "r", "s",
                        text));
        ReviewFinding withNull = findingRepository.saveAndFlush(
                new ReviewFinding(report.getId(), 1, "BUG", "LOW", 0.5,
                        "R-2", "title", "src/B.java", 1, 1, "d", "r", "s",
                        null));

        assertEquals("text", columnType("review_finding", "references_json"));
        assertEquals(text, jdbcTemplate.queryForObject(
                "SELECT references_json FROM review_finding WHERE id = ?",
                String.class, withText.getId()));
        assertNull(jdbcTemplate.queryForObject(
                "SELECT references_json FROM review_finding WHERE id = ?",
                String.class, withNull.getId()));
    }

    @Test
    void m4DoubleConfidenceRoundTrips() {
        long taskId = nextTaskId();
        ReviewReport report = reportRepository.saveAndFlush(report(taskId,
                commitSha(taskId), PublishStatus.PENDING, 1, 0, null, null));
        ReviewFinding finding = findingRepository.saveAndFlush(
                new ReviewFinding(report.getId(), 0, "BUG", "LOW",
                        0.123456789, "R-1", "title", "src/A.java", 1, 1,
                        "d", "r", "s", "[]"));

        ReviewFinding read = findingRepository.findById(finding.getId())
                .orElseThrow();

        assertEquals(0.123456789, read.getConfidence(), 1e-12);
        assertEquals("double", columnType("review_finding", "confidence"));
    }

    @Test
    void m5PublishStatusUsesEnumStringMapping() {
        long taskId = nextTaskId();
        ReviewReport saved = reportRepository.saveAndFlush(report(taskId,
                commitSha(taskId), PublishStatus.PARTIAL, 0, 0, null, null));

        ReviewReport read = reportRepository.findById(saved.getId())
                .orElseThrow();

        assertEquals(PublishStatus.PARTIAL, read.getPublishStatus());
        assertEquals("varchar(20)",
                columnType("review_report", "publish_status"));
    }

    @Test
    void m6NullableGithubCommentIdAllowsMultipleNulls() {
        long taskId = nextTaskId();
        ReviewReport report = reportRepository.saveAndFlush(report(taskId,
                commitSha(taskId), PublishStatus.PARTIAL, 0, 2, null, null));
        ReviewComment first = commentRepository.saveAndFlush(
                commentRow(report.getId(), 0, null, "src/A.java"));
        ReviewComment second = commentRepository.saveAndFlush(
                commentRow(report.getId(), 1, null, "src/B.java"));

        assertNull(commentRepository.findById(first.getId())
                .orElseThrow().getGithubCommentId());
        assertNull(commentRepository.findById(second.getId())
                .orElseThrow().getGithubCommentId());
        assertEquals("YES",
                nullable("review_comment", "github_comment_id"));
    }

    @Test
    void m7ColumnLengthsAndNullabilityMatchApprovedDdl() {
        assertEquals(255, characterLength("review_finding", "rule_id"));
        assertEquals(1000, characterLength("review_finding", "title"));
        assertEquals(1024, characterLength("review_finding", "file_path"));
        assertEquals(1024, characterLength("review_comment", "file_path"));
        assertEquals(20, characterLength("review_report", "ai_status"));
        assertEquals(20, characterLength("review_report", "publish_status"));
        assertEquals("NO", nullable("review_report", "created_at"));
        assertEquals("NO", nullable("review_report", "updated_at"));
        assertEquals("YES", nullable("review_report", "summary_comment_id"));
        assertEquals("YES", nullable("review_report", "published_at"));
        assertEquals("YES", nullable("review_finding", "references_json"));
        assertEquals("YES", nullable("review_comment", "github_comment_id"));

        long taskId = nextTaskId();
        ReviewReport report = reportRepository.saveAndFlush(report(taskId,
                commitSha(taskId), PublishStatus.PENDING, 1, 0, null, null));
        ReviewFinding finding = findingRepository.saveAndFlush(
                new ReviewFinding(report.getId(), 0, "BUG", "LOW", 0.5,
                        "r".repeat(255), "t".repeat(1000),
                        "p".repeat(1024), 1, 1, "d", "r", "s", null));
        ReviewFinding read = findingRepository.findById(finding.getId())
                .orElseThrow();

        assertEquals(255, read.getRuleId().length());
        assertEquals(1000, read.getTitle().length());
        assertEquals(1024, read.getFilePath().length());
        assertNotNull(read.getCreatedAt());
        assertNotNull(reportRepository.findById(report.getId())
                .orElseThrow().getCreatedAt());
    }

    private String columnType(String table, String column) {
        return jdbcTemplate.queryForObject(
                "SELECT COLUMN_TYPE FROM information_schema.COLUMNS "
                        + "WHERE TABLE_SCHEMA = DATABASE() "
                        + "AND TABLE_NAME = ? AND COLUMN_NAME = ?",
                String.class, table, column);
    }

    private Integer datetimePrecision(String table, String column) {
        return jdbcTemplate.queryForObject(
                "SELECT DATETIME_PRECISION FROM information_schema.COLUMNS "
                        + "WHERE TABLE_SCHEMA = DATABASE() "
                        + "AND TABLE_NAME = ? AND COLUMN_NAME = ?",
                Integer.class, table, column);
    }

    private Integer characterLength(String table, String column) {
        return jdbcTemplate.queryForObject(
                "SELECT CHARACTER_MAXIMUM_LENGTH "
                        + "FROM information_schema.COLUMNS "
                        + "WHERE TABLE_SCHEMA = DATABASE() "
                        + "AND TABLE_NAME = ? AND COLUMN_NAME = ?",
                Integer.class, table, column);
    }

    private String nullable(String table, String column) {
        return jdbcTemplate.queryForObject(
                "SELECT IS_NULLABLE FROM information_schema.COLUMNS "
                        + "WHERE TABLE_SCHEMA = DATABASE() "
                        + "AND TABLE_NAME = ? AND COLUMN_NAME = ?",
                String.class, table, column);
    }
}