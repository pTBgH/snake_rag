package com.dkt.beqtda.service;

import com.dkt.beqtda.dto.RagResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.HashMap;
import java.util.Map;

@Service
public class RagService {

    private final RestTemplate restTemplate;

    // Lấy URL từ file application.properties
    @Value("${rag.fastapi.url}")
    private String fastApiUrl;

    public RagService(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }

    public RagResponse getAnswerFromRAG(String userQuery) {
        // 1. Chuẩn bị dữ liệu gửi sang Python
        // Python FastAPI đang đợi JSON dạng: {"query": "Nội dung câu hỏi"}
        Map<String, String> requestBody = new HashMap<>();
        requestBody.put("question", userQuery);;

        try {
            // 2. Gọi POST request sang FastAPI
            ResponseEntity<RagResponse> response = restTemplate.postForEntity(
                    fastApiUrl,
                    requestBody,
                    RagResponse.class
            );

            // 3. Trả về body kết quả
            return response.getBody();

        } catch (Exception e) {
            // Xử lý lỗi nếu Python service chết hoặc lỗi mạng
            RagResponse errorResponse = new RagResponse();
            errorResponse.setAnswer("Hệ thống đang bận, vui lòng thử lại sau. (Lỗi kết nối RAG Core)");
            return errorResponse;
        }
    }
}
