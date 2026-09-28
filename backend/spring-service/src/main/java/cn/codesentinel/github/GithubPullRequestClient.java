package cn.codesentinel.github;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

@Component
public class GithubPullRequestClient {

    private static final Logger log = LoggerFactory.getLogger(GithubPullRequestClient.class);

    private final GithubApiClient apiClient;
    private final GithubAuthService authService;

    public GithubPullRequestClient(GithubApiClient apiClient,
                                   GithubAuthService authService) {
        this.apiClient = apiClient;
        this.authService = authService;
    }

    public PullRequest getPullRequest(String owner, String repo, int pullNumber) {
        InstallationToken token = authService.getInstallationToken();

        log.debug("Fetching pull request {}/{}/pulls/{}", owner, repo, pullNumber);

        return apiClient.getRestClient()
                .get()
                .uri("/repos/{owner}/{repo}/pulls/{pull_number}",
                        owner, repo, pullNumber)
                .header("Authorization", "Bearer " + token.token())
                .retrieve()
                .body(PullRequest.class);
    }
}