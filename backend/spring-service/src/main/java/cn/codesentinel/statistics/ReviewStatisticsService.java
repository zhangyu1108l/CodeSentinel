package cn.codesentinel.statistics;

import cn.codesentinel.review.InvalidReviewHistoryFilterException;
import cn.codesentinel.review.InvalidReviewHistoryPaginationException;
import cn.codesentinel.review.ReviewHistoryDataIntegrityException;
import cn.codesentinel.review.ReviewHistoryFilter;
import cn.codesentinel.review.ReviewHistoryQueryService;
import cn.codesentinel.review.ReviewPageResponse;
import cn.codesentinel.statistics.ReviewStatisticsRepository.FindingAggregateRow;
import cn.codesentinel.statistics.ReviewStatisticsRepository.ReportStatisticsRow;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.time.DayOfWeek;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.ZoneId;
import java.time.temporal.ChronoUnit;
import java.time.temporal.TemporalAdjusters;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/**
 * Read-only statistics service of the Dashboard Insights API
 * (Phase 11.2.4-B1; category trend counters added in Phase 11.3-B1).
 *
 * <p>Report-level metrics always use every {@code review_report} in the
 * effective range. Finding metrics, including every trend category
 * counter, only use reports whose actual Finding row count equals
 * {@code finding_count}; comment metrics only use reports whose actual
 * comment row count equals {@code published_comment_count}. Exclusions are
 * reported in {@link ReviewStatisticsDataQuality}.
 *
 * <p>Time is application-local wall-clock time, matching the existing
 * {@code DATETIME(6)} storage convention. SQL date functions are never used
 * to derive the range or a trend bucket.
 */
@Service
public class ReviewStatisticsService {

    public static final int DEFAULT_RANGE_DAYS = 30;
    public static final int MAX_RANGE_DAYS = 366;
    public static final int MAX_PAGE_SIZE =
            ReviewHistoryQueryService.MAX_PAGE_SIZE;

    private static final LocalTime END_OF_DAY =
            LocalTime.of(23, 59, 59, 999_999_000);
    private static final List<String> CATEGORY_KEYS =
            List.of("BUG", "SECURITY", "PERFORMANCE", "QUALITY", "UNKNOWN");
    private static final List<String> SEVERITY_KEYS =
            List.of("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO", "UNKNOWN");
    private static final List<String> PUBLISH_STATUS_KEYS =
            List.of("PUBLISHED", "PARTIAL", "FAILED", "PENDING", "UNKNOWN");
    private static final List<String> AI_STATUS_KEYS =
            List.of("COMPLETED", "DEGRADED", "UNKNOWN");
    private static final Set<String> KNOWN_PUBLISH_STATUSES =
            Set.of("PUBLISHED", "PARTIAL", "FAILED", "PENDING");
    private static final Set<String> KNOWN_AI_STATUSES =
            Set.of("COMPLETED", "DEGRADED");

    private final ReviewStatisticsRepository repository;
    private final ZoneId zoneId;
    private final Clock clock;

    @Autowired
    public ReviewStatisticsService(ReviewStatisticsRepository repository) {
        this(repository, ZoneId.systemDefault(),
                Clock.system(ZoneId.systemDefault()));
    }

    ReviewStatisticsService(ReviewStatisticsRepository repository,
                            ZoneId zoneId, Clock clock) {
        this.repository = Objects.requireNonNull(repository);
        this.zoneId = Objects.requireNonNull(zoneId);
        this.clock = Objects.requireNonNull(clock).withZone(zoneId);
    }

    @Transactional(readOnly = true,
            isolation = Isolation.REPEATABLE_READ)
    public ReviewStatisticsOverviewResponse overview(
            ReviewHistoryFilter filter, String granularity) {
        StatisticsGranularity parsed = StatisticsGranularity.parse(granularity);
        EffectiveRange range = resolveRange(filter);
        Snapshot snapshot = loadSnapshot(filter, range);
        return new ReviewStatisticsOverviewResponse(
                new ReviewStatisticsRange(range.from(), range.to(),
                        zoneId.getId(), parsed),
                LocalDateTime.now(clock),
                buildSummary(snapshot),
                buildTrend(snapshot, range, parsed),
                buildDataQuality(snapshot));
    }

