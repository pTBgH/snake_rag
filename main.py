import os
import time
import logging
import secrets
import re
import asyncio
import hashlib
from typing import Optional, Dict

# --- [FIXED] DÒNG NÀY RẤT QUAN TRỌNG ---
from contextlib import asynccontextmanager 

from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security.api_key import APIKeyHeader
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_fixed

from elasticsearch import AsyncElasticsearch
from sentence_transformers import SentenceTransformer
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("snake_rag")

# --- CONFIG ---
ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = "google/gemini-2.5-flash-lite"
EMBEDDING_MODEL = "BAAI/bge-m3"
API_KEY_VAL = os.getenv("APP_API_KEY", "secret-snake-key")

# --- CACHE ---
PARSE_CACHE = {} 
EMBED_CACHE = {}

# --- 1. HYBRID PARSER ---
class SearchFilters(BaseModel):
    must_country: Optional[str] = None
    must_not_country: Optional[str] = None
    danger_level: Optional[str] = None
    intent_type: str = "detail"
    limit: int = 5

class HybridParser:
    def __init__(self, llm):
        self.llm_parser = JsonOutputParser(pydantic_object=SearchFilters)
        self.llm_chain = (
            ChatPromptTemplate.from_template("""
            Phân tích query tìm rắn sang JSON.
            Quy tắc: 
            - Quốc gia chuẩn tiếng Anh (Vietnam, Laos). 
            - Độc: Venomous/Non-venomous.
            - Nếu user hỏi "kể về", "chi tiết", "là con gì" -> intent_type="detail".
            
            Query: {query}
            JSON: {format_instructions}
            """) 
            | llm 
            | self.llm_parser
        )
        
        self.re_vietnam = re.compile(r'\b(viet\s*nam|vn|nuoc\s*ta)\b', re.IGNORECASE)
        self.re_listing = re.compile(r'\b(liet\s*ke|danh\s*sach|top|nhung\s*loai|cac\s*loai)\b', re.IGNORECASE)
        self.re_venom = re.compile(r'\b(doc|noc|nguy\s*hiem|chet\s*nguoi)\b', re.IGNORECASE)
        self.re_safe = re.compile(r'\b(lanh|khong\s*doc|vo\s*hai)\b', re.IGNORECASE)
        self.re_negation = re.compile(r'\b(khong|chua|tranh|tru)\b', re.IGNORECASE)

    async def parse(self, query: str) -> dict:
        q_hash = hashlib.md5(query.encode()).hexdigest()
        if q_hash in PARSE_CACHE: return PARSE_CACHE[q_hash]

        # Fast Path (Regex)
        if not self.re_negation.search(query):
            intent = {"intent_type": "detail", "limit": 5, "must_country": None, "must_not_country": None, "danger_level": None}
            if self.re_listing.search(query):
                intent["intent_type"] = "listing"
                intent["limit"] = 10
            if self.re_vietnam.search(query):
                intent["must_country"] = "Vietnam"
            if self.re_safe.search(query):
                intent["danger_level"] = "Non-venomous"
            elif self.re_venom.search(query):
                intent["danger_level"] = "Venomous"
            
            PARSE_CACHE[q_hash] = intent
            return intent

        # Slow Path (LLM)
        try:
            res = await self.llm_chain.ainvoke({"query": query, "format_instructions": self.llm_parser.get_format_instructions()})
            PARSE_CACHE[q_hash] = res
            return res
        except:
            return {"intent_type": "detail", "limit": 5}

# --- 2. SETUP ---
resources = {}
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(key: str = Security(api_key_header)):
    if key and secrets.compare_digest(key, API_KEY_VAL): return key
    return "dev_mode"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ES Client
    es = AsyncElasticsearch(ES_HOST, verify_certs=False, ssl_show_warn=False, request_timeout=5)
    
    logger.info("⏳ Loading Embed Model...")
    embed_model = SentenceTransformer(EMBEDDING_MODEL)
    
    llm = ChatOpenAI(
        openai_api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
        model=OPENROUTER_MODEL,
        temperature=0.3
    )
    
    # Prompt Tóm tắt thông minh
    summarizer_prompt = ChatPromptTemplate.from_template("""
    Bạn là chuyên gia bò sát học. Dựa vào dữ liệu sau về loài rắn:
    {context}
    
    Câu hỏi của người dùng: "{question}"
    
    NHIỆM VỤ:
    - Hãy viết một câu trả lời tự nhiên, hấp dẫn (khoảng 3-4 câu).
    - Kết hợp thông tin về hình dáng, nơi sống và độ độc.
    - Nếu dữ liệu phân bố (country) bị thiếu, đừng nhắc đến nó.
    - Nếu rắn có độc, hãy cảnh báo.
    """)
    
    resources["es"] = es
    resources["embed"] = embed_model
    resources["parser"] = HybridParser(llm)
    resources["summarizer"] = summarizer_prompt | llm | StrOutputParser()
    
    logger.info("✅ Ready!")
    yield
    await es.close()
    resources.clear()

