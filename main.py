import time
import random
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Snake API (Mock)")

class QueryRequest(BaseModel):
    question: str

@app.post("/api/ask-snake")
async def ask_snake_endpoint(request: QueryRequest):
    # Giả lập thời gian xử lý (delay 1 chút cho giống thật)
    time.sleep(random.uniform(0.5, 1.5))
    
    start_time = time.time()
    user_question = request.question.lower()
    
    # --- LOGIC MÔ PHỎNG ĐỂ TEST FRONTEND ---
    
    # CASE 1: Test trường hợp KHÔNG TÌM THẤY (Gõ từ khóa "unknown" hoặc "không có")
    if "unknown" in user_question or "không có" in user_question:
        return {
            "answer": "Hệ thống không tìm thấy loài rắn nào phù hợp với mô tả của bạn.",
            "sources": [],
            "mode": "no_result",
            "time": f"{time.time() - start_time:.2f}s"
        }

    # CASE 2: Test trường hợp LỖI HỆ THỐNG / FALLBACK (Gõ từ khóa "error" hoặc "lỗi")
    if "error" in user_question or "lỗi" in user_question:
        return {
            "answer": "⚠️ **CẢNH BÁO: LOÀI RẮN NÀY CÓ ĐỘC!**\n\n(Đây là nội dung Fallback khi AI sập, trả về dữ liệu thô).",
            "sources": ["Naja naja"],
            "mode": "fallback_offline",
            "time": f"{time.time() - start_time:.2f}s"
        }

    # CASE 3: MẶC ĐỊNH - Trả về kết quả đẹp (Happy Case)
    mock_answer = """
⚠️ **CẢNH BÁO: LOÀI RẮN NÀY CÓ ĐỘC!**

Dựa trên dữ liệu, đây là thông tin về **Rắn Hổ Mang Chúa**:

- **Tên khoa học**: _Ophiophagus hannah_
- **Họ (Family)**: Elapidae
- **Mức độ nguy hiểm**: Cực kỳ nguy hiểm (Venomous)
- **Kích thước tối đa**: Khoảng 585 cm

**Đặc điểm**:
Rắn hổ mang chúa là loài rắn độc dài nhất thế giới. Chúng có khả năng nâng cao 1/3 cơ thể lên khỏi mặt đất và bạnh cổ khi bị đe dọa.

_(Thông tin từ server giả lập)_
    """
    
    return {
        "answer": mock_answer.strip(),
        "sources": ["Ophiophagus hannah", "Naja naja"],
        "mode": "ai_expert",
        "time": f"{time.time() - start_time:.2f}s"
    }