package cn.codesentinel.github;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Request body for the pull request review comment endpoint.
 *
 * <p>Field names follow the GitHub REST API JSON contract ({@code body},
 * {@code commit_id}, {@code path}, {@code line}, {@code side}, plus the
 * optional multi-line fields {@code start_line} and {@code start_side}).
 * {@code side} and {@code start_side} are passed through unchanged and
 * are expected to be {@code LEFT} or {@code RIGHT} as defined by GitHub.
 * The client never infers or rewrites the caller's line and side: diff
 * position mapping happens before the request is built.
 *
 * <p>Null fields are omitted from the JSON, so a single-line request
 * built through the five-argument constructor carries no
 * {@code start_line} / {@code start_side} entries at all.
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record ReviewCommentRequest(
        @JsonProperty("body") String body,
        @JsonProperty("commit_id") String commitId,
        @JsonProperty("path") String path,
        @JsonProperty("line") int line,
        @JsonProperty("side") String side,
        @JsonProperty("start_line") Integer startLine,
        @JsonProperty("start_side") String startSide) {

    /** Single-line convenience: no multi-line start fields. */
    public ReviewCommentRequest(String body, String commitId, String path,
                                int line, String side) {
        this(body, commitId, path, line, side, null, null);
    }
}