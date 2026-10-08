package cn.codesentinel.github;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.util.UriUtils;

import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.Base64;

@Component
public class GithubFileContentClient {

    private static final Logger log =
            LoggerFactory.getLogger(GithubFileContentClient.class);

    public static final long DEFAULT_MAX_FILE_BYTES = 262_144L;

    private final GithubApiClient apiClient;
    private final GithubAuthService authService;

    public GithubFileContentClient(GithubApiClient apiClient,
                                   GithubAuthService authService) {
        this.apiClient = apiClient;
        this.authService = authService;
    }

    public FileContent getFileContent(String owner, String repo,
                                      String path, String ref) {
        return getFileContent(owner, repo, path, ref,
                authService.getInstallationToken(), DEFAULT_MAX_FILE_BYTES);
    }

    public FileContent getFileContent(String owner, String repo,
                                      String path, String ref,
                                      InstallationToken token,
                                      long maxBytes) {
        log.debug("Fetching file content {}/{}/contents/{}?ref={}",
                owner, repo, path, ref);

        GithubFileContentResponse response = apiClient.getRestClient()
                .get()
                .uri(contentsUri(owner, repo, path, ref))
                .header("Authorization", "Bearer " + token.token())
                .retrieve()
                .body(GithubFileContentResponse.class);

        String responsePath = response.path != null ? response.path : path;

        if (!"file".equals(response.type)) {
            return new FileContent(responsePath, null, FileContent.REASON_BINARY);
        }
        if (response.size != null && response.size > maxBytes) {
            return new FileContent(responsePath, null, FileContent.REASON_TOO_LARGE);
        }
        if (!"base64".equals(response.encoding) || response.content == null) {
            return new FileContent(responsePath, null, FileContent.REASON_BINARY);
        }

        byte[] decoded;
        try {
            String cleaned = response.content.replace("\r", "").replace("\n", "");
            decoded = Base64.getDecoder().decode(cleaned);
        } catch (IllegalArgumentException e) {
            log.warn("Rejecting non base64 content for {}/{}: {}",
                    owner, repo, path);
            return new FileContent(responsePath, null, FileContent.REASON_BINARY);
        }

        if (decoded.length > maxBytes) {
            return new FileContent(responsePath, null, FileContent.REASON_TOO_LARGE);
        }
        if (containsNulByte(decoded)) {
            return new FileContent(responsePath, null, FileContent.REASON_BINARY);
        }

        return new FileContent(responsePath,
                new String(decoded, StandardCharsets.UTF_8), null);
    }

    private URI contentsUri(String owner, String repo, String path, String ref) {
        StringBuilder builder = new StringBuilder("/repos/");
        builder.append(UriUtils.encodePathSegment(owner, StandardCharsets.UTF_8))
                .append('/')
                .append(UriUtils.encodePathSegment(repo, StandardCharsets.UTF_8))
                .append("/contents");
        for (String segment : path.split("/", -1)) {
            builder.append('/')
                    .append(UriUtils.encodePathSegment(segment, StandardCharsets.UTF_8));
        }
        builder.append("?ref=")
                .append(UriUtils.encodeQueryParam(ref, StandardCharsets.UTF_8));
        return URI.create(builder.toString());
    }

    private boolean containsNulByte(byte[] decoded) {
        for (byte value : decoded) {
            if (value == 0) {
                return true;
            }
        }
        return false;
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    private record GithubFileContentResponse(
            @JsonProperty("type") String type,
            @JsonProperty("content") String content,
            @JsonProperty("encoding") String encoding,
            @JsonProperty("size") Long size,
            @JsonProperty("path") String path) {}
}