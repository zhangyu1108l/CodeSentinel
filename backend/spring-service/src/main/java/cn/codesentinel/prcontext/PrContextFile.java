package cn.codesentinel.prcontext;

import com.fasterxml.jackson.annotation.JsonProperty;

public record PrContextFile(
        String path,
        String previousPath,
        String status,
        int additions,
        int deletions,
        int changes,
        String patch,
        String blobUrl,
        @JsonProperty("content_available") boolean contentAvailable,
        @JsonProperty("content_truncated") boolean contentTruncated,
        @JsonProperty("content_reason") String contentReason,
        String content) {
}