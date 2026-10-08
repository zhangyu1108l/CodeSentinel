package cn.codesentinel.github;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

@JsonIgnoreProperties(ignoreUnknown = true)
public record PullRequestFile(
        @JsonProperty("filename") String path,
        @JsonProperty("previous_filename") String previousPath,
        @JsonProperty("status") String status,
        @JsonProperty("additions") int additions,
        @JsonProperty("deletions") int deletions,
        @JsonProperty("changes") int changes,
        @JsonProperty("patch") String patch,
        @JsonProperty("blob_url") String blobUrl) {
}