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

# --- 1. CẤU HÌNH ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# --- CHỌN MODEL (Đã đổi sang Llama 3 để tránh lỗi 429) ---
# Nếu Llama 3 lỗi, bạn có thể thử: "microsoft/phi-3-medium-128k-instruct:free"
OPENROUTER_MODEL = "google/gemini-2.5-flash-lite"

resources = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # A. Elasticsearch
    es_host = os.getenv("ES_HOST", "http://localhost:9200")
    es_client = Elasticsearch(es_host)
    if es_client.ping():
        logging.info(f"✅ Connected to Elasticsearch at {es_host}")
    else:
        logging.error(f"❌ Failed to connect to Elasticsearch at {es_host}")

    # B. Embedding Model
    # LƯU Ý: Phải đúng với model trong file etl_snake.py (kiểm tra lại file đó dùng model gì)
    # Nếu etl dùng 'paraphrase-multilingual...', hãy sửa dòng dưới đây.
    model_name = 'paraphrase-multilingual-MiniLM-L12-v2' # Hoặc 'all-MiniLM-L6-v2'
    logging.info(f"⏳ Loading Embedding Model ({model_name})...")
    embed_model = SentenceTransformer(model_name)
    logging.info("✅ Embedding Model Loaded!")

    # C. OpenRouter LLM
    api_key = os.getenv("OPENROUTER_API_KEY")
    
    llm = ChatOpenAI(
        openai_api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        model=OPENROUTER_MODEL, 
        temperature=0,
        default_headers={
            "HTTP-Referer": os.getenv("YOUR_SITE_URL", "http://localhost:3000"),
            "X-Title": os.getenv("YOUR_SITE_NAME", "SnakeRAG"),
        },
        max_retries=1 # Chỉ thử lại 1 lần nếu lỗi để tránh treo lâu
    )

    # Chain 1: Dịch
    translate_prompt = ChatPromptTemplate.from_template("""
    You are a scientific search assistant.
    Task: Translate the following Vietnamese query into an English scientific search query about snakes.
    Keep scientific names if present. Return ONLY the English query.

    Input: "{question}"
    Output:
    """)
    translator_chain = translate_prompt | llm | StrOutputParser()

    # Chain 2: Trả lời
    answer_prompt = ChatPromptTemplate.from_template("""
    Based on the context below, answer the user's question in VIETNAMESE.
    If the context implies the snake is dangerous, emphasize it.
    
    [CONTEXT]:
    {context}

    [QUESTION]:
    {question}
    """)
    llm_chain = answer_prompt | llm | StrOutputParser()
    
    resources["es"] = es_client
    resources["embed"] = embed_model
    resources["translator"] = translator_chain
    resources["llm"] = llm_chain
    
    yield
    resources.clear()

app = FastAPI(title="Snake RAG API", lifespan=lifespan)

class QueryRequest(BaseModel):
    question: str

@app.post("/api/ask-snake")
async def ask_snake_endpoint(request: QueryRequest):
    start_time = time.time()
    user_question = request.question.strip()
    
    es_client = resources.get("es")
    embed_model = resources.get("embed")
    translator = resources.get("translator")
    llm_qa = resources.get("llm")

    # --- 1. DỊCH (Kèm bắt lỗi) ---
    english_query = user_question
    try:
        # Gọi AI dịch
        english_query = translator.invoke({"question": user_question})
        logging.info(f"Translated: {english_query}")
    except Exception as e:
        logging.error(f"Translation API Error (Rate Limit?): {e}")
        # Nếu lỗi dịch (do hết tiền/quá tải), dùng luôn tiếng Việt để tìm kiếm
        # Không raise lỗi để app vẫn chạy tiếp
        english_query = user_question

    # --- 2. EMBEDDING ---
    try:
        query_vector = embed_model.encode(english_query).tolist()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding Error: {str(e)}")

    # --- 3. SEARCH ES ---
    try:
        search_body = {
            "size": 3,
            "query": {
                "script_score": {
                    "query": {"match_all": {}},
                    "script": {
                        "source": "cosineSimilarity(params.query_vector, 'vector_embedding') + 1.0",
                        "params": {"query_vector": query_vector}
                    }
                }
            },
            "_source": ["scientific_name", "common_names", "full_text_context"]
        }
        response = es_client.search(index="snakes", body=search_body)
        hits = response['hits']['hits']
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")

    # --- 4. LỌC KẾT QUẢ ---
    context_text = ""
    sources = []
    
    for hit in hits:
        score = hit['_score']
        source = hit['_source']
        
        # Hạ ngưỡng xuống 1.1 cho an toàn
        if score > 1.1:
            context_text += f"Species: {source.get('scientific_name')}. Info: {source.get('full_text_context')}\n\n"
            sources.append(source.get('scientific_name'))

    if not context_text:
        return {
            "answer": "Xin lỗi, tôi không tìm thấy thông tin phù hợp trong cơ sở dữ liệu.",
            "sources": [],
            "time_taken": f"{time.time() - start_time:.2f}s"
        }

    # --- 5. TRẢ LỜI (Kèm bắt lỗi) ---
    try:
        answer = llm_qa.invoke({
            "context": context_text,
            "question": user_question
        })
    except Exception as e:
        logging.error(f"LLM Generation Error: {e}")
        # Trả về lỗi đẹp thay vì sập server 500
        return {
            "answer": "Hệ thống AI đang bị quá tải (Rate Limited). Dưới đây là thông tin thô tìm được từ Database:\n\n" + context_text,
            "sources": sources,
            "time_taken": f"{time.time() - start_time:.2f}s",
            "error_note": "AI Provider Overloaded"
        }

    return {
        "answer": answer,
        "sources": list(set(sources)),
        "time_taken": f"{time.time() - start_time:.2f}s"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)