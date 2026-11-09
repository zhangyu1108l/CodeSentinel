package cn.codesentinel.task;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.test.util.ReflectionTestUtils;

import java.sql.SQLException;
import java.time.LocalDateTime;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class ReviewHistoryServiceTest {

    private static final String SHA = "abc123def456";

    private ReviewReportRepository reportRepository;
    private ReviewFindingRepository findingRepository;
    private ReviewCommentRepository commentRepository;
    private ObjectMapper objectMapper;
    private ReviewHistoryService service;

    @BeforeEach
    void setUp() {
        reportRepository = mock(ReviewReportRepository.class);
        findingRepository = mock(ReviewFindingRepository.class);
        commentRepository = mock(ReviewCommentRepository.class);
        objectMapper = new ObjectMapper();
        service = new ReviewHistoryService(reportRepository, findingRepository,
                commentRepository, objectMapper);
    }

    @Test
    void shouldInsertReportAndAllFindingsOnFirstWrite() throws Exception {
        List<ReviewResultFinding> findings = List.of(
                finding("BUG", "HIGH", 0.9, "R-1", "title", "src/A.java", 1, 2,
                        Arrays.asList("CWE-89", null)),
                finding("SECURITY", "LOW", 0.5, "R-2", "other", "src/B.java",
                        3, 3, List.of()));
        stubFreshReport();
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of());
        when(findingRepository.saveAndFlush(any(ReviewFinding.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        service.ensureHistory(task(), delivery("COMPLETED", findings));

        ArgumentCaptor<ReviewReport> reportCaptor =
                ArgumentCaptor.forClass(ReviewReport.class);
        verify(reportRepository).saveAndFlush(reportCaptor.capture());
        ReviewReport report = reportCaptor.getValue();
        assertEquals(1L, report.getTaskId());
        assertEquals(SHA, report.getCommitSha());
        assertEquals("COMPLETED", report.getAiStatus());
        assertEquals(PublishStatus.PENDING, report.getPublishStatus());
        assertEquals(2, report.getFindingCount());
        assertEquals(0, report.getPublishedCommentCount());
        assertNull(report.getSummaryCommentId());
        assertNull(report.getPublishedAt());

        ArgumentCaptor<ReviewFinding> findingCaptor =
                ArgumentCaptor.forClass(ReviewFinding.class);
        verify(findingRepository, times(2))
                .saveAndFlush(findingCaptor.capture());
        List<ReviewFinding> rows = findingCaptor.getAllValues();
        assertEquals(0, rows.get(0).getOrdinal());
        assertEquals(1, rows.get(1).getOrdinal());
        assertEquals(7L, rows.get(0).getReportId());
        assertEquals("BUG", rows.get(0).getCategory());
        assertEquals("HIGH", rows.get(0).getSeverity());
        assertEquals(0.9, rows.get(0).getConfidence());
        assertEquals("R-1", rows.get(0).getRuleId());
        assertEquals("title", rows.get(0).getTitle());
        assertEquals("src/A.java", rows.get(0).getFilePath());
        assertEquals(1, rows.get(0).getStartLine());
        assertEquals(2, rows.get(0).getEndLine());
        assertEquals("description", rows.get(0).getDescription());
        assertEquals("reason", rows.get(0).getReason());
        assertEquals("suggestion", rows.get(0).getSuggestion());
        assertEquals("[\"CWE-89\",null]", rows.get(0).getReferencesJson());
        assertEquals("[]", rows.get(1).getReferencesJson());
    }

    @Test
    void shouldWriteReportWithoutFindingsForEmptySnapshot() throws Exception {
        stubFreshReport();
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of());

        service.ensureHistory(task(), delivery("COMPLETED", "[]"));

        ArgumentCaptor<ReviewReport> captor =
                ArgumentCaptor.forClass(ReviewReport.class);
        verify(reportRepository).saveAndFlush(captor.capture());
        assertEquals(0, captor.getValue().getFindingCount());
        verify(findingRepository, never())
                .saveAndFlush(any(ReviewFinding.class));
    }

    @Test
    void shouldNotWriteAgainWhenHistoryIsComplete() throws Exception {
        ReviewReport report = report(7L, 2);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(findingRow(7L, 0), findingRow(7L, 1)));

        service.ensureHistory(task(), delivery("COMPLETED", List.of(
                finding("BUG", "HIGH", 0.9, "R-1", "title", "src/A.java", 1, 2,
                        List.of()),
                finding("BUG", "HIGH", 0.9, "R-2", "title", "src/B.java", 3, 4,
                        List.of()))));

        verify(reportRepository, never())
                .saveAndFlush(any(ReviewReport.class));
        verify(findingRepository, never())
                .saveAndFlush(any(ReviewFinding.class));
    }

    @Test
    void shouldInsertOnlyMissingFindingsDuringSelfHeal() throws Exception {
        ReviewReport report = report(7L, 3);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(findingRow(7L, 0), findingRow(7L, 2)));
        when(findingRepository.saveAndFlush(any(ReviewFinding.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        service.ensureHistory(task(), delivery("COMPLETED", List.of(
                finding("BUG", "HIGH", 0.9, "R-1", "title", "src/A.java", 1, 2,
                        List.of()),
                finding("BUG", "HIGH", 0.9, "R-2", "title", "src/B.java", 3, 4,
                        List.of()),
                finding("BUG", "HIGH", 0.9, "R-3", "title", "src/C.java", 5, 6,
                        List.of()))));

        ArgumentCaptor<ReviewFinding> captor =
                ArgumentCaptor.forClass(ReviewFinding.class);
        verify(findingRepository).saveAndFlush(captor.capture());
        assertEquals(1, captor.getValue().getOrdinal());
        verify(reportRepository, never())
                .saveAndFlush(any(ReviewReport.class));
    }

    @Test
    void shouldAcceptValuesAtTheLimits() throws Exception {
        stubFreshReport();
        ReviewResultFinding finding = new ReviewResultFinding("BUG", "HIGH",
                0.9, "r".repeat(ReviewHistoryService.MAX_RULE_ID_CHARS),
                "t".repeat(ReviewHistoryService.MAX_TITLE_CHARS),
                "p".repeat(ReviewHistoryService.MAX_FILE_PATH_CHARS), 1, 2,
                "a".repeat(ReviewHistoryService.MAX_TEXT_BYTES), "reason",
                "suggestion", List.of("x".repeat(65_500)));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of());
        when(findingRepository.saveAndFlush(any(ReviewFinding.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        service.ensureHistory(task(),
                delivery("COMPLETED", List.of(finding)));

        verify(findingRepository).saveAndFlush(any(ReviewFinding.class));
    }

    @Test
    void shouldRejectOverlongFieldsBeforeAnyWrite() throws Exception {
        assertRejectedWithoutWrites(
                finding("BUG", "HIGH", 0.9, "r".repeat(256), "title",
                        "src/A.java", 1, 2, List.of()),
                "rule_id", ReviewHistoryService.MAX_RULE_ID_CHARS);
        assertRejectedWithoutWrites(
                finding("BUG", "HIGH", 0.9, "R-1", "t".repeat(1001),
                        "src/A.java", 1, 2, List.of()),
                "title", ReviewHistoryService.MAX_TITLE_CHARS);
        assertRejectedWithoutWrites(
                finding("BUG", "HIGH", 0.9, "R-1", "title",
                        "p".repeat(1025), 1, 2, List.of()),
                "file_path", ReviewHistoryService.MAX_FILE_PATH_CHARS);
        assertRejectedWithoutWrites(
                textFinding("a".repeat(65_536)),
                "description", ReviewHistoryService.MAX_TEXT_BYTES);
        assertRejectedWithoutWrites(
                textFinding("d", "r".repeat(65_536), "s"),
                "reason", ReviewHistoryService.MAX_TEXT_BYTES);
        assertRejectedWithoutWrites(
                textFinding("d", "r", "s".repeat(65_536)),
                "suggestion", ReviewHistoryService.MAX_TEXT_BYTES);
        assertRejectedWithoutWrites(
                finding("BUG", "HIGH", 0.9, "R-1", "title", "src/A.java", 1, 2,
                        List.of("x".repeat(65_600))),
                "references_json", ReviewHistoryService.MAX_TEXT_BYTES);
    }

    @Test
    void shouldValidateUtf8BytesForMultiByteText() throws Exception {
        stubFreshReport();
        ReviewResultFinding finding = textFinding("中".repeat(21_845));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of());
        when(findingRepository.saveAndFlush(any(ReviewFinding.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        service.ensureHistory(task(),
                delivery("COMPLETED", List.of(finding)));

        verify(findingRepository).saveAndFlush(any(ReviewFinding.class));
    }

    @Test
    void shouldRejectMultiByteTextOverTheByteLimit() throws Exception {
        assertRejectedWithoutWrites(textFinding("中".repeat(21_846)),
                "description", ReviewHistoryService.MAX_TEXT_BYTES);
    }

    @Test
    void shouldRejectEmojiTextOverTheByteLimit() throws Exception {
        assertRejectedWithoutWrites(
                textFinding("d", "r", "😀".repeat(16_384)),
                "suggestion", ReviewHistoryService.MAX_TEXT_BYTES);
    }

    @Test
    void shouldTreatConcurrentReportInsertAsIdempotentWhenRowExists()
            throws Exception {
        ReviewReport existing = report(7L, 1);
        when(reportRepository.findByTaskId(1L))
                .thenReturn(Optional.empty(), Optional.of(existing));
        when(reportRepository.saveAndFlush(any(ReviewReport.class)))
                .thenThrow(duplicateKeyFailure());
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of());
        when(findingRepository.saveAndFlush(any(ReviewFinding.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        service.ensureHistory(task(), delivery("COMPLETED", List.of(
                finding("BUG", "HIGH", 0.9, "R-1", "title", "src/A.java", 1, 2,
                        List.of()))));

        verify(findingRepository).saveAndFlush(any(ReviewFinding.class));
    }

    @Test
    void shouldRethrowWhenConcurrentReportRowIsStillMissing()
            throws Exception {
        DataIntegrityViolationException failure = duplicateKeyFailure();
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.empty());
        when(reportRepository.saveAndFlush(any(ReviewReport.class)))
                .thenThrow(failure);

        DataIntegrityViolationException thrown = assertThrows(
                DataIntegrityViolationException.class,
                () -> service.ensureHistory(task(), delivery("COMPLETED",
                        List.of(finding("BUG", "HIGH", 0.9, "R-1", "title",
                                "src/A.java", 1, 2, List.of())))));
        assertSame(failure, thrown);

        verify(findingRepository, never())
                .saveAndFlush(any(ReviewFinding.class));
        verify(findingRepository, never())
                .findByReportIdOrderByOrdinalAsc(any());
    }

    @Test
    void shouldTreatConcurrentFindingInsertAsIdempotentWhenRowExists()
            throws Exception {
        ReviewReport report = report(7L, 1);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(), List.of(new ReviewFinding(7L, 0,
                        "BUG", "HIGH", 0.9, "R-1", "title", "src/A.java",
                        1, 2, "description", "reason", "suggestion", "[]")));
        when(findingRepository.saveAndFlush(any(ReviewFinding.class)))
                .thenThrow(duplicateKeyFailure());

        service.ensureHistory(task(), delivery("COMPLETED", List.of(
                finding("BUG", "HIGH", 0.9, "R-1", "title", "src/A.java", 1, 2,
                        List.of()))));

        verify(findingRepository, times(2))
                .findByReportIdOrderByOrdinalAsc(7L);
        verify(findingRepository).saveAndFlush(any(ReviewFinding.class));
    }

    @Test
    void shouldRethrowWhenConcurrentFindingRowIsStillMissing()
            throws Exception {
        ReviewReport report = report(7L, 1);
        DataIntegrityViolationException failure = duplicateKeyFailure();
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(), List.of());
        when(findingRepository.saveAndFlush(any(ReviewFinding.class)))
                .thenThrow(failure);

        DataIntegrityViolationException thrown = assertThrows(
                DataIntegrityViolationException.class,
                () -> service.ensureHistory(task(), delivery("COMPLETED",
                        List.of(finding("BUG", "HIGH", 0.9, "R-1", "title",
                                "src/A.java", 1, 2, List.of())))));
        assertSame(failure, thrown);
    }

    @Test
    void shouldFailSafelyWhenStoredFindingCountDiffersFromSnapshot()
            throws Exception {
        ReviewReport report = report(7L, 1);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));

        ReviewHistoryConstraintException error = assertThrows(
                ReviewHistoryConstraintException.class,
                () -> service.ensureHistory(task(), delivery("COMPLETED",
                        List.of(finding("BUG", "HIGH", 0.9, "R-1", "title",
                                        "src/A.java", 1, 2, List.of()),
                                finding("BUG", "HIGH", 0.9, "R-2", "title",
                                        "src/B.java", 3, 4, List.of())))));

        assertTrue(error.getMessage().contains("finding_count_mismatch"),
                error.getMessage());
        assertTrue(error.getMessage().contains("stored=1"),
                error.getMessage());
        assertTrue(error.getMessage().contains("snapshot=2"),
                error.getMessage());
        verify(reportRepository, never())
                .saveAndFlush(any(ReviewReport.class));
        verify(findingRepository, never())
                .saveAndFlush(any(ReviewFinding.class));
        verify(findingRepository, never())
                .findByReportIdOrderByOrdinalAsc(any());
    }

    @Test
    void shouldRejectUnreadableSnapshotWithoutWrites() {
        ReviewHistoryConstraintException error = assertThrows(
                ReviewHistoryConstraintException.class,
                () -> service.ensureHistory(task(),
                        delivery("COMPLETED", "not-json")));

        assertTrue(error.getMessage().contains("findings_parse_failed"),
                error.getMessage());
        verifyNoInteractions(reportRepository);
        verifyNoInteractions(findingRepository);
    }

    @Test
    void shouldRejectNullSnapshotWithoutWrites() {
        ReviewHistoryConstraintException error = assertThrows(
                ReviewHistoryConstraintException.class,
                () -> service.ensureHistory(task(),
                        delivery("COMPLETED", "null")));

        assertTrue(error.getMessage().contains("findings_parse_failed"),
                error.getMessage());
        verifyNoInteractions(reportRepository);
        verifyNoInteractions(findingRepository);
    }

    @Test
    void shouldWriteOnlyPublishedInlineCommentsAndUpdateReport() {
        ReviewReport report = report(7L, 2);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(
                        findingRow(7L, 0, "src/A.java", 1, 2),
                        findingRow(7L, 1, "src/B.java", 3, 4)));
        ReviewComment injected = commentRow(7L, 0, 501L, "src/A.java", 1, 2);
        when(commentRepository.findByReportIdOrderByFindingOrdinalAsc(7L))
                .thenReturn(List.of(), List.of(injected));
        LocalDateTime publishedAt = LocalDateTime.of(2026, 5, 6, 7, 8);
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.PARTIAL,
                outcome("PARTIAL", "FAILED", null,
                        commentItem("PUBLISHED", "src/A.java", 1, 2, 501L),
                        commentItem("SKIPPED", "src/B.java", 3, 4, null)),
                publishedAt);

        service.ensurePublishHistory(task(), delivery);

        ArgumentCaptor<ReviewComment> commentCaptor =
                ArgumentCaptor.forClass(ReviewComment.class);
        verify(commentRepository).saveAndFlush(commentCaptor.capture());
        ReviewComment row = commentCaptor.getValue();
        assertEquals(7L, row.getReportId());
        assertEquals(0, row.getFindingOrdinal());
        assertEquals(501L, row.getGithubCommentId());
        assertEquals("src/A.java", row.getFilePath());
        assertEquals(1, row.getStartLine());
        assertEquals(2, row.getEndLine());

        ArgumentCaptor<ReviewReport> reportCaptor =
                ArgumentCaptor.forClass(ReviewReport.class);
        verify(reportRepository).save(reportCaptor.capture());
        ReviewReport updated = reportCaptor.getValue();
        assertEquals(PublishStatus.PARTIAL, updated.getPublishStatus());
        assertEquals(1, updated.getPublishedCommentCount());
        assertNull(updated.getSummaryCommentId());
        assertEquals(publishedAt, updated.getPublishedAt());
    }

    @Test
    void shouldAllowNullGithubCommentIdForConfirmedPublishedItem() {
        ReviewReport report = report(7L, 1);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(findingRow(7L, 0, "src/A.java", 1, 2)));
        when(commentRepository.findByReportIdOrderByFindingOrdinalAsc(7L))
                .thenReturn(List.of(), List.of(
                        commentRow(7L, 0, null, "src/A.java", 1, 2)));
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.PARTIAL,
                outcome("PARTIAL", "FAILED", null,
                        commentItem("PUBLISHED", "src/A.java", 1, 2, null)));

        service.ensurePublishHistory(task(), delivery);

        ArgumentCaptor<ReviewComment> captor =
                ArgumentCaptor.forClass(ReviewComment.class);
        verify(commentRepository).saveAndFlush(captor.capture());
        assertNull(captor.getValue().getGithubCommentId());
        assertEquals(0, captor.getValue().getFindingOrdinal());
    }

    @Test
    void shouldNotCreateCommentsForFailedOrSkippedItems() {
        ReviewReport report = report(7L, 2);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(
                        findingRow(7L, 0, "src/A.java", 1, 2),
                        findingRow(7L, 1, "src/B.java", 3, 4)));
        when(commentRepository.findByReportIdOrderByFindingOrdinalAsc(7L))
                .thenReturn(List.of());
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.FAILED,
                outcome("FAILED", "FAILED", null,
                        commentItem("SKIPPED", "src/A.java", 1, 2, null),
                        commentItem("FAILED", "src/B.java", 3, 4, null)));

        service.ensurePublishHistory(task(), delivery);

        verify(commentRepository, never())
                .saveAndFlush(any(ReviewComment.class));
        ArgumentCaptor<ReviewReport> captor =
                ArgumentCaptor.forClass(ReviewReport.class);
        verify(reportRepository).save(captor.capture());
        assertEquals(PublishStatus.FAILED, captor.getValue().getPublishStatus());
        assertEquals(0, captor.getValue().getPublishedCommentCount());
    }

    @Test
    void shouldBeIdempotentWhenCommentsAlreadyExist() {
        ReviewReport report = report(7L, 1);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(findingRow(7L, 0, "src/A.java", 1, 2)));
        ReviewComment existing = commentRow(7L, 0, 501L, "src/A.java", 1, 2);
        when(commentRepository.findByReportIdOrderByFindingOrdinalAsc(7L))
                .thenReturn(List.of(existing));
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.PARTIAL,
                outcome("PARTIAL", "FAILED", null,
                        commentItem("PUBLISHED", "src/A.java", 1, 2, 501L)));

        service.ensurePublishHistory(task(), delivery);

        verify(commentRepository, never())
                .saveAndFlush(any(ReviewComment.class));
        ArgumentCaptor<ReviewReport> captor =
                ArgumentCaptor.forClass(ReviewReport.class);
        verify(reportRepository).save(captor.capture());
        assertEquals(1, captor.getValue().getPublishedCommentCount());
    }

    @Test
    void shouldInsertOnlyMissingCommentsDuringSelfHeal() {
        ReviewReport report = report(7L, 3);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(
                        findingRow(7L, 0, "src/A.java", 1, 2),
                        findingRow(7L, 1, "src/B.java", 3, 4),
                        findingRow(7L, 2, "src/C.java", 5, 6)));
        ReviewComment row0 = commentRow(7L, 0, 501L, "src/A.java", 1, 2);
        ReviewComment row1 = commentRow(7L, 1, 502L, "src/B.java", 3, 4);
        ReviewComment row2 = commentRow(7L, 2, 503L, "src/C.java", 5, 6);
        when(commentRepository.findByReportIdOrderByFindingOrdinalAsc(7L))
                .thenReturn(List.of(row0), List.of(row0, row1, row2));
        when(commentRepository.saveAndFlush(any(ReviewComment.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.PUBLISHED,
                outcome("PUBLISHED", "FAILED", null,
                        commentItem("PUBLISHED", "src/A.java", 1, 2, 501L),
                        commentItem("PUBLISHED", "src/B.java", 3, 4, 502L),
                        commentItem("PUBLISHED", "src/C.java", 5, 6, 503L)));

        service.ensurePublishHistory(task(), delivery);

        ArgumentCaptor<ReviewComment> captor =
                ArgumentCaptor.forClass(ReviewComment.class);
        verify(commentRepository, times(2)).saveAndFlush(captor.capture());
        assertEquals(1, captor.getAllValues().get(0).getFindingOrdinal());
        assertEquals(2, captor.getAllValues().get(1).getFindingOrdinal());
        ArgumentCaptor<ReviewReport> reportCaptor =
                ArgumentCaptor.forClass(ReviewReport.class);
        verify(reportRepository).save(reportCaptor.capture());
        assertEquals(3, reportCaptor.getValue().getPublishedCommentCount());
    }

    @Test
    void shouldSkipPublishHistoryWhenReportIsMissing() {
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.empty());
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.PARTIAL,
                outcome("PARTIAL", "FAILED", null,
                        commentItem("PUBLISHED", "src/A.java", 1, 2, 501L)));

        service.ensurePublishHistory(task(), delivery);

        verifyNoInteractions(findingRepository);
        verifyNoInteractions(commentRepository);
        verify(reportRepository, never()).save(any(ReviewReport.class));
    }

    @Test
    void shouldFillSummaryCommentIdOnlyWhenMissing() {
        ReviewReport report = report(7L, 1, PublishStatus.PARTIAL, 800L, null);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(findingRow(7L, 0, "src/A.java", 1, 2)));
        when(commentRepository.findByReportIdOrderByFindingOrdinalAsc(7L))
                .thenReturn(List.of(
                        commentRow(7L, 0, 501L, "src/A.java", 1, 2)));
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.PARTIAL,
                outcome("PARTIAL", "PUBLISHED", 900L,
                        commentItem("PUBLISHED", "src/A.java", 1, 2, 501L)));

        service.ensurePublishHistory(task(), delivery);

        ArgumentCaptor<ReviewReport> captor =
                ArgumentCaptor.forClass(ReviewReport.class);
        verify(reportRepository).save(captor.capture());
        assertEquals(800L, captor.getValue().getSummaryCommentId());
        assertEquals(1, captor.getValue().getPublishedCommentCount());
    }

    @Test
    void shouldStoreSummaryIdWithoutCountingItAsInlineComment() {
        ReviewReport report = report(7L, 0);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of());
        when(commentRepository.findByReportIdOrderByFindingOrdinalAsc(7L))
                .thenReturn(List.of());
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.PUBLISHED,
                outcome("PUBLISHED", "PUBLISHED", 900L));

        service.ensurePublishHistory(task(), delivery);

        ArgumentCaptor<ReviewReport> captor =
                ArgumentCaptor.forClass(ReviewReport.class);
        verify(reportRepository).save(captor.capture());
        assertEquals(0, captor.getValue().getPublishedCommentCount());
        assertEquals(900L, captor.getValue().getSummaryCommentId());
        assertEquals(PublishStatus.PUBLISHED,
                captor.getValue().getPublishStatus());
    }

    @Test
    void shouldNotClearSummaryIdWhenSummaryFailed() {
        ReviewReport report = report(7L, 0, PublishStatus.PARTIAL, 800L, null);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of());
        when(commentRepository.findByReportIdOrderByFindingOrdinalAsc(7L))
                .thenReturn(List.of());
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.FAILED,
                outcome("FAILED", "FAILED", null));

        service.ensurePublishHistory(task(), delivery);

        ArgumentCaptor<ReviewReport> captor =
                ArgumentCaptor.forClass(ReviewReport.class);
        verify(reportRepository).save(captor.capture());
        assertEquals(800L, captor.getValue().getSummaryCommentId());
    }

    @Test
    void shouldCopyPublishedAtFromDelivery() {
        ReviewReport report = report(7L, 1);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(findingRow(7L, 0, "src/A.java", 1, 2)));
        when(commentRepository.findByReportIdOrderByFindingOrdinalAsc(7L))
                .thenReturn(List.of(
                        commentRow(7L, 0, 501L, "src/A.java", 1, 2)));
        LocalDateTime publishedAt = LocalDateTime.of(2026, 5, 6, 7, 8);
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.PARTIAL,
                outcome("PARTIAL", "FAILED", null,
                        commentItem("PUBLISHED", "src/A.java", 1, 2, 501L)),
                publishedAt);

        service.ensurePublishHistory(task(), delivery);

        ArgumentCaptor<ReviewReport> captor =
                ArgumentCaptor.forClass(ReviewReport.class);
        verify(reportRepository).save(captor.capture());
        assertNotNull(captor.getValue().getPublishedAt());
        assertEquals(publishedAt, captor.getValue().getPublishedAt());
    }

    @Test
    void shouldNotClearExistingPublishedAtWhenDeliveryHasNone() {
        LocalDateTime existing = LocalDateTime.of(2025, 1, 1, 0, 0);
        ReviewReport report = report(7L, 0, PublishStatus.PARTIAL, null,
                existing);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of());
        when(commentRepository.findByReportIdOrderByFindingOrdinalAsc(7L))
                .thenReturn(List.of());
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.FAILED,
                outcome("FAILED", "FAILED", null));

        service.ensurePublishHistory(task(), delivery);

        ArgumentCaptor<ReviewReport> captor =
                ArgumentCaptor.forClass(ReviewReport.class);
        verify(reportRepository).save(captor.capture());
        assertEquals(existing, captor.getValue().getPublishedAt());
    }

    @Test
    void shouldRejectOutcomeWithFewerCommentsThanFindings() {
        ReviewReport report = report(7L, 2);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(
                        findingRow(7L, 0, "src/A.java", 1, 2),
                        findingRow(7L, 1, "src/B.java", 3, 4)));
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.PARTIAL,
                outcome("PARTIAL", "FAILED", null,
                        commentItem("PUBLISHED", "src/A.java", 1, 2, 501L)));

        ReviewHistoryConstraintException error = assertThrows(
                ReviewHistoryConstraintException.class,
                () -> service.ensurePublishHistory(task(), delivery));

        assertTrue(error.getMessage().contains("outcome_findings_mismatch"),
                error.getMessage());
        verifyNoInteractions(commentRepository);
        verify(reportRepository, never()).save(any(ReviewReport.class));
    }

    @Test
    void shouldRejectGapInFindingOrdinals() {
        ReviewReport report = report(7L, 2);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(
                        findingRow(7L, 0, "src/A.java", 1, 2),
                        findingRow(7L, 2, "src/C.java", 5, 6)));
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.PARTIAL,
                outcome("PARTIAL", "FAILED", null,
                        commentItem("PUBLISHED", "src/A.java", 1, 2, 501L),
                        commentItem("PUBLISHED", "src/C.java", 5, 6, 502L)));

        ReviewHistoryConstraintException error = assertThrows(
                ReviewHistoryConstraintException.class,
                () -> service.ensurePublishHistory(task(), delivery));

        assertTrue(error.getMessage().contains("ordinal gap"),
                error.getMessage());
        verifyNoInteractions(commentRepository);
        verify(reportRepository, never()).save(any(ReviewReport.class));
    }

    @Test
    void shouldRejectFindingIdentityMismatch() {
        ReviewReport report = report(7L, 1);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(findingRow(7L, 0, "src/A.java", 1, 2)));
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.PARTIAL,
                outcome("PARTIAL", "FAILED", null,
                        commentItem("PUBLISHED", "src/B.java", 1, 2, 501L)));

        ReviewHistoryConstraintException error = assertThrows(
                ReviewHistoryConstraintException.class,
                () -> service.ensurePublishHistory(task(), delivery));

        assertTrue(error.getMessage()
                .contains("outcome_finding_identity_mismatch"), error.getMessage());
        verifyNoInteractions(commentRepository);
        verify(reportRepository, never()).save(any(ReviewReport.class));
    }

    @Test
    void shouldRejectOverlongCommentPathBeforeAnyWrite() {
        String longPath = "p".repeat(ReviewHistoryService.MAX_FILE_PATH_CHARS + 1);
        ReviewReport report = report(7L, 2);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(
                        findingRow(7L, 0, "src/A.java", 1, 2),
                        findingRow(7L, 1, longPath, 3, 4)));
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.PUBLISHED,
                outcome("PUBLISHED", "FAILED", null,
                        commentItem("PUBLISHED", "src/A.java", 1, 2, 501L),
                        commentItem("PUBLISHED", longPath, 3, 4, 502L)));

        ReviewHistoryConstraintException error = assertThrows(
                ReviewHistoryConstraintException.class,
                () -> service.ensurePublishHistory(task(), delivery));

        assertTrue(error.getMessage().contains("field_limit_exceeded"),
                error.getMessage());
        assertTrue(error.getMessage().contains("comments[ordinal=1]"),
                error.getMessage());
        verifyNoInteractions(commentRepository);
        verify(reportRepository, never()).save(any(ReviewReport.class));
    }

    @Test
    void shouldRejectOutcomeStatusThatDoesNotMatchDelivery() {
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.PARTIAL,
                outcome("PUBLISHED", "FAILED", null));

        ReviewHistoryConstraintException error = assertThrows(
                ReviewHistoryConstraintException.class,
                () -> service.ensurePublishHistory(task(), delivery));

        assertTrue(error.getMessage().contains("outcome_status_mismatch"),
                error.getMessage());
        verifyNoInteractions(reportRepository);
        verifyNoInteractions(findingRepository);
        verifyNoInteractions(commentRepository);
    }

    @Test
    void shouldRejectUnknownCommentStatus() {
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.PUBLISHED,
                outcome("PUBLISHED", "FAILED", null,
                        commentItem("DONE", "src/A.java", 1, 2, 501L)));

        ReviewHistoryConstraintException error = assertThrows(
                ReviewHistoryConstraintException.class,
                () -> service.ensurePublishHistory(task(), delivery));

        assertTrue(error.getMessage().contains("outcome_status_unknown"),
                error.getMessage());
        verifyNoInteractions(reportRepository);
        verifyNoInteractions(findingRepository);
        verifyNoInteractions(commentRepository);
    }

    @Test
    void shouldRejectUnknownSummaryStatus() {
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.FAILED,
                outcome("FAILED", "SKIPPED", null));

        ReviewHistoryConstraintException error = assertThrows(
                ReviewHistoryConstraintException.class,
                () -> service.ensurePublishHistory(task(), delivery));

        assertTrue(error.getMessage().contains("summary_status_unknown"),
                error.getMessage());
        verifyNoInteractions(reportRepository);
        verifyNoInteractions(findingRepository);
        verifyNoInteractions(commentRepository);
    }

    @Test
    void shouldRejectUnreadablePublishOutcome() {
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.FAILED,
                "not-json");

        ReviewHistoryConstraintException error = assertThrows(
                ReviewHistoryConstraintException.class,
                () -> service.ensurePublishHistory(task(), delivery));

        assertTrue(error.getMessage().contains("outcome_parse_failed"),
                error.getMessage());
        verifyNoInteractions(reportRepository);
        verifyNoInteractions(findingRepository);
        verifyNoInteractions(commentRepository);
    }

    @Test
    void shouldRejectExistingCommentIdentityMismatch() {
        ReviewReport report = report(7L, 1);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(findingRow(7L, 0, "src/A.java", 1, 2)));
        when(commentRepository.findByReportIdOrderByFindingOrdinalAsc(7L))
                .thenReturn(List.of(
                        commentRow(7L, 0, 501L, "src/B.java", 1, 2)));
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.PARTIAL,
                outcome("PARTIAL", "FAILED", null,
                        commentItem("PUBLISHED", "src/A.java", 1, 2, 501L)));

        ReviewHistoryConstraintException error = assertThrows(
                ReviewHistoryConstraintException.class,
                () -> service.ensurePublishHistory(task(), delivery));

        assertTrue(error.getMessage().contains("comment_identity_mismatch"),
                error.getMessage());
        verify(commentRepository, never())
                .saveAndFlush(any(ReviewComment.class));
        verify(reportRepository, never()).save(any(ReviewReport.class));
    }

    @Test
    void shouldTreatConcurrentCommentInsertAsIdempotentWhenIdentityMatches() {
        ReviewReport report = report(7L, 1);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(findingRow(7L, 0, "src/A.java", 1, 2)));
        ReviewComment row = commentRow(7L, 0, 501L, "src/A.java", 1, 2);
        when(commentRepository.findByReportIdOrderByFindingOrdinalAsc(7L))
                .thenReturn(List.of(), List.of(row), List.of(row));
        when(commentRepository.saveAndFlush(any(ReviewComment.class)))
                .thenThrow(duplicateKeyFailure());
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.PARTIAL,
                outcome("PARTIAL", "FAILED", null,
                        commentItem("PUBLISHED", "src/A.java", 1, 2, 501L)));

        service.ensurePublishHistory(task(), delivery);

        verify(commentRepository, times(1))
                .saveAndFlush(any(ReviewComment.class));
        verify(commentRepository, never()).save(any(ReviewComment.class));
        verify(commentRepository, never()).delete(any(ReviewComment.class));
        assertEquals(0, row.getFindingOrdinal());
        assertEquals("src/A.java", row.getFilePath());
        assertEquals(1, row.getStartLine());
        assertEquals(2, row.getEndLine());

        ArgumentCaptor<ReviewReport> captor =
                ArgumentCaptor.forClass(ReviewReport.class);
        verify(reportRepository).save(captor.capture());
        assertEquals(1, captor.getValue().getPublishedCommentCount());
    }

    @Test
    void shouldRethrowWhenConcurrentCommentPathDiffers() {
        ReviewReport report = report(7L, 1);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(findingRow(7L, 0, "src/A.java", 1, 2)));
        ReviewComment conflicting =
                commentRow(7L, 0, 501L, "src/B.java", 1, 2);
        when(commentRepository.findByReportIdOrderByFindingOrdinalAsc(7L))
                .thenReturn(List.of(), List.of(conflicting));
        DataIntegrityViolationException failure =
                duplicateKeyFailure();
        when(commentRepository.saveAndFlush(any(ReviewComment.class)))
                .thenThrow(failure);
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.PARTIAL,
                outcome("PARTIAL", "FAILED", null,
                        commentItem("PUBLISHED", "src/A.java", 1, 2, 501L)));

        DataIntegrityViolationException thrown = assertThrows(
                DataIntegrityViolationException.class,
                () -> service.ensurePublishHistory(task(), delivery));

        assertSame(failure, thrown);
        assertEquals("src/B.java", conflicting.getFilePath());
        verify(commentRepository, times(1))
                .saveAndFlush(any(ReviewComment.class));
        verify(commentRepository, never()).save(any(ReviewComment.class));
        verify(commentRepository, never()).delete(any(ReviewComment.class));
        verify(reportRepository, never()).save(any(ReviewReport.class));
    }

    @Test
    void shouldRethrowWhenConcurrentCommentStartLineDiffers() {
        ReviewReport report = report(7L, 1);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(findingRow(7L, 0, "src/A.java", 1, 2)));
        ReviewComment conflicting =
                commentRow(7L, 0, 501L, "src/A.java", 2, 2);
        when(commentRepository.findByReportIdOrderByFindingOrdinalAsc(7L))
                .thenReturn(List.of(), List.of(conflicting));
        DataIntegrityViolationException failure =
                duplicateKeyFailure();
        when(commentRepository.saveAndFlush(any(ReviewComment.class)))
                .thenThrow(failure);
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.PARTIAL,
                outcome("PARTIAL", "FAILED", null,
                        commentItem("PUBLISHED", "src/A.java", 1, 2, 501L)));

        DataIntegrityViolationException thrown = assertThrows(
                DataIntegrityViolationException.class,
                () -> service.ensurePublishHistory(task(), delivery));

        assertSame(failure, thrown);
        assertEquals(2, conflicting.getStartLine());
        verify(commentRepository, times(1))
                .saveAndFlush(any(ReviewComment.class));
        verify(commentRepository, never()).save(any(ReviewComment.class));
        verify(commentRepository, never()).delete(any(ReviewComment.class));
        verify(reportRepository, never()).save(any(ReviewReport.class));
    }

    @Test
    void shouldRethrowWhenConcurrentCommentEndLineDiffers() {
        ReviewReport report = report(7L, 1);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(findingRow(7L, 0, "src/A.java", 1, 2)));
        ReviewComment conflicting =
                commentRow(7L, 0, 501L, "src/A.java", 1, 3);
        when(commentRepository.findByReportIdOrderByFindingOrdinalAsc(7L))
                .thenReturn(List.of(), List.of(conflicting));
        DataIntegrityViolationException failure =
                duplicateKeyFailure();
        when(commentRepository.saveAndFlush(any(ReviewComment.class)))
                .thenThrow(failure);
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.PARTIAL,
                outcome("PARTIAL", "FAILED", null,
                        commentItem("PUBLISHED", "src/A.java", 1, 2, 501L)));

        DataIntegrityViolationException thrown = assertThrows(
                DataIntegrityViolationException.class,
                () -> service.ensurePublishHistory(task(), delivery));

        assertSame(failure, thrown);
        assertEquals(3, conflicting.getEndLine());
        verify(commentRepository, times(1))
                .saveAndFlush(any(ReviewComment.class));
        verify(commentRepository, never()).save(any(ReviewComment.class));
        verify(commentRepository, never()).delete(any(ReviewComment.class));
        verify(reportRepository, never()).save(any(ReviewReport.class));
    }

    @Test
    void shouldRethrowWhenConcurrentCommentOrdinalIsMissing() {
        ReviewReport report = report(7L, 1);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(findingRow(7L, 0, "src/A.java", 1, 2)));
        ReviewComment otherOrdinal =
                commentRow(7L, 1, 502L, "src/A.java", 1, 2);
        when(commentRepository.findByReportIdOrderByFindingOrdinalAsc(7L))
                .thenReturn(List.of(), List.of(otherOrdinal));
        DataIntegrityViolationException failure =
                duplicateKeyFailure();
        when(commentRepository.saveAndFlush(any(ReviewComment.class)))
                .thenThrow(failure);
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.PARTIAL,
                outcome("PARTIAL", "FAILED", null,
                        commentItem("PUBLISHED", "src/A.java", 1, 2, 501L)));

        DataIntegrityViolationException thrown = assertThrows(
                DataIntegrityViolationException.class,
                () -> service.ensurePublishHistory(task(), delivery));

        assertSame(failure, thrown);
        assertEquals(1, otherOrdinal.getFindingOrdinal());
        verify(commentRepository, times(1))
                .saveAndFlush(any(ReviewComment.class));
        verify(commentRepository, never()).save(any(ReviewComment.class));
        verify(commentRepository, never()).delete(any(ReviewComment.class));
        verify(reportRepository, never()).save(any(ReviewReport.class));
    }

    @Test
    void shouldPropagateReportUpdateFailureAndSucceedOnRetry() {
        ReviewReport report = report(7L, 1);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(findingRow(7L, 0, "src/A.java", 1, 2)));
        ReviewComment row = commentRow(7L, 0, 501L, "src/A.java", 1, 2);
        when(commentRepository.findByReportIdOrderByFindingOrdinalAsc(7L))
                .thenReturn(List.of(), List.of(row), List.of(row),
                        List.of(row));
        when(commentRepository.saveAndFlush(any(ReviewComment.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));
        when(reportRepository.save(any(ReviewReport.class)))
                .thenThrow(new IllegalStateException("database down"))
                .thenAnswer(invocation -> invocation.getArgument(0));
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.PARTIAL,
                outcome("PARTIAL", "FAILED", null,
                        commentItem("PUBLISHED", "src/A.java", 1, 2, 501L)));

        assertThrows(IllegalStateException.class,
                () -> service.ensurePublishHistory(task(), delivery));

        service.ensurePublishHistory(task(), delivery);

        verify(commentRepository, times(1))
                .saveAndFlush(any(ReviewComment.class));
        verify(reportRepository, times(2)).save(any(ReviewReport.class));
    }

    @Test
    void shouldDoNothingWhenDeliveryHasNoTerminalOutcome() {
        service.ensurePublishHistory(task(),
                delivery("COMPLETED", "[]"));

        verifyNoInteractions(reportRepository);
        verifyNoInteractions(findingRepository);
        verifyNoInteractions(commentRepository);
    }

    @Test
    void shouldDoNothingWhenTerminalStatusHasNoOutcomeJson() {
        ReviewResultDelivery delivery = delivery("COMPLETED", "[]");
        ReflectionTestUtils.setField(delivery, "publishStatus",
                PublishStatus.PUBLISHED);

        service.ensurePublishHistory(task(), delivery);

        verifyNoInteractions(reportRepository);
        verifyNoInteractions(findingRepository);
        verifyNoInteractions(commentRepository);
    }

    @Test
    void shouldRejectReportCommitShaMismatchInPublishHistory() {
        ReviewReport report = report(7L, 1, "other-sha");
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.PARTIAL,
                outcome("PARTIAL", "FAILED", null,
                        commentItem("PUBLISHED", "src/A.java", 1, 2, 501L)));

        ReviewHistoryConstraintException error = assertThrows(
                ReviewHistoryConstraintException.class,
                () -> service.ensurePublishHistory(task(), delivery));

        assertTrue(error.getMessage().contains("report_commit_mismatch"),
                error.getMessage());
        verifyNoInteractions(findingRepository);
        verifyNoInteractions(commentRepository);
        verify(reportRepository, never()).save(any(ReviewReport.class));
    }

    @Test
    void shouldRejectExistingReportCommitShaMismatchInEnsureHistory() {
        ReviewReport report = report(7L, 0, "other-sha");
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));

        ReviewHistoryConstraintException error = assertThrows(
                ReviewHistoryConstraintException.class,
                () -> service.ensureHistory(task(),
                        delivery("COMPLETED", "[]")));

        assertTrue(error.getMessage().contains("report_commit_mismatch"),
                error.getMessage());
        verifyNoInteractions(findingRepository);
        verify(reportRepository, never())
                .saveAndFlush(any(ReviewReport.class));
    }

    @Test
    void shouldRejectCommitShaMismatchAfterConcurrentReportInsert() {
        ReviewReport existing = report(7L, 1, "other-sha");
        when(reportRepository.findByTaskId(1L))
                .thenReturn(Optional.empty(), Optional.of(existing));
        when(reportRepository.saveAndFlush(any(ReviewReport.class)))
                .thenThrow(duplicateKeyFailure());

        ReviewHistoryConstraintException error = assertThrows(
                ReviewHistoryConstraintException.class,
                () -> service.ensureHistory(task(), delivery("COMPLETED",
                        List.of(finding("BUG", "HIGH", 0.9, "R-1", "title",
                                "src/A.java", 1, 2, List.of())))));

        assertTrue(error.getMessage().contains("report_commit_mismatch"),
                error.getMessage());
        verify(findingRepository, never())
                .saveAndFlush(any(ReviewFinding.class));
    }

    @Test
    void shouldRejectConcurrentReportInsertWhenFindingCountDiffers() {
        ReviewReport existing = report(7L, 2);
        when(reportRepository.findByTaskId(1L))
                .thenReturn(Optional.empty(), Optional.of(existing));
        when(reportRepository.saveAndFlush(any(ReviewReport.class)))
                .thenThrow(duplicateKeyFailure());

        ReviewHistoryConstraintException error = assertThrows(
                ReviewHistoryConstraintException.class,
                () -> service.ensureHistory(task(), delivery("COMPLETED",
                        List.of(finding("BUG", "HIGH", 0.9, "R-1", "title",
                                "src/A.java", 1, 2, List.of())))));

        assertTrue(error.getMessage().contains("finding_count_mismatch"),
                error.getMessage());
        verify(findingRepository, never())
                .saveAndFlush(any(ReviewFinding.class));
    }

    @Test
    void shouldNotOverwriteExistingGithubCommentId() {
        ReviewReport report = report(7L, 1);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(findingRow(7L, 0, "src/A.java", 1, 2)));
        ReviewComment existing = commentRow(7L, 0, 501L, "src/A.java", 1, 2);
        when(commentRepository.findByReportIdOrderByFindingOrdinalAsc(7L))
                .thenReturn(List.of(existing));
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.PARTIAL,
                outcome("PARTIAL", "FAILED", null,
                        commentItem("PUBLISHED", "src/A.java", 1, 2, 999L)));

        service.ensurePublishHistory(task(), delivery);

        assertEquals(501L, existing.getGithubCommentId());
        verify(commentRepository, never())
                .saveAndFlush(any(ReviewComment.class));
        ArgumentCaptor<ReviewReport> captor =
                ArgumentCaptor.forClass(ReviewReport.class);
        verify(reportRepository).save(captor.capture());
        assertEquals(1, captor.getValue().getPublishedCommentCount());
    }

    @Test
    void shouldNotBackfillExistingNullGithubCommentId() {
        ReviewReport report = report(7L, 1);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(findingRow(7L, 0, "src/A.java", 1, 2)));
        ReviewComment existing = commentRow(7L, 0, null, "src/A.java", 1, 2);
        when(commentRepository.findByReportIdOrderByFindingOrdinalAsc(7L))
                .thenReturn(List.of(existing));
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.PARTIAL,
                outcome("PARTIAL", "FAILED", null,
                        commentItem("PUBLISHED", "src/A.java", 1, 2, 501L)));

        service.ensurePublishHistory(task(), delivery);

        assertNull(existing.getGithubCommentId());
        verify(commentRepository, never())
                .saveAndFlush(any(ReviewComment.class));
    }

    @Test
    void shouldRejectExistingCommentLineMismatch() {
        ReviewReport report = report(7L, 1);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(findingRow(7L, 0, "src/A.java", 1, 2)));
        when(commentRepository.findByReportIdOrderByFindingOrdinalAsc(7L))
                .thenReturn(List.of(
                        commentRow(7L, 0, 501L, "src/A.java", 1, 3)));
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.PARTIAL,
                outcome("PARTIAL", "FAILED", null,
                        commentItem("PUBLISHED", "src/A.java", 1, 2, 501L)));

        ReviewHistoryConstraintException error = assertThrows(
                ReviewHistoryConstraintException.class,
                () -> service.ensurePublishHistory(task(), delivery));

        assertTrue(error.getMessage().contains("comment_identity_mismatch"),
                error.getMessage());
        verify(commentRepository, never())
                .saveAndFlush(any(ReviewComment.class));
        verify(reportRepository, never()).save(any(ReviewReport.class));
    }

    @Test
    void shouldRejectIncompleteFindingRows() {
        ReviewReport report = report(7L, 2);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(findingRow(7L, 0, "src/A.java", 1, 2)));
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.PARTIAL,
                outcome("PARTIAL", "FAILED", null,
                        commentItem("PUBLISHED", "src/A.java", 1, 2, 501L),
                        commentItem("PUBLISHED", "src/B.java", 3, 4, 502L)));

        ReviewHistoryConstraintException error = assertThrows(
                ReviewHistoryConstraintException.class,
                () -> service.ensurePublishHistory(task(), delivery));

        assertTrue(error.getMessage().contains("report_findings_incomplete"),
                error.getMessage());
        verifyNoInteractions(commentRepository);
        verify(reportRepository, never()).save(any(ReviewReport.class));
    }

    @Test
    void shouldNotDeleteExistingCommentThatIsNotPublishedNow() {
        ReviewReport report = report(7L, 1);
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(findingRow(7L, 0, "src/A.java", 1, 2)));
        ReviewComment existing = commentRow(7L, 0, 501L, "src/A.java", 1, 2);
        when(commentRepository.findByReportIdOrderByFindingOrdinalAsc(7L))
                .thenReturn(List.of(existing));
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.FAILED,
                outcome("FAILED", "FAILED", null,
                        commentItem("SKIPPED", "src/A.java", 1, 2, null)));

        service.ensurePublishHistory(task(), delivery);

        verify(commentRepository, never())
                .saveAndFlush(any(ReviewComment.class));
        verify(commentRepository, never()).delete(any(ReviewComment.class));
        ArgumentCaptor<ReviewReport> captor =
                ArgumentCaptor.forClass(ReviewReport.class);
        verify(reportRepository).save(captor.capture());
        assertEquals(1, captor.getValue().getPublishedCommentCount());
    }

    @Test
    void shouldRethrowNonUniqueReportFailureWithoutRereading() throws Exception {
        ReviewReport existing = report(7L, 1);
        DataIntegrityViolationException failure = nonUniqueFailure();
        when(reportRepository.findByTaskId(1L))
                .thenReturn(Optional.empty(), Optional.of(existing));
        when(reportRepository.saveAndFlush(any(ReviewReport.class)))
                .thenThrow(failure);

        DataIntegrityViolationException thrown = assertThrows(
                DataIntegrityViolationException.class,
                () -> service.ensureHistory(task(),
                        delivery("COMPLETED", "[]")));

        assertSame(failure, thrown);
        verify(reportRepository, times(1)).findByTaskId(1L);
        verify(findingRepository, never())
                .findByReportIdOrderByOrdinalAsc(any());
    }

    @Test
    void shouldRethrowNonUniqueFindingFailureWithoutRereading()
            throws Exception {
        ReviewReport report = report(7L, 1);
        DataIntegrityViolationException failure = nonUniqueFailure();
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(), List.of(findingRow(7L, 0)));
        when(findingRepository.saveAndFlush(any(ReviewFinding.class)))
                .thenThrow(failure);

        DataIntegrityViolationException thrown = assertThrows(
                DataIntegrityViolationException.class,
                () -> service.ensureHistory(task(), delivery("COMPLETED",
                        List.of(finding("BUG", "HIGH", 0.9, "R-1", "title",
                                "src/A.java", 1, 2, List.of())))));

        assertSame(failure, thrown);
        verify(findingRepository, times(1))
                .findByReportIdOrderByOrdinalAsc(7L);
    }

    @Test
    void shouldRethrowUniqueFindingConflictWhenIdentityDiffers()
            throws Exception {
        ReviewReport report = report(7L, 1);
        ReviewFinding conflicting = new ReviewFinding(7L, 0, "BUG", "LOW",
                0.5, "R-OTHER", "other", "src/A.java", 1, 2,
                "description", "reason", "suggestion", "[]");
        DataIntegrityViolationException failure = duplicateKeyFailure();
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(), List.of(conflicting));
        when(findingRepository.saveAndFlush(any(ReviewFinding.class)))
                .thenThrow(failure);

        DataIntegrityViolationException thrown = assertThrows(
                DataIntegrityViolationException.class,
                () -> service.ensureHistory(task(), delivery("COMPLETED",
                        List.of(finding("BUG", "HIGH", 0.9, "R-1", "title",
                                "src/A.java", 1, 2, List.of())))));

        assertSame(failure, thrown);
        verify(findingRepository, times(2))
                .findByReportIdOrderByOrdinalAsc(7L);
        verify(reportRepository, never()).save(any(ReviewReport.class));
    }

    @Test
    void shouldRethrowNonUniqueCommentFailureWithoutRereading() {
        ReviewReport report = report(7L, 1);
        ReviewComment row = commentRow(7L, 0, 501L, "src/A.java", 1, 2);
        DataIntegrityViolationException failure = nonUniqueFailure();
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.of(report));
        when(findingRepository.findByReportIdOrderByOrdinalAsc(7L))
                .thenReturn(List.of(findingRow(7L, 0, "src/A.java", 1, 2)));
        when(commentRepository.findByReportIdOrderByFindingOrdinalAsc(7L))
                .thenReturn(List.of(), List.of(row));
        when(commentRepository.saveAndFlush(any(ReviewComment.class)))
                .thenThrow(failure);
        ReviewResultDelivery delivery = publishDelivery(PublishStatus.PARTIAL,
                outcome("PARTIAL", "FAILED", null,
                        commentItem("PUBLISHED", "src/A.java", 1, 2, 501L)));

        DataIntegrityViolationException thrown = assertThrows(
                DataIntegrityViolationException.class,
                () -> service.ensurePublishHistory(task(), delivery));

        assertSame(failure, thrown);
        verify(commentRepository, times(1))
                .findByReportIdOrderByFindingOrdinalAsc(7L);
        verify(reportRepository, never()).save(any(ReviewReport.class));
    }

    private static DataIntegrityViolationException duplicateKeyFailure() {
        return new DuplicateKeyException("duplicate key");
    }

    private static DataIntegrityViolationException nonUniqueFailure() {
        return new DataIntegrityViolationException("not null",
                new SQLException("not null", "23000", 1048));
    }

    private void assertRejectedWithoutWrites(ReviewResultFinding finding,
                                             String field, int limit)
            throws Exception {
        ReviewResultDelivery delivery =
                delivery("COMPLETED", List.of(finding));

        ReviewHistoryConstraintException error = assertThrows(
                ReviewHistoryConstraintException.class,
                () -> service.ensureHistory(task(), delivery));

        assertTrue(error.getMessage().contains("field_limit_exceeded"),
                error.getMessage());
        assertTrue(error.getMessage().contains(field), error.getMessage());
        assertTrue(error.getMessage().contains("limit=" + limit),
                error.getMessage());
        verifyNoInteractions(reportRepository);
        verifyNoInteractions(findingRepository);
    }

    private void stubFreshReport() {
        when(reportRepository.findByTaskId(1L)).thenReturn(Optional.empty());
        when(reportRepository.saveAndFlush(any(ReviewReport.class)))
                .thenAnswer(invocation -> {
                    ReviewReport saved = invocation.getArgument(0);
                    ReflectionTestUtils.setField(saved, "id", 7L);
                    return saved;
                });
    }

    private ReviewResultDelivery delivery(String aiStatus,
                                          List<ReviewResultFinding> findings)
            throws Exception {
        return delivery(aiStatus, objectMapper.writeValueAsString(findings));
    }

    private static ReviewResultDelivery delivery(String aiStatus,
                                                 String findingsJson) {
        return new ReviewResultDelivery(1L, SHA, aiStatus, findingsJson,
                PublishStatus.PENDING);
    }

    private static ReviewTask task() {
        ReviewTask task = new ReviewTask("o", "r", 1, SHA);
        ReflectionTestUtils.setField(task, "id", 1L);
        return task;
    }

    private static ReviewResultFinding finding(String category, String severity,
                                               double confidence, String ruleId,
                                               String title, String filePath,
                                               int startLine, int endLine,
                                               List<String> references) {
        return new ReviewResultFinding(category, severity, confidence, ruleId,
                title, filePath, startLine, endLine, "description", "reason",
                "suggestion", references);
    }

    private static ReviewResultFinding textFinding(String description) {
        return textFinding(description, "reason", "suggestion");
    }

    private static ReviewResultFinding textFinding(String description,
                                                   String reason,
                                                   String suggestion) {
        return new ReviewResultFinding("BUG", "HIGH", 0.9, "R-1", "title",
                "src/A.java", 1, 2, description, reason, suggestion,
                List.of());
    }

    private static ReviewReport report(long id, int findingCount) {
        return report(id, findingCount, SHA);
    }

    private static ReviewReport report(long id, int findingCount,
                                       String commitSha) {
        return report(id, findingCount, commitSha, PublishStatus.PENDING,
                null, null);
    }

    private static ReviewReport report(long id, int findingCount,
                                       PublishStatus publishStatus,
                                       Long summaryCommentId,
                                       LocalDateTime publishedAt) {
        return report(id, findingCount, SHA, publishStatus, summaryCommentId,
                publishedAt);
    }

    private static ReviewReport report(long id, int findingCount,
                                       String commitSha,
                                       PublishStatus publishStatus,
                                       Long summaryCommentId,
                                       LocalDateTime publishedAt) {
        ReviewReport report = new ReviewReport(1L, commitSha, "COMPLETED",
                publishStatus, findingCount, 0, summaryCommentId,
                publishedAt);
        ReflectionTestUtils.setField(report, "id", id);
        return report;
    }

    private static ReviewFinding findingRow(long reportId, int ordinal) {
        return findingRow(reportId, ordinal, "src/A.java", 1, 2);
    }

    private static ReviewFinding findingRow(long reportId, int ordinal,
                                            String filePath, int startLine,
                                            int endLine) {
        return new ReviewFinding(reportId, ordinal, "BUG", "HIGH", 0.9, "R-1",
                "title", filePath, startLine, endLine, "d", "r", "s", "[]");
    }

    private static ReviewComment commentRow(long reportId, int ordinal,
                                            Long githubCommentId,
                                            String filePath, int startLine,
                                            int endLine) {
        return new ReviewComment(reportId, ordinal, githubCommentId, filePath,
                startLine, endLine);
    }

    private static ReviewResultDelivery publishDelivery(
            PublishStatus status, String outcomeJson) {
        return publishDelivery(status, outcomeJson, null);
    }

    private static ReviewResultDelivery publishDelivery(
            PublishStatus status, String outcomeJson,
            LocalDateTime publishedAt) {
        ReviewResultDelivery delivery = new ReviewResultDelivery(1L, SHA,
                "COMPLETED", "[]", PublishStatus.PENDING);
        delivery.recordPublishOutcome(status, outcomeJson, publishedAt);
        return delivery;
    }

    private static String outcome(String status, String summaryStatus,
                                  Long summaryCommentId,
                                  String... comments) {
        return "{\"status\":\"" + status + "\",\"summary\":{\"status\":\""
                + summaryStatus + "\",\"reason\":null,\"commentId\":"
                + summaryCommentId + "},\"comments\":["
                + String.join(",", comments) + "]}";
    }

    private static String commentItem(String status, String filePath,
                                      int startLine, int endLine,
                                      Long commentId) {
        return "{\"filePath\":\"" + filePath + "\",\"startLine\":"
                + startLine + ",\"endLine\":" + endLine + ",\"status\":\""
                + status + "\",\"reason\":null,\"commentId\":"
                + commentId + "}";
    }
}