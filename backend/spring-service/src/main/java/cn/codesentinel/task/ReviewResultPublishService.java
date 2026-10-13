package cn.codesentinel.task;

import cn.codesentinel.comment.InlineCommentFinding;
import cn.codesentinel.comment.ReviewSummaryMarkdownBuilder;
import cn.codesentinel.comment.ReviewSummaryStatus;
import cn.codesentinel.comment.SummaryFinding;
import cn.codesentinel.github.GithubApiException;
import cn.codesentinel.github.GithubAuthService;
import cn.codesentinel.github.GithubIssueCommentClient;
import cn.codesentinel.github.InstallationToken;
import cn.codesentinel.github.IssueCommentRequest;
import cn.codesentinel.github.IssueCommentResponse;
import cn.codesentinel.github.ReviewCommentOutcome;
import cn.codesentinel.github.ReviewCommentPublisher;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClientException;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/**
 * Synchronous publication of one persisted review result (Phase 9.5.3C).
 *
 * <p>Only the first receipt of a (taskId, commitSha) key reaches this
 * service; duplicate receipts never publish again. The stored findings
 * snapshot is projected onto the inline comment publisher and the PR
 * summary issue comment, and the terminal {@link PublishStatus} plus a
 * stable per-item outcome JSON is returned for persistence on the
 * delivery row.
 *
 * <p>Status rules:
 * <ul>
 *   <li>{@code PUBLISHED}: the summary and every inline finding were
 *       published;</li>
 *   <li>{@code FAILED}: nothing was published and no external side
 *       effect is uncertain (setup failures before any request,
 *       definitive HTTP failures, skipped placements);</li>
 *   <li>{@code PARTIAL}: everything else, including transport failures
 *       whose external outcome is unknown. A known success is never
 *       discarded because of a later failure.</li>
 * </ul>
 *
 * <p>{@code publishedAt} is set only when at least one item was
 * confirmed published. External GitHub side effects are not
 * transactional and are never rolled back here; failures are recorded
 * and never thrown into the receipt path. No automatic retry or crash
 * recovery exists (documented limitation).
 */
@Service
public class ReviewResultPublishService {

    static final String REASON_SETUP_FAILED = "setup_failed";
    static final String REASON_FINDINGS_PARSE_FAILED =
            "findings_parse_failed";
    static final String REASON_TRANSPORT_ERROR =
            ReviewCommentPublisher.FAILURE_REASON_TRANSPORT;
    static final String REASON_GITHUB_API_ERROR =
            ReviewCommentPublisher.FAILURE_REASON_GITHUB_API;
    static final String HTTP_REASON_PREFIX =
            ReviewCommentPublisher.FAILURE_REASON_HTTP_PREFIX;

    private static final String STATUS_PUBLISHED = "PUBLISHED";
    private static final String STATUS_FAILED = "FAILED";
    private static final String STATUS_DEGRADED = "DEGRADED";

    private static final Logger log =
            LoggerFactory.getLogger(ReviewResultPublishService.class);

    private final ObjectMapper objectMapper;
    private final ReviewCommentPublisher commentPublisher;
    private final GithubIssueCommentClient issueCommentClient;
    private final GithubAuthService authService;

    public ReviewResultPublishService(
            ObjectMapper objectMapper,
            ReviewCommentPublisher commentPublisher,
            GithubIssueCommentClient issueCommentClient,
            GithubAuthService authService) {
        this.objectMapper = objectMapper;
        this.commentPublisher = commentPublisher;
        this.issueCommentClient = issueCommentClient;
        this.authService = authService;
    }

