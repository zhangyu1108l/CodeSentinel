package cn.codesentinel.security;

import jakarta.servlet.DispatcherType;
import jakarta.servlet.FilterRegistration;
import jakarta.servlet.ServletException;
import jakarta.servlet.ServletRegistration;
import org.apache.catalina.connector.Request;
import org.apache.catalina.connector.Response;
import org.apache.catalina.valves.ValveBase;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.boot.web.embedded.tomcat.TomcatServletWebServerFactory;
import org.springframework.boot.web.server.WebServer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.context.support.AnnotationConfigWebApplicationContext;
import org.springframework.web.servlet.DispatcherServlet;
import org.springframework.web.servlet.config.annotation.EnableWebMvc;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.EnumSet;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Proves the Dashboard local-access boundary with a real embedded Tomcat
 * and the real Spring MVC dispatcher, not with MockMvc.
 *
 * <p>The peer address observed by the filter is injected by a Tomcat
 * context valve so the test can deterministically exercise loopback and
 * non-loopback peers. Request parsing, servlet mapping, filter execution,
 * Spring MVC path matching, and HTTP status handling all run in the
 * container.
 */
class DashboardLocalAccessFilterTomcatTest {

    private static final String NON_LOCAL = "203.0.113.10";

    private static final AtomicReference<String> ROOT_REMOTE_ADDR =
            new AtomicReference<>("127.0.0.1");

    private static final AtomicReference<String> CONTEXT_REMOTE_ADDR =
            new AtomicReference<>("127.0.0.1");

    private static WebServer rootServer;
    private static WebServer contextServer;

    @BeforeAll
    static void startServers() {
        rootServer = startServer("", ROOT_REMOTE_ADDR);
        contextServer = startServer("/app", CONTEXT_REMOTE_ADDR);
    }

    @AfterAll
    static void stopServers() {
        if (contextServer != null) {
            contextServer.stop();
        }
        if (rootServer != null) {
            rootServer.stop();
        }
    }

    @Test
    void shouldRejectNonLocalDashboardPathsAfterContainerProcessing()
            throws Exception {
        ROOT_REMOTE_ADDR.set(NON_LOCAL);

        for (String path : new String[]{
                "/api/dashboard/reviews",
                "/api/dashboard;x/reviews",
                "/api/%64ashboard/reviews",
                "/api/dashboard%3Bx/reviews",
                "/api/%2564ashboard/reviews"}) {
            HttpResult result = send(rootServer.getPort(), "GET", path,
                    Map.of());

            assertEquals(403, result.status(), path);
            assertEquals("", result.body(), path);
            assertFalse(result.body().contains("dashboard-ok"), path);
        }
    }

    @Test
    void shouldRejectNonLocalContextPathDashboardPaths()
            throws Exception {
        CONTEXT_REMOTE_ADDR.set(NON_LOCAL);

        for (String path : new String[]{
                "/app/api/dashboard/reviews",
                "/app/api/dashboard;x/reviews",
                "/app/api/%64ashboard/reviews",
                "/app/api/dashboard%3Bx/reviews",
                "/app/api/%2564ashboard/reviews"}) {
            HttpResult result = send(contextServer.getPort(), "GET", path,
                    Map.of());

            assertEquals(403, result.status(), path);
            assertFalse(result.body().contains("dashboard-ok"), path);
        }
    }

    @Test
    void shouldRejectNonLocalDashboardRootAndEncodedBackslashPaths()
            throws Exception {
        ROOT_REMOTE_ADDR.set(NON_LOCAL);

        assertFilterRejects(rootServer.getPort(), "/api/dashboard");
        assertFilterRejects(rootServer.getPort(), "/api/dashboard/");
        assertContainerOrFilterRejects(rootServer.getPort(),
                "/api/dashboard%5Creviews");
    }

    @Test
    void shouldRejectNonLocalContextPathDashboardRootAndEncodedBackslashPaths()
            throws Exception {
        CONTEXT_REMOTE_ADDR.set(NON_LOCAL);

        assertFilterRejects(contextServer.getPort(), "/app/api/dashboard");
        assertFilterRejects(contextServer.getPort(), "/app/api/dashboard/");
        assertContainerOrFilterRejects(contextServer.getPort(),
                "/app/api/dashboard%5Creviews");
    }

    @Test
    void shouldAllowLoopbackPeers() throws Exception {
        for (String address : new String[]{
                "127.0.0.1", "::1", "0:0:0:0:0:0:0:1"}) {
            ROOT_REMOTE_ADDR.set(address);

            HttpResult result = get("/api/dashboard/reviews");

            assertEquals(200, result.status(), address);
            assertEquals("dashboard-ok", result.body(), address);
        }

        CONTEXT_REMOTE_ADDR.set("127.0.0.1");
        HttpResult contextResult = send(contextServer.getPort(), "GET",
                "/app/api/dashboard/reviews", Map.of());
        assertEquals(200, contextResult.status());
        assertEquals("dashboard-ok", contextResult.body());
    }

    @Test
    void shouldRejectBlankOrUnparseablePeerAddress() throws Exception {
        ROOT_REMOTE_ADDR.set("");
        assertEquals(403, get("/api/dashboard/reviews").status());

        ROOT_REMOTE_ADDR.set("1.2.3.4.5");
        assertEquals(403, get("/api/dashboard/reviews").status());
    }

