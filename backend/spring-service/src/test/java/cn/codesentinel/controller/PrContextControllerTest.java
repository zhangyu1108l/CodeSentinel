package cn.codesentinel.controller;

import cn.codesentinel.github.GithubApiException;
import cn.codesentinel.prcontext.PrContextFile;
import cn.codesentinel.prcontext.PrContextResponse;
import cn.codesentinel.prcontext.PrContextService;
import cn.codesentinel.task.TaskNotFoundException;
import jakarta.servlet.ServletException;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.hamcrest.Matchers.nullValue;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(PrContextController.class)
class PrContextControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private PrContextService prContextService;

    private PrContextResponse response() {
        PrContextFile available = new PrContextFile(
                "src/App.java",
                null,
                "modified",
                3,
                1,
                4,
                "@@ patch @@",
                "https://github.com/owner/repo/blob/abc/src/App.java",
                true,
                false,
                null,
                "class App {}");
        PrContextFile skipped = new PrContextFile(
                "src/Old.java",
                "src/Legacy.java",
                "removed",
                0,
                5,
                5,
                null,
                "https://github.com/owner/repo/blob/abc/src/Old.java",
                false,
                false,
                "removed",
                null);
        return new PrContextResponse(
                7L, "owner", "repo", 42, "abc123",
                "Add review context", "open", "main", "feature/context",
                List.of(available, skipped));
    }

    @Test
    void shouldReturnPrContext() throws Exception {
        when(prContextService.buildContext(7L)).thenReturn(response());

        mockMvc.perform(get("/api/tasks/7/pr-context"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.taskId").value(7))
                .andExpect(jsonPath("$.owner").value("owner"))
                .andExpect(jsonPath("$.repo").value("repo"))
                .andExpect(jsonPath("$.prNumber").value(42))
                .andExpect(jsonPath("$.commitSha").value("abc123"))
                .andExpect(jsonPath("$.title").value("Add review context"))
                .andExpect(jsonPath("$.state").value("open"))
                .andExpect(jsonPath("$.baseRef").value("main"))
                .andExpect(jsonPath("$.headRef").value("feature/context"))
                .andExpect(jsonPath("$.files.length()").value(2));
    }

    @Test
    void shouldExposeFileFieldsAndContentState() throws Exception {
        when(prContextService.buildContext(7L)).thenReturn(response());

        mockMvc.perform(get("/api/tasks/7/pr-context"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.files[0].path").value("src/App.java"))
                .andExpect(jsonPath("$.files[0].status").value("modified"))
                .andExpect(jsonPath("$.files[0].additions").value(3))
                .andExpect(jsonPath("$.files[0].deletions").value(1))
                .andExpect(jsonPath("$.files[0].changes").value(4))
                .andExpect(jsonPath("$.files[0].patch").value("@@ patch @@"))
                .andExpect(jsonPath("$.files[0].content_available").value(true))
                .andExpect(jsonPath("$.files[0].content_truncated").value(false))
                .andExpect(jsonPath("$.files[0].content_reason").value(nullValue()))
                .andExpect(jsonPath("$.files[0].content").value("class App {}"))
                .andExpect(jsonPath("$.files[1].previousPath").value("src/Legacy.java"))
                .andExpect(jsonPath("$.files[1].content_available").value(false))
                .andExpect(jsonPath("$.files[1].content_reason").value("removed"))
                .andExpect(jsonPath("$.files[1].content").value(nullValue()))
                .andExpect(jsonPath("$.files[1].patch").value(nullValue()));
    }

    @Test
    void shouldPassTaskIdToService() throws Exception {
        when(prContextService.buildContext(7L)).thenReturn(response());

        mockMvc.perform(get("/api/tasks/7/pr-context"))
                .andExpect(status().isOk());

        verify(prContextService).buildContext(7L);
    }

    @Test
    void shouldReturn404WhenTaskIsMissing() throws Exception {
        when(prContextService.buildContext(99L))
                .thenThrow(new TaskNotFoundException(99L));

        mockMvc.perform(get("/api/tasks/99/pr-context"))
                .andExpect(status().isNotFound());
    }

    @Test
    void shouldFailWhenContextCannotBeBuilt() throws Exception {
        when(prContextService.buildContext(7L))
                .thenThrow(new GithubApiException(404, "Not Found"));

        // No handler for GitHub failures by design: the servlet container
        // turns the propagated exception into a 5xx response, matching the
        // existing project style of not inventing a new error body.
        ServletException thrown = assertThrows(ServletException.class, () ->
                mockMvc.perform(get("/api/tasks/7/pr-context")));

        assertInstanceOf(GithubApiException.class, thrown.getCause());
    }
}