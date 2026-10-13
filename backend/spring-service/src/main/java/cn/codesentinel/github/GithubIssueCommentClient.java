package cn.codesentinel.github;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Creates issue comments on a pull request (the PR conversation view).
 *
 * <p>Calls {@code POST /repos/{owner}/{repo}/issues/{pull_number}/comments}.
 * The shared {@link GithubApiClient} request and error handling is reused:
 * any non-2xx response raises {@link GithubApiException} and is never
 * swallowed. Constructed by {@link GithubCommentClientConfig} with a
 * dedicated timed client; wired through the Phase 9.5.3C publish flow.
 */
public class GithubIssueCommentClient {

    private static final Logger log =
            LoggerFactory.getLogger(GithubIssueCommentClient.class);

    private final GithubApiClient apiClient;
    private final GithubAuthService authService;

    public GithubIssueCommentClient(GithubApiClient apiClient,
                                    GithubAuthService authService) {
        this.apiClient = apiClient;
        this.authService = authService;
    }

    public IssueCommentResponse createComment(String owner, String repo,
                                              int pullNumber,
                                              IssueCommentRequest request) {
        return createComment(owner, repo, pullNumber, request,
                authService.getInstallationToken());
    }

    public IssueCommentResponse createComment(String owner, String repo,
                                              int pullNumber,
                                              IssueCommentRequest request,
                                              InstallationToken token) {
        log.debug("Creating issue comment on {}/{}/issues/{}",
                owner, repo, pullNumber);

        return apiClient.getRestClient()
                .post()
                .uri("/repos/{owner}/{repo}/issues/{pull_number}/comments",
                        owner, repo, pullNumber)
                .header("Authorization", "Bearer " + token.token())
                .body(request)
                .retrieve()
                .body(IssueCommentResponse.class);
    }
}