    @Transactional(readOnly = true,
            isolation = Isolation.REPEATABLE_READ)
    public ReviewPageResponse<ReviewStatisticsReviewItem> reviews(
            ReviewHistoryFilter filter, int page, int size,
            String sort, String direction) {
        validatePagination(page, size);
        SortKey sortKey = parseSort(sort);
        boolean ascending = parseAscending(direction);
        EffectiveRange range = resolveRange(filter);
        Snapshot snapshot = loadSnapshot(filter, range);

        List<ReviewWithReport> rows = snapshot.reports().stream()
                .map(report -> new ReviewWithReport(
                        report.getReportId(),
                        toReviewItem(report,
                                snapshot.aggregates().get(report.getReportId()))))
                .toList();

        Comparator<ReviewWithReport> comparator = comparator(sortKey);
        if (!ascending) {
            comparator = comparator.reversed();
        }
        comparator = comparator.thenComparing(
                Comparator.comparingLong(ReviewWithReport::reportId).reversed());
        List<ReviewWithReport> sorted = rows.stream()
                .sorted(comparator)
                .toList();

        long totalItems = sorted.size();
        int totalPages = (int) ((totalItems + size - 1) / size);
        long fromIndexLong = (long) (page - 1) * size;
        List<ReviewStatisticsReviewItem> items;
        if (fromIndexLong >= sorted.size()) {
            items = List.of();
        } else {
            int fromIndex = (int) fromIndexLong;
            int toIndex = Math.min(fromIndex + size, sorted.size());
            items = sorted.subList(fromIndex, toIndex).stream()
                    .map(ReviewWithReport::item)
                    .toList();
        }
        return new ReviewPageResponse<>(items, page, size, totalItems,
                totalPages, page < totalPages);
    }

    private EffectiveRange resolveRange(ReviewHistoryFilter filter) {
        LocalDate today = LocalDate.now(clock);
        LocalDateTime from = filter.createdFrom();
        LocalDateTime to = filter.createdTo();

        if (from == null && to == null) {
            from = today.minusDays(DEFAULT_RANGE_DAYS - 1L).atStartOfDay();
            to = today.atTime(END_OF_DAY);
        } else if (from == null) {
            from = to.toLocalDate()
                    .minusDays(DEFAULT_RANGE_DAYS - 1L)
                    .atStartOfDay();
        } else if (to == null) {
            to = today.atTime(END_OF_DAY);
        }

        if (from.isAfter(to)) {
            throw new InvalidReviewHistoryFilterException(
                    "createdFrom must not be after createdTo");
        }
        long calendarDays = ChronoUnit.DAYS.between(
                from.toLocalDate(), to.toLocalDate()) + 1;
        if (calendarDays > MAX_RANGE_DAYS) {
            throw new InvalidStatisticsRangeException(
                    "Statistics range must not exceed "
                            + MAX_RANGE_DAYS + " calendar days");
        }
        return new EffectiveRange(from, to);
    }

    private Snapshot loadSnapshot(ReviewHistoryFilter filter,
                                  EffectiveRange range) {
        List<ReportStatisticsRow> reports =
                repository.findReportStatistics(
                        filter.owner(), filter.repo(), filter.prNumber(),
                        filter.taskStatus() == null
                                ? null : filter.taskStatus().name(),
                        filter.publishStatus() == null
                                ? null : filter.publishStatus().name(),
                        filter.aiStatus(),
                        range.from(), range.to());

        for (ReportStatisticsRow report : reports) {
            if (report.getTaskId() == null
                    || report.getOwner() == null
                    || report.getRepo() == null
                    || report.getPrNumber() == null
                    || report.getCommitSha() == null
                    || report.getTaskStatus() == null
                    || report.getCreatedAt() == null
                    || report.getAiStatus() == null
                    || report.getPublishStatus() == null) {
                throw new ReviewHistoryDataIntegrityException(
                        "Missing review_task for report id="
                                + report.getReportId());
            }
        }

        if (reports.isEmpty()) {
            return new Snapshot(List.of(), Map.of());
        }

        List<FindingAggregateRow> aggregateRows =
                repository.findFindingAggregates(
                        filter.owner(), filter.repo(), filter.prNumber(),
                        filter.taskStatus() == null
                                ? null : filter.taskStatus().name(),
                        filter.publishStatus() == null
                                ? null : filter.publishStatus().name(),
                        filter.aiStatus(),
                        range.from(), range.to());

        Map<Long, FindingAggregateRow> aggregates = new LinkedHashMap<>();
        for (FindingAggregateRow row : aggregateRows) {
            if (aggregates.put(row.getReportId(), row) != null) {
                throw new ReviewHistoryDataIntegrityException(
                        "Duplicate finding aggregate for report id="
                                + row.getReportId());
            }
        }

        Map<Long, ReportStatisticsRow> byId = new LinkedHashMap<>();
        for (ReportStatisticsRow report : reports) {
            byId.put(report.getReportId(), report);
        }
        for (FindingAggregateRow aggregate : aggregateRows) {
            if (!byId.containsKey(aggregate.getReportId())) {
                throw new ReviewHistoryDataIntegrityException(
                        "Finding aggregate without report id="
                                + aggregate.getReportId());
            }
        }
        for (ReportStatisticsRow report : reports) {
            long actual = count(report.getActualFindingCount());
            FindingAggregateRow aggregate =
                    aggregates.get(report.getReportId());
            long aggregated = aggregate == null
                    ? 0L : count(aggregate.getActualFindingCount());
            if (actual != aggregated) {
                throw new ReviewHistoryDataIntegrityException(
                        "Inconsistent finding rows for report id="
                                + report.getReportId()
                                + " actual=" + actual
                                + " aggregated=" + aggregated);
            }
        }
        return new Snapshot(List.copyOf(reports), Map.copyOf(aggregates));
    }

