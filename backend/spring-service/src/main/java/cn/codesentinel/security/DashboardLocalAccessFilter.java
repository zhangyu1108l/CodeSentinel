package cn.codesentinel.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.server.PathContainer;
import org.springframework.http.server.RequestPath;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;
import org.springframework.web.util.ServletRequestPathUtils;
import org.springframework.web.util.UriUtils;
import org.springframework.web.util.pattern.PathPattern;
import org.springframework.web.util.pattern.PathPatternParser;

import java.io.IOException;
import java.net.InetAddress;
import java.net.UnknownHostException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayDeque;
import java.util.Deque;

/**
 * Restricts every {@code /api/dashboard/**} endpoint to loopback peers
 * (Phase 11.2.2-A).
 *
 * <p>The check uses the TCP peer address from
 * {@link HttpServletRequest#getRemoteAddr()} and deliberately ignores
 * {@code X-Forwarded-For}, {@code Forwarded}, and every other
 * proxy-supplied header. Forwarded-header processing is disabled in
 * {@code application.yml}, so a remote client cannot make itself look
 * local by sending a header.
 *
 * <p>Dashboard path detection uses Spring MVC's own
 * {@link RequestPath} / {@link PathPattern} parsing, so percent-encoded
 * segments and matrix parameters are interpreted the same way as
 * controller routing. A bounded canonicalization fallback additionally
 * rejects encoded matrix delimiters and double-encoded variants. A
 * malformed path is treated as a Dashboard request (fail closed).
 *
 * <p>This is an application-level personal-use boundary, not user
 * authentication. A reverse proxy running on the same host would also
 * appear as loopback; any such proxy must enforce its own authentication
 * before exposing the Dashboard.
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class DashboardLocalAccessFilter extends OncePerRequestFilter {

    private static final Logger log =
            LoggerFactory.getLogger(DashboardLocalAccessFilter.class);

    private static final String DASHBOARD_PATH = "/api/dashboard";

    private static final PathPattern DASHBOARD_ROOT =
            new PathPatternParser().parse(DASHBOARD_PATH);

    private static final PathPattern DASHBOARD_NAMESPACE =
            new PathPatternParser().parse(DASHBOARD_PATH + "/**");

    /**
     * Spring MVC decodes the request path once. Repeating the decode a
     * few times only widens the filter's boundary for malformed or
     * multiply encoded paths; it never narrows it.
     */
    private static final int MAX_CANONICALIZATION_PASSES = 3;

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !isDashboardRequest(request);
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain)
            throws ServletException, IOException {
        String remoteAddr = request.getRemoteAddr();
        if (!isLoopback(remoteAddr)) {
            log.warn("Rejected non-local dashboard request from {}",
                    remoteAddr);
            response.setStatus(HttpServletResponse.SC_FORBIDDEN);
            return;
        }
        filterChain.doFilter(request, response);
    }

    private static boolean isDashboardRequest(HttpServletRequest request) {
        try {
            PathContainer path = ServletRequestPathUtils.parseAndCache(request)
                    .pathWithinApplication();

            return DASHBOARD_ROOT.matches(path)
                    || DASHBOARD_NAMESPACE.matches(path)
                    || canonicalizesToDashboard(path.value());
        } catch (RuntimeException invalidPath) {
            // The container and Spring MVC cannot agree on this path;
            // let the loopback gate make the decision instead of routing it.
            return true;
        }
    }

    /**
     * Decodes and cleans the context-relative path until it stabilizes.
     * This catches encoded matrix parameters (for example
     * {@code dashboard%3Bx}) and double-encoded names that a single
     * {@code URLDecoder} call would miss. Invalid escapes are treated as
     * Dashboard paths so the request cannot slip past the boundary.
     */
    private static boolean canonicalizesToDashboard(String path) {
        String current = path;
        for (int pass = 0; pass < MAX_CANONICALIZATION_PASSES; pass++) {
            String decoded = UriUtils.decode(current, StandardCharsets.UTF_8);
            String next = normalizePath(removeMatrixParameters(decoded));
            if (next.equals(current)) {
                break;
            }
            current = next;
        }
        return current.equals(DASHBOARD_PATH)
                || current.startsWith(DASHBOARD_PATH + "/");
    }

    /**
     * Collapses duplicate separators, unifies backslashes, and removes
     * {@code .}/{@code ..} segments. These are container- or
     * proxy-dependent variants of the same lookup path.
     */
    private static String normalizePath(String path) {
        String slashed = path.replace('\\', '/');
        boolean absolute = slashed.startsWith("/");
        boolean trailingSlash = slashed.endsWith("/");

        Deque<String> segments = new ArrayDeque<>();
        for (String segment : slashed.split("/", -1)) {
            if (segment.isEmpty() || ".".equals(segment)) {
                continue;
            }
            if ("..".equals(segment)) {
                if (!segments.isEmpty()) {
                    segments.removeLast();
                }
                continue;
            }
            segments.addLast(segment);
        }

        StringBuilder normalized = new StringBuilder();
        if (absolute) {
            normalized.append('/');
        }
        boolean first = true;
        for (String segment : segments) {
            if (!first) {
                normalized.append('/');
            }
            normalized.append(segment);
            first = false;
        }
        if (trailingSlash && normalized.length() > 0
                && normalized.charAt(normalized.length() - 1) != '/') {
            normalized.append('/');
        }
        return normalized.length() == 0
                ? (absolute ? "/" : "") : normalized.toString();
    }

    /**
     * Removes {@code ;...} path parameters from each segment, matching
     * the servlet container / Spring MVC lookup-path behavior.
     */
    private static String removeMatrixParameters(String path) {
        if (path.indexOf(';') < 0) {
            return path;
        }
        StringBuilder result = new StringBuilder(path.length());
        int segmentStart = 0;
        while (segmentStart <= path.length()) {
            int segmentEnd = path.indexOf('/', segmentStart);
            if (segmentEnd < 0) {
                segmentEnd = path.length();
            }
            int parameter = path.indexOf(';', segmentStart);
            int cut = (parameter >= 0 && parameter < segmentEnd)
                    ? parameter : segmentEnd;
            result.append(path, segmentStart, cut);
            if (segmentEnd == path.length()) {
                break;
            }
            result.append('/');
            segmentStart = segmentEnd + 1;
        }
        return result.toString();
    }

    private static boolean isLoopback(String remoteAddr) {
        if (remoteAddr == null || remoteAddr.isBlank()) {
            return false;
        }
        try {
            return InetAddress.getByName(remoteAddr).isLoopbackAddress();
        } catch (UnknownHostException error) {
            return false;
        }
    }
}
