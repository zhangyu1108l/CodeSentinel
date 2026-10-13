package cn.codesentinel.github;

import cn.codesentinel.comment.InlineCommentFinding;
import cn.codesentinel.comment.InlineCommentMarkdownBuilder;
import cn.codesentinel.comment.InlineCommentPlacement;
import cn.codesentinel.comment.PatchCommentableLines;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.client.RestClientException;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Component-level orchestration for publishing inline review comments
 * (Phase 9.5.3A). Wired into the first-receipt publish flow through
 * {@code ReviewResultPublishService} (Phase 9.5.3C); it never touches
 * Webhook / Task / Redis / Worker.
 *
 * <p>For one review the changed files are fetched once and one
 * installation token is reused for the whole run. Every finding then
 * becomes one independent {@link ReviewCommentOutcome}: a finding that
 * cannot be located on the diff is skipped with the full placement
 * reason and no request is sent; a finding whose comment request fails
 * (HTTP error or transport error) is recorded as failed without
 * interrupting the other findings. Nothing is fabricated, and
 * {@link Optional} results are only unwrapped after an emptiness check.
 *
 * <p>Known limit: the changed-file patches come from the current PR diff
 * while {@code commitSha} is the reviewed head SHA. If the PR advanced
 * between the review and the publish the two can drift; this class does
 * not silently assume they match, it only records per-finding failures
 * and skips. The changed-file fetch is also subject to the existing
 * {@code review.context.max-files} cap; findings outside the fetched
 * files are skipped as {@code path_not_in_pr}.
 */
public class ReviewCommentPublisher {

    public static final String SKIP_REASON_PATH_NOT_IN_PR = "path_not_in_pr";
    public static final String FAILURE_REASON_INVALID_BODY = "invalid_body";
    public static final String FAILURE_REASON_GITHUB_API = "github_api_error";
    public static final String FAILURE_REASON_TRANSPORT = "transport_error";
    public static final String FAILURE_REASON_HTTP_PREFIX = "http_";

    private static final Logger log =
            LoggerFactory.getLogger(ReviewCommentPublisher.class);

    private final GithubPullRequestFilesClient filesClient;
    private final GithubReviewCommentClient commentClient;
    private final GithubAuthService authService;

    public ReviewCommentPublisher(GithubPullRequestFilesClient filesClient,
                                  GithubReviewCommentClient commentClient,
                                  GithubAuthService authService) {
        this.filesClient = filesClient;
        this.commentClient = commentClient;
        this.authService = authService;
    }

    /**
     * Publish one comment per locatable finding. Blank task inputs
     * (owner / repo / commitSha / pullNumber) are a caller contract
     * violation and raise {@link IllegalArgumentException} before any
     * request is made; a null {@code findings} list behaves like an
     * empty list and performs no request.
     */
    public List<ReviewCommentOutcome> publish(String owner, String repo,
                                              int pullNumber, String commitSha,
                                              List<InlineCommentFinding> findings) {
        requireText(owner, "owner");
        requireText(repo, "repo");
        requireText(commitSha, "commitSha");
        if (pullNumber < 1) {
            throw new IllegalArgumentException(
                    "pullNumber must be positive: " + pullNumber);
        }
        List<InlineCommentFinding> safeFindings =
                findings == null ? List.of() : findings;
        if (safeFindings.isEmpty()) {
            return List.of();
        }

        InstallationToken token = authService.getInstallationToken();
        Map<String, String> patches =
                fetchPatches(owner, repo, pullNumber, token);

        List<ReviewCommentOutcome> outcomes =
                new ArrayList<>(safeFindings.size());
        for (InlineCommentFinding finding : safeFindings) {
            outcomes.add(publishOne(owner, repo, pullNumber, commitSha,
                    patches, token, finding));
        }
        return List.copyOf(outcomes);
    }

    private ReviewCommentOutcome publishOne(String owner, String repo,
                                            int pullNumber, String commitSha,
                                            Map<String, String> patches,
                                            InstallationToken token,
                                            InlineCommentFinding finding) {
        String path = finding.filePath() == null
                ? ""
                : finding.filePath().trim();
        if (path.isEmpty() || !patches.containsKey(path)) {
            log.debug("Skipping comment for {}/{}#{}: path not in changed files",
                    owner, repo, pullNumber);
            return ReviewCommentOutcome.skipped(finding,
                    SKIP_REASON_PATH_NOT_IN_PR);
        }

        InlineCommentPlacement placement = PatchCommentableLines
                .parse(patches.get(path))
                .placeRight(finding.startLine(), finding.endLine());
        String body = InlineCommentMarkdownBuilder.build(finding);
        if (body == null || body.isBlank()) {
            log.warn("Comment failed for {}/{}#{}: blank comment body",
                    owner, repo, pullNumber);
            return ReviewCommentOutcome.failed(finding,
                    FAILURE_REASON_INVALID_BODY);
        }

        Optional<ReviewCommentRequest> request = ReviewCommentRequestMapper
                .map(body, commitSha, path, placement);
        if (request.isEmpty()) {
            return ReviewCommentOutcome.skipped(finding, placement.reason());
        }

        try {
            ReviewCommentResponse response = commentClient.createComment(
                    owner, repo, pullNumber, request.get(), token);
            return ReviewCommentOutcome.published(finding,
                    response == null ? null : response.id());
        } catch (GithubApiException error) {
            String reason = error.getStatusCode() > 0
                    ? FAILURE_REASON_HTTP_PREFIX + error.getStatusCode()
                    : FAILURE_REASON_GITHUB_API;
            log.warn("Comment failed for {}/{}#{}: {}", owner, repo,
                    pullNumber, reason);
            return ReviewCommentOutcome.failed(finding, reason);
        } catch (RestClientException error) {
            log.warn("Comment transport failed for {}/{}#{}: {}", owner, repo,
                    pullNumber, error.getClass().getSimpleName());
            return ReviewCommentOutcome.failed(finding,
                    FAILURE_REASON_TRANSPORT);
        }
    }

    private Map<String, String> fetchPatches(String owner, String repo,
                                             int pullNumber,
                                             InstallationToken token) {
        List<PullRequestFile> changedFiles =
                filesClient.getChangedFiles(owner, repo, pullNumber, token);
        Map<String, String> patches = new LinkedHashMap<>();
        for (PullRequestFile file : changedFiles) {
            if (file.path() != null && !file.path().isBlank()) {
                patches.putIfAbsent(file.path(), file.patch());
            }
        }
        return patches;
    }

    private static void requireText(String value, String name) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
    }
}