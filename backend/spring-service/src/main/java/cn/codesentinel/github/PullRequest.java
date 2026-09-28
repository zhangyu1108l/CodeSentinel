package cn.codesentinel.github;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

@JsonIgnoreProperties(ignoreUnknown = true)
public record PullRequest(
        @JsonProperty("number") int number,
        @JsonProperty("title") String title,
        @JsonProperty("state") String state,
        @JsonProperty("head") Head head,
        @JsonProperty("base") Base base) {

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Head(
            @JsonProperty("sha") String sha,
            @JsonProperty("ref") String ref) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Base(
            @JsonProperty("ref") String ref) {}
}