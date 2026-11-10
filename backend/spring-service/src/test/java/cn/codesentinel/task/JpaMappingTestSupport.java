package cn.codesentinel.task;

import jakarta.persistence.Column;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;

import java.lang.annotation.Annotation;
import java.lang.reflect.Field;
import java.util.Collection;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Reflection helpers for verifying the Phase 10 entity metadata against
 * the approved Phase 10.1 DDL without a database.
 */
final class JpaMappingTestSupport {

    private static final List<String> RELATION_ANNOTATIONS = List.of(
            "ManyToOne", "OneToMany", "OneToOne", "ManyToMany",
            "JoinColumn", "JoinTable", "ElementCollection");

    private JpaMappingTestSupport() {
    }

    static void assertTable(Class<?> entityClass, String expectedName) {
        Table table = entityClass.getAnnotation(Table.class);
        assertNotNull(table, "missing @Table on "
                + entityClass.getSimpleName());
        assertEquals(expectedName, table.name());
    }

    static void assertUniqueConstraint(Class<?> entityClass, String name,
                                       String... columns) {
        Table table = entityClass.getAnnotation(Table.class);
        assertNotNull(table, "missing @Table on "
                + entityClass.getSimpleName());
        for (UniqueConstraint constraint : table.uniqueConstraints()) {
            if (name.equals(constraint.name())) {
                assertArrayEquals(columns, constraint.columnNames(),
                        "columns of " + name);
                return;
            }
        }
        fail("missing unique constraint " + name + " on "
                + entityClass.getSimpleName());
    }

    static Column column(Class<?> entityClass, String fieldName) {
        Column column = field(entityClass, fieldName)
                .getAnnotation(Column.class);
        assertNotNull(column, "missing @Column on "
                + entityClass.getSimpleName() + "." + fieldName);
        return column;
    }

    static void assertColumn(Class<?> entityClass, String fieldName,
                             String expectedColumnName, boolean nullable) {
        Column column = column(entityClass, fieldName);
        assertEquals(expectedColumnName, column.name(),
                "column name of " + fieldName);
        assertEquals(nullable, column.nullable(), "nullable of " + fieldName);
    }

    static Field field(Class<?> entityClass, String fieldName) {
        try {
            return entityClass.getDeclaredField(fieldName);
        } catch (NoSuchFieldException error) {
            throw new AssertionError("missing field " + fieldName + " on "
                    + entityClass.getSimpleName(), error);
        }
    }

    static Enumerated enumerated(Class<?> entityClass, String fieldName) {
        Enumerated enumerated = field(entityClass, fieldName)
                .getAnnotation(Enumerated.class);
        assertNotNull(enumerated, "missing @Enumerated on " + fieldName);
        return enumerated;
    }

    static GeneratedValue generatedValue(Class<?> entityClass,
                                         String fieldName) {
        GeneratedValue generated = field(entityClass, fieldName)
                .getAnnotation(GeneratedValue.class);
        assertNotNull(generated, "missing @GeneratedValue on " + fieldName);
        return generated;
    }

    static void assertNoRelationshipMappings(Class<?> entityClass) {
        for (Field field : entityClass.getDeclaredFields()) {
            for (Annotation annotation : field.getAnnotations()) {
                assertFalse(
                        RELATION_ANNOTATIONS.contains(
                                annotation.annotationType().getSimpleName()),
                        "relationship mapping on " + field.getName());
            }
            assertFalse(
                    Collection.class.isAssignableFrom(field.getType())
                            || Map.class.isAssignableFrom(field.getType())
                            || field.getType().isArray(),
                    "collection-typed field " + field.getName());
        }
        for (Annotation annotation : entityClass.getAnnotations()) {
            assertFalse(
                    RELATION_ANNOTATIONS.contains(
                            annotation.annotationType().getSimpleName()),
                    "relationship mapping on the entity class");
        }
    }
}