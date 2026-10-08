package cn.codesentinel.github;

import cn.codesentinel.config.ReviewContextProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Component
public class GithubPullRequestFilesClient {

    private static final Logger log =
            LoggerFactory.getLogger(GithubPullRequestFilesClient.class);

    private static final int PER_PAGE = 100;
    private static final Pattern LINK_PATTERN =
            Pattern.compile("<([^>]+)>\\s*;\\s*rel=\"([^\"]+)\"");

    private final GithubApiClient apiClient;
    private final GithubAuthService authService;
    private final ReviewContextProperties properties;

    public GithubPullRequestFilesClient(GithubApiClient apiClient,
                                        GithubAuthService authService,
                                        ReviewContextProperties properties) {
        this.apiClient = apiClient;
        this.authService = authService;
        this.properties = properties;
    }

    public List<PullRequestFile> getChangedFiles(String owner, String repo,
                                                 int pullNumber) {
        return getChangedFiles(owner, repo, pullNumber,
                authService.getInstallationToken());
    }

    public List<PullRequestFile> getChangedFiles(String owner, String repo,
                                                 int pullNumber,
                                                 InstallationToken token) {
        List<PullRequestFile> collected = new ArrayList<>();
        String nextUrl = null;
        int page = 1;

        while (collected.size() < properties.maxFiles()
                && page <= properties.maxFetchPages()) {
            PullRequestFilesPage result =
                    fetchPage(owner, repo, pullNumber, page, nextUrl, token);
            if (result.files().isEmpty()) {
                break;
            }
            collected.addAll(result.files());
            nextUrl = result.nextUrl();
            if (nextUrl == null) {
                break;
            }
            page++;
        }

        if (collected.size() > properties.maxFiles()) {
            log.debug("Changed files capped at max-files={} (fetched {})",
                    properties.maxFiles(), collected.size());
            return List.copyOf(collected.subList(0, properties.maxFiles()));
        }
        return List.copyOf(collected);
    }

    private PullRequestFilesPage fetchPage(String owner, String repo,
                                           int pullNumber, int page,
                                           String nextUrl,
                                           InstallationToken token) {
        URI uri = nextUrl != null
                ? safeUri(nextUrl)
                : URI.create(String.format(
                        "/repos/%s/%s/pulls/%d/files?per_page=%d&page=%d",
                        owner, repo, pullNumber, PER_PAGE, page));
        if (uri == null) {
            return new PullRequestFilesPage(List.of(), null);
        }

        log.debug("Fetching changed files {}/{}/pulls/{}/files page={}",
                owner, repo, pullNumber, page);

        ResponseEntity<List<PullRequestFile>> response = apiClient.getRestClient()
                .get()
                .uri(uri)
                .header("Authorization", "Bearer " + token.token())
                .retrieve()
                .toEntity(new ParameterizedTypeReference<>() {
                });

        List<PullRequestFile> files =
                response.getBody() != null ? response.getBody() : List.of();
        return new PullRequestFilesPage(files, nextPageUrl(response.getHeaders()));
    }

    private String nextPageUrl(HttpHeaders headers) {
        List<String> linkHeaders = headers.get(HttpHeaders.LINK);
        if (linkHeaders == null) {
            return null;
        }
        for (String headerValue : linkHeaders) {
            for (String part : headerValue.split(",")) {
                Matcher matcher = LINK_PATTERN.matcher(part.trim());
                if (matcher.matches() && "next".equals(matcher.group(2))) {
                    return matcher.group(1);
                }
            }
        }
        return null;
    }

    private URI safeUri(String url) {
        try {
            return URI.create(url);
        } catch (IllegalArgumentException e) {
            log.warn("Ignoring malformed Link header URL: {}", url);
            return null;
        }
    }

    private record PullRequestFilesPage(List<PullRequestFile> files,
                                        String nextUrl) {
    }
}