    public ReviewResultPublishResult publish(ReviewTask task,
                                             ReviewResultDelivery delivery) {
        Objects.requireNonNull(task, "task");
        Objects.requireNonNull(delivery, "delivery");

        List<ReviewResultFinding> findings;
        try {
            findings = parseFindings(delivery.getFindingsJson());
        } catch (Exception error) {
            log.error(
                    "Stored findings could not be parsed for task {} "
                            + "commit {}: {}",
                    delivery.getTaskId(), delivery.getCommitSha(),
                    error.getClass().getSimpleName());
            return new ReviewResultPublishResult(PublishStatus.FAILED,
                    parseFailureOutcomeJson(), null);
        }

        List<ReviewCommentOutcome> outcomes =
                publishInlineComments(task, delivery, findings);
        SummaryOutcome summary = publishSummary(task, delivery, findings);
        ReviewResultPublishResult result = assemble(outcomes, summary);

        log.info(
                "Publication finished for task {} commit {}: status={}",
                delivery.getTaskId(), delivery.getCommitSha(),
                result.status());
        return result;
    }

    private List<ReviewCommentOutcome> publishInlineComments(
            ReviewTask task, ReviewResultDelivery delivery,
            List<ReviewResultFinding> findings) {
        try {
            return commentPublisher.publish(task.getOwner(), task.getRepo(),
                    task.getPrNumber(), delivery.getCommitSha(),
                    toInlineFindings(findings));
        } catch (Exception error) {
            // The publisher contract fetches the installation token and
            // the changed files before any comment request, so this is a
            // setup failure with no external side effect to lose.
            log.error(
                    "Inline comment publishing could not start for task "
                            + "{} commit {}: {}",
                    delivery.getTaskId(), delivery.getCommitSha(),
                    failureReason(error));
            List<ReviewCommentOutcome> outcomes =
                    new ArrayList<>(findings.size());
            for (ReviewResultFinding finding : findings) {
                outcomes.add(ReviewCommentOutcome.failed(
                        toInlineFinding(finding), REASON_SETUP_FAILED));
            }
            return outcomes;
        }
    }

    private SummaryOutcome publishSummary(ReviewTask task,
                                          ReviewResultDelivery delivery,
                                          List<ReviewResultFinding> findings) {
        String markdown = ReviewSummaryMarkdownBuilder.build(
                toSummaryFindings(findings),
                new ReviewSummaryStatus(
                        STATUS_DEGRADED.equals(delivery.getAiStatus()),
                        List.of()));

        InstallationToken token;
        try {
            token = authService.getInstallationToken();
        } catch (Exception error) {
            log.error(
                    "PR summary publishing could not start for task {} "
                            + "commit {}: {}",
                    delivery.getTaskId(), delivery.getCommitSha(),
                    failureReason(error));
            return SummaryOutcome.failed(REASON_SETUP_FAILED, false);
        }

        try {
            IssueCommentResponse response = issueCommentClient.createComment(
                    task.getOwner(), task.getRepo(), task.getPrNumber(),
                    new IssueCommentRequest(markdown), token);
            return SummaryOutcome.published(
                    response == null ? null : response.id());
        } catch (Exception error) {
            String reason = failureReason(error);
            boolean uncertain = error instanceof RestClientException;
            log.error(
                    "PR summary publishing failed for task {} commit {}: {}",
                    delivery.getTaskId(), delivery.getCommitSha(), reason);
            return SummaryOutcome.failed(reason, uncertain);
        }
    }

    private ReviewResultPublishResult assemble(
            List<ReviewCommentOutcome> outcomes, SummaryOutcome summary) {
        long published = outcomes.stream()
                .filter(outcome -> outcome.status()
                        == ReviewCommentOutcome.Status.PUBLISHED)
                .count();
        if (STATUS_PUBLISHED.equals(summary.status())) {
            published++;
        }

        boolean uncertain = outcomes.stream().anyMatch(outcome ->
                outcome.status() == ReviewCommentOutcome.Status.FAILED
                        && REASON_TRANSPORT_ERROR.equals(outcome.reason()))
                || (STATUS_FAILED.equals(summary.status())
                        && summary.uncertain());

        boolean everythingPublished =
                STATUS_PUBLISHED.equals(summary.status())
                        && outcomes.stream().allMatch(outcome ->
                        outcome.status()
                                == ReviewCommentOutcome.Status.PUBLISHED);

        PublishStatus status;
        if (everythingPublished) {
            status = PublishStatus.PUBLISHED;
        } else if (published == 0 && !uncertain) {
            status = PublishStatus.FAILED;
        } else {
            status = PublishStatus.PARTIAL;
        }

        LocalDateTime publishedAt =
                published > 0 ? LocalDateTime.now() : null;
        return new ReviewResultPublishResult(status,
                toOutcomeJson(status, outcomes, summary), publishedAt);
    }

