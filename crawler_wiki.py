import pymongo
import mysql.connector
import wikipediaapi
import time
import os
import logging
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

# Cấu hình Mongo
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
mongo_client = pymongo.MongoClient(MONGO_URI)
db_mongo = mongo_client["snake_raw_data"]
col_wiki = db_mongo["wiki_articles"]

# Cấu hình Wiki
wiki_vi = wikipediaapi.Wikipedia(user_agent='SnakeBot/1.0', language='vi')
wiki_en = wikipediaapi.Wikipedia(user_agent='SnakeBot/1.0', language='en')

# --- HÀM KẾT NỐI MYSQL (CỦA BẠN) ---
def get_mysql_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=os.getenv("MYSQL_PORT", "3306"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DB", "snake_db")
    )

def get_snake_names():
    """Lấy danh sách tên khoa học từ MySQL"""
    names = []
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor()
        logging.info("Fetching species list from MySQL...")
        # Lấy genus và species để ghép lại
        cursor.execute("SELECT DISTINCT genus, species FROM tax__subspecies")
        rows = cursor.fetchall()
        
        for r in rows:
            names.append(f"{r[0]} {r[1]}")
            
        conn.close()
        logging.info(f"Found {len(names)} species in DB.")
        return names
    except Exception as e:
        logging.error(f"❌ Error connecting to MySQL: {e}")
        return []

def run_crawler():
    snakes = get_snake_names()
    if not snakes:
        return

    logging.info(f"🚀 Starting Wiki Crawler for {len(snakes)} species...")

    for name in tqdm(snakes):
        # 1. Kiểm tra xem đã cào chưa (Tránh spam)
        if col_wiki.find_one({"scientific_name": name}):
            continue

        # 2. Thử Wiki Tiếng Việt trước
        page = wiki_vi.page(name)
        lang = 'vi'
        
        # 3. Nếu không có, thử Tiếng Anh
        if not page.exists():
            page = wiki_en.page(name)
            lang = 'en'

        # 4. Lưu dữ liệu
        if page.exists():
            # Lấy text từng mục (sections)
            sections_data = {s.title: s.text[0:1500] for s in page.sections}
            
            data = {
                "scientific_name": name,
                "language": lang,
                "url": page.fullurl,
                "summary": page.summary[0:2000],
                "full_text": page.text[0:5000], # Giới hạn 5000 ký tự raw
                "sections": sections_data,
                "processed": False, # Flag để AI xử lý sau
                "last_scraped": time.time()
            }
            col_wiki.insert_one(data)
        else:
            # Ghi nhận là không tìm thấy
            col_wiki.insert_one({"scientific_name": name, "found": False})
        
        # 5. Rate Limiting (Quan trọng)
        time.sleep(1)

    logging.info("✅ Crawler Finished.")

if __name__ == "__main__":
    run_crawler()