    private ReviewStatisticsSummary buildSummary(Snapshot snapshot) {
        List<ReportStatisticsRow> reports = snapshot.reports();
        List<ReportStatisticsRow> findingReports = reports.stream()
                .filter(ReviewStatisticsService::findingsConsistent)
                .toList();
        List<ReportStatisticsRow> commentReports = reports.stream()
                .filter(ReviewStatisticsService::commentsConsistent)
                .toList();

        long findingCount = findingReports.stream()
                .mapToLong(report -> count(report.getActualFindingCount()))
                .sum();
        long publishedInlineCommentCount = commentReports.stream()
                .mapToLong(report -> count(report.getActualCommentCount()))
                .sum();

        Map<String, Long> categoryCounts = emptyCounts(CATEGORY_KEYS);
        Map<String, Long> severityCounts = emptyCounts(SEVERITY_KEYS);
        accumulateFindingCounts(snapshot, findingReports,
                categoryCounts, severityCounts);

        Map<String, Long> publishStatusCounts =
                emptyCounts(PUBLISH_STATUS_KEYS);
        Map<String, Long> aiStatusCounts = emptyCounts(AI_STATUS_KEYS);
        for (ReportStatisticsRow report : reports) {
            incrementKnownOrUnknown(publishStatusCounts,
                    report.getPublishStatus(), KNOWN_PUBLISH_STATUSES);
            incrementKnownOrUnknown(aiStatusCounts,
                    report.getAiStatus(), KNOWN_AI_STATUSES);
        }

        long reviewsWithFindings = findingReports.stream()
                .filter(report -> count(report.getActualFindingCount()) > 0)
                .count();
        long highSeverityFindingCount =
                severityCounts.get("CRITICAL") + severityCounts.get("HIGH");
        long reviewsWithInlineComments = commentReports.stream()
                .filter(report -> count(report.getActualCommentCount()) > 0)
                .count();
        long summaryCommentIdPresentCount = reports.stream()
                .filter(report -> count(
                        report.getSummaryCommentIdPresent()) > 0)
                .count();

        return new ReviewStatisticsSummary(
                reports.size(),
                findingReports.size(),
                findingCount,
                ratio(findingCount, findingReports.size()),
                median(findingReports.stream()
                        .map(report -> count(report.getActualFindingCount()))
                        .toList()),
                max(findingReports.stream()
                        .map(report -> count(report.getActualFindingCount()))
                        .toList()),
                reviewsWithFindings,
                ratio(reviewsWithFindings, findingReports.size()),
                highSeverityFindingCount,
                ratio(highSeverityFindingCount, findingCount),
                commentReports.size(),
                publishedInlineCommentCount,
                reviewsWithInlineComments,
                ratio(reviewsWithInlineComments, commentReports.size()),
                summaryCommentIdPresentCount,
                toCounts(categoryCounts),
                toCounts(severityCounts),
                toCounts(publishStatusCounts),
                toCounts(aiStatusCounts));
    }

