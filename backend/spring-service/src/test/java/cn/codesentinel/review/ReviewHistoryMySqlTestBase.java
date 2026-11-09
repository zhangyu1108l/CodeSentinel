package cn.codesentinel.review;

import cn.codesentinel.task.PublishStatus;
import cn.codesentinel.task.ReviewComment;
import cn.codesentinel.task.ReviewCommentRepository;
import cn.codesentinel.task.ReviewFinding;
import cn.codesentinel.task.ReviewFindingRepository;
import cn.codesentinel.task.ReviewHistoryService;
import cn.codesentinel.task.ReviewReport;
import cn.codesentinel.task.ReviewReportRepository;
import cn.codesentinel.task.ReviewResultDelivery;
import cn.codesentinel.task.ReviewResultDeliveryRepository;
import cn.codesentinel.task.ReviewResultFinding;
import cn.codesentinel.task.ReviewTask;
import cn.codesentinel.task.ReviewTaskService;
import cn.codesentinel.task.TaskStatus;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import org.testcontainers.containers.MySQLContainer;

import javax.sql.DataSource;
import jakarta.persistence.EntityManagerFactory;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.atomic.AtomicLong;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * Shared real-MySQL integration fixture for Phase 10.6.2 / 10.6.3.
 *
 * <p>Uses a disposable Testcontainers MySQL instance and the three
 * history tables from {@code db/review_history.sql} plus the Phase 9
 * {@code review_result_delivery} table. It deliberately does not create
 * or touch {@code review_task}; {@link ReviewTaskService} is mocked so
 * query and race tests can use synthetic task ids that do not exist in
 * the production schema.
 *
 * <p>The test transaction is disabled: individual repository/service calls
 * must own their transactions so unique-key conflicts and the fresh re-read
 * after {@code DataIntegrityViolationException} behave exactly as in
 * production.
 */
@DataJpaTest(properties = {
        "spring.jpa.hibernate.ddl-auto=none",
        "spring.jpa.properties.hibernate.generate_statistics=true",
        "spring.datasource.hikari.maximum-pool-size=20"
})
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Import({ReviewHistoryService.class, ReviewHistoryQueryService.class,
        ReviewHistoryMySqlTestBase.JacksonConfig.class})
@Transactional(propagation = Propagation.NOT_SUPPORTED)
@Tag("mysql-it")
public abstract class ReviewHistoryMySqlTestBase {

    protected static final long BASE_TASK_ID = 9_000_000_000L;
    private static final AtomicLong TASK_IDS = new AtomicLong(BASE_TASK_ID);

    /**
     * Singleton container: started once per test JVM, not once per test
     * class. This keeps the Spring TestContext cache valid across the
     * multiple IT classes (a per-class stop would leave cached JDBC
     * properties pointing at a dead container). Testcontainers' Ryuk
     * reaper removes the container when the JVM exits.
     */
    protected static final MySQLContainer<?> MYSQL =
            new MySQLContainer<>("mysql:8.0.46")
                    .withDatabaseName("codesentinel_it")
                    .withUsername("it")
                    .withPassword("it")
                    .withInitScripts("db/review_history.sql",
                            "db/review_result_delivery.sql");

    static {
        MYSQL.start();
    }

