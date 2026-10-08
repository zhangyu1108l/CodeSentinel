package cn.codesentinel.github;

public record FileContent(
        String path,
        String content,
        String contentReason) {

    public static final String REASON_TOO_LARGE = "too_large";
    public static final String REASON_BINARY = "binary";
}