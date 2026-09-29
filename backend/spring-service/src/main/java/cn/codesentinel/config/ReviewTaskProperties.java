package cn.codesentinel.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "review.task")
public record ReviewTaskProperties(int maxRetries) {
}