import os
import time
import logging
import pandas as pd
import torch
import mysql.connector
from elasticsearch import Elasticsearch, helpers
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
from tqdm import tqdm  # Thanh hiển thị tiến độ

# --- 1. CẤU HÌNH ---
load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# Kết nối Elasticsearch
es = Elasticsearch(os.getenv("ES_HOST"))

# Kết nối MySQL
def get_mysql_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        port=os.getenv("MYSQL_PORT"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DB")
    )

# Load Model AI (Chạy 1 lần)
# Nếu có GPU thì dùng, không thì CPU
device = 'cuda' if torch.cuda.is_available() else 'cpu'
logging.info(f"Loading AI Model on: {device}...")
model = SentenceTransformer('all-MiniLM-L6-v2', device=device)
EMBEDDING_DIMS = 384  # Kích thước vector của model all-MiniLM-L6-v2

# --- 2. HÀM XỬ LÝ DỮ LIỆU ---

def create_index_if_not_exists(index_name="snakes"):
    """Tạo mapping cho Index trong Elasticsearch"""
    if es.indices.exists(index=index_name):
        logging.info(f"Index '{index_name}' already exists. Skipping creation.")
        return

    mapping = {
        "mappings": {
            "properties": {
                "id": {"type": "keyword"},
                "scientific_name": {"type": "text"},
                "common_names": {"type": "text", "analyzer": "standard"},
                "family": {"type": "keyword"},
                "danger_level": {"type": "keyword"},
                "full_text_context": {"type": "text"}, # Dùng để AI đọc trả lời
                "vector_embedding": {
                    "type": "dense_vector",
                    "dims": EMBEDDING_DIMS, # Phải khớp với model (384)
                    "index": True,
                    "similarity": "cosine"
                }
            }
        }
    }
    es.indices.create(index=index_name, body=mapping)
    logging.info(f"Created index '{index_name}' with {EMBEDDING_DIMS} dimensions.")

def fetch_snake_data():
    """Lấy dữ liệu từ MySQL và Flatten thành bảng phẳng"""
    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)
    
    logging.info("Fetching data from MySQL... This might take a moment.")
    
    # Câu Query "Thần thánh" để gom dữ liệu từ nhiều bảng
    # Chúng ta join bảng tax__subspecies với tên, độ nguy hiểm, kích thước
    query = """
    SELECT 
        -- Tạo ID duy nhất
        TRIM(CONCAT(t.genus, ' ', t.species, ' ', t.subspecies)) AS full_scientific_name,
        t.genus,
        t.species,
        t.subspecies,
        tf.family,
        
        -- Gom tất cả tên thường gọi lại thành 1 chuỗi (ưu tiên tiếng Anh, Việt nếu có)
        (
            SELECT GROUP_CONCAT(DISTINCT cname SEPARATOR ', ') 
            FROM map__cname m 
            WHERE m.genus = t.genus AND m.species = t.species AND m.subspecies = t.subspecies
        ) AS common_names,
        
        -- Lấy mức độ nguy hiểm
        (
            SELECT danger FROM map__danger d 
            WHERE d.genus = t.genus AND d.species = t.species AND d.subspecies = t.subspecies 
            LIMIT 1
        ) AS danger_level,
        
        -- Lấy kích thước tối đa (Total Body Length)
        (
            SELECT MAX(tbl) FROM val__size s 
            WHERE s.genus = t.genus AND s.species = t.species AND s.subspecies = t.subspecies
        ) AS max_len_cm,
        
        -- Lấy kiểu sinh sản
        (
             SELECT reproduction FROM map__reproduction r 
             WHERE r.genus = t.genus AND r.species = t.species AND r.subspecies = t.subspecies
             LIMIT 1
        ) AS reproduction
        
    FROM tax__subspecies t
    LEFT JOIN tax__genus tg ON t.genus = tg.genus
    LEFT JOIN tax__family tf ON tg.family = tf.family
    """
    
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        df = pd.DataFrame(rows)
        logging.info(f"Fetched {len(df)} records from MySQL.")
        return df
    except Exception as e:
        logging.error(f"Error fetching data: {e}")
        return pd.DataFrame()
    finally:
        cursor.close()
        conn.close()