    private void accumulateFindingCounts(
            Snapshot snapshot, List<ReportStatisticsRow> findingReports,
            Map<String, Long> categoryCounts,
            Map<String, Long> severityCounts) {
        for (ReportStatisticsRow report : findingReports) {
            FindingAggregateRow aggregate =
                    snapshot.aggregates().get(report.getReportId());
            if (aggregate == null) {
                continue;
            }
            categoryCounts.merge("BUG",
                    count(aggregate.getBugCount()), Long::sum);
            categoryCounts.merge("SECURITY",
                    count(aggregate.getSecurityCount()), Long::sum);
            categoryCounts.merge("PERFORMANCE",
                    count(aggregate.getPerformanceCount()), Long::sum);
            categoryCounts.merge("QUALITY",
                    count(aggregate.getQualityCount()), Long::sum);
            categoryCounts.merge("UNKNOWN",
                    count(aggregate.getUnknownCategoryCount()), Long::sum);

            severityCounts.merge("CRITICAL",
                    count(aggregate.getCriticalCount()), Long::sum);
            severityCounts.merge("HIGH",
                    count(aggregate.getHighCount()), Long::sum);
            severityCounts.merge("MEDIUM",
                    count(aggregate.getMediumCount()), Long::sum);
            severityCounts.merge("LOW",
                    count(aggregate.getLowCount()), Long::sum);
            severityCounts.merge("INFO",
                    count(aggregate.getInfoCount()), Long::sum);
            severityCounts.merge("UNKNOWN",
                    count(aggregate.getUnknownSeverityCount()), Long::sum);
        }
    }

    private ReviewStatisticsTrend buildTrend(
            Snapshot snapshot, EffectiveRange range,
            StatisticsGranularity granularity) {
        if (snapshot.reports().isEmpty()) {
            return new ReviewStatisticsTrend(granularity, false, List.of());
        }

        Map<LocalDate, TrendBucket> buckets = new LinkedHashMap<>();
        LocalDate fromDate = range.from().toLocalDate();
        LocalDate toDate = range.to().toLocalDate();
        if (granularity == StatisticsGranularity.DAY) {
            for (LocalDate date = fromDate; !date.isAfter(toDate);
                 date = date.plusDays(1)) {
                buckets.put(date, new TrendBucket(date, date));
            }
        } else {
            LocalDate firstWeek = fromDate.with(
                    TemporalAdjusters.previousOrSame(DayOfWeek.MONDAY));
            LocalDate lastWeek = toDate.with(
                    TemporalAdjusters.previousOrSame(DayOfWeek.MONDAY));
            for (LocalDate week = firstWeek; !week.isAfter(lastWeek);
                 week = week.plusWeeks(1)) {
                buckets.put(week, new TrendBucket(week, week.plusDays(6)));
            }
        }

        for (ReportStatisticsRow report : snapshot.reports()) {
            LocalDate date = report.getCreatedAt().toLocalDate();
            LocalDate key = granularity == StatisticsGranularity.DAY
                    ? date
                    : date.with(TemporalAdjusters.previousOrSame(
                            DayOfWeek.MONDAY));
            TrendBucket bucket = buckets.get(key);
            if (bucket == null) {
                throw new ReviewHistoryDataIntegrityException(
                        "Report id=" + report.getReportId()
                                + " is outside the trend buckets");
            }
            bucket.reviewCount++;
            if (findingsConsistent(report)) {
                BucketCounts counts = findingCounts(snapshot, report);
                bucket.findingCount += counts.findingCount();
                bucket.highSeverityFindingCount +=
                        counts.highSeverityFindingCount();
                bucket.bugCount += counts.bugCount();
                bucket.securityCount += counts.securityCount();
                bucket.performanceCount += counts.performanceCount();
                bucket.qualityCount += counts.qualityCount();
                bucket.unknownCategoryCount +=
                        counts.unknownCategoryCount();
            }
        }

        List<ReviewStatisticsTrendPoint> points =
                buckets.values().stream()
                        .map(bucket -> new ReviewStatisticsTrendPoint(
                                bucket.start, bucket.end,
                                bucket.reviewCount, bucket.findingCount,
                                bucket.highSeverityFindingCount,
                                bucket.bugCount, bucket.securityCount,
                                bucket.performanceCount, bucket.qualityCount,
                                bucket.unknownCategoryCount))
                        .toList();
        return new ReviewStatisticsTrend(granularity, true, points);
    }

