package cn.codesentinel.persistence;

import org.springframework.dao.DuplicateKeyException;

import java.sql.SQLException;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.Set;

/**
 * Recognises an explicit MySQL unique-key violation (Phase 10.6.3).
 *
 * <p>The classifier deliberately accepts only two kinds of evidence:
 * a Spring {@link DuplicateKeyException} anywhere in the cause chain, or
 * a {@link SQLException} with MySQL error code 1062 and SQLState 23000
 * anywhere in the cause chain. A generic
 * {@code DataIntegrityViolationException}, another SQLState 23000 error
 * code, or an exception without one of those markers is not sufficient.
 *
 * <p>It never inspects exception messages (which may contain SQL or
 * user data) and never mutates or swallows the supplied exception.
 */
public final class UniqueKeyViolationClassifier {

    static final int MYSQL_DUPLICATE_ENTRY = 1062;
    static final String MYSQL_INTEGRITY_SQL_STATE = "23000";

    private UniqueKeyViolationClassifier() {
    }

    public static boolean isUniqueKeyViolation(Throwable throwable) {
        Set<Throwable> visited = Collections.newSetFromMap(
                new IdentityHashMap<>());
        for (Throwable current = throwable;
                current != null;
                current = current.getCause()) {
            if (!visited.add(current)) {
                // A malformed cause cycle must not cause an infinite loop.
                return false;
            }
            if (current instanceof DuplicateKeyException) {
                return true;
            }
            if (current instanceof SQLException sqlError
                    && sqlError.getErrorCode() == MYSQL_DUPLICATE_ENTRY
                    && MYSQL_INTEGRITY_SQL_STATE.equals(
                            sqlError.getSQLState())) {
                return true;
            }
        }
        return false;
    }
}