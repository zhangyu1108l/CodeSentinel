package cn.codesentinel.controller;

import cn.codesentinel.task.ReviewTaskService;
import cn.codesentinel.task.TaskFailureResponse;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(ReviewTaskController.class)
class ReviewTaskControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private ReviewTaskService reviewTaskService;

    @Test
    void shouldMarkRunning() throws Exception {
        mockMvc.perform(post("/api/tasks/1/running"))
                .andExpect(status().isOk());

        verify(reviewTaskService).updateStatus(eq(1L), any());
    }

    @Test
    void shouldMarkComplete() throws Exception {
        mockMvc.perform(post("/api/tasks/2/complete"))
                .andExpect(status().isOk());

        verify(reviewTaskService).updateStatus(eq(2L), any());
    }

    @Test
    void shouldReportFailureWithRetry() throws Exception {
        TaskFailureResponse response = new TaskFailureResponse(true, 1L, 2, "PENDING");
        when(reviewTaskService.reportFailure(eq(1L), anyString()))
                .thenReturn(response);

        mockMvc.perform(post("/api/tasks/1/failure")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"errorMessage\":\"Handler error\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.retry").value(true))
                .andExpect(jsonPath("$.taskId").value(1))
                .andExpect(jsonPath("$.retryCount").value(2))
                .andExpect(jsonPath("$.status").value("PENDING"));
    }

    @Test
    void shouldReportFailureWithoutRetry() throws Exception {
        TaskFailureResponse response = new TaskFailureResponse(false, 1L, 3, "FAILED");
        when(reviewTaskService.reportFailure(eq(1L), anyString()))
                .thenReturn(response);

        mockMvc.perform(post("/api/tasks/1/failure")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"errorMessage\":\"Fatal error\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.retry").value(false))
                .andExpect(jsonPath("$.status").value("FAILED"));
    }
}