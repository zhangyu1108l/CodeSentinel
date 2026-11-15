package cn.codesentinel.statistics;

import java.time.LocalDate;

/**
 * One zero-filled trend bucket (Phase 11.2.4-B1, category counters added in
 * Phase 11.3-B1).
 *
 * <p>A DAY bucket covers one application-local calendar day. A WEEK bucket
 * covers one ISO-8601 week (Monday through Sunday); the first and last
 * buckets of a range may extend past the requested bounds.
 *
 * <p>Finding counters, including the category counters, only include
 * reports whose actual Finding row count equals {@code finding_count} -
 * exactly the reports used by {@code summary.categoryCounts}. An empty
 * bucket, or a report without Finding aggregates, yields zero for every
 * counter. {@code unknownCategoryCount} counts Findings whose stored
 * category is not one of the four known categories.
 */
public record ReviewStatisticsTrendPoint(
        LocalDate bucketStart,
        LocalDate bucketEnd,
        long reviewCount,
        long findingCount,
        long highSeverityFindingCount,
        long bugCount,
        long securityCount,
        long performanceCount,
        long qualityCount,
        long unknownCategoryCount) {
}
