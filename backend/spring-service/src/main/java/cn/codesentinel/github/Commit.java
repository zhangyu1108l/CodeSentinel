package cn.codesentinel.github;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public record Commit(
        @JsonProperty("sha") String sha,
        @JsonProperty("commit") CommitInfo commit,
        @JsonProperty("files") List<CommitFile> files) {

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record CommitInfo(
            @JsonProperty("message") String message) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record CommitFile(
            @JsonProperty("filename") String filename,
            @JsonProperty("status") String status,
            @JsonProperty("additions") int additions,
            @JsonProperty("deletions") int deletions,
            @JsonProperty("patch") String patch) {}
}