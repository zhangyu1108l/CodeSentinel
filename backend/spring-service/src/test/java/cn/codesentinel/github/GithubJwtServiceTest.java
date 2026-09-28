package cn.codesentinel.github;

import cn.codesentinel.config.GithubAppProperties;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyFactory;
import java.security.PrivateKey;
import java.security.PublicKey;
import java.security.Signature;
import java.security.spec.PKCS8EncodedKeySpec;
import java.util.Base64;

import static org.junit.jupiter.api.Assertions.*;

class GithubJwtServiceTest {

    private static String pkcs8PemContent;
    private static String pkcs1PemContent;
    private static PublicKey testPublicKey;

    private static final String TEST_APP_ID = "5086582";

    @BeforeAll
    static void loadTestKeys() throws Exception {
        Path pkcs8Path = Path.of("src/test/resources/test-key.pem");
        pkcs8PemContent = Files.readString(pkcs8Path);

        Path pkcs1Path = Path.of("src/test/resources/test-key-pkcs1.pem");
        pkcs1PemContent = Files.readString(pkcs1Path);

        String b64 = pkcs8PemContent
                .replace("-----BEGIN PRIVATE KEY-----", "")
                .replace("-----END PRIVATE KEY-----", "")
                .replaceAll("\\s", "");
        byte[] der = Base64.getDecoder().decode(b64);

        KeyFactory kf = KeyFactory.getInstance("RSA");
        PrivateKey pk = kf.generatePrivate(new PKCS8EncodedKeySpec(der));
        java.security.spec.RSAPrivateCrtKeySpec spec =
                kf.getKeySpec(pk, java.security.spec.RSAPrivateCrtKeySpec.class);
        java.security.spec.RSAPublicKeySpec pubSpec =
                new java.security.spec.RSAPublicKeySpec(
                        spec.getModulus(), spec.getPublicExponent());
        testPublicKey = kf.generatePublic(pubSpec);
    }

    @Test
    void shouldGenerateValidJwtFromPkcs8Path() {
        GithubAppProperties props = new GithubAppProperties(
                TEST_APP_ID, null,
                "src/test/resources/test-key.pem", null, null, null);
        GithubJwtService service = new GithubJwtService(props);

        String jwt = service.generateAppJwt();

        assertNotNull(jwt);
        assertFalse(jwt.isBlank());
        String[] parts = jwt.split("\\.");
        assertEquals(3, parts.length, "JWT must have 3 parts separated by dots");
    }

    @Test
    void shouldGenerateValidJwtFromPkcs8String() {
        GithubAppProperties props = new GithubAppProperties(
                TEST_APP_ID, pkcs8PemContent, null, null, null, null);
        GithubJwtService service = new GithubJwtService(props);

        String jwt = service.generateAppJwt();

        assertNotNull(jwt);
        String[] parts = jwt.split("\\.");
        assertEquals(3, parts.length);
    }

    @Test
    void shouldGenerateValidJwtFromPkcs1Path() {
        GithubAppProperties props = new GithubAppProperties(
                TEST_APP_ID, null,
                "src/test/resources/test-key-pkcs1.pem", null, null, null);
        GithubJwtService service = new GithubJwtService(props);

        String jwt = service.generateAppJwt();

        assertNotNull(jwt);
        String[] parts = jwt.split("\\.");
        assertEquals(3, parts.length);
    }

    @Test
    void shouldGenerateValidJwtFromPkcs1String() {
        GithubAppProperties props = new GithubAppProperties(
                TEST_APP_ID, pkcs1PemContent, null, null, null, null);
        GithubJwtService service = new GithubJwtService(props);

        String jwt = service.generateAppJwt();

        assertNotNull(jwt);
        String[] parts = jwt.split("\\.");
        assertEquals(3, parts.length);
    }

