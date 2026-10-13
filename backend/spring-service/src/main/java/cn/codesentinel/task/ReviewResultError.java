package cn.codesentinel.task;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Small error body of the result reception endpoint. It carries a safe,
 * field-level message only: never payload values, finding content or
 * secrets.
 */
public record ReviewResultError(@JsonProperty("error") String error) {
}