package cn.codesentinel.webhook;

import cn.codesentinel.config.GithubAppProperties;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.util.HexFormat;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class WebhookSignatureVerifierTest {

    private static final String TEST_SECRET = "test-webhook-secret";
    private static final String HMAC_ALGORITHM = "HmacSHA256";

    private WebhookSignatureVerifier verifier;

    @BeforeEach
    void setUp() {
        GithubAppProperties properties = new GithubAppProperties(null, null, null, TEST_SECRET, null, null);
        verifier = new WebhookSignatureVerifier(properties);
    }

    @Test
    void shouldAcceptValidSignature() {
        byte[] payload = "test-payload".getBytes(StandardCharsets.UTF_8);
        String signature = makeSignature(payload, TEST_SECRET);

        assertTrue(verifier.verify(payload, signature));
    }

    @Test
    void shouldAcceptValidSignatureWithJsonPayload() {
        byte[] payload = "{\"action\":\"opened\",\"pull_request\":{\"number\":1}}"
                .getBytes(StandardCharsets.UTF_8);
        String signature = makeSignature(payload, TEST_SECRET);

        assertTrue(verifier.verify(payload, signature));
    }

    @Test
    void shouldRejectSignatureWithWrongSecret() {
        byte[] payload = "test-payload".getBytes(StandardCharsets.UTF_8);
        String signature = makeSignature(payload, "wrong-secret");

        assertFalse(verifier.verify(payload, signature));
    }

    @Test
    void shouldRejectNullSignatureHeader() {
        byte[] payload = "test".getBytes(StandardCharsets.UTF_8);
        assertFalse(verifier.verify(payload, null));
    }

    @Test
    void shouldRejectEmptySignatureHeader() {
        byte[] payload = "test".getBytes(StandardCharsets.UTF_8);
        assertFalse(verifier.verify(payload, ""));
    }

    @Test
    void shouldRejectSignatureWithWrongPrefix() {
        byte[] payload = "test".getBytes(StandardCharsets.UTF_8);
        String signature = "sha1=" + makeHexSignature(payload, TEST_SECRET);

        assertFalse(verifier.verify(payload, signature));
    }

    @Test
    void shouldRejectSignatureWithEmptyHexValue() {
        byte[] payload = "test".getBytes(StandardCharsets.UTF_8);

        assertFalse(verifier.verify(payload, "sha256="));
    }

    @Test
    void shouldRejectSignatureWithInvalidHexValue() {
        byte[] payload = "test".getBytes(StandardCharsets.UTF_8);

        assertFalse(verifier.verify(payload, "sha256=zzz"));
    }

    @Test
    void shouldRejectTamperedPayload() {
        byte[] originalPayload = "original".getBytes(StandardCharsets.UTF_8);
        String signature = makeSignature(originalPayload, TEST_SECRET);
        byte[] tamperedPayload = "tampered".getBytes(StandardCharsets.UTF_8);

        assertFalse(verifier.verify(tamperedPayload, signature));
    }

    @Test
    void shouldAcceptEmptyPayload() {
        byte[] payload = new byte[0];
        String signature = makeSignature(payload, TEST_SECRET);

        assertTrue(verifier.verify(payload, signature));
    }

    @Test
    void shouldRejectWhenSecretNotConfigured() {
        GithubAppProperties emptyProperties = new GithubAppProperties(null, null, null, "", null, null);
        WebhookSignatureVerifier emptyVerifier = new WebhookSignatureVerifier(emptyProperties);

        byte[] payload = "test".getBytes(StandardCharsets.UTF_8);
        String signature = makeSignature(payload, TEST_SECRET);

        assertFalse(emptyVerifier.verify(payload, signature));
    }

    private static String makeSignature(byte[] payload, String secret) {
        return "sha256=" + makeHexSignature(payload, secret);
    }

    private static String makeHexSignature(byte[] payload, String secret) {
        try {
            Mac mac = Mac.getInstance(HMAC_ALGORITHM);
            SecretKeySpec keySpec = new SecretKeySpec(
                    secret.getBytes(StandardCharsets.UTF_8),
                    HMAC_ALGORITHM
            );
            mac.init(keySpec);
            byte[] hmac = mac.doFinal(payload);
            return HexFormat.of().formatHex(hmac);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }
}