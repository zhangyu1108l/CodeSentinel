package cn.codesentinel.config;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class ReviewContextPropertiesTest {

    @Test
    void shouldApplyDefaultsWhenValuesAreMissing() {
        ReviewContextProperties properties =
                new ReviewContextProperties(0, 0, 0, null);

        assertEquals(50, properties.maxFiles());
        assertEquals(262_144, properties.maxFileBytes());
        assertEquals(5, properties.maxFetchPages());
        assertEquals(List.of("java", "py"), properties.includeContentExtensions());
    }

    @Test
    void shouldApplyDefaultsWhenExtensionsAreEmpty() {
        ReviewContextProperties properties =
                new ReviewContextProperties(10, 1000, 2, List.of());

        assertEquals(List.of("java", "py"), properties.includeContentExtensions());
    }

    @Test
    void shouldNormalizeConfiguredExtensions() {
        ReviewContextProperties properties = new ReviewContextProperties(
                10, 1000, 2, List.of("JAVA", ".py", " ", "kt"));

        assertEquals(List.of("java", "py", "kt"), properties.includeContentExtensions());
    }

    @Test
    void shouldIncludeConfiguredLanguages() {
        ReviewContextProperties properties =
                new ReviewContextProperties(50, 262_144, 5, List.of("java", "py"));

        assertTrue(properties.includesContent("src/main/App.java"));
        assertTrue(properties.includesContent("agent/app/main.py"));
    }

    @Test
    void shouldMatchExtensionCaseInsensitively() {
        ReviewContextProperties properties =
                new ReviewContextProperties(50, 262_144, 5, List.of("java", "py"));

        assertTrue(properties.includesContent("SRC/APP.JAVA"));
        assertTrue(properties.includesContent("Main.PY"));
    }

    @Test
    void shouldRejectOtherLanguages() {
        ReviewContextProperties properties =
                new ReviewContextProperties(50, 262_144, 5, List.of("java", "py"));

        assertFalse(properties.includesContent("README.md"));
        assertFalse(properties.includesContent("pom.xml"));
        assertFalse(properties.includesContent("script.sh"));
    }

    @Test
    void shouldRejectFilesWithoutExtension() {
        ReviewContextProperties properties =
                new ReviewContextProperties(50, 262_144, 5, List.of("java", "py"));

        assertFalse(properties.includesContent("Makefile"));
        assertFalse(properties.includesContent("Dockerfile"));
        assertFalse(properties.includesContent("dir/"));
        assertFalse(properties.includesContent("trailing."));
    }

    @Test
    void shouldRejectNullPath() {
        ReviewContextProperties properties =
                new ReviewContextProperties(50, 262_144, 5, List.of("java", "py"));

        assertFalse(properties.includesContent(null));
    }

    @Test
    void shouldRespectCustomExtensionList() {
        ReviewContextProperties properties =
                new ReviewContextProperties(50, 262_144, 5, List.of("kt"));

        assertFalse(properties.includesContent("App.java"));
        assertTrue(properties.includesContent("App.kt"));
    }
}