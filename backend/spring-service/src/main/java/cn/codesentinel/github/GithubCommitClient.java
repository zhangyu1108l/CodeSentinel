package cn.codesentinel.github;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

@Component
public class GithubCommitClient {

    private static final Logger log = LoggerFactory.getLogger(GithubCommitClient.class);

    private final GithubApiClient apiClient;
    private final GithubAuthService authService;

    public GithubCommitClient(GithubApiClient apiClient,
                              GithubAuthService authService) {
        this.apiClient = apiClient;
        this.authService = authService;
    }

    public Commit getCommit(String owner, String repo, String sha) {
        InstallationToken token = authService.getInstallationToken();

        log.debug("Fetching commit {}/{}/commits/{}", owner, repo, sha);

        return apiClient.getRestClient()
                .get()
                .uri("/repos/{owner}/{repo}/commits/{sha}", owner, repo, sha)
                .header("Authorization", "Bearer " + token.token())
                .retrieve()
                .body(Commit.class);
    }
}