package com.dkt.beqtda.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

import java.util.List;

@Data
public class RagResponse {
    private String answer;
    private List<String> sources;
    @JsonProperty("time_taken")
    private String timeTaken;
}
