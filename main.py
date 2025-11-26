import os
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# --- CẤU HÌNH ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Model LLM (Bạn có thể đổi model khác trên OpenRouter tại đây)
OPENROUTER_MODEL = "google/gemini-2.5-flash-lite"

resources = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Kết nối Elasticsearch
    es_host = os.getenv("ES_HOST", "http://localhost:9200")
    es_client = Elasticsearch(es_host, verify_certs=False, ssl_show_warn=False)
    
    # 2. Load Model Embedding (BẮT BUỘC KHỚP VỚI ETL)
    model_name = 'BAAI/bge-m3'
    logging.info(f"⏳ Đang tải Model Embedding ({model_name})...")
    # Tải model vào RAM khi khởi động app
    embed_model = SentenceTransformer(model_name)
    logging.info("✅ Embedding Model đã sẵn sàng!")

    # 3. Kết nối OpenRouter LLM
    llm = ChatOpenAI(
        openai_api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
        model=OPENROUTER_MODEL, 
        temperature=0.3, # Nhiệt độ thấp để trả lời chính xác, ít bịa
        max_retries=1    # Thử lại 1 lần thôi, không được thì Fallback ngay
    )

    # 4. Prompt Engineering "Khôn ngoan"
    # Dùng BAAI nên không cần bước dịch (Translator), đưa thẳng ngữ cảnh vào Prompt
    answer_prompt = ChatPromptTemplate.from_template("""
    Bạn là một chuyên gia bò sát học (Herpetologist) am hiểu và cẩn thận.
    Nhiệm vụ: Trả lời câu hỏi của người dùng HOÀN TOÀN BẰNG TIẾNG VIỆT.
    
    Dữ liệu tham khảo (Context):
    {context}

    Câu hỏi của người dùng:
    {question}

    YÊU CẦU TRẢ LỜI:
    1. **An toàn là trên hết**: Nếu Context có từ khóa 'venom', 'poison', 'dangerous', hãy bắt đầu câu trả lời bằng: "⚠️ **CẢNH BÁO: LOÀI RẮN NÀY CÓ ĐỘC/NGUY HIỂM!**".
    2. **Cấu trúc rõ ràng**:
       - Tên khoa học & Tên thường gọi.
       - Đặc điểm nhận dạng (Kích thước, màu sắc nếu có).
       - Mức độ nguy hiểm.
       - Nơi sống/Sinh sản (nếu có trong context).
    3. **Dịch thuật ngữ**: Hãy dịch các từ như Family (Họ), Danger Level (Mức độ độc) sang tiếng Việt.
    4. **Trung thực**: Nếu Context không có thông tin, hãy nói "Dữ liệu hiện tại chưa có thông tin chi tiết về vấn đề bạn hỏi."

    Hãy trả lời ngắn gọn, súc tích và chuyên nghiệp.
    """)
    
    llm_chain = answer_prompt | llm | StrOutputParser()
    
    resources["es"] = es_client
    resources["embed"] = embed_model
    resources["llm"] = llm_chain
    
    yield
    # Dọn dẹp tài nguyên khi tắt app
    resources.clear()

app = FastAPI(title="Snake RAG API", lifespan=lifespan)

class QueryRequest(BaseModel):
    question: str

# --- HÀM FALLBACK (QUAN TRỌNG) ---
def format_fallback_response_vn(hits, error_msg=""):
    """
    Hàm này chạy khi LLM bị lỗi (mất mạng, hết tiền, quá tải).
    Nó biến dữ liệu thô từ ES thành câu trả lời Tiếng Việt dễ đọc.
    """
    if not hits:
        return "Xin lỗi, hệ thống không tìm thấy loài rắn nào phù hợp trong cơ sở dữ liệu."
    
    # Header thông báo chế độ Fallback
    response = f"⚠️ **Lưu ý**: {error_msg} Hệ thống đang hiển thị dữ liệu gốc từ kho lưu trữ:\n\n"
    
    for i, hit in enumerate(hits, 1):
        src = hit['_source']
        
        # Xử lý icon cảnh báo dựa trên text
        danger_text = str(src.get('danger_level', '')).lower()
        is_dangerous = any(x in danger_text for x in ['venom', 'danger', 'fatal', 'toxic'])
        icon = "☠️" if is_dangerous else "🟢"
        
        # Dịch sơ bộ một số trường
        family = src.get('family', 'Không rõ')
        size = src.get('max_len_cm')
        size_str = f"{size} cm" if size else "Chưa có dữ liệu"
        
        response += f"**{i}. {src.get('scientific_name')}**\n"
        response += f"   - **Tên gọi khác**: {src.get('common_names')}\n"
        response += f"   - **Họ**: {family}\n"
        response += f"   - **Độ độc**: {icon} {src.get('danger_level')}\n"
        response += f"   - **Kích thước tối đa**: {size_str}\n"
        # Cắt ngắn mô tả để không quá dài
        desc = src.get('full_text_context', '')[:150] + "..."
        response += f"   - **Thông tin gốc**: _{desc}_\n\n"
        
    return response

