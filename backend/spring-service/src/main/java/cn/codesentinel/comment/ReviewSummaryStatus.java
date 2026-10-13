package cn.codesentinel.comment;

import java.util.List;

/**
 * Minimal summary-only review status view.
 *
 * <p>{@code degraded} mirrors the review result's degraded flag: a
 * degraded review was not completed in full, and the summary must say so
 * instead of implying a complete result. {@code notes} carries the
 * optional short, safe explanations recorded by the review report (for
 * example the PR context unavailability reason); null entries and blank
 * strings are ignored by the builder.
 *
 * <p>This is not a transport DTO: the cross-language result contract
 * does not exist on the Java side yet, and no transport DTO is defined
 * here.
 */
public record ReviewSummaryStatus(boolean degraded, List<String> notes) {
}