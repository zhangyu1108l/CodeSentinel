package cn.codesentinel.github;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

@Component
public class GithubRepositoryClient {

    private static final Logger log = LoggerFactory.getLogger(GithubRepositoryClient.class);

    private final GithubApiClient apiClient;
    private final GithubAuthService authService;

    public GithubRepositoryClient(GithubApiClient apiClient,
                                  GithubAuthService authService) {
        this.apiClient = apiClient;
        this.authService = authService;
    }

    public Repository getRepository(String owner, String repo) {
        InstallationToken token = authService.getInstallationToken();

        log.debug("Fetching repository {}/{}", owner, repo);

        return apiClient.getRestClient()
                .get()
                .uri("/repos/{owner}/{repo}", owner, repo)
                .header("Authorization", "Bearer " + token.token())
                .retrieve()
                .body(Repository.class);
    }
}