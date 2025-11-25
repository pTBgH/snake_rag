package com.dkt.beqtda.dto;

import com.fasterxml.jackson.annotation.JsonProperty; // 1. Import dòng này
import lombok.Data;

@Data
public class UserQueryRequest {

    @JsonProperty("question")
    private String query;
}