    @DynamicPropertySource
    static void datasourceProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", MYSQL::getJdbcUrl);
        registry.add("spring.datasource.username", MYSQL::getUsername);
        registry.add("spring.datasource.password", MYSQL::getPassword);
        registry.add("spring.datasource.driver-class-name",
                () -> "com.mysql.cj.jdbc.Driver");
        registry.add("spring.jpa.hibernate.ddl-auto", () -> "none");
    }

    @MockBean
    protected ReviewTaskService reviewTaskService;

    @Autowired
    protected ReviewReportRepository reportRepository;
    @Autowired
    protected ReviewFindingRepository findingRepository;
    @Autowired
    protected ReviewCommentRepository commentRepository;
    @Autowired
    protected ReviewResultDeliveryRepository deliveryRepository;
    @Autowired
    protected ReviewHistoryService historyService;
    @Autowired
    protected ReviewHistoryQueryService queryService;
    @Autowired
    protected ObjectMapper objectMapper;
    @Autowired
    protected DataSource dataSource;
    @Autowired
    protected PlatformTransactionManager transactionManager;
    @Autowired
    protected EntityManagerFactory entityManagerFactory;

    protected JdbcTemplate jdbcTemplate;

    @BeforeEach
    void resetHistoryTablesAndVerifyImage() {
        jdbcTemplate = new JdbcTemplate(dataSource);
        assertEquals("8.0.46",
                jdbcTemplate.queryForObject("SELECT VERSION()", String.class));
        commentRepository.deleteAllInBatch();
        findingRepository.deleteAllInBatch();
        reportRepository.deleteAllInBatch();
    }

    protected static long nextTaskId() {
        return TASK_IDS.getAndIncrement();
    }

    protected static String commitSha(long taskId) {
        return String.format("it%038d", taskId);
    }

    protected ReviewTask task(long taskId) {
        ReviewTask task = new ReviewTask("it-owner", "phase10-6-2", 900001,
                commitSha(taskId));
        ReflectionTestUtils.setField(task, "id", taskId);
        task.setStatus(TaskStatus.COMPLETED);
        return task;
    }

    protected ReviewResultDelivery delivery(long taskId,
                                            List<ReviewResultFinding> findings)
            throws Exception {
        return new ReviewResultDelivery(taskId, commitSha(taskId), "COMPLETED",
                objectMapper.writeValueAsString(findings),
                PublishStatus.PENDING);
    }

    protected ReviewResultDelivery publishedDelivery(
            long taskId,
            List<ReviewResultFinding> findings,
            String outcomeJson,
            PublishStatus status,
            LocalDateTime publishedAt) throws Exception {
        ReviewResultDelivery delivery = delivery(taskId, findings);
        delivery.recordPublishOutcome(status, outcomeJson, publishedAt);
        return delivery;
    }

    protected ReviewResultFinding finding(int index) {
        return new ReviewResultFinding(
                index % 2 == 0 ? "SECURITY" : "BUG",
                index % 2 == 0 ? "HIGH" : "MEDIUM",
                0.90 + (index % 10) / 100.0,
                "RULE-" + index,
                "title-" + index,
                "src/File" + index + ".java",
                10 + index,
                10 + index,
                "description-" + index,
                "reason-" + index,
                "suggestion-" + index,
                Arrays.asList("CWE-" + index, null));
    }

    protected List<ReviewResultFinding> findings(int count) {
        List<ReviewResultFinding> findings = new ArrayList<>(count);
        for (int i = 0; i < count; i++) {
            findings.add(finding(i));
        }
        return findings;
    }

    protected String outcome(String status, String summaryStatus,
                             Long summaryCommentId,
                             List<OutcomeComment> comments) throws Exception {
        ObjectNode root = objectMapper.createObjectNode();
        root.put("status", status);
        ObjectNode summary = root.putObject("summary");
        summary.put("status", summaryStatus);
        summary.putNull("reason");
        if (summaryCommentId == null) {
            summary.putNull("commentId");
        } else {
            summary.put("commentId", summaryCommentId);
        }
        ArrayNode array = root.putArray("comments");
        for (OutcomeComment comment : comments) {
            ObjectNode item = array.addObject();
            item.put("filePath", comment.filePath());
            item.put("startLine", comment.startLine());
            item.put("endLine", comment.endLine());
            item.put("status", comment.status());
            item.putNull("reason");
            if (comment.commentId() == null) {
                item.putNull("commentId");
            } else {
                item.put("commentId", comment.commentId());
            }
        }
        return objectMapper.writeValueAsString(root);
    }

    protected String outcomeForComments(String status, String summaryStatus,
                                        Long summaryCommentId,
                                        ReviewComment... comments)
            throws Exception {
        List<OutcomeComment> items = new ArrayList<>();
        for (ReviewComment comment : comments) {
            items.add(new OutcomeComment("PUBLISHED", comment.getFilePath(),
                    comment.getStartLine(), comment.getEndLine(),
                    comment.getGithubCommentId()));
        }
        return outcome(status, summaryStatus, summaryCommentId, items);
    }

    protected static ReviewFinding findingRow(long reportId, int ordinal,
                                              String filePath) {
        return new ReviewFinding(reportId, ordinal, "SECURITY", "HIGH", 0.94,
                "RULE-" + ordinal, "title-" + ordinal, filePath,
                10 + ordinal, 10 + ordinal, "description", "reason",
                "suggestion", "[\"CWE-" + ordinal + "\",null]");
    }

    protected static ReviewComment commentRow(long reportId, int ordinal,
                                              Long githubCommentId,
                                              String filePath) {
        return new ReviewComment(reportId, ordinal, githubCommentId, filePath,
                10 + ordinal, 10 + ordinal);
    }

    protected static ReviewReport report(long taskId, String commitSha,
                                         PublishStatus status, int findingCount,
                                         int commentCount, Long summaryId,
                                         LocalDateTime publishedAt) {
        return new ReviewReport(taskId, commitSha, "COMPLETED", status,
                findingCount, commentCount, summaryId, publishedAt);
    }

    protected record OutcomeComment(String status, String filePath,
                                    int startLine, int endLine,
                                    Long commentId) {
    }

    @TestConfiguration
    public static class JacksonConfig {

        @Bean
        public ObjectMapper objectMapper() {
            return new ObjectMapper();
        }
    }
}