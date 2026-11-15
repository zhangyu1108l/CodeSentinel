package cn.codesentinel.statistics;

/**
 * One ordered distribution bucket of the statistics API
 * (Phase 11.2.4-B1). A list is used instead of a JSON object so the
 * display order is explicit and an {@code UNKNOWN} key cannot break a
 * frontend enum type.
 */
public record ReviewStatisticsCount(String key, long count) {
}