    @Test
    void shouldContainCorrectHeader() {
        GithubAppProperties props = new GithubAppProperties(
                TEST_APP_ID, null,
                "src/test/resources/test-key.pem", null, null, null);
        GithubJwtService service = new GithubJwtService(props);

        String jwt = service.generateAppJwt();
        String[] parts = jwt.split("\\.");

        String header = new String(Base64.getUrlDecoder().decode(parts[0]));

        assertTrue(header.contains("\"alg\""));
        assertTrue(header.contains("RS256"));
        assertTrue(header.contains("\"typ\""));
        assertTrue(header.contains("JWT"));
    }

    @Test
    void shouldContainCorrectClaims() {
        GithubAppProperties props = new GithubAppProperties(
                TEST_APP_ID, null,
                "src/test/resources/test-key.pem", null, null, null);
        GithubJwtService service = new GithubJwtService(props);

        String jwt = service.generateAppJwt();
        String[] parts = jwt.split("\\.");

        String payload = new String(Base64.getUrlDecoder().decode(parts[1]));

        assertTrue(payload.contains("\"iss\""));
        assertTrue(payload.contains("\"iat\""));
        assertTrue(payload.contains("\"exp\""));
        assertTrue(payload.contains(TEST_APP_ID));
    }

    @Test
    void shouldHaveIssClaimEqualToAppId() {
        GithubAppProperties props = new GithubAppProperties(
                TEST_APP_ID, null,
                "src/test/resources/test-key.pem", null, null, null);
        GithubJwtService service = new GithubJwtService(props);

        String jwt = service.generateAppJwt();
        String[] parts = jwt.split("\\.");

        String payload = new String(Base64.getUrlDecoder().decode(parts[1]));

        assertTrue(payload.contains("\"iss\":\"" + TEST_APP_ID + "\""));
    }

    @Test
    void shouldHaveValidExpiryRange() {
        GithubAppProperties props = new GithubAppProperties(
                TEST_APP_ID, null,
                "src/test/resources/test-key.pem", null, null, null);
        GithubJwtService service = new GithubJwtService(props);

        String jwt = service.generateAppJwt();
        String[] parts = jwt.split("\\.");

        String payload = new String(Base64.getUrlDecoder().decode(parts[1]));

        long now = System.currentTimeMillis() / 1000;
        long iat = extractClaim(payload, "iat");
        long exp = extractClaim(payload, "exp");

        assertTrue(exp > iat, "exp must be greater than iat");
        assertTrue(exp > now, "exp must be in the future");

        long ttl = exp - iat;
        assertTrue(ttl >= 540 && ttl <= 600,
                "TTL should be around 9 minutes (540s), got: " + ttl);
    }

    @Test
    void shouldUseClockSkewForIat() {
        GithubAppProperties props = new GithubAppProperties(
                TEST_APP_ID, null,
                "src/test/resources/test-key.pem", null, null, null);
        GithubJwtService service = new GithubJwtService(props);

        String jwt = service.generateAppJwt();
        String[] parts = jwt.split("\\.");

        String payload = new String(Base64.getUrlDecoder().decode(parts[1]));

        long now = System.currentTimeMillis() / 1000;
        long iat = extractClaim(payload, "iat");

        assertTrue(iat < now, "iat should be before now due to clock skew");
        assertTrue(now - iat < 120, "iat should be within 2 minutes of now (60s skew + tolerance)");
    }

    @Test
    void shouldVerifySignature() throws Exception {
        GithubAppProperties props = new GithubAppProperties(
                TEST_APP_ID, null,
                "src/test/resources/test-key.pem", null, null, null);
        GithubJwtService service = new GithubJwtService(props);

        String jwt = service.generateAppJwt();
        String[] parts = jwt.split("\\.");

        String signingInput = parts[0] + "." + parts[1];
        byte[] signature = Base64.getUrlDecoder().decode(parts[2]);

        Signature verifier = Signature.getInstance("SHA256withRSA");
        verifier.initVerify(testPublicKey);
        verifier.update(signingInput.getBytes());
        assertTrue(verifier.verify(signature), "JWT signature must be valid");
    }

    @Test
    void shouldProduceDistinctJwtsWhenTimePasses() throws Exception {
        GithubAppProperties props = new GithubAppProperties(
                TEST_APP_ID, null,
                "src/test/resources/test-key.pem", null, null, null);
        GithubJwtService service = new GithubJwtService(props);

        String jwt1 = service.generateAppJwt();
        Thread.sleep(1100);
        String jwt2 = service.generateAppJwt();

        assertNotEquals(jwt1, jwt2,
                "JWTs with different iat must be distinct");
    }

