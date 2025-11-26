import os
import logging
import pandas as pd
import torch
import mysql.connector
from elasticsearch import Elasticsearch, helpers
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
from tqdm import tqdm

# --- 1. CẤU HÌNH ---
load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# Kết nối Elasticsearch
es = Elasticsearch(
    os.getenv("ES_HOST", "http://localhost:9200"),
    verify_certs=False, 
    ssl_show_warn=False
)

# Kết nối MySQL
def get_mysql_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=os.getenv("MYSQL_PORT", "3306"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DB", "snake_db")
    )

# --- CẤU HÌNH AI MODEL (BAAI) ---
# BAAI/bge-m3 hỗ trợ đa ngôn ngữ cực tốt, không cần dịch query
MODEL_NAME = 'BAAI/bge-m3'
EMBEDDING_DIMS = 1024  # Kích thước vector của BGE-M3 là 1024

device = 'cuda' if torch.cuda.is_available() else 'cpu'
logging.info(f"🔄 Đang tải Model AI: {MODEL_NAME} trên thiết bị: {device}...")
try:
    model = SentenceTransformer(MODEL_NAME, device=device)
    logging.info("✅ Tải Model thành công!")
except Exception as e:
    logging.error(f"❌ Không tải được model. Lỗi: {e}")
    exit(1)

# --- 2. HÀM XỬ LÝ DỮ LIỆU ---

def create_index_if_not_exists(index_name="snakes"):
    """Tự động xóa và tạo lại Index nếu kích thước Vector thay đổi"""
    if es.indices.exists(index=index_name):
        # Kiểm tra xem index cũ có đúng kích thước 1024 không
        try:
            mapping = es.indices.get_mapping(index=index_name)
            props = mapping[index_name]['mappings']['properties']
            current_dims = props.get('vector_embedding', {}).get('dims', 0)
            
            if current_dims != EMBEDDING_DIMS:
                logging.warning(f"⚠️ Index cũ ({current_dims} dims) không khớp model mới ({EMBEDDING_DIMS} dims).")
                logging.warning("🗑️ Đang xóa Index cũ để tạo lại...")
                es.indices.delete(index=index_name)
            else:
                logging.info(f"✅ Index '{index_name}' đã tồn tại và đúng cấu hình.")
                return
        except Exception as e:
            logging.warning(f"⚠️ Không kiểm tra được mapping cũ, sẽ tạo lại. Lỗi: {e}")

    # Tạo Mapping mới
    mapping = {
        "mappings": {
            "properties": {
                "id": {"type": "keyword"},
                "scientific_name": {"type": "text"},
                "common_names": {"type": "text", "analyzer": "standard"},
                "family": {"type": "keyword"},
                "danger_level": {"type": "keyword"},
                "max_len_cm": {"type": "float"}, # Đổi sang float để sort nếu cần
                "full_text_context": {"type": "text"},
                "vector_embedding": {
                    "type": "dense_vector",
                    "dims": EMBEDDING_DIMS,
                    "index": True,
                    "similarity": "cosine" # Cosine tốt cho ngữ nghĩa
                }
            }
        }
    }
    es.indices.create(index=index_name, body=mapping)
    logging.info(f"✅ Đã tạo Index '{index_name}' với kích thước Vector: {EMBEDDING_DIMS}")

def fetch_snake_data():
    """Lấy dữ liệu từ MySQL"""
    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)
    
    logging.info("📥 Đang lấy dữ liệu từ MySQL...")
    
    query = """
    SELECT 
        TRIM(CONCAT(t.genus, ' ', t.species, ' ', t.subspecies)) AS full_scientific_name,
        tf.family,
        (SELECT GROUP_CONCAT(DISTINCT cname SEPARATOR ', ') FROM map__cname m WHERE m.genus = t.genus AND m.species = t.species AND m.subspecies = t.subspecies) AS common_names,
        (SELECT danger FROM map__danger d WHERE d.genus = t.genus AND d.species = t.species AND d.subspecies = t.subspecies LIMIT 1) AS danger_level,
        (SELECT MAX(tbl) FROM val__size s WHERE s.genus = t.genus AND s.species = t.species AND s.subspecies = t.subspecies) AS max_len_cm,
        (SELECT reproduction FROM map__reproduction r WHERE r.genus = t.genus AND r.species = t.species AND r.subspecies = t.subspecies LIMIT 1) AS reproduction
    FROM tax__subspecies t
    LEFT JOIN tax__genus tg ON t.genus = tg.genus
    LEFT JOIN tax__family tf ON tg.family = tf.family
    """
    
    try:
        cursor.execute(query)
        df = pd.DataFrame(cursor.fetchall())
        logging.info(f"📊 Đã lấy {len(df)} dòng dữ liệu.")
        return df
    except Exception as e:
        logging.error(f"❌ Lỗi SQL: {e}")
        return pd.DataFrame()
    finally:
        cursor.close()
        conn.close()

def construct_context(row):
    """Tạo đoạn văn mô tả đầy đủ để AI Embed"""
    # Xử lý Null
    cnames = row['common_names'] if row['common_names'] else "Unknown"
    danger = row['danger_level'] if row['danger_level'] else "Unknown"
    family = row['family'] if row['family'] else "Unknown"
    
    # Text này sẽ được biến thành Vector. Càng chi tiết càng tốt.
    # Model BAAI hiểu cả Anh lẫn Việt, nhưng dữ liệu gốc nên để tiếng Anh chuẩn khoa học.
    text = (
        f"Species: {row['full_scientific_name']}. "
        f"Common names: {cnames}. "
        f"Family: {family}. "
        f"Danger level: {danger}. "
        f"Max length: {row['max_len_cm']} cm. "
        f"Reproduction: {row['reproduction']}."
    )
    return text

def run_etl(batch_size=64):
    create_index_if_not_exists("snakes")
    df = fetch_snake_data()
    if df.empty: return

    logging.info("📝 Đang tạo ngữ cảnh (Context building)...")
    df['full_text_context'] = df.apply(construct_context, axis=1)
    
    logging.info(f"🚀 Bắt đầu Embed và Index {len(df)} bản ghi...")
    
    # Xử lý theo batch để tránh tràn RAM
    for i in tqdm(range(0, len(df), batch_size), desc="Indexing"):
        batch = df.iloc[i : i + batch_size].copy()
        
        try:
            # Encode bằng BAAI/bge-m3
            embeddings = model.encode(batch['full_text_context'].tolist(), show_progress_bar=False)
            batch['vector_embedding'] = embeddings.tolist()
            
            actions = []
            for rec in batch.to_dict(orient="records"):
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
                        "full_text_context": rec['full_text_context'],
                        "vector_embedding": rec['vector_embedding']
                    }
                }
                actions.append(action)
            
            if actions:
                helpers.bulk(es, actions)
                
        except Exception as e:
            logging.error(f"❌ Lỗi tại batch {i}: {e}")

    logging.info("🎉 ETL Hoàn tất! Dữ liệu đã sẵn sàng.")

if __name__ == "__main__":
    if es.ping():
        run_etl()
    else:
        logging.error("❌ Không thể kết nối Elasticsearch.")