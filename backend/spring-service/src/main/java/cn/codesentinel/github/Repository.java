package cn.codesentinel.github;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

@JsonIgnoreProperties(ignoreUnknown = true)
public record Repository(
        @JsonProperty("id") Long id,
        @JsonProperty("full_name") String fullName,
        @JsonProperty("name") String name) {
}