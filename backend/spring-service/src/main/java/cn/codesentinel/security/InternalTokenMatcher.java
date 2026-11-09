package cn.codesentinel.security;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/**
 * Constant-time comparison of service-level internal credentials
 * (Phase 10.5).
 *
 * <p>The configured token is treated as unset when it is null or blank:
 * every request is rejected (fail closed). A null supplied token also
 * fails. The comparison itself uses
 * {@link MessageDigest#isEqual(byte[], byte[])} so a mismatch does not
 * short-circuit on the first differing byte.
 */
public final class InternalTokenMatcher {

    private InternalTokenMatcher() {
    }

    public static boolean matches(String expected, String provided) {
        if (expected == null || expected.isBlank() || provided == null) {
            return false;
        }
        return MessageDigest.isEqual(
                expected.getBytes(StandardCharsets.UTF_8),
                provided.getBytes(StandardCharsets.UTF_8));
    }
}