    private ReviewStatisticsDataQuality buildDataQuality(Snapshot snapshot) {
        List<ReportStatisticsRow> reports = snapshot.reports();
        List<ReportStatisticsRow> findingReports = reports.stream()
                .filter(ReviewStatisticsService::findingsConsistent)
                .toList();
        List<ReportStatisticsRow> commentReports = reports.stream()
                .filter(ReviewStatisticsService::commentsConsistent)
                .toList();

        Map<String, Long> categoryCounts = emptyCounts(CATEGORY_KEYS);
        Map<String, Long> severityCounts = emptyCounts(SEVERITY_KEYS);
        accumulateFindingCounts(snapshot, findingReports,
                categoryCounts, severityCounts);

        long unknownAiStatusReportCount = reports.stream()
                .filter(report -> !KNOWN_AI_STATUSES.contains(
                        report.getAiStatus()))
                .count();
        long unknownPublishStatusReportCount = reports.stream()
                .filter(report -> !KNOWN_PUBLISH_STATUSES.contains(
                        report.getPublishStatus()))
                .count();

        long totalReportCount = reports.size();
        long findingsConsistentReportCount = findingReports.size();
        long commentsConsistentReportCount = commentReports.size();
        return new ReviewStatisticsDataQuality(
                totalReportCount,
                findingsConsistentReportCount,
                commentsConsistentReportCount,
                totalReportCount - findingsConsistentReportCount,
                totalReportCount - commentsConsistentReportCount,
                categoryCounts.get("UNKNOWN"),
                severityCounts.get("UNKNOWN"),
                unknownAiStatusReportCount,
                unknownPublishStatusReportCount);
    }

    private static ReviewStatisticsReviewItem toReviewItem(
            ReportStatisticsRow report, FindingAggregateRow aggregate) {
        long actualFindings = count(report.getActualFindingCount());
        long actualComments = count(report.getActualCommentCount());
        long critical = count(aggregate == null
                ? null : aggregate.getCriticalCount());
        long high = count(aggregate == null
                ? null : aggregate.getHighCount());
        return new ReviewStatisticsReviewItem(
                report.getTaskId(),
                report.getOwner(),
                report.getRepo(),
                report.getPrNumber(),
                report.getCommitSha(),
                report.getCreatedAt(),
                report.getTaskStatus(),
                report.getAiStatus(),
                report.getPublishStatus(),
                report.getDeclaredFindingCount(),
                actualFindings,
                actualFindings == count(report.getDeclaredFindingCount()),
                report.getDeclaredCommentCount(),
                actualComments,
                actualComments == count(report.getDeclaredCommentCount()),
                critical,
                high,
                critical + high,
                count(aggregate == null ? null : aggregate.getMediumCount()),
                count(aggregate == null ? null : aggregate.getLowCount()),
                count(aggregate == null ? null : aggregate.getInfoCount()),
                count(aggregate == null
                        ? null : aggregate.getUnknownSeverityCount()),
                count(aggregate == null ? null : aggregate.getBugCount()),
                count(aggregate == null ? null : aggregate.getSecurityCount()),
                count(aggregate == null
                        ? null : aggregate.getPerformanceCount()),
                count(aggregate == null ? null : aggregate.getQualityCount()),
                count(aggregate == null
                        ? null : aggregate.getUnknownCategoryCount()));
    }

    private static BucketCounts findingCounts(
            Snapshot snapshot, ReportStatisticsRow report) {
        FindingAggregateRow aggregate =
                snapshot.aggregates().get(report.getReportId());
        if (aggregate == null) {
            return new BucketCounts(0L, 0L, 0L, 0L, 0L, 0L, 0L);
        }
        return new BucketCounts(
                count(aggregate.getActualFindingCount()),
                count(aggregate.getCriticalCount())
                        + count(aggregate.getHighCount()),
                count(aggregate.getBugCount()),
                count(aggregate.getSecurityCount()),
                count(aggregate.getPerformanceCount()),
                count(aggregate.getQualityCount()),
                count(aggregate.getUnknownCategoryCount()));
    }

    private static Comparator<ReviewWithReport> comparator(SortKey sortKey) {
        return switch (sortKey) {
            case CREATED_AT -> Comparator.comparing(
                    row -> row.item().createdAt(),
                    Comparator.nullsLast(Comparator.naturalOrder()));
            case ACTUAL_FINDING_COUNT -> Comparator.comparingLong(
                    row -> row.item().actualFindingCount());
            case HIGH_SEVERITY_FINDING_COUNT -> Comparator.comparingLong(
                    row -> row.item().highSeverityFindingCount());
            case ACTUAL_COMMENT_COUNT -> Comparator.comparingLong(
                    row -> row.item().actualCommentCount());
        };
    }