    private String toOutcomeJson(PublishStatus status,
                                 List<ReviewCommentOutcome> outcomes,
                                 SummaryOutcome summary) {
        Map<String, Object> root = new LinkedHashMap<>();
        root.put("status", status.name());

        Map<String, Object> summaryJson = new LinkedHashMap<>();
        summaryJson.put("status", summary.status());
        summaryJson.put("reason", summary.reason());
        summaryJson.put("commentId", summary.commentId());
        root.put("summary", summaryJson);

        List<Map<String, Object>> comments =
                new ArrayList<>(outcomes.size());
        for (ReviewCommentOutcome outcome : outcomes) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("filePath", outcome.filePath());
            item.put("startLine", outcome.startLine());
            item.put("endLine", outcome.endLine());
            item.put("status", outcome.status().name());
            item.put("reason", outcome.reason());
            item.put("commentId", outcome.commentId());
            comments.add(item);
        }
        root.put("comments", comments);

        try {
            return objectMapper.writeValueAsString(root);
        } catch (JsonProcessingException error) {
            log.error("Failed to serialize the publish outcome: {}",
                    error.getClass().getSimpleName());
            return "{\"status\":\"" + status.name()
                    + "\",\"summary\":{\"status\":\""
                    + summary.status()
                    + "\",\"reason\":null,\"commentId\":null},"
                    + "\"comments\":[]}";
        }
    }

    private static String parseFailureOutcomeJson() {
        return "{\"status\":\"" + STATUS_FAILED
                + "\",\"summary\":{\"status\":\"" + STATUS_FAILED
                + "\",\"reason\":\"" + REASON_FINDINGS_PARSE_FAILED
                + "\",\"commentId\":null},\"comments\":[]}";
    }

    private List<ReviewResultFinding> parseFindings(String findingsJson)
            throws JsonProcessingException {
        return objectMapper.readValue(findingsJson,
                new TypeReference<List<ReviewResultFinding>>() {
                });
    }

    private static String failureReason(Exception error) {
        if (error instanceof GithubApiException apiError) {
            return apiError.getStatusCode() > 0
                    ? HTTP_REASON_PREFIX + apiError.getStatusCode()
                    : REASON_GITHUB_API_ERROR;
        }
        if (error instanceof RestClientException) {
            return REASON_TRANSPORT_ERROR;
        }
        return REASON_SETUP_FAILED;
    }

    private static List<InlineCommentFinding> toInlineFindings(
            List<ReviewResultFinding> findings) {
        List<InlineCommentFinding> views = new ArrayList<>(findings.size());
        for (ReviewResultFinding finding : findings) {
            views.add(toInlineFinding(finding));
        }
        return views;
    }

    private static InlineCommentFinding toInlineFinding(
            ReviewResultFinding finding) {
        return new InlineCommentFinding(finding.filePath(),
                finding.startLine(), finding.endLine(), finding.severity(),
                finding.category(), finding.title(), finding.description(),
                finding.reason(), finding.suggestion(), finding.ruleId());
    }

    private static List<SummaryFinding> toSummaryFindings(
            List<ReviewResultFinding> findings) {
        List<SummaryFinding> views = new ArrayList<>(findings.size());
        for (ReviewResultFinding finding : findings) {
            views.add(new SummaryFinding(
                    finding.category(), finding.severity()));
        }
        return views;
    }

    private record SummaryOutcome(String status, String reason,
                                  Long commentId, boolean uncertain) {

        static SummaryOutcome published(Long commentId) {
            return new SummaryOutcome(
                    STATUS_PUBLISHED, null, commentId, false);
        }

        static SummaryOutcome failed(String reason, boolean uncertain) {
            return new SummaryOutcome(
                    STATUS_FAILED, reason, null, uncertain);
        }
    }
}