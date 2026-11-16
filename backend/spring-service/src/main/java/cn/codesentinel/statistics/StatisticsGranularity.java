package cn.codesentinel.statistics;

import java.util.Locale;

/**
 * Supported trend bucket granularities (Phase 11.2.4-B1).
 */
public enum StatisticsGranularity {
    DAY,
    WEEK;

    public static StatisticsGranularity parse(String value) {
        if (value == null || value.isBlank()) {
            return DAY;
        }
        try {
            return valueOf(value.trim().toUpperCase(Locale.ROOT));
        } catch (IllegalArgumentException error) {
            throw new InvalidStatisticsGranularityException(
                    "granularity must be DAY or WEEK");
        }
    }
}