    @Test
    void shouldIgnoreForwardedHeadersInRealContainer() throws Exception {
        ROOT_REMOTE_ADDR.set(NON_LOCAL);
        Map<String, String> headers = new LinkedHashMap<>();
        headers.put("X-Forwarded-For", "127.0.0.1");
        headers.put("X-Real-IP", "127.0.0.1");
        headers.put("Forwarded", "for=127.0.0.1");

        HttpResult result = send(rootServer.getPort(), "GET",
                "/api/dashboard/reviews", headers);

        assertEquals(403, result.status());
    }

    @Test
    void shouldNotAffectPhase10WebhookOrSiblingPaths() throws Exception {
        ROOT_REMOTE_ADDR.set(NON_LOCAL);

        assertEquals(200, get("/api/reviews/7").status());
        assertEquals(200, get("/api/dashboard-other").status());
        assertEquals(200, send(rootServer.getPort(), "POST",
                "/api/github/webhook", Map.of()).status());
    }

    private static void assertFilterRejects(int port, String path)
            throws IOException {
        HttpResult result = send(port, "GET", path, Map.of());

        assertEquals(403, result.status(), path);
        assertEquals("", result.body(), path);
        assertFalse(result.body().contains("dashboard-ok"), path);
    }

    private static void assertContainerOrFilterRejects(int port, String path)
            throws IOException {
        HttpResult result = send(port, "GET", path, Map.of());

        assertTrue(result.status() == 400 || result.status() == 403,
                path + " status=" + result.status());
        if (result.status() == 403) {
            assertEquals("", result.body(), path);
        }
        assertFalse(result.body().contains("dashboard-ok"), path);
    }

    private static HttpResult get(String path) throws IOException {
        return send(rootServer.getPort(), "GET", path, Map.of());
    }

    private static WebServer startServer(String contextPath,
                                         AtomicReference<String> remoteAddr) {
        TomcatServletWebServerFactory factory =
                new TomcatServletWebServerFactory();
        factory.setPort(0);
        if (!contextPath.isEmpty()) {
            factory.setContextPath(contextPath);
        }
        factory.addContextValves(new RemoteAddrValve(remoteAddr));

        WebServer server = factory.getWebServer(servletContext -> {
            AnnotationConfigWebApplicationContext context =
                    new AnnotationConfigWebApplicationContext();
            context.register(WebConfig.class);

            DispatcherServlet dispatcherServlet =
                    new DispatcherServlet(context);
            ServletRegistration.Dynamic servlet =
                    servletContext.addServlet("dispatcher",
                            dispatcherServlet);
            servlet.setLoadOnStartup(1);
            servlet.addMapping("/");

            FilterRegistration.Dynamic filter =
                    servletContext.addFilter(
                            "dashboardLocalAccessFilter",
                            new DashboardLocalAccessFilter());
            filter.addMappingForUrlPatterns(
                    EnumSet.of(DispatcherType.REQUEST), true, "/*");
        });
        server.start();
        return server;
    }

    private static HttpResult send(int port,
                                   String method,
                                   String target,
                                   Map<String, String> headers)
            throws IOException {
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress(
                    InetAddress.getLoopbackAddress(), port), 5_000);
            socket.setSoTimeout(5_000);

            StringBuilder request = new StringBuilder();
            request.append(method).append(' ').append(target)
                    .append(" HTTP/1.1\r\n");
            request.append("Host: localhost:").append(port)
                    .append("\r\n");
            request.append("Connection: close\r\n");
            for (Map.Entry<String, String> header : headers.entrySet()) {
                request.append(header.getKey()).append(": ")
                        .append(header.getValue()).append("\r\n");
            }
            if ("POST".equals(method)) {
                request.append("Content-Length: 0\r\n");
            }
            request.append("\r\n");

            OutputStream output = socket.getOutputStream();
            output.write(request.toString()
                    .getBytes(StandardCharsets.ISO_8859_1));
            output.flush();

            byte[] response = socket.getInputStream().readAllBytes();
            String text = new String(response, StandardCharsets.ISO_8859_1);
            int statusLineEnd = text.indexOf("\r\n");
            String statusLine = statusLineEnd < 0
                    ? text : text.substring(0, statusLineEnd);
            int status = Integer.parseInt(statusLine.split(" ")[1]);
            int bodyStart = text.indexOf("\r\n\r\n");
            String body = bodyStart < 0 ? "" : text.substring(bodyStart + 4);
            return new HttpResult(status, body);
        }
    }

    @Configuration
    @EnableWebMvc
    static class WebConfig {

        @Bean
        DashboardProbeController dashboardProbeController() {
            return new DashboardProbeController();
        }
    }

    @RestController
    static class DashboardProbeController {

        @GetMapping("/api/dashboard/reviews")
        String dashboard() {
            return "dashboard-ok";
        }

        @GetMapping("/api/dashboard-other")
        String dashboardOther() {
            return "dashboard-other-ok";
        }

        @GetMapping("/api/reviews/7")
        String phase10() {
            return "phase10-ok";
        }

        @PostMapping("/api/github/webhook")
        String webhook() {
            return "webhook-ok";
        }
    }

    private static final class RemoteAddrValve extends ValveBase {

        private final AtomicReference<String> remoteAddr;

        private RemoteAddrValve(AtomicReference<String> remoteAddr) {
            this.remoteAddr = remoteAddr;
        }

        @Override
        public void invoke(Request request, Response response)
                throws IOException, ServletException {
            request.setRemoteAddr(remoteAddr.get());
            getNext().invoke(request, response);
        }
    }

    private record HttpResult(int status, String body) {
    }
}
