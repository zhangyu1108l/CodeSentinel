package cn.codesentinel.github;

import cn.codesentinel.config.GithubAppProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.io.ByteArrayInputStream;
import java.io.DataInputStream;
import java.io.IOException;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyFactory;
import java.security.PrivateKey;
import java.security.Signature;
import java.security.spec.PKCS8EncodedKeySpec;
import java.security.spec.RSAPrivateKeySpec;
import java.time.Instant;
import java.util.Base64;

@Component
public class GithubJwtService {

    private static final Logger log = LoggerFactory.getLogger(GithubJwtService.class);

    private static final long CLOCK_SKEW_SECONDS = 60;
    private static final long JWT_TTL_SECONDS = 540;
    private static final String RSA_ALGORITHM = "RSA";
    private static final String SIGN_ALGORITHM = "SHA256withRSA";

    private final GithubAppProperties properties;
    private volatile PrivateKey privateKey;

    public GithubJwtService(GithubAppProperties properties) {
        this.properties = properties;
    }

    private PrivateKey getPrivateKey() {
        if (this.privateKey == null) {
            synchronized (this) {
                if (this.privateKey == null) {
                    this.privateKey = loadPrivateKey();
                }
            }
        }
        return this.privateKey;
    }

    public String generateAppJwt() {
        String appId = properties.appId();
        if (appId == null || appId.isBlank()) {
            throw new IllegalStateException("GitHub App ID is not configured");
        }

        String header = base64UrlEncode(
                "{\"alg\":\"RS256\",\"typ\":\"JWT\"}".getBytes(StandardCharsets.UTF_8));

        long now = Instant.now().getEpochSecond();
        long iat = now - CLOCK_SKEW_SECONDS;
        long exp = iat + JWT_TTL_SECONDS;

        String payloadJson = String.format(
                "{\"iat\":%d,\"exp\":%d,\"iss\":\"%s\"}", iat, exp, appId);
        String payload = base64UrlEncode(
                payloadJson.getBytes(StandardCharsets.UTF_8));

        String signingInput = header + "." + payload;
        byte[] signatureBytes = sign(signingInput.getBytes(StandardCharsets.UTF_8));
        String signature = base64UrlEncode(signatureBytes);

        String jwt = signingInput + "." + signature;
        log.debug("Generated GitHub App JWT (exp={}, iss={})", exp, appId);
        return jwt;
    }

    private PrivateKey loadPrivateKey() {
        String pemContent = readPemContent();
        if (pemContent == null || pemContent.isBlank()) {
            throw new IllegalStateException(
                    "GitHub App private key is not configured. "
                            + "Set github.app.private-key-path or github.app.private-key");
        }

        try {
            return parsePemPrivateKey(pemContent);
        } catch (Exception e) {
            throw new RuntimeException("Failed to parse GitHub App private key", e);
        }
    }

    private String readPemContent() {
        String path = properties.privateKeyPath();
        if (path != null && !path.isBlank()) {
            try {
                String content = Files.readString(Path.of(path));
                log.debug("Loaded private key from path: {}", path);
                return content;
            } catch (IOException e) {
                throw new RuntimeException(
                        "Failed to read private key file: " + path, e);
            }
        }

        return properties.privateKey();
    }

    PrivateKey parsePemPrivateKey(String pemContent) throws Exception {
        String trimmed = pemContent.strip();

        boolean isPkcs1 = trimmed.contains("BEGIN RSA PRIVATE KEY");
        boolean isPkcs8 = trimmed.contains("BEGIN PRIVATE KEY");

        String base64 = trimmed
                .replace("-----BEGIN RSA PRIVATE KEY-----", "")
                .replace("-----END RSA PRIVATE KEY-----", "")
                .replace("-----BEGIN PRIVATE KEY-----", "")
                .replace("-----END PRIVATE KEY-----", "")
                .replaceAll("\\s", "");

        byte[] der = Base64.getDecoder().decode(base64);

        if (isPkcs1) {
            log.debug("Parsing PKCS#1 private key");
            return parsePkcs1Der(der);
        }

        if (isPkcs8) {
            log.debug("Parsing PKCS#8 private key");
            PKCS8EncodedKeySpec spec = new PKCS8EncodedKeySpec(der);
            KeyFactory kf = KeyFactory.getInstance(RSA_ALGORITHM);
            return kf.generatePrivate(spec);
        }

        throw new IllegalArgumentException(
                "Unrecognized PEM format: expected RSA PRIVATE KEY or PRIVATE KEY");
    }

    private PrivateKey parsePkcs1Der(byte[] der) throws Exception {
        try (DataInputStream din = new DataInputStream(new ByteArrayInputStream(der))) {

            int tag = din.readUnsignedByte();
            if (tag != 0x30) {
                throw new IllegalArgumentException(
                        "Expected SEQUENCE tag (0x30) but got 0x"
                                + Integer.toHexString(tag));
            }
            readDerLength(din);

            tag = din.readUnsignedByte();
            if (tag != 0x02) {
                throw new IllegalArgumentException(
                        "Expected INTEGER (version) tag in PKCS#1 key");
            }
            int verLen = readDerLength(din);
            din.skipBytes(verLen);

            tag = din.readUnsignedByte();
            if (tag != 0x02) {
                throw new IllegalArgumentException(
                        "Expected INTEGER (modulus) tag in PKCS#1 key");
            }
            int modLen = readDerLength(din);
            byte[] modBytes = new byte[modLen];
            din.readFully(modBytes);
            BigInteger modulus = new BigInteger(1, modBytes);

            tag = din.readUnsignedByte();
            int pubLen = readDerLength(din);
            din.skipBytes(pubLen);

            tag = din.readUnsignedByte();
            if (tag != 0x02) {
                throw new IllegalArgumentException(
                        "Expected INTEGER (privateExponent) tag in PKCS#1 key");
            }
            int privLen = readDerLength(din);
            byte[] privBytes = new byte[privLen];
            din.readFully(privBytes);
            BigInteger privateExponent = new BigInteger(1, privBytes);

            RSAPrivateKeySpec spec = new RSAPrivateKeySpec(modulus, privateExponent);
            KeyFactory kf = KeyFactory.getInstance(RSA_ALGORITHM);
            return kf.generatePrivate(spec);
        }
    }

    private int readDerLength(DataInputStream din) throws IOException {
        int b = din.readUnsignedByte();
        if (b < 0x80) {
            return b;
        }
        int numBytes = b & 0x7F;
        int length = 0;
        for (int i = 0; i < numBytes; i++) {
            length = (length << 8) | din.readUnsignedByte();
        }
        return length;
    }

    private byte[] sign(byte[] data) {
        try {
            Signature signature = Signature.getInstance(SIGN_ALGORITHM);
            signature.initSign(getPrivateKey());
            signature.update(data);
            return signature.sign();
        } catch (java.security.NoSuchAlgorithmException
                 | java.security.InvalidKeyException
                 | java.security.SignatureException e) {
            throw new RuntimeException("Failed to sign JWT", e);
        }
    }

    static String base64UrlEncode(byte[] data) {
        return Base64.getUrlEncoder().withoutPadding().encodeToString(data);
    }
}