package cn.codesentinel.github;

import cn.codesentinel.config.GithubAppProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

/**
 * Wires the GitHub comment clients and the inline-comment publisher onto
 * a dedicated {@link GithubApiClient} instance with explicit HTTP
 * timeouts.
 *
 * <p>The auto-configured {@link RestClient.Builder} is prototype scoped, so
 * applying a request factory here only affects the local client created in
 * this configuration. The shared {@code GithubApiClient} component and the
 * other GitHub clients keep their current behavior, and the existing
 * MockRestServiceServer-based tests are untouched. The timed client is
 * deliberately NOT registered as a bean: a second {@code GithubApiClient}
 * bean would make the existing by-type injections ambiguous.
 */
@Configuration
public class GithubCommentClientConfig {

    private static final int CONNECT_TIMEOUT_MILLIS = 5_000;
    private static final int READ_TIMEOUT_MILLIS = 30_000;

    @Bean
    public GithubIssueCommentClient githubIssueCommentClient(
            RestClient.Builder restClientBuilder,
            GithubAppProperties properties,
            GithubAuthService authService) {
        return new GithubIssueCommentClient(
                commentApiClient(restClientBuilder, properties), authService);
    }

    @Bean
    public GithubReviewCommentClient githubReviewCommentClient(
            RestClient.Builder restClientBuilder,
            GithubAppProperties properties,
            GithubAuthService authService) {
        return new GithubReviewCommentClient(
                commentApiClient(restClientBuilder, properties), authService);
    }

    @Bean
    public ReviewCommentPublisher reviewCommentPublisher(
            GithubPullRequestFilesClient filesClient,
            GithubReviewCommentClient reviewCommentClient,
            GithubAuthService authService) {
        return new ReviewCommentPublisher(
                filesClient, reviewCommentClient, authService);
    }

    private static GithubApiClient commentApiClient(
            RestClient.Builder restClientBuilder,
            GithubAppProperties properties) {
        SimpleClientHttpRequestFactory requestFactory =
                new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(CONNECT_TIMEOUT_MILLIS);
        requestFactory.setReadTimeout(READ_TIMEOUT_MILLIS);
        restClientBuilder.requestFactory(requestFactory);
        return new GithubApiClient(restClientBuilder, properties);
    }
}