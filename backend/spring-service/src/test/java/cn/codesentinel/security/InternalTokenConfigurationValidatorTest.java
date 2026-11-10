package cn.codesentinel.security;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;

class InternalTokenConfigurationValidatorTest {

    @Test
    void shouldRejectIdenticalNonBlankTokens() {
        InternalTokenConfigurationValidator validator =
                new InternalTokenConfigurationValidator(
                        "shared-secret-token", "shared-secret-token");

        IllegalStateException error = assertThrows(
                IllegalStateException.class, validator::afterPropertiesSet);

        assertFalse(error.getMessage().contains("shared-secret-token"));
    }

    @Test
    void shouldAllowDifferentNonBlankTokens() {
        assertDoesNotThrow(() -> validator("result-token", "history-token")
                .afterPropertiesSet());
    }

    @Test
    void shouldAllowBlankResultTokenWithConfiguredHistoryToken() {
        assertDoesNotThrow(() -> validator("", "history-token")
                .afterPropertiesSet());
    }

    @Test
    void shouldAllowConfiguredResultTokenWithBlankHistoryToken() {
        assertDoesNotThrow(() -> validator("result-token", "")
                .afterPropertiesSet());
    }

    @Test
    void shouldAllowBothTokensBlank() {
        assertDoesNotThrow(() -> validator("", "").afterPropertiesSet());
    }

    @Test
    void shouldAllowBothTokensWhitespace() {
        assertDoesNotThrow(() -> validator("   ", "\t\n")
                .afterPropertiesSet());
    }

    private static InternalTokenConfigurationValidator validator(
            String resultToken, String historyToken) {
        return new InternalTokenConfigurationValidator(resultToken,
                historyToken);
    }
}