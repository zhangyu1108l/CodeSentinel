package cn.codesentinel.github;

import cn.codesentinel.config.GithubAppProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

@Component
public class GithubApiClient {

    private static final Logger log = LoggerFactory.getLogger(GithubApiClient.class);

    private static final String GITHUB_API_ACCEPT = "application/vnd.github.v3+json";

    private final RestClient restClient;

    public GithubApiClient(RestClient.Builder restClientBuilder,
                           GithubAppProperties properties) {
        String baseUrl = properties.apiBaseUrl();
        if (baseUrl == null || baseUrl.isBlank()) {
            baseUrl = "https://api.github.com";
        }

        this.restClient = restClientBuilder
                .baseUrl(baseUrl)
                .defaultHeader("Accept", GITHUB_API_ACCEPT)
                .defaultStatusHandler(HttpStatusCode::isError, (request, response) -> {
                    String body;
                    try {
                        body = new String(response.getBody().readAllBytes());
                    } catch (Exception e) {
                        body = "(unable to read response body)";
                    }
                    int statusCode = response.getStatusCode().value();
                    String msg = "GitHub API error " + statusCode + ": " + body;

                    if (statusCode >= 400 && statusCode < 500) {
                        log.warn("GitHub API client error ({}): {}", statusCode, body);
                    } else {
                        log.error("GitHub API server error ({}): {}", statusCode, body);
                    }

                    throw new GithubApiException(statusCode, msg);
                })
                .build();

        log.debug("GitHub API client initialized with base URL: {}", baseUrl);
    }

    public RestClient getRestClient() {
        return restClient;
    }
}