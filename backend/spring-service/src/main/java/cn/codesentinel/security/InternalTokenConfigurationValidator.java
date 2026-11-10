package cn.codesentinel.security;

import org.springframework.beans.factory.InitializingBean;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/**
 * Fails application startup when the Result and History service tokens
 * are both configured with the same non-blank value (Phase 10.5).
 *
 * <p>Either token may be blank: that endpoint stays fail-closed and the
 * other endpoint can still be enabled. Both blank is also valid for
 * local development. The comparison uses
 * {@link MessageDigest#isEqual(byte[], byte[])} and the failure message
 * contains no token value.
 */
@Component
public class InternalTokenConfigurationValidator implements InitializingBean {

    private final String resultToken;
    private final String historyToken;

    public InternalTokenConfigurationValidator(
            @Value("${review.result.internal-token:}") String resultToken,
            @Value("${review.history.internal-token:}") String historyToken) {
        this.resultToken = resultToken;
        this.historyToken = historyToken;
    }

    @Override
    public void afterPropertiesSet() {
        if (isBlank(resultToken) || isBlank(historyToken)) {
            return;
        }
        if (MessageDigest.isEqual(
                resultToken.getBytes(StandardCharsets.UTF_8),
                historyToken.getBytes(StandardCharsets.UTF_8))) {
            throw new IllegalStateException(
                    "review.result.internal-token and "
                            + "review.history.internal-token must differ");
        }
    }

    private static boolean isBlank(String token) {
        return token == null || token.isBlank();
    }
}