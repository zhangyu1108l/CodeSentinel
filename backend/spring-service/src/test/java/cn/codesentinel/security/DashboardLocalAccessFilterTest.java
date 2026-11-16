package cn.codesentinel.security;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import java.util.concurrent.atomic.AtomicBoolean;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class DashboardLocalAccessFilterTest {

    private final DashboardLocalAccessFilter filter =
            new DashboardLocalAccessFilter();

    @Test
    void shouldAllowIpv4LoopbackPeers() throws Exception {
        for (String address : new String[]{"127.0.0.1", "127.0.0.2"}) {
            Invocation invocation = invoke("/api/dashboard/reviews", address);
            assertTrue(invocation.invoked());
            assertEquals(200, invocation.response().getStatus());
        }
    }

    @Test
    void shouldAllowIpv6LoopbackPeers() throws Exception {
        for (String address : new String[]{"::1", "0:0:0:0:0:0:0:1",
                "::ffff:127.0.0.1"}) {
            Invocation invocation = invoke("/api/dashboard/reviews", address);
            assertTrue(invocation.invoked());
            assertEquals(200, invocation.response().getStatus());
        }
    }

    @Test
    void shouldRejectNonLocalPeersWithEmptyForbidden() throws Exception {
        Invocation invocation = invoke("/api/dashboard/reviews",
                "203.0.113.10");

        assertFalse(invocation.invoked());
        assertEquals(403, invocation.response().getStatus());
        assertEquals("", invocation.response().getContentAsString());
    }

    @Test
    void shouldRejectEncodedAndMatrixParameterDashboardPaths()
            throws Exception {
        for (String path : new String[]{
                "/api/dashboard;x/reviews",
                "/api/%64ashboard/reviews",
                "/api/dashboard%3Bx/reviews",
                "/api/%2564ashboard/reviews",
                "/api/dashboard%2Freviews",
                "/api/dashboard/reviews;jsessionid=x",
                "/api/dashboard;x"}) {
            Invocation invocation = invoke(path, "203.0.113.10");

            assertFalse(invocation.invoked(), path);
            assertEquals(403, invocation.response().getStatus(), path);
            assertEquals("", invocation.response().getContentAsString(),
                    path);
        }
    }

    @Test
    void shouldRejectEncodedDashboardPathsWithContextPath()
            throws Exception {
        for (String path : new String[]{
                "/app/api/dashboard;x/reviews",
                "/app/api/%64ashboard/reviews",
                "/app/api/dashboard%3Bx/reviews",
                "/app/api/%2564ashboard/reviews"}) {
            MockHttpServletRequest request = request(path, "203.0.113.10");
            request.setContextPath("/app");

            Invocation invocation = invoke(request);

            assertFalse(invocation.invoked(), path);
            assertEquals(403, invocation.response().getStatus(), path);
        }
    }

    @Test
    void shouldRejectOtherDashboardPathVariants() throws Exception {
        for (String path : new String[]{
                "/api/./dashboard/reviews",
                "/api//dashboard/reviews",
                "/api/foo/../dashboard/reviews",
                "/api/dashboard\\reviews",
                "/api/%2e/dashboard/reviews"}) {
            Invocation invocation = invoke(path, "203.0.113.10");

            assertFalse(invocation.invoked(), path);
            assertEquals(403, invocation.response().getStatus(), path);
        }
    }

    @Test
    void shouldAllowLoopbackForEncodedDashboardPaths() throws Exception {
        for (String path : new String[]{
                "/api/dashboard;x/reviews",
                "/api/%64ashboard/reviews",
                "/api/dashboard%3Bx/reviews",
                "/api/%2564ashboard/reviews"}) {
            Invocation invocation = invoke(path, "127.0.0.1");

            assertTrue(invocation.invoked(), path);
            assertEquals(200, invocation.response().getStatus(), path);
        }
    }

    @Test
    void shouldIgnoreForwardedHeadersForBoundaryDecision() throws Exception {
        MockHttpServletRequest request = request("/api/dashboard/reviews",
                "203.0.113.10");
        request.addHeader("X-Forwarded-For", "127.0.0.1");
        request.addHeader("X-Real-IP", "127.0.0.1");
        request.addHeader("Forwarded", "for=127.0.0.1");

        Invocation invocation = invoke(request);

        assertFalse(invocation.invoked());
        assertEquals(403, invocation.response().getStatus());
    }

    @Test
    void shouldNotFilterOtherApiPaths() throws Exception {
        Invocation invocation = invoke("/api/reviews/7", "203.0.113.10");

        assertTrue(invocation.invoked());
        assertEquals(200, invocation.response().getStatus());
    }

    @Test
    void shouldFilterDashboardNamespaceExactly() throws Exception {
        assertFalse(invoke("/api/dashboard", "203.0.113.10").invoked());
        assertFalse(invoke("/api/dashboard/reviews", "203.0.113.10")
                .invoked());
        assertTrue(invoke("/api/dashboard-other", "203.0.113.10").invoked());
        assertTrue(invoke("/api/%64ashboard-other", "203.0.113.10")
                .invoked());
        assertTrue(invoke("/api/dashboardx/reviews", "203.0.113.10")
                .invoked());
    }

    @Test
    void shouldHandleContextPath() throws Exception {
        MockHttpServletRequest request = request("/app/api/dashboard/reviews",
                "203.0.113.10");
        request.setContextPath("/app");

        Invocation invocation = invoke(request);

        assertFalse(invocation.invoked());
        assertEquals(403, invocation.response().getStatus());

        MockHttpServletRequest local = request("/app/api/dashboard/reviews",
                "127.0.0.1");
        local.setContextPath("/app");
        assertTrue(invoke(local).invoked());
    }

    @Test
    void shouldRejectBlankOrUnparseablePeerAddress() throws Exception {
        assertFalse(invoke("/api/dashboard/reviews", "").invoked());
        assertFalse(invoke("/api/dashboard/reviews", "1.2.3.4.5")
                .invoked());
    }

    private Invocation invoke(String path, String remoteAddr) throws Exception {
        return invoke(request(path, remoteAddr));
    }

    private Invocation invoke(MockHttpServletRequest request) throws Exception {
        MockHttpServletResponse response = new MockHttpServletResponse();
        AtomicBoolean invoked = new AtomicBoolean();
        filter.doFilter(request, response,
                (servletRequest, servletResponse) -> invoked.set(true));
        return new Invocation(invoked.get(), response);
    }

    private static MockHttpServletRequest request(String path,
                                                  String remoteAddr) {
        MockHttpServletRequest request = new MockHttpServletRequest("GET",
                path);
        request.setRequestURI(path);
        request.setRemoteAddr(remoteAddr);
        return request;
    }

    private record Invocation(boolean invoked,
                              MockHttpServletResponse response) {
    }
}
