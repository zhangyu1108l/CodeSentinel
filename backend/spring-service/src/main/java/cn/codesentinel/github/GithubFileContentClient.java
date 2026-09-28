package cn.codesentinel.github;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.Base64;

@Component
public class GithubFileContentClient {

    private static final Logger log = LoggerFactory.getLogger(GithubFileContentClient.class);

    private final GithubApiClient apiClient;
    private final GithubAuthService authService;

    public GithubFileContentClient(GithubApiClient apiClient,
                                   GithubAuthService authService) {
        this.apiClient = apiClient;
        this.authService = authService;
    }

    public FileContent getFileContent(String owner, String repo,
                                      String path, String ref) {
        InstallationToken token = authService.getInstallationToken();

        log.debug("Fetching file content {}/{}/contents/{}?ref={}",
                owner, repo, path, ref);

        URI uri = URI.create(String.format(
                        "/repos/%s/%s/contents/%s?ref=%s",
                        owner, repo, path, ref));

        GithubFileContentResponse response = apiClient.getRestClient()
                .get()
                .uri(uri)
                .header("Authorization", "Bearer " + token.token())
                .retrieve()
                .body(GithubFileContentResponse.class);

        String responsePath = response.path != null ? response.path : path;

        if (!"file".equals(response.type) || response.content == null) {
            return new FileContent(responsePath, null);
        }

        String cleaned = response.content.replace("\r", "").replace("\n", "");
        byte[] decoded = Base64.getDecoder().decode(cleaned);
        String decodedContent = new String(decoded, StandardCharsets.UTF_8);

        return new FileContent(responsePath, decodedContent);
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    private record GithubFileContentResponse(
            @JsonProperty("type") String type,
            @JsonProperty("content") String content,
            @JsonProperty("encoding") String encoding,
            @JsonProperty("path") String path) {}
}