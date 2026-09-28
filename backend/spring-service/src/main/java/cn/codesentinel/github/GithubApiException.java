package cn.codesentinel.github;

public class GithubApiException extends RuntimeException {

    private final int statusCode;

    public GithubApiException(String message) {
        super(message);
        this.statusCode = 0;
    }

    public GithubApiException(int statusCode, String message) {
        super(message);
        this.statusCode = statusCode;
    }

    public GithubApiException(String message, Throwable cause) {
        super(message, cause);
        this.statusCode = 0;
    }

    public int getStatusCode() {
        return statusCode;
    }

    public boolean isClientError() {
        return statusCode >= 400 && statusCode < 500;
    }

    public boolean isServerError() {
        return statusCode >= 500;
    }
}