app = FastAPI(title="Snake RAG Smart", lifespan=lifespan)

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=500)

@app.post("/api/ask-snake", dependencies=[Depends(verify_api_key)])
async def ask_snake(req: QueryRequest):
    start = time.time()
    
    # 1. Parse
    intent = await resources["parser"].parse(req.question)
    
    # 2. Embed
    q_hash = hashlib.md5(req.question.encode()).hexdigest()
    if q_hash in EMBED_CACHE:
        query_vector = EMBED_CACHE[q_hash]
    else:
        query_vector = await run_in_threadpool(resources["embed"].encode, req.question)
        query_vector = query_vector.tolist()
        EMBED_CACHE[q_hash] = query_vector

    # 3. Query ES
    must, must_not = [], []
    if intent.get("must_country"): must.append({"match": {"countries": intent["must_country"]}})
    if intent.get("must_not_country"): must_not.append({"match": {"countries": intent["must_not_country"]}})
    if intent.get("danger_level"): must.append({"term": {"danger_level": intent["danger_level"]}})
    
    limit = min(intent.get("limit", 5), 50)
    
    es_query = {
        "size": limit,
        "_source": ["scientific_name", "vietnamese_name", "family", "danger_level", "countries", "wiki_biology", "wiki_venom"],
        "knn": {
            "field": "vector_embedding",
            "query_vector": query_vector,
            "k": limit,
            "num_candidates": 100,
            "filter": {"bool": {"must": must, "must_not": must_not}}
        },
        "query": {
            "bool": {
                "should": [
                    {"multi_match": {"query": req.question, "fields": ["vietnamese_name^4", "scientific_name^2", "common_names"], "type": "phrase"}},
                    {"multi_match": {"query": req.question, "fields": ["vietnamese_name", "scientific_name"], "type": "best_fields"}}
                ],
                "filter": {"bool": {"must": must, "must_not": must_not}}
            }
        }
    }

    try:
        res = await resources["es"].search(index="snakes", body=es_query)
        hits = res['hits']['hits']
    except Exception as e:
        return {"error": str(e)}

    # 4. Process Data & Context
    data = []
    context_text = ""
    
    for i, hit in enumerate(hits):
        src = hit['_source']
        vn_name = src.get("vietnamese_name") or src.get("scientific_name")
        
        item = {
            "name": vn_name,
            "sci_name": src.get("scientific_name"),
            "danger": src.get("danger_level"),
            "country": src.get("countries"),
            "details": str(src.get("wiki_biology", ""))[:300] + "..."
        }
        data.append(item)
        
        if i < 3: 
            context_text += f"""
            - Loài: {vn_name} ({src.get('scientific_name')})
            - Họ: {src.get('family')}
            - Độc tính: {src.get('danger_level')}
            - Phân bố: {src.get('countries')}
            - Đặc điểm: {src.get('wiki_biology', '')}
            - Nọc độc: {src.get('wiki_venom', '')}
            ----------------
            """

    # 5. Smart Response Logic
    if not hits:
        answer = "Xin lỗi, tôi không tìm thấy thông tin về loài rắn này trong cơ sở dữ liệu."
    
    elif intent["intent_type"] == "listing" and len(hits) > 1:
        answer = f"Tìm thấy {len(hits)} loài rắn phù hợp với yêu cầu của bạn. Xem chi tiết trong danh sách bên dưới."
        
    else:
        # Dùng AI Summarizer
        try:
            answer = await resources["summarizer"].ainvoke({
                "context": context_text,
                "question": req.question
            })
        except Exception as e:
            top = data[0]
            answer = f"Kết quả: {top['name']} ({top['sci_name']}). {top['details']}"

    return {
        "answer": answer,
        "data": data,
        "meta": {"intent": intent, "latency": f"{time.time() - start:.3f}s"}
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)