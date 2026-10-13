package cn.codesentinel.github;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Request body for the GitHub issue comment endpoint.
 *
 * <p>Field name follows the GitHub REST API JSON contract
 * ({@code {"body": "..."}}).
 */
public record IssueCommentRequest(
        @JsonProperty("body") String body) {
}