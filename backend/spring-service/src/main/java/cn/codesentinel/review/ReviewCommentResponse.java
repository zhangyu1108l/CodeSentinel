package cn.codesentinel.review;

/**
 * Public representation of one successfully published inline comment
 * (Phase 10.5). Summary comments are not part of this list.
 */
public record ReviewCommentResponse(
        int findingOrdinal,
        Long githubCommentId,
        String filePath,
        int startLine,
        int endLine) {
}