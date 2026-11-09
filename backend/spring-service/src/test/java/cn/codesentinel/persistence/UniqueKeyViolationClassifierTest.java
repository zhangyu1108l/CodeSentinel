package cn.codesentinel.persistence;

import org.junit.jupiter.api.Test;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.dao.DuplicateKeyException;

import java.sql.SQLException;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class UniqueKeyViolationClassifierTest {

    @Test
    void shouldRecognizeSpringDuplicateKeyException() {
        assertTrue(UniqueKeyViolationClassifier.isUniqueKeyViolation(
                new DuplicateKeyException("duplicate")));
    }

    @Test
    void shouldRecognizeSqlException1062WithState23000() {
        assertTrue(UniqueKeyViolationClassifier.isUniqueKeyViolation(
                new SQLException("duplicate", "23000", 1062)));
    }

    @Test
    void shouldRecognizeDataIntegrityViolationWrapping1062() {
        assertTrue(UniqueKeyViolationClassifier.isUniqueKeyViolation(
                new DataIntegrityViolationException("constraint",
                        new SQLException("duplicate", "23000", 1062))));
    }

    @Test
    void shouldRecognizeDeeplyNestedCause1062() {
        Throwable nested = new RuntimeException("outer",
                new IllegalStateException("middle",
                        new DataIntegrityViolationException("constraint",
                                new SQLException("duplicate", "23000", 1062))));

        assertTrue(UniqueKeyViolationClassifier.isUniqueKeyViolation(nested));
    }

    @Test
    void shouldRejectNotNullViolation1048() {
        assertFalse(UniqueKeyViolationClassifier.isUniqueKeyViolation(
                new SQLException("not null", "23000", 1048)));
    }

    @Test
    void shouldRejectTooLongViolation1406() {
        assertFalse(UniqueKeyViolationClassifier.isUniqueKeyViolation(
                new SQLException("too long", "22001", 1406)));
    }

    @Test
    void shouldRejectPlainDataIntegrityViolation() {
        assertFalse(UniqueKeyViolationClassifier.isUniqueKeyViolation(
                new DataIntegrityViolationException("constraint")));
    }

    @Test
    void shouldRejectOrdinaryRuntimeException() {
        assertFalse(UniqueKeyViolationClassifier.isUniqueKeyViolation(
                new RuntimeException("ordinary")));
    }

    @Test
    void shouldRejectOtherErrorCodeWithState23000() {
        assertFalse(UniqueKeyViolationClassifier.isUniqueKeyViolation(
                new SQLException("other integrity error", "23000", 1205)));
    }

    @Test
    void shouldReject1062WithDifferentSqlState() {
        assertFalse(UniqueKeyViolationClassifier.isUniqueKeyViolation(
                new SQLException("wrong state", "42000", 1062)));
    }

    @Test
    void shouldRejectNull() {
        assertFalse(UniqueKeyViolationClassifier.isUniqueKeyViolation(null));
    }

    @Test
    void shouldRejectCauseCycleWithoutHanging() {
        RuntimeException first = new RuntimeException("first");
        RuntimeException second = new RuntimeException("second", first);
        first.initCause(second);

        assertFalse(UniqueKeyViolationClassifier.isUniqueKeyViolation(first));
    }
}