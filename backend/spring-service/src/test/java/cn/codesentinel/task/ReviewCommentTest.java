package cn.codesentinel.task;

import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import org.junit.jupiter.api.Test;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.mapping.PropertyPath;

import java.lang.reflect.Method;
import java.util.List;

import static cn.codesentinel.task.JpaMappingTestSupport.assertColumn;
import static cn.codesentinel.task.JpaMappingTestSupport.assertNoRelationshipMappings;
import static cn.codesentinel.task.JpaMappingTestSupport.assertTable;
import static cn.codesentinel.task.JpaMappingTestSupport.assertUniqueConstraint;
import static cn.codesentinel.task.JpaMappingTestSupport.column;
import static cn.codesentinel.task.JpaMappingTestSupport.field;
import static cn.codesentinel.task.JpaMappingTestSupport.generatedValue;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ReviewCommentTest {

    @Test
    void shouldMapTableAndBothUniqueConstraints() {
        assertTable(ReviewComment.class, "review_comment");
        assertUniqueConstraint(ReviewComment.class,
                "uk_review_comment_report_finding",
                "report_id", "finding_ordinal");
        assertUniqueConstraint(ReviewComment.class,
                "uk_review_comment_github_id", "github_comment_id");
    }

    @Test
    void shouldMapEveryColumnAccordingToTheApprovedDdl() {
        assertColumn(ReviewComment.class, "reportId", "report_id", false);
        assertColumn(ReviewComment.class, "findingOrdinal", "finding_ordinal",
                false);
        assertColumn(ReviewComment.class, "githubCommentId",
                "github_comment_id", true);
        assertColumn(ReviewComment.class, "filePath", "file_path", false);
        assertEquals(1024, column(ReviewComment.class, "filePath").length());
        assertColumn(ReviewComment.class, "startLine", "start_line", false);
        assertColumn(ReviewComment.class, "endLine", "end_line", false);
        assertColumn(ReviewComment.class, "createdAt", "created_at", false);
        assertFalse(column(ReviewComment.class, "createdAt").updatable());
        assertNotNull(field(ReviewComment.class, "id").getAnnotation(Id.class));
        assertEquals(GenerationType.IDENTITY,
                generatedValue(ReviewComment.class, "id").strategy());
    }

    @Test
    void shouldUseNoRelationshipMappings() {
        assertNoRelationshipMappings(ReviewComment.class);
    }

    @Test
    void shouldCarryAllBusinessFieldsThroughTheConstructor() {
        ReviewComment comment = new ReviewComment(7L, 2, 501L, "src/A.java",
                2, 2);

        assertEquals(7L, comment.getReportId());
        assertEquals(2, comment.getFindingOrdinal());
        assertEquals(501L, comment.getGithubCommentId());
        assertEquals("src/A.java", comment.getFilePath());
        assertEquals(2, comment.getStartLine());
        assertEquals(2, comment.getEndLine());
        assertNotNull(comment.getCreatedAt());
    }

    @Test
    void shouldAllowNullGithubCommentId() {
        ReviewComment comment = new ReviewComment(7L, 2, null, "src/A.java",
                2, 2);

        assertNull(comment.getGithubCommentId());
        assertTrue(column(ReviewComment.class, "githubCommentId").nullable());
    }

    @Test
    void repositoryShouldExposeTheOrderedReportFinder() throws Exception {
        assertTrue(JpaRepository.class
                .isAssignableFrom(ReviewCommentRepository.class));
        Method method = ReviewCommentRepository.class
                .getMethod("findByReportIdOrderByFindingOrdinalAsc", Long.class);
        assertEquals(List.class, method.getReturnType());
        assertNotNull(PropertyPath.from("reportId", ReviewComment.class));
        assertNotNull(
                PropertyPath.from("findingOrdinal", ReviewComment.class));
    }

    @Test
    void repositoryShouldExposePagedFinderAndCount() throws Exception {
        Method pageMethod = ReviewCommentRepository.class.getMethod(
                "findByReportId", Long.class, Pageable.class);
        assertEquals(Page.class, pageMethod.getReturnType());

        Method countMethod = ReviewCommentRepository.class.getMethod(
                "countByReportId", Long.class);
        assertEquals(long.class, countMethod.getReturnType());

        assertNotNull(PropertyPath.from("reportId", ReviewComment.class));
        assertNotNull(
                PropertyPath.from("findingOrdinal", ReviewComment.class));
    }
}