    @Test
    void shouldThrowWhenAppIdIsNull() {
        GithubAppProperties props = new GithubAppProperties(
                null, pkcs8PemContent, null, null, null, null);

        assertThrows(IllegalStateException.class, () -> {
            GithubJwtService service = new GithubJwtService(props);
            service.generateAppJwt();
        });
    }

    @Test
    void shouldThrowWhenAppIdIsBlank() {
        GithubAppProperties props = new GithubAppProperties(
                "  ", pkcs8PemContent, null, null, null, null);

        assertThrows(IllegalStateException.class, () -> {
            GithubJwtService service = new GithubJwtService(props);
            service.generateAppJwt();
        });
    }

    @Test
    void shouldThrowWhenPrivateKeyNotConfigured() {
        GithubAppProperties props = new GithubAppProperties(
                TEST_APP_ID, null, null, null, null, null);
        GithubJwtService service = new GithubJwtService(props);

        assertThrows(IllegalStateException.class, service::generateAppJwt);
    }

    @Test
    void shouldThrowWhenPrivateKeyIsBlank() {
        GithubAppProperties props = new GithubAppProperties(
                TEST_APP_ID, "  ", null, null, null, null);
        GithubJwtService service = new GithubJwtService(props);

        assertThrows(IllegalStateException.class, service::generateAppJwt);
    }

    @Test
    void shouldThrowWhenPrivateKeyPathIsInvalid() {
        GithubAppProperties props = new GithubAppProperties(
                TEST_APP_ID, null,
                "src/test/resources/nonexistent.pem", null, null, null);
        GithubJwtService service = new GithubJwtService(props);

        assertThrows(RuntimeException.class, service::generateAppJwt);
    }

    @Test
    void shouldThrowWhenPrivateKeyIsInvalidPem() {
        GithubAppProperties props = new GithubAppProperties(
                TEST_APP_ID, "not-a-valid-pem-format", null, null, null, null);
        GithubJwtService service = new GithubJwtService(props);

        assertThrows(RuntimeException.class, service::generateAppJwt);
    }

    @Test
    void shouldPreferPrivateKeyPathOverPrivateKeyString() throws Exception {
        GithubAppProperties props = new GithubAppProperties(
                TEST_APP_ID,
                "this-should-be-ignored-because-path-is-set",
                "src/test/resources/test-key.pem",
                null, null, null);

        GithubJwtService service = new GithubJwtService(props);
        String jwt = service.generateAppJwt();

        assertNotNull(jwt);
        String[] parts = jwt.split("\\.");
        assertEquals(3, parts.length);
    }

    @Test
    void shouldFallbackToPrivateKeyStringWhenPathIsNull() {
        GithubAppProperties props = new GithubAppProperties(
                TEST_APP_ID, pkcs8PemContent, null, null, null, null);

        GithubJwtService service = new GithubJwtService(props);
        String jwt = service.generateAppJwt();

        assertNotNull(jwt);
        String[] parts = jwt.split("\\.");
        assertEquals(3, parts.length);
    }

    @Test
    void base64UrlEncodeShouldBeUrlSafe() {
        byte[] data = new byte[]{0x3f, 0x3f, (byte) 0xff};

        String encoded = GithubJwtService.base64UrlEncode(data);

        assertFalse(encoded.contains("+"));
        assertFalse(encoded.contains("/"));
        assertFalse(encoded.contains("="));
    }

    private long extractClaim(String payload, String claimName) {
        String search = "\"" + claimName + "\":";
        int start = payload.indexOf(search);
        if (start < 0) {
            throw new IllegalArgumentException("Claim " + claimName + " not found");
        }
        start += search.length();
        int end = start;
        while (end < payload.length()
                && Character.isDigit(payload.charAt(end))) {
            end++;
        }
        return Long.parseLong(payload.substring(start, end));
    }
}