package cn.codesentinel.github;

import com.fasterxml.jackson.annotation.JsonProperty;

public record InstallationToken(
        @JsonProperty("token") String token,
        @JsonProperty("expires_at") String expiresAt) {
}