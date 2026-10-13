package cn.codesentinel.github;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Response of the pull request review comment endpoint. Only the fields
 * needed by the review output flow are kept; unknown fields are ignored.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record ReviewCommentResponse(
        @JsonProperty("id") long id,
        @JsonProperty("body") String body,
        @JsonProperty("html_url") String htmlUrl) {
}