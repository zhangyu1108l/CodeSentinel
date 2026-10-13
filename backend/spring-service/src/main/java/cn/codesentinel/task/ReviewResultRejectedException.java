package cn.codesentinel.task;

/**
 * A client-error rejection of one result delivery. {@code status} is the
 * HTTP status the controller must answer with (currently 409 conflict or
 * 422 unprocessable entity); the message is field-level and safe to
 * expose.
 */
public class ReviewResultRejectedException extends RuntimeException {

    private final int status;

    public ReviewResultRejectedException(int status, String message) {
        super(message);
        this.status = status;
    }

    public int getStatus() {
        return status;
    }
}