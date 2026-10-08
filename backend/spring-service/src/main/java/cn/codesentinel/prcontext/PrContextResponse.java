package cn.codesentinel.prcontext;

import java.util.List;

public record PrContextResponse(
        long taskId,
        String owner,
        String repo,
        int prNumber,
        String commitSha,
        String title,
        String state,
        String baseRef,
        String headRef,
        List<PrContextFile> files) {
}