@app.post("/api/ask-snake")
async def ask_snake_endpoint(request: QueryRequest):
    start_time = time.time()
    user_question = request.question.strip()
    
    es_client = resources.get("es")
    embed_model = resources.get("embed")
    llm_qa = resources.get("llm")

    # BƯỚC 1: EMBEDDING (Vector hóa câu hỏi)
    try:
        # BAAI/bge-m3 xử lý tiếng Việt rất tốt, embed trực tiếp
        query_vector = embed_model.encode(user_question).tolist()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý AI (Embedding): {str(e)}")

    # BƯỚC 2: TÌM KIẾM (Elasticsearch)
    try:
        search_body = {
            "size": 3, # Lấy 3 kết quả tốt nhất
            "query": {
                "script_score": {
                    "query": {"match_all": {}},
                    "script": {
                        # Cộng 1.0 để đảm bảo điểm số luôn dương
                        "source": "cosineSimilarity(params.query_vector, 'vector_embedding') + 1.0",
                        "params": {"query_vector": query_vector}
                    }
                }
            },
            "_source": ["scientific_name", "common_names", "family", "danger_level", "max_len_cm", "full_text_context"]
        }
        response = es_client.search(index="snakes", body=search_body)
        hits = response['hits']['hits']
    except Exception as e:
        # Nếu mất kết nối ES thì chịu, trả lỗi luôn
        raise HTTPException(status_code=500, detail=f"Lỗi kết nối CSDL: {str(e)}")

    # Lọc kết quả rác (ngưỡng score > 1.35 cho BGE-M3 là khá an toàn)
    valid_hits = [hit for hit in hits if hit['_score'] > 1.35]
    
    # Lấy danh sách tên nguồn
    sources = list(set([h['_source']['scientific_name'] for h in valid_hits]))

    if not valid_hits:
        return {
            "answer": "Xin lỗi, tôi không tìm thấy thông tin nào về loài rắn này trong hệ thống.",
            "sources": [],
            "mode": "no_result",
            "time_taken": f"{time.time() - start_time:.2f}s"
        }

    # BƯỚC 3: SINH CÂU TRẢ LỜI (Thử LLM -> Nếu lỗi -> Fallback)
    try:
        # Chuẩn bị context dạng text cho AI đọc
        context_text = "\n\n".join([
            f"Snake {i+1}: {h['_source']['full_text_context']}" 
            for i, h in enumerate(valid_hits)
        ])
        
        # Gọi LLM OpenRouter
        logging.info("🤖 Đang gửi request tới OpenRouter...")
        answer = llm_qa.invoke({
            "context": context_text,
            "question": user_question
        })
        mode = "ai_expert" # Chế độ trả lời thông minh

    except Exception as e:
        logging.error(f"⚠️ LLM Error (OpenRouter/Gemini): {e}")
        # --- KÍCH HOẠT FALLBACK ---
        # Tự động chuyển sang chế độ trả dữ liệu thô
        answer = format_fallback_response_vn(valid_hits, error_msg="Kết nối AI đang gián đoạn.")
        mode = "fallback_offline" # Chế độ dự phòng

    return {
        "answer": answer,
        "sources": sources,
        "mode": mode,
        "time_taken": f"{time.time() - start_time:.2f}s"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)