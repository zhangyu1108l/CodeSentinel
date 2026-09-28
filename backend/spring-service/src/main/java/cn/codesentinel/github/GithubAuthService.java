package cn.codesentinel.github;

import cn.codesentinel.config.GithubAppProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

@Component
public class GithubAuthService {

    private static final Logger log = LoggerFactory.getLogger(GithubAuthService.class);

    private static final String ACCESS_TOKEN_PATH = "/app/installations/{installationId}/access_tokens";
    private static final String GITHUB_API_ACCEPT = "application/vnd.github.v3+json";

    private final GithubJwtService jwtService;
    private final GithubAppProperties properties;
    private final RestClient restClient;
    private final ObjectMapper objectMapper;

    public GithubAuthService(GithubJwtService jwtService,
                             GithubAppProperties properties,
                             RestClient.Builder restClientBuilder,
                             ObjectMapper objectMapper) {
        this.jwtService = jwtService;
        this.properties = properties;
        this.objectMapper = objectMapper;
        this.restClient = buildRestClient(restClientBuilder);
    }

    private RestClient buildRestClient(RestClient.Builder builder) {
        String baseUrl = properties.apiBaseUrl();
        if (baseUrl == null || baseUrl.isBlank()) {
            baseUrl = "https://api.github.com";
        }
        return builder.baseUrl(baseUrl).build();
    }

    public InstallationToken getInstallationToken() {
        String installationId = properties.installationId();
        if (installationId == null || installationId.isBlank()) {
            throw new IllegalStateException(
                    "GitHub App installation ID is not configured. "
                            + "Set github.app.installation-id");
        }
        return getInstallationToken(installationId);
    }

    public InstallationToken getInstallationToken(String installationId) {
        String jwt = jwtService.generateAppJwt();

        log.debug("Requesting installation access token for installation {}", installationId);

        try {
            String responseBody = restClient.post()
                    .uri(ACCESS_TOKEN_PATH, installationId)
                    .header("Authorization", "Bearer " + jwt)
                    .accept(MediaType.parseMediaType(GITHUB_API_ACCEPT))
                    .retrieve()
                    .onStatus(HttpStatusCode::isError, (request, response) -> {
                        String body = new String(response.getBody().readAllBytes());
                        throw new GithubApiException(
                                response.getStatusCode().value(),
                                "GitHub API error " + response.getStatusCode()
                                        + " for installation " + installationId
                                        + ": " + body);
                    })
                    .body(String.class);

            InstallationToken tokenResponse =
                    objectMapper.readValue(responseBody, InstallationToken.class);

            if (tokenResponse.token() == null || tokenResponse.token().isBlank()) {
                throw new GithubApiException(
                        "GitHub installation token response missing token field");
            }

            log.debug("Obtained installation access token (expires at {})",
                    tokenResponse.expiresAt());
            return tokenResponse;

        } catch (GithubApiException e) {
            throw e;
        } catch (Exception e) {
            throw new GithubApiException(
                    "Failed to obtain installation access token: " + e.getMessage(), e);
        }
    }
}