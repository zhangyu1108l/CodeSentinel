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
import cn.codesentinel.task.TaskNotFoundException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class PrContextServiceTest {

    private static final InstallationToken TOKEN =
            new InstallationToken("ghs_test-token", "2025-01-01T00:00:00Z");
    private static final long TASK_ID = 1L;
    private static final String OWNER = "owner";
    private static final String REPO = "repo";
    private static final int PR_NUMBER = 42;
    private static final String COMMIT_SHA = "abc123";

    private ReviewTaskService reviewTaskService;
    private GithubAuthService authService;
    private GithubPullRequestClient pullRequestClient;
    private GithubPullRequestFilesClient pullRequestFilesClient;
    private GithubFileContentClient fileContentClient;
    private PrContextService service;

    @BeforeEach
    void setUp() {
        reviewTaskService = mock(ReviewTaskService.class);
        authService = mock(GithubAuthService.class);
        pullRequestClient = mock(GithubPullRequestClient.class);
        pullRequestFilesClient = mock(GithubPullRequestFilesClient.class);
        fileContentClient = mock(GithubFileContentClient.class);
        service = new PrContextService(
                reviewTaskService,
                authService,
                pullRequestClient,
                pullRequestFilesClient,
                fileContentClient,
                new ReviewContextProperties(50, 262_144, 5, List.of("java", "py")));
    }

    private void stubTaskAndPullRequest() {
        when(reviewTaskService.getTaskById(TASK_ID))
                .thenReturn(new ReviewTask(OWNER, REPO, PR_NUMBER, COMMIT_SHA));
        when(authService.getInstallationToken()).thenReturn(TOKEN);
        when(pullRequestClient.getPullRequest(OWNER, REPO, PR_NUMBER, TOKEN))
                .thenReturn(new PullRequest(
                        PR_NUMBER,
                        "Add review context",
                        "open",
                        new PullRequest.Head(COMMIT_SHA, "feature/context"),
                        new PullRequest.Base("main")));
    }

    private PullRequestFile file(String path, String status, String patch) {
        return new PullRequestFile(path, null, status, 1, 1, 2, patch,
                "https://github.com/owner/repo/blob/abc/" + path);
    }

    @Test
    void shouldBuildContextWithContentForSupportedFiles() {
        stubTaskAndPullRequest();
        when(pullRequestFilesClient.getChangedFiles(OWNER, REPO, PR_NUMBER, TOKEN))
                .thenReturn(List.of(
                        file("src/App.java", "modified", "@@ patch @@"),
                        file("agent/main.py", "added", null)));
        when(fileContentClient.getFileContent(
                OWNER, REPO, "src/App.java", COMMIT_SHA, TOKEN, 262_144))
                .thenReturn(new FileContent("src/App.java", "class App {}", null));
        when(fileContentClient.getFileContent(
                OWNER, REPO, "agent/main.py", COMMIT_SHA, TOKEN, 262_144))
                .thenReturn(new FileContent("agent/main.py", "print(1)", null));

        PrContextResponse response = service.buildContext(TASK_ID);

        assertEquals(TASK_ID, response.taskId());
        assertEquals(OWNER, response.owner());
        assertEquals(REPO, response.repo());
        assertEquals(PR_NUMBER, response.prNumber());
        assertEquals(COMMIT_SHA, response.commitSha());
        assertEquals("Add review context", response.title());
        assertEquals("open", response.state());
        assertEquals("main", response.baseRef());
        assertEquals("feature/context", response.headRef());

        assertEquals(2, response.files().size());
        PrContextFile javaFile = response.files().get(0);
        assertEquals("src/App.java", javaFile.path());
        assertTrue(javaFile.contentAvailable());
        assertFalse(javaFile.contentTruncated());
        assertNull(javaFile.contentReason());
        assertEquals("class App {}", javaFile.content());
        assertEquals("@@ patch @@", javaFile.patch());

        PrContextFile pythonFile = response.files().get(1);
        assertTrue(pythonFile.contentAvailable());
        assertEquals("print(1)", pythonFile.content());
        assertNull(pythonFile.patch());
    }

    @Test
    void shouldReuseOneInstallationTokenPerContext() {
        stubTaskAndPullRequest();
        when(pullRequestFilesClient.getChangedFiles(OWNER, REPO, PR_NUMBER, TOKEN))
                .thenReturn(List.of(
                        file("a/A.java", "modified", "p"),
                        file("b/B.java", "modified", "p")));
        when(fileContentClient.getFileContent(
                anyString(), anyString(), anyString(), anyString(), any(), anyLong()))
                .thenReturn(new FileContent("a/A.java", "content", null));

        service.buildContext(TASK_ID);

        verify(authService, times(1)).getInstallationToken();
        verify(pullRequestClient).getPullRequest(OWNER, REPO, PR_NUMBER, TOKEN);
        verify(pullRequestFilesClient).getChangedFiles(OWNER, REPO, PR_NUMBER, TOKEN);
        verify(fileContentClient, times(2)).getFileContent(
                eq(OWNER), eq(REPO), anyString(), eq(COMMIT_SHA), eq(TOKEN), eq(262_144L));
    }

    @Test
    void shouldNotRequestContentForRemovedFile() {
        stubTaskAndPullRequest();
        when(pullRequestFilesClient.getChangedFiles(OWNER, REPO, PR_NUMBER, TOKEN))
                .thenReturn(List.of(file("src/Old.java", "removed", "@@ gone @@")));

        PrContextResponse response = service.buildContext(TASK_ID);

        PrContextFile removed = response.files().get(0);
        assertFalse(removed.contentAvailable());
        assertEquals("removed", removed.contentReason());
        assertNull(removed.content());
        assertEquals("@@ gone @@", removed.patch());
        verify(fileContentClient, never()).getFileContent(
                anyString(), anyString(), anyString(), anyString(), any(), anyLong());
    }

    @Test
    void shouldNotRequestContentForUnsupportedLanguage() {
        stubTaskAndPullRequest();
        when(pullRequestFilesClient.getChangedFiles(OWNER, REPO, PR_NUMBER, TOKEN))
                .thenReturn(List.of(
                        file("README.md", "modified", "p"),
                        file("Makefile", "modified", "p")));

        PrContextResponse response = service.buildContext(TASK_ID);

        assertEquals(2, response.files().size());
        response.files().forEach(file -> {
            assertFalse(file.contentAvailable());
            assertEquals("unsupported_language", file.contentReason());
            assertNull(file.content());
        });
        verify(fileContentClient, never()).getFileContent(
                anyString(), anyString(), anyString(), anyString(), any(), anyLong());
    }

    @Test
    void shouldFetchContentForUppercaseExtension() {
        stubTaskAndPullRequest();
        when(pullRequestFilesClient.getChangedFiles(OWNER, REPO, PR_NUMBER, TOKEN))
                .thenReturn(List.of(file("SRC/App.JAVA", "modified", "p")));
        when(fileContentClient.getFileContent(
                OWNER, REPO, "SRC/App.JAVA", COMMIT_SHA, TOKEN, 262_144))
                .thenReturn(new FileContent("SRC/App.JAVA", "class App {}", null));

        PrContextResponse response = service.buildContext(TASK_ID);

        assertTrue(response.files().get(0).contentAvailable());
    }

    @Test
    void shouldDegradeWhenContentIsTooLarge() {
        stubTaskAndPullRequest();
        when(pullRequestFilesClient.getChangedFiles(OWNER, REPO, PR_NUMBER, TOKEN))
                .thenReturn(List.of(file("src/Big.java", "modified", "p")));
        when(fileContentClient.getFileContent(
                OWNER, REPO, "src/Big.java", COMMIT_SHA, TOKEN, 262_144))
                .thenReturn(new FileContent("src/Big.java", null,
                        FileContent.REASON_TOO_LARGE));

        PrContextFile contextFile = service.buildContext(TASK_ID).files().get(0);

        assertFalse(contextFile.contentAvailable());
        assertEquals("too_large", contextFile.contentReason());
        assertNull(contextFile.content());
    }

    @Test
    void shouldDegradeSingleFileFailureWithoutFailingTheContext() {
        stubTaskAndPullRequest();
        when(pullRequestFilesClient.getChangedFiles(OWNER, REPO, PR_NUMBER, TOKEN))
                .thenReturn(List.of(
                        file("src/Broken.java", "modified", "p"),
                        file("src/Ok.java", "modified", "p")));
        when(fileContentClient.getFileContent(
                OWNER, REPO, "src/Broken.java", COMMIT_SHA, TOKEN, 262_144))
                .thenThrow(new GithubApiException(403, "Forbidden"));
        when(fileContentClient.getFileContent(
                OWNER, REPO, "src/Ok.java", COMMIT_SHA, TOKEN, 262_144))
                .thenReturn(new FileContent("src/Ok.java", "class Ok {}", null));

        PrContextResponse response = service.buildContext(TASK_ID);

        PrContextFile broken = response.files().get(0);
        assertFalse(broken.contentAvailable());
        assertEquals("fetch_failed:403", broken.contentReason());
        assertNull(broken.content());

        PrContextFile ok = response.files().get(1);
        assertTrue(ok.contentAvailable());
        assertEquals("class Ok {}", ok.content());
    }

    @Test
    void shouldPreserveChangedFileOrder() {
        stubTaskAndPullRequest();
        when(pullRequestFilesClient.getChangedFiles(OWNER, REPO, PR_NUMBER, TOKEN))
                .thenReturn(List.of(
                        file("c/C.java", "modified", "p"),
                        file("a/A.java", "modified", "p"),
                        file("b/B.py", "modified", "p")));
        when(fileContentClient.getFileContent(
                anyString(), anyString(), anyString(), anyString(), any(), anyLong()))
                .thenReturn(new FileContent("x", "content", null));

        PrContextResponse response = service.buildContext(TASK_ID);

        assertEquals(List.of("c/C.java", "a/A.java", "b/B.py"),
                response.files().stream().map(PrContextFile::path).toList());
    }

    @Test
    void shouldNormalizeEmptyPatchToNull() {
        stubTaskAndPullRequest();
        when(pullRequestFilesClient.getChangedFiles(OWNER, REPO, PR_NUMBER, TOKEN))
                .thenReturn(List.of(file("src/App.java", "modified", "")));
        when(fileContentClient.getFileContent(
                anyString(), anyString(), anyString(), anyString(), any(), anyLong()))
                .thenReturn(new FileContent("src/App.java", "class App {}", null));

        assertNull(service.buildContext(TASK_ID).files().get(0).patch());
    }

    @Test
    void shouldReturnEmptyFilesWhenNoChangedFiles() {
        stubTaskAndPullRequest();
        when(pullRequestFilesClient.getChangedFiles(OWNER, REPO, PR_NUMBER, TOKEN))
                .thenReturn(List.of());

        PrContextResponse response = service.buildContext(TASK_ID);

        assertTrue(response.files().isEmpty());
        verify(fileContentClient, never()).getFileContent(
                anyString(), anyString(), anyString(), anyString(), any(), anyLong());
    }

    @Test
    void shouldPropagatePullRequestNotFound() {
        stubTaskAndPullRequest();
        when(pullRequestClient.getPullRequest(OWNER, REPO, PR_NUMBER, TOKEN))
                .thenThrow(new GithubApiException(404, "Not Found"));

        GithubApiException ex = assertThrows(GithubApiException.class, () ->
                service.buildContext(TASK_ID));

        assertEquals(404, ex.getStatusCode());
    }

    @Test
    void shouldPropagateChangedFilesFailure() {
        stubTaskAndPullRequest();
        when(pullRequestFilesClient.getChangedFiles(OWNER, REPO, PR_NUMBER, TOKEN))
                .thenThrow(new GithubApiException(500, "Server Error"));

        assertThrows(GithubApiException.class, () -> service.buildContext(TASK_ID));
    }

    @Test
    void shouldPropagateTaskNotFound() {
        when(reviewTaskService.getTaskById(99L))
                .thenThrow(new TaskNotFoundException(99L));

        assertThrows(TaskNotFoundException.class, () -> service.buildContext(99L));
    }
}