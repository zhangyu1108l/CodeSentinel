package cn.codesentinel.webhook;

import cn.codesentinel.config.GithubAppProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;

@Component
public class WebhookSignatureVerifier {

    private static final Logger log = LoggerFactory.getLogger(WebhookSignatureVerifier.class);
    private static final String SIGNATURE_PREFIX = "sha256=";
    private static final String HMAC_ALGORITHM = "HmacSHA256";

    private final GithubAppProperties properties;

    public WebhookSignatureVerifier(GithubAppProperties properties) {
        this.properties = properties;
    }

    public boolean verify(byte[] payload, String signatureHeader) {
        if (signatureHeader == null || signatureHeader.isEmpty()) {
            log.debug("Signature header is null or empty");
            return false;
        }

        if (!signatureHeader.startsWith(SIGNATURE_PREFIX)) {
            log.debug("Signature header missing expected prefix '{}'", SIGNATURE_PREFIX);
            return false;
        }

        String secret = properties.webhookSecret();
        if (secret == null || secret.isEmpty()) {
            log.warn("Webhook secret is not configured, rejecting all webhook requests");
            return false;
        }

        String hexSignature = signatureHeader.substring(SIGNATURE_PREFIX.length());
        if (hexSignature.isEmpty()) {
            log.debug("Signature header has empty hex value");
            return false;
        }

        byte[] expectedSignature;
        try {
            expectedSignature = HexFormat.of().parseHex(hexSignature);
        } catch (IllegalArgumentException e) {
            log.debug("Invalid hex in signature header: {}", hexSignature);
            return false;
        }

        byte[] computedSignature = computeHmac(payload, secret);

        return MessageDigest.isEqual(expectedSignature, computedSignature);
    }

    private byte[] computeHmac(byte[] payload, String secret) {
        try {
            Mac mac = Mac.getInstance(HMAC_ALGORITHM);
            SecretKeySpec keySpec = new SecretKeySpec(
                    secret.getBytes(StandardCharsets.UTF_8),
                    HMAC_ALGORITHM
            );
            mac.init(keySpec);
            return mac.doFinal(payload);
        } catch (Exception e) {
            throw new RuntimeException("Failed to compute HMAC-SHA256", e);
        }
    }
}