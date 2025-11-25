package com.dkt.beqtda.controller;

import com.dkt.beqtda.dto.RagResponse;
import com.dkt.beqtda.dto.UserQueryRequest;
import com.dkt.beqtda.service.RagService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api")
// @CrossOrigin: Cho phép Frontend (chạy ở cổng khác, ví dụ 3000) gọi vào
// Khi deploy thật nên đổi "*" thành domain cụ thể
@CrossOrigin(origins = "*")
public class SearchController {

    @Autowired
    private RagService ragService;

    @PostMapping("/search")
    public ResponseEntity<RagResponse> search(@RequestBody UserQueryRequest request) {
        // Kiểm tra đầu vào đơn giản
        if (request.getQuery() == null || request.getQuery().trim().isEmpty()) {
            RagResponse error = new RagResponse();
            error.setAnswer("Vui lòng nhập câu hỏi.");
            return ResponseEntity.badRequest().body(error);
        }

        // Gọi service xử lý
        RagResponse result = ragService.getAnswerFromRAG(request.getQuery());
        return ResponseEntity.ok(result);
    }
}
