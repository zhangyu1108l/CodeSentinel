package cn.codesentinel.security;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class InternalTokenMatcherTest {

    @Test
    void shouldMatchExactToken() {
        assertTrue(InternalTokenMatcher.matches("secret-token",
                "secret-token"));
    }

    @Test
    void shouldRejectWrongToken() {
        assertFalse(InternalTokenMatcher.matches("secret-token",
                "other-token"));
        assertFalse(InternalTokenMatcher.matches("secret-token",
                "secret-token "));
        assertFalse(InternalTokenMatcher.matches("secret-token",
                "secret"));
    }

    @Test
    void shouldRejectNullProvidedToken() {
        assertFalse(InternalTokenMatcher.matches("secret-token", null));
    }

    @Test
    void shouldRejectUnconfiguredToken() {
        assertFalse(InternalTokenMatcher.matches(null, "secret-token"));
        assertFalse(InternalTokenMatcher.matches("", "secret-token"));
        assertFalse(InternalTokenMatcher.matches("   ", "secret-token"));
    }

    @Test
    void shouldRejectEmptyProvidedToken() {
        assertFalse(InternalTokenMatcher.matches("secret-token", ""));
    }

    @Test
    void shouldRejectBlankProvidedToken() {
        assertFalse(InternalTokenMatcher.matches("secret-token", "   "));
    }
}