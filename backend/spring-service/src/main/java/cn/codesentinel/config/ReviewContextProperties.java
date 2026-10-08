package cn.codesentinel.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.List;
import java.util.Locale;

@ConfigurationProperties(prefix = "review.context")
public record ReviewContextProperties(
        int maxFiles,
        int maxFileBytes,
        int maxFetchPages,
        List<String> includeContentExtensions) {

    private static final int DEFAULT_MAX_FILES = 50;
    private static final int DEFAULT_MAX_FILE_BYTES = 262_144;
    private static final int DEFAULT_MAX_FETCH_PAGES = 5;
    private static final List<String> DEFAULT_EXTENSIONS = List.of("java", "py");

    public ReviewContextProperties {
        maxFiles = maxFiles > 0 ? maxFiles : DEFAULT_MAX_FILES;
        maxFileBytes = maxFileBytes > 0 ? maxFileBytes : DEFAULT_MAX_FILE_BYTES;
        maxFetchPages = maxFetchPages > 0 ? maxFetchPages : DEFAULT_MAX_FETCH_PAGES;
        includeContentExtensions =
                includeContentExtensions == null || includeContentExtensions.isEmpty()
                        ? DEFAULT_EXTENSIONS
                        : includeContentExtensions.stream()
                                .filter(extension -> extension != null && !extension.isBlank())
                                .map(extension -> extension.toLowerCase(Locale.ROOT).replace(".", ""))
                                .toList();
    }

    public boolean includesContent(String path) {
        if (path == null) {
            return false;
        }
        int dot = path.lastIndexOf('.');
        if (dot < 0 || dot == path.length() - 1) {
            return false;
        }
        String extension = path.substring(dot + 1).toLowerCase(Locale.ROOT);
        return includeContentExtensions.contains(extension);
    }
}