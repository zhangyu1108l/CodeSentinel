package cn.codesentinel.github;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Creates review comments on the pull request diff.
 *
 * <p>Calls {@code POST /repos/{owner}/{repo}/pulls/{pull_number}/comments}.
 * The shared {@link GithubApiClient} request and error handling is reused:
 * any non-2xx response raises {@link GithubApiException} and is never
 * swallowed. Constructed by {@link GithubCommentClientConfig} with a
 * dedicated timed client; wired through {@link ReviewCommentPublisher}.
 */
public class GithubReviewCommentClient {

    private static final Logger log =
            LoggerFactory.getLogger(GithubReviewCommentClient.class);

    private final GithubApiClient apiClient;
    private final GithubAuthService authService;

    public GithubReviewCommentClient(GithubApiClient apiClient,
                                     GithubAuthService authService) {
        this.apiClient = apiClient;
        this.authService = authService;
    }

    public ReviewCommentResponse createComment(String owner, String repo,
                                               int pullNumber,
                                               ReviewCommentRequest request) {
        return createComment(owner, repo, pullNumber, request,
                authService.getInstallationToken());
    }

    public ReviewCommentResponse createComment(String owner, String repo,
                                               int pullNumber,
                                               ReviewCommentRequest request,
                                               InstallationToken token) {
        log.debug("Creating review comment on {}/{}/pulls/{}",
                owner, repo, pullNumber);

        return apiClient.getRestClient()
                .post()
                .uri("/repos/{owner}/{repo}/pulls/{pull_number}/comments",
                        owner, repo, pullNumber)
                .header("Authorization", "Bearer " + token.token())
                .body(request)
                .retrieve()
                .body(ReviewCommentResponse.class);
    }
}