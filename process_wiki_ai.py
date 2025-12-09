import os
import pymongo
from tqdm import tqdm
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL_NAME = "google/gemini-2.5-flash-lite" 

client = pymongo.MongoClient(MONGO_URI)
db = client["snake_raw_data"]
col_raw = db["wiki_articles"]
col_clean = db["wiki_cleaned"]

# --- [CẬP NHẬT] THÊM TRƯỜNG vietnamese_name ---
class SnakeDataClean(BaseModel):
    vietnamese_name: str = Field(description="Tên thường gọi chính xác bằng Tiếng Việt của loài này (VD: Rắn hổ mang chúa). Nếu không có, trả về chuỗi rỗng.")
    biology: str = Field(description="Mô tả hình dáng, màu sắc (Tiếng Việt).")
    venom: str = Field(description="Thông tin nọc độc. Nếu không độc ghi 'Không độc'.")
    behavior: str = Field(description="Tập tính, sinh sản.")
    distribution: str = Field(description="Khu vực phân bố.")

llm = ChatOpenAI(
    openai_api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    model=MODEL_NAME,
    temperature=0
)

parser = JsonOutputParser(pydantic_object=SnakeDataClean)

prompt = ChatPromptTemplate.from_template("""
Bạn là chuyên gia sinh học. Đọc văn bản và trích xuất thông tin JSON.
Quan trọng: Hãy tìm tên gọi phổ biến nhất bằng Tiếng Việt của loài này trong văn bản.

VĂN BẢN:
{text}

JSON OUTPUT:
{format_instructions}
""")

chain = prompt | llm | parser

def run_ai_processing():
    # Lấy các bài chưa xử lý AI (hoặc bạn có thể xóa col_clean đi chạy lại từ đầu)
    query = {"processed": False, "found": {"$ne": False}}
    total = col_raw.count_documents(query)
    cursor = col_raw.find(query)
    
    print(f"🤖 Bắt đầu trích xuất tên Tiếng Việt cho {total} loài...")

    for doc in tqdm(cursor, total=total):
        try:
            raw_text = f"Summary: {doc.get('summary', '')}\n"
            # Thêm title vào text để AI dễ bắt tên
            raw_text += f"Title from URL: {doc.get('url', '')}\n" 
            
            cleaned_data = chain.invoke({
                "text": raw_text[:6000],
                "format_instructions": parser.get_format_instructions()
            })

            col_clean.update_one(
                {"scientific_name": doc['scientific_name']},
                {"$set": {
                    "scientific_name": doc['scientific_name'],
                    "ai_data": cleaned_data,
                    "original_url": doc.get('url')
                }},
                upsert=True
            )
            col_raw.update_one({"_id": doc["_id"]}, {"$set": {"processed": True}})

        except Exception as e:
            print(f"⚠️ Lỗi: {doc['scientific_name']} - {e}")

if __name__ == "__main__":
    run_ai_processing()