def construct_context(row):
    """Tạo đoạn văn mô tả để Embed"""
    # Xử lý dữ liệu Null
    cnames = row['common_names'] if row['common_names'] else "Unknown common name"
    danger = row['danger_level'] if row['danger_level'] else "Unknown danger level"
    family = row['family'] if row['family'] else "Unknown family"
    maxlen = f"{row['max_len_cm']} cm" if row['max_len_cm'] else "unknown size"
    repro = row['reproduction'] if row['reproduction'] else "unknown reproduction mode"
    
    # Tạo câu văn tự nhiên (Đây là input cho RAG)
    text = (
        f"The snake {row['full_scientific_name']} is a member of the {family} family. "
        f"It is commonly known as: {cnames}. "
        f"Danger level: {danger}. "
        f"Max length: {maxlen}. "
        f"Reproduction: {repro}."
    )
    return text

# --- 3. HÀM CHÍNH ---

def run_etl(batch_size=100):
    # 1. Chuẩn bị Elasticsearch
    create_index_if_not_exists("snakes")
    
    # 2. Lấy dữ liệu
    df = fetch_snake_data()
    if df.empty:
        logging.warning("No data found. Exiting.")
        return

    # 3. Tạo cột Text Context
    logging.info("Constructing text contexts...")
    df['full_text_context'] = df.apply(construct_context, axis=1)
    
    # 4. Xử lý theo Batch
    total_records = len(df)
    logging.info(f"Start processing {total_records} snakes...")
    
    for i in tqdm(range(0, total_records, batch_size), desc="Indexing Batches"):
        batch = df.iloc[i : i + batch_size].copy()
        
        # A. Tạo Embedding (Vector hóa)
        # batch['full_text_context'].tolist() đưa list text vào model
        try:
            embeddings = model.encode(batch['full_text_context'].tolist(), show_progress_bar=False)
            # Chuyển numpy array sang list để ES hiểu
            batch['vector_embedding'] = embeddings.tolist()
        except Exception as e:
            logging.error(f"Error embedding batch {i}: {e}")
            continue

        # B. Chuẩn bị dữ liệu đẩy vào ES
        actions = []
        records = batch.to_dict(orient="records")
        
        for rec in records:
            # Tạo ID duy nhất bằng cách xóa khoảng trắng thừa
            doc_id = rec['full_scientific_name'].replace(" ", "_")
            
            action = {
                "_index": "snakes",
                "_id": doc_id,
                "_source": {
                    "id": doc_id,
                    "scientific_name": rec['full_scientific_name'],
                    "common_names": rec.get('common_names', ''),
                    "family": rec.get('family', ''),
                    "danger_level": rec.get('danger_level', ''),
                    "max_len_cm": rec.get('max_len_cm'),
                    "reproduction": rec.get('reproduction', ''),
                    "full_text_context": rec['full_text_context'], # Text để hiển thị
                    "vector_embedding": rec['vector_embedding']    # Vector để search
                }
            }
            actions.append(action)
            
        # C. Đẩy vào Elasticsearch
        if actions:
            try:
                success, failed = helpers.bulk(es, actions, stats_only=True)
                # logging.info(f"Batch {i//batch_size + 1}: Indexed {success}, Failed {failed}")
            except Exception as e:
                logging.error(f"Error indexing batch: {e}")

    logging.info("ETL Process Completed Successfully!")

if __name__ == "__main__":
    # Kiểm tra kết nối ES trước
    if es.ping():
        logging.info("Connected to Elasticsearch!")
        run_etl(batch_size=50)
    else:
        logging.error("Could not connect to Elasticsearch. Check .env or Docker.")