import os
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

# 1. Cấu hình
es = Elasticsearch(os.getenv("ES_HOST"))
model = SentenceTransformer('all-MiniLM-L6-v2') # Phải dùng đúng model lúc ETL

def search_snake(question):
    print(f"\n--- Đang tìm kiếm cho câu hỏi: '{question}' ---")
    
    # Bước 1: Biến câu hỏi thành Vector
    query_vector = model.encode(question).tolist()
    
    # Bước 2: Gửi query vector lên Elasticsearch
    # Dùng thuật toán Cosine Similarity để tìm vector giống nhất
    query_body = {
        "size": 3, # Lấy 3 kết quả tốt nhất
        "query": {
            "script_score": {
                "query": {"match_all": {}},
                "script": {
                    "source": "cosineSimilarity(params.query_vector, 'vector_embedding') + 1.0",
                    "params": {"query_vector": query_vector}
                }
            }
        }
    }
    
    try:
        response = es.search(index="snakes", body=query_body)
        hits = response['hits']['hits']
        
        if not hits:
            print("Không tìm thấy kết quả nào!")
            return

        for hit in hits:
            score = hit['_score']
            source = hit['_source']
            print(f"[Độ khớp: {score:.4f}] {source['scientific_name']} ({source['common_names']})")
            # print(f"   -> Context: {source['full_text_context'][:100]}...") # In thử 100 ký tự đầu
            
    except Exception as e:
        print(f"Lỗi: {e}")

if __name__ == "__main__":
    # Thử các câu hỏi ngữ nghĩa (Semantic Search)
    # Ví dụ: Bạn không cần gõ chính xác tên rắn, chỉ cần mô tả đặc điểm
    search_snake("Con rắn nào phun được nọc độc?")
    search_snake("Rắn hổ mang chúa sống ở đâu?")
    search_snake("Loài nào to nhất thế giới?")