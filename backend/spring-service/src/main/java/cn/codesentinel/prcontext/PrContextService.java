package cn.codesentinel.prcontext;

import cn.codesentinel.config.ReviewContextProperties;
import cn.codesentinel.github.FileContent;
import cn.codesentinel.github.GithubApiException;
import cn.codesentinel.github.GithubAuthService;
import cn.codesentinel.github.GithubFileContentClient;
import cn.codesentinel.github.GithubPullRequestClient;
import cn.codesentinel.github.GithubPullRequestFilesClient;
import cn.codesentinel.github.InstallationToken;
import cn.codesentinel.github.PullRequest;
import cn.codesentinel.github.PullRequestFile;
import cn.codesentinel.task.ReviewTask;
import cn.codesentinel.task.ReviewTaskService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

@Service
public class PrContextService {

    private static final Logger log =
            LoggerFactory.getLogger(PrContextService.class);

    private static final String REASON_REMOVED = "removed";
    private static final String REASON_UNSUPPORTED_LANGUAGE = "unsupported_language";
    private static final String REASON_FETCH_FAILED_PREFIX = "fetch_failed:";

    private final ReviewTaskService reviewTaskService;
    private final GithubAuthService authService;
    private final GithubPullRequestClient pullRequestClient;
    private final GithubPullRequestFilesClient pullRequestFilesClient;
    private final GithubFileContentClient fileContentClient;
    private final ReviewContextProperties properties;

    public PrContextService(ReviewTaskService reviewTaskService,
                            GithubAuthService authService,
                            GithubPullRequestClient pullRequestClient,
                            GithubPullRequestFilesClient pullRequestFilesClient,
                            GithubFileContentClient fileContentClient,
                            ReviewContextProperties properties) {
        this.reviewTaskService = reviewTaskService;
        this.authService = authService;
        this.pullRequestClient = pullRequestClient;
        this.pullRequestFilesClient = pullRequestFilesClient;
        this.fileContentClient = fileContentClient;
        this.properties = properties;
    }

    public PrContextResponse buildContext(long taskId) {
        ReviewTask task = reviewTaskService.getTaskById(taskId);
        String owner = task.getOwner();
        String repo = task.getRepo();
        int prNumber = task.getPrNumber();
        String commitSha = task.getCommitSha();

        log.info("Building PR context for task {}: {}/{}#{}@{}",
                taskId, owner, repo, prNumber, commitSha);

        InstallationToken token = authService.getInstallationToken();
        PullRequest pullRequest =
                pullRequestClient.getPullRequest(owner, repo, prNumber, token);
        List<PullRequestFile> changedFiles =
                pullRequestFilesClient.getChangedFiles(owner, repo, prNumber, token);

        List<PrContextFile> files = new ArrayList<>(changedFiles.size());
        for (PullRequestFile changedFile : changedFiles) {
            files.add(toContextFile(changedFile, owner, repo, commitSha, token));
        }

        log.info("PR context for task {} built: changedFiles={}, withContent={}",
                taskId, files.size(),
                files.stream().filter(PrContextFile::contentAvailable).count());

        return new PrContextResponse(
                taskId,
                owner,
                repo,
                prNumber,
                commitSha,
                pullRequest.title(),
                pullRequest.state(),
                pullRequest.base().ref(),
                pullRequest.head().ref(),
                List.copyOf(files));
    }

    private PrContextFile toContextFile(PullRequestFile file, String owner,
                                        String repo, String ref,
                                        InstallationToken token) {
        String patch = file.patch() == null || file.patch().isEmpty()
                ? null
                : file.patch();
        String status = file.status();

        if ("removed".equals(status)) {
            return skipped(file, patch, REASON_REMOVED);
        }
        if (!properties.includesContent(file.path())) {
            return skipped(file, patch, REASON_UNSUPPORTED_LANGUAGE);
        }

        try {
            FileContent content = fileContentClient.getFileContent(
                    owner, repo, file.path(), ref, token, properties.maxFileBytes());
            if (content.content() == null) {
                return skipped(file, patch, content.contentReason() != null
                        ? content.contentReason()
                        : FileContent.REASON_BINARY);
            }
            return new PrContextFile(
                    file.path(),
                    file.previousPath(),
                    status,
                    file.additions(),
                    file.deletions(),
                    file.changes(),
                    patch,
                    file.blobUrl(),
                    true,
                    false,
                    null,
                    content.content());
        } catch (GithubApiException e) {
            String statusPart = e.getStatusCode() > 0
                    ? String.valueOf(e.getStatusCode())
                    : "unknown";
            log.warn("File content fetch failed for {} (task owner {}): {}",
                    file.path(), owner, e.getMessage());
            return skipped(file, patch, REASON_FETCH_FAILED_PREFIX + statusPart);
        }
    }

    private PrContextFile skipped(PullRequestFile file, String patch,
                                  String reason) {
        return new PrContextFile(
                file.path(),
                file.previousPath(),
                file.status(),
                file.additions(),
                file.deletions(),
                file.changes(),
                patch,
                file.blobUrl(),
                false,
                false,
                reason,
                null);
    }
}