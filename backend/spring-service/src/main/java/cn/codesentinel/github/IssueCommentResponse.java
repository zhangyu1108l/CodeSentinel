package cn.codesentinel.github;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Response of the GitHub issue comment endpoint. Only the fields needed
 * by the review output flow are kept; unknown fields are ignored.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record IssueCommentResponse(
        @JsonProperty("id") long id,
        @JsonProperty("body") String body,
        @JsonProperty("html_url") String htmlUrl) {
}