    private static SortKey parseSort(String sort) {
        if (sort == null || sort.isBlank()) {
            return SortKey.CREATED_AT;
        }
        String normalized = sort.trim();
        for (SortKey key : SortKey.values()) {
            if (key.apiName.equals(normalized)) {
                return key;
            }
        }
        throw new InvalidStatisticsSortException(
                "sort must be createdAt, actualFindingCount, "
                        + "highSeverityFindingCount or actualCommentCount");
    }

    private static boolean parseAscending(String direction) {
        if (direction == null || direction.isBlank()) {
            return false;
        }
        String normalized = direction.trim().toLowerCase(Locale.ROOT);
        if ("asc".equals(normalized)) {
            return true;
        }
        if ("desc".equals(normalized)) {
            return false;
        }
        throw new InvalidStatisticsSortException(
                "direction must be asc or desc");
    }

    private static void validatePagination(int page, int size) {
        if (page < 1 || size < 1 || size > MAX_PAGE_SIZE) {
            throw new InvalidReviewHistoryPaginationException(
                    "page must be >= 1 and size must be between 1 and "
                            + MAX_PAGE_SIZE);
        }
    }

    private static boolean findingsConsistent(ReportStatisticsRow report) {
        return count(report.getActualFindingCount())
                == count(report.getDeclaredFindingCount());
    }

    private static boolean commentsConsistent(ReportStatisticsRow report) {
        return count(report.getActualCommentCount())
                == count(report.getDeclaredCommentCount());
    }

    private static long count(Number value) {
        return value == null ? 0L : value.longValue();
    }

    private static Double ratio(long numerator, long denominator) {
        return denominator == 0
                ? null : (double) numerator / denominator;
    }

    private static Double median(List<Long> values) {
        if (values.isEmpty()) {
            return null;
        }
        List<Long> sorted = new ArrayList<>(values);
        sorted.sort(Comparator.naturalOrder());
        int middle = sorted.size() / 2;
        if (sorted.size() % 2 == 1) {
            return (double) sorted.get(middle);
        }
        return (sorted.get(middle - 1) + sorted.get(middle)) / 2.0;
    }

    private static Long max(List<Long> values) {
        return values.stream().max(Comparator.naturalOrder()).orElse(null);
    }

    private static Map<String, Long> emptyCounts(List<String> keys) {
        Map<String, Long> counts = new LinkedHashMap<>();
        for (String key : keys) {
            counts.put(key, 0L);
        }
        return counts;
    }

    private static void incrementKnownOrUnknown(Map<String, Long> counts,
                                                String value,
                                                Set<String> knownKeys) {
        String key = knownKeys.contains(value) ? value : "UNKNOWN";
        counts.merge(key, 1L, Long::sum);
    }

    private static List<ReviewStatisticsCount> toCounts(
            Map<String, Long> counts) {
        return counts.entrySet().stream()
                .map(entry -> new ReviewStatisticsCount(
                        entry.getKey(), entry.getValue()))
                .toList();
    }

    private enum SortKey {
        CREATED_AT("createdAt"),
        ACTUAL_FINDING_COUNT("actualFindingCount"),
        HIGH_SEVERITY_FINDING_COUNT("highSeverityFindingCount"),
        ACTUAL_COMMENT_COUNT("actualCommentCount");

        private final String apiName;

        SortKey(String apiName) {
            this.apiName = apiName;
        }
    }

    private record EffectiveRange(LocalDateTime from, LocalDateTime to) {
    }

    private record Snapshot(List<ReportStatisticsRow> reports,
                            Map<Long, FindingAggregateRow> aggregates) {
    }

    private static final class TrendBucket {
        private final LocalDate start;
        private final LocalDate end;
        private long reviewCount;
        private long findingCount;
        private long highSeverityFindingCount;
        private long bugCount;
        private long securityCount;
        private long performanceCount;
        private long qualityCount;
        private long unknownCategoryCount;

        private TrendBucket(LocalDate start, LocalDate end) {
            this.start = start;
            this.end = end;
        }
    }

    private record ReviewWithReport(long reportId,
                                    ReviewStatisticsReviewItem item) {
    }

    private record BucketCounts(long findingCount,
                                long highSeverityFindingCount,
                                long bugCount,
                                long securityCount,
                                long performanceCount,
                                long qualityCount,
                                long unknownCategoryCount) {
    }
}
