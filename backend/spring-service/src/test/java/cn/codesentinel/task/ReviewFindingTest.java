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
import static org.junit.jupiter.api.Assertions.assertTrue;

class ReviewFindingTest {

    @Test
    void shouldMapTableAndUniqueReportOrdinalConstraint() {
        assertTable(ReviewFinding.class, "review_finding");
        assertUniqueConstraint(ReviewFinding.class,
                "uk_review_finding_report_ordinal", "report_id", "ordinal");
    }

    @Test
    void shouldMapEveryColumnAccordingToTheApprovedDdl() {
        assertColumn(ReviewFinding.class, "reportId", "report_id", false);
        assertColumn(ReviewFinding.class, "ordinal", "ordinal", false);
        assertColumn(ReviewFinding.class, "category", "category", false);
        assertEquals(20, column(ReviewFinding.class, "category").length());
        assertColumn(ReviewFinding.class, "severity", "severity", false);
        assertEquals(20, column(ReviewFinding.class, "severity").length());
        assertColumn(ReviewFinding.class, "confidence", "confidence", false);
        assertColumn(ReviewFinding.class, "ruleId", "rule_id", false);
        assertEquals(255, column(ReviewFinding.class, "ruleId").length());
        assertColumn(ReviewFinding.class, "title", "title", false);
        assertEquals(1000, column(ReviewFinding.class, "title").length());
        assertColumn(ReviewFinding.class, "filePath", "file_path", false);
        assertEquals(1024, column(ReviewFinding.class, "filePath").length());
        assertColumn(ReviewFinding.class, "startLine", "start_line", false);
        assertColumn(ReviewFinding.class, "endLine", "end_line", false);
        assertColumn(ReviewFinding.class, "description", "description", false);
        assertEquals("TEXT",
                column(ReviewFinding.class, "description").columnDefinition());
        assertColumn(ReviewFinding.class, "reason", "reason", false);
        assertEquals("TEXT",
                column(ReviewFinding.class, "reason").columnDefinition());
        assertColumn(ReviewFinding.class, "suggestion", "suggestion", false);
        assertEquals("TEXT",
                column(ReviewFinding.class, "suggestion").columnDefinition());
        assertColumn(ReviewFinding.class, "referencesJson", "references_json",
                true);
        assertEquals("TEXT",
                column(ReviewFinding.class, "referencesJson")
                        .columnDefinition());
        assertColumn(ReviewFinding.class, "createdAt", "created_at", false);
        assertFalse(column(ReviewFinding.class, "createdAt").updatable());
        assertNotNull(field(ReviewFinding.class, "id").getAnnotation(Id.class));
        assertEquals(GenerationType.IDENTITY,
                generatedValue(ReviewFinding.class, "id").strategy());
    }

    @Test
    void shouldUseNoRelationshipMappings() {
        assertNoRelationshipMappings(ReviewFinding.class);
    }

    @Test
    void shouldCarryAllBusinessFieldsThroughTheConstructor() {
        ReviewFinding finding = new ReviewFinding(7L, 2, "BUG", "HIGH", 0.9,
                "CWE-89", "title", "src/A.java", 1, 2, "description", "reason",
                "suggestion", "[\"CWE-89\",null]");

        assertEquals(7L, finding.getReportId());
        assertEquals(2, finding.getOrdinal());
        assertEquals("BUG", finding.getCategory());
        assertEquals("HIGH", finding.getSeverity());
        assertEquals(0.9, finding.getConfidence());
        assertEquals("CWE-89", finding.getRuleId());
        assertEquals("title", finding.getTitle());
        assertEquals("src/A.java", finding.getFilePath());
        assertEquals(1, finding.getStartLine());
        assertEquals(2, finding.getEndLine());
        assertEquals("description", finding.getDescription());
        assertEquals("reason", finding.getReason());
        assertEquals("suggestion", finding.getSuggestion());
        assertEquals("[\"CWE-89\",null]", finding.getReferencesJson());
        assertNotNull(finding.getCreatedAt());
    }

    @Test
    void repositoryShouldExposeTheOrderedReportFinder() throws Exception {
        assertTrue(JpaRepository.class
                .isAssignableFrom(ReviewFindingRepository.class));
        Method method = ReviewFindingRepository.class
                .getMethod("findByReportIdOrderByOrdinalAsc", Long.class);
        assertEquals(List.class, method.getReturnType());
        assertNotNull(PropertyPath.from("reportId", ReviewFinding.class));
        assertNotNull(PropertyPath.from("ordinal", ReviewFinding.class));
    }

    @Test
    void repositoryShouldExposePagedFinderAndCount() throws Exception {
        Method pageMethod = ReviewFindingRepository.class.getMethod(
                "findByReportId", Long.class, Pageable.class);
        assertEquals(Page.class, pageMethod.getReturnType());

        Method countMethod = ReviewFindingRepository.class.getMethod(
                "countByReportId", Long.class);
        assertEquals(long.class, countMethod.getReturnType());

        assertNotNull(PropertyPath.from("reportId", ReviewFinding.class));
        assertNotNull(PropertyPath.from("ordinal", ReviewFinding.class));
    }
}