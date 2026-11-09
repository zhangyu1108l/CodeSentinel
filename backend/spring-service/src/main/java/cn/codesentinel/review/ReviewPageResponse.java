package cn.codesentinel.review;

import java.util.List;

/**
 * Stable pagination envelope of the review history API (Phase 10.5).
 * Spring Data's {@code Page} is mapped explicitly so its internal JSON
 * shape is never part of the public contract.
 */
public record ReviewPageResponse<T>(
        List<T> items,
        int page,
        int size,
        long totalItems,
        int totalPages,
        boolean hasNext) {
}