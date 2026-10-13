package cn.codesentinel.task;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.dao.DataIntegrityViolationException;

import java.time.LocalDateTime;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class ReviewResultServiceTest {

    private static final String SHA = "abc123def456";
    private static final String OUTCOME_JSON = "{\"status\":\"PARTIAL\"}";

    private ReviewTaskService reviewTaskService;
    private ReviewResultDeliveryRepository repository;
    private ObjectMapper objectMapper;
    private ReviewResultPublishService publishService;
    private ReviewResultService service;

    @BeforeEach
    void setUp() {
        reviewTaskService = mock(ReviewTaskService.class);
        repository = mock(ReviewResultDeliveryRepository.class);
        objectMapper = new ObjectMapper();
        publishService = mock(ReviewResultPublishService.class);
        service = new ReviewResultService(
                reviewTaskService, repository, objectMapper, publishService);
    }

    @Test
    void shouldPublishFirstReceiptAndReturnFinalStatus() throws Exception {
        when(reviewTaskService.getTaskById(1L)).thenReturn(task(SHA));
        when(repository.findByTaskIdAndCommitSha(1L, SHA))
                .thenReturn(Optional.empty());
        when(repository.saveAndFlush(any(ReviewResultDelivery.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));
        LocalDateTime publishedAt = LocalDateTime.of(2026, 1, 2, 3, 4);
        when(publishService.publish(any(ReviewTask.class),
                any(ReviewResultDelivery.class)))
                .thenReturn(new ReviewResultPublishResult(
                        PublishStatus.PARTIAL, OUTCOME_JSON, publishedAt));

        List<ReviewResultFinding> findings = List.of(validFinding());
        ReviewResultResponse response = service.receiveResult(
                1L, request(SHA, "COMPLETED", findings));

        assertFalse(response.duplicate());
        assertEquals("PARTIAL", response.publishStatus());
        assertEquals(1L, response.taskId());
        assertEquals(SHA, response.commitSha());
        assertNotNull(response.receivedAt());

        ArgumentCaptor<ReviewResultDelivery> savedCaptor =
                ArgumentCaptor.forClass(ReviewResultDelivery.class);
        verify(repository).saveAndFlush(savedCaptor.capture());
        ReviewResultDelivery saved = savedCaptor.getValue();

        // B1 reception fields stay frozen
        assertEquals(1L, saved.getTaskId());
        assertEquals(SHA, saved.getCommitSha());
        assertEquals("COMPLETED", saved.getAiStatus());
        assertEquals(canonical(findings), saved.getFindingsJson());

        // publication columns come from the publish result
        assertEquals(PublishStatus.PARTIAL, saved.getPublishStatus());
        assertEquals(OUTCOME_JSON, saved.getPublishOutcomeJson());
        assertEquals(publishedAt, saved.getPublishedAt());

        ArgumentCaptor<ReviewResultDelivery> publishCaptor =
                ArgumentCaptor.forClass(ReviewResultDelivery.class);
        verify(publishService).publish(any(ReviewTask.class),
                publishCaptor.capture());
        assertSame(saved, publishCaptor.getValue());
        verify(repository).save(saved);
    }

    @Test
    void shouldRecordFailedPublicationOnFirstReceipt() {
        when(reviewTaskService.getTaskById(1L)).thenReturn(task(SHA));
        when(repository.findByTaskIdAndCommitSha(1L, SHA))
                .thenReturn(Optional.empty());
        when(repository.saveAndFlush(any(ReviewResultDelivery.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));
        when(publishService.publish(any(ReviewTask.class),
                any(ReviewResultDelivery.class)))
                .thenReturn(new ReviewResultPublishResult(
                        PublishStatus.FAILED, "{\"status\":\"FAILED\"}",
                        null));

        ReviewResultResponse response = service.receiveResult(
                1L, request(SHA, "COMPLETED", List.of(validFinding())));

        assertFalse(response.duplicate());
        assertEquals("FAILED", response.publishStatus());

        ArgumentCaptor<ReviewResultDelivery> captor =
                ArgumentCaptor.forClass(ReviewResultDelivery.class);
        verify(repository).saveAndFlush(captor.capture());
        assertEquals(PublishStatus.FAILED,
                captor.getValue().getPublishStatus());
        assertNull(captor.getValue().getPublishedAt());
    }

    @Test
    void shouldReturnDuplicateForIdenticalPayloadWithoutPublishing()
            throws Exception {
        List<ReviewResultFinding> findings = List.of(validFinding());
        ReviewResultDelivery existing = delivery(
                "COMPLETED", canonical(findings), PublishStatus.PUBLISHED);
        when(reviewTaskService.getTaskById(1L)).thenReturn(task(SHA));
        when(repository.findByTaskIdAndCommitSha(1L, SHA))
                .thenReturn(Optional.of(existing));

        ReviewResultResponse response = service.receiveResult(
                1L, request(SHA, "COMPLETED", findings));

        assertTrue(response.duplicate());
        assertEquals("PUBLISHED", response.publishStatus());
        verifyNoInteractions(publishService);
        verify(repository, never())
                .saveAndFlush(any(ReviewResultDelivery.class));
        verify(repository, never()).save(any(ReviewResultDelivery.class));
    }

    @Test
    void shouldRejectConflictingFindingsPayload() throws Exception {
        ReviewResultDelivery existing = delivery(
                "COMPLETED", canonical(List.of(validFinding())),
                PublishStatus.PENDING);
        when(reviewTaskService.getTaskById(1L)).thenReturn(task(SHA));
        when(repository.findByTaskIdAndCommitSha(1L, SHA))
                .thenReturn(Optional.of(existing));

        ReviewResultFinding other = new ReviewResultFinding(
                "BUG", "LOW", 0.5, "R-2", "other title", "src/B.java",
                3, 3, "other description", "other reason", "other suggestion",
                List.of());

        ReviewResultRejectedException error = assertThrows(
                ReviewResultRejectedException.class,
                () -> service.receiveResult(1L,
                        request(SHA, "COMPLETED", List.of(other))));

        assertEquals(409, error.getStatus());
        assertTrue(error.getMessage().contains("different result"));
        verify(repository, never())
                .saveAndFlush(any(ReviewResultDelivery.class));
    }

    @Test
    void shouldRejectConflictingAiStatus() throws Exception {
        ReviewResultDelivery existing = delivery(
                "DEGRADED", canonical(List.of(validFinding())),
                PublishStatus.PENDING);
        when(reviewTaskService.getTaskById(1L)).thenReturn(task(SHA));
        when(repository.findByTaskIdAndCommitSha(1L, SHA))
                .thenReturn(Optional.of(existing));

        ReviewResultRejectedException error = assertThrows(
                ReviewResultRejectedException.class,
                () -> service.receiveResult(1L,
                        request(SHA, "COMPLETED", List.of(validFinding()))));

        assertEquals(409, error.getStatus());
    }

    @Test
    void shouldRejectUnknownAiStatus() {
        ReviewResultRejectedException error = assertThrows(
                ReviewResultRejectedException.class,
                () -> service.receiveResult(1L,
                        request(SHA, "FAILED", List.of())));

        assertEquals(422, error.getStatus());
        assertTrue(error.getMessage().contains("status"));
        verifyNoInteractions(reviewTaskService);
        verifyNoInteractions(repository);
    }

    @Test
    void shouldRejectMissingFindingsList() {
        ReviewResultRejectedException error = assertThrows(
                ReviewResultRejectedException.class,
                () -> service.receiveResult(1L,
                        new ReviewResultRequest(SHA, "COMPLETED", null)));

        assertEquals(422, error.getStatus());
        assertTrue(error.getMessage().contains("findings"));
    }

    @Test
    void shouldRejectBlankCommitShaBeforeTaskLookup() {
        ReviewResultRejectedException error = assertThrows(
                ReviewResultRejectedException.class,
                () -> service.receiveResult(1L,
                        new ReviewResultRequest("  ", "COMPLETED", List.of())));

        assertEquals(422, error.getStatus());
        verifyNoInteractions(reviewTaskService);
    }

    @Test
    void shouldRejectInvalidFindingEnumsRangesAndConfidence() {
        List<ReviewResultFinding> invalidFindings = Arrays.asList(
                finding("FEATURE", "HIGH", 0.5, 1, 1, List.of()),
                finding("BUG", "SEVERE", 0.5, 1, 1, List.of()),
                finding("BUG", "HIGH", 1.5, 1, 1, List.of()),
                finding("BUG", "HIGH", -0.1, 1, 1, List.of()),
                finding("BUG", "HIGH", null, 1, 1, List.of()),
                finding("BUG", "HIGH", 0.5, 0, 1, List.of()),
                finding("BUG", "HIGH", 0.5, 3, 2, List.of()),
                finding("BUG", "HIGH", 0.5, 1, 1, null),
                null);

        for (ReviewResultFinding invalid : invalidFindings) {
            ReviewResultRejectedException error = assertThrows(
                    ReviewResultRejectedException.class,
                    () -> service.receiveResult(1L, request(SHA, "COMPLETED",
                            Collections.singletonList(invalid))));
            assertEquals(422, error.getStatus());
            assertTrue(error.getMessage().startsWith("findings["),
                    error.getMessage());
        }
    }

    @Test
    void shouldRejectBlankFindingTextFields() {
        List<ReviewResultFinding> invalidFindings = List.of(
                textFinding(" ", "title", "src/A.java", "d", "r", "s"),
                textFinding("R-1", "", "src/A.java", "d", "r", "s"),
                textFinding("R-1", "title", "  ", "d", "r", "s"),
                textFinding("R-1", "title", "src/A.java", "", "r", "s"),
                textFinding("R-1", "title", "src/A.java", "d", " ", "s"),
                textFinding("R-1", "title", "src/A.java", "d", "r", ""));

        for (ReviewResultFinding invalid : invalidFindings) {
            ReviewResultRejectedException error = assertThrows(
                    ReviewResultRejectedException.class,
                    () -> service.receiveResult(1L, request(SHA, "COMPLETED",
                            List.of(invalid))));
            assertEquals(422, error.getStatus());
            assertTrue(error.getMessage().contains("must not be blank"),
                    error.getMessage());
        }
    }

    @Test
    void shouldRejectShaMismatchBeforePersistence() {
        when(reviewTaskService.getTaskById(1L)).thenReturn(task("other-sha"));

        ReviewResultRejectedException error = assertThrows(
                ReviewResultRejectedException.class,
                () -> service.receiveResult(1L,
                        request(SHA, "COMPLETED", List.of())));

        assertEquals(409, error.getStatus());
        verifyNoInteractions(repository);
    }

    @Test
    void shouldPropagateTaskNotFound() {
        when(reviewTaskService.getTaskById(99L))
                .thenThrow(new TaskNotFoundException(99L));

        assertThrows(TaskNotFoundException.class,
                () -> service.receiveResult(99L,
                        request(SHA, "COMPLETED", List.of())));
    }

    @Test
    void shouldAcceptEmptyFindingsList() {
        when(reviewTaskService.getTaskById(1L)).thenReturn(task(SHA));
        when(repository.findByTaskIdAndCommitSha(1L, SHA))
                .thenReturn(Optional.empty());
        when(repository.saveAndFlush(any(ReviewResultDelivery.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));
        when(publishService.publish(any(ReviewTask.class),
                any(ReviewResultDelivery.class)))
                .thenReturn(new ReviewResultPublishResult(
                        PublishStatus.PUBLISHED, "{\"status\":\"PUBLISHED\"}",
                        LocalDateTime.of(2026, 1, 1, 0, 0)));

        ReviewResultResponse response = service.receiveResult(
                1L, request(SHA, "DEGRADED", List.of()));

        assertFalse(response.duplicate());
        assertEquals("PUBLISHED", response.publishStatus());

        ArgumentCaptor<ReviewResultDelivery> captor =
                ArgumentCaptor.forClass(ReviewResultDelivery.class);
        verify(repository).saveAndFlush(captor.capture());
        assertEquals("[]", captor.getValue().getFindingsJson());
        assertEquals("DEGRADED", captor.getValue().getAiStatus());
        verify(publishService).publish(any(ReviewTask.class),
                any(ReviewResultDelivery.class));
    }

    @Test
    void shouldReturnDuplicateWhenConcurrentInsertConflictsWithCommittedRecord()
            throws Exception {
        List<ReviewResultFinding> findings = List.of(validFinding());
        ReviewResultDelivery existing = delivery(
                "COMPLETED", canonical(findings), PublishStatus.PENDING);
        when(reviewTaskService.getTaskById(1L)).thenReturn(task(SHA));
        when(repository.findByTaskIdAndCommitSha(1L, SHA))
                .thenReturn(Optional.empty(), Optional.of(existing));
        when(repository.saveAndFlush(any(ReviewResultDelivery.class)))
                .thenThrow(new DataIntegrityViolationException(
                        "duplicate key"));

        ReviewResultResponse response = service.receiveResult(
                1L, request(SHA, "COMPLETED", findings));

        assertTrue(response.duplicate());
        assertEquals("PENDING", response.publishStatus());
        verifyNoInteractions(publishService);
    }

    @Test
    void shouldRejectWhenConcurrentInsertIsNotYetCommitted() {
        when(reviewTaskService.getTaskById(1L)).thenReturn(task(SHA));
        when(repository.findByTaskIdAndCommitSha(1L, SHA))
                .thenReturn(Optional.empty());
        when(repository.saveAndFlush(any(ReviewResultDelivery.class)))
                .thenThrow(new DataIntegrityViolationException(
                        "duplicate key"));

        ReviewResultRejectedException error = assertThrows(
                ReviewResultRejectedException.class,
                () -> service.receiveResult(1L,
                        request(SHA, "COMPLETED", List.of())));

        assertEquals(409, error.getStatus());
        assertTrue(error.getMessage().contains("concurrent"));
        verifyNoInteractions(publishService);
    }

    @Test
    void shouldPropagateNonDuplicatePersistenceFailure() {
        when(reviewTaskService.getTaskById(1L)).thenReturn(task(SHA));
        when(repository.findByTaskIdAndCommitSha(1L, SHA))
                .thenReturn(Optional.empty());
        when(repository.saveAndFlush(any(ReviewResultDelivery.class)))
                .thenThrow(new DataAccessResourceFailureException(
                        "database down"));

        assertThrows(DataAccessResourceFailureException.class,
                () -> service.receiveResult(1L,
                        request(SHA, "COMPLETED", List.of())));
        verifyNoInteractions(publishService);
    }

    private ReviewResultDelivery delivery(String aiStatus, String findingsJson,
                                          PublishStatus publishStatus) {
        return new ReviewResultDelivery(1L, SHA, aiStatus, findingsJson,
                publishStatus);
    }

    private String canonical(List<ReviewResultFinding> findings)
            throws Exception {
        return objectMapper.writeValueAsString(findings);
    }

    private static ReviewTask task(String commitSha) {
        return new ReviewTask("o", "r", 1, commitSha);
    }

    private static ReviewResultRequest request(String commitSha, String status,
                                               List<ReviewResultFinding> findings) {
        return new ReviewResultRequest(commitSha, status, findings);
    }

    private static ReviewResultFinding validFinding() {
        return new ReviewResultFinding("BUG", "HIGH", 0.9, "R-1", "title",
                "src/A.java", 1, 2, "description", "reason", "suggestion",
                List.of("CWE-1"));
    }

    private static ReviewResultFinding finding(String category, String severity,
                                               Double confidence, int start,
                                               int end,
                                               List<String> references) {
        return new ReviewResultFinding(category, severity, confidence, "R-1",
                "title", "src/A.java", start, end, "description", "reason",
                "suggestion", references);
    }

    private static ReviewResultFinding textFinding(String ruleId, String title,
                                                   String filePath,
                                                   String description,
                                                   String reason,
                                                   String suggestion) {
        return new ReviewResultFinding("BUG", "HIGH", 0.9, ruleId, title,
                filePath, 1, 2, description, reason, suggestion, List.of());
    }
}