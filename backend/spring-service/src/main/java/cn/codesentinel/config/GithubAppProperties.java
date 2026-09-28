package cn.codesentinel.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "github.app")
public record GithubAppProperties(
        String appId,
        String privateKey,
        String privateKeyPath,
        String webhookSecret,
        String installationId,
        String apiBaseUrl
) {}