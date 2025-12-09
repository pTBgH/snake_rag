import os
import logging
import pandas as pd
import torch
import mysql.connector
import pymongo
from elasticsearch import Elasticsearch, helpers
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
from tqdm import tqdm

# --- 1. CẤU HÌNH ---
load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MODEL_NAME = 'BAAI/bge-m3'
EMBEDDING_DIMS = 1024

# Kết nối AI
device = 'cuda' if torch.cuda.is_available() else 'cpu'
logging.info(f"Loading AI Model {MODEL_NAME} on {device}...")
model = SentenceTransformer(MODEL_NAME, device=device)

# Kết nối DB
es = Elasticsearch(ES_HOST, verify_certs=False, ssl_show_warn=False)
mongo_client = pymongo.MongoClient(MONGO_URI)
col_clean = mongo_client["snake_raw_data"]["wiki_cleaned"]

def get_mysql_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=os.getenv("MYSQL_PORT", "3306"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DB", "snake_db")
    )

def create_index():
    index_name = "snakes"
    if es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)
    
    mapping = {
        "mappings": {
            "properties": {
                "scientific_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                
                # Sửa: Bỏ "boost": 2.0 (Elasticsearch 8.x không hỗ trợ boost tại đây)
                "vietnamese_name": {"type": "text", "analyzer": "standard"}, 
                
                "common_names": {"type": "text", "analyzer": "standard"},
                "family": {"type": "keyword"},
                "danger_level": {"type": "keyword"},
                "max_len": {"type": "float"},
                "countries": {"type": "text"},
                "wiki_biology": {"type": "text"},
                "wiki_venom": {"type": "text"},
                "wiki_behavior": {"type": "text"},
                "full_text_context": {"type": "text"},
                "vector_embedding": {
                    "type": "dense_vector",
                    "dims": EMBEDDING_DIMS,
                    "index": True,
                    "similarity": "cosine"
                }
            }
        }
    }
    es.indices.create(index=index_name, body=mapping)
    logging.info(f"✅ Created Index '{index_name}'")

def fetch_data_from_mysql():
    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)
    logging.info("📥 Fetching data from MySQL...")
    
    query = """
    SELECT 
        TRIM(CONCAT(t.genus, ' ', t.species, ' ', IFNULL(t.subspecies, ''))) AS scientific_name,
        tf.family,
        (SELECT GROUP_CONCAT(DISTINCT cname SEPARATOR ', ') FROM map__cname m WHERE m.genus = t.genus AND m.species = t.species) AS common_names,
        (SELECT danger FROM map__danger d WHERE d.genus = t.genus AND d.species = t.species LIMIT 1) AS danger_level,
        (SELECT MAX(tbl) FROM val__size s WHERE s.genus = t.genus AND s.species = t.species) AS max_len
    FROM tax__subspecies t
    LEFT JOIN tax__genus tg ON t.genus = tg.genus
    LEFT JOIN tax__family tf ON tg.family = tf.family
    """
    
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        logging.info(f"📊 Loaded {len(df)} records from MySQL.")
        return df
    except Exception as e:
        logging.error(f"❌ MySQL Error: {e}")
        return pd.DataFrame()
    finally:
        cursor.close()
        conn.close()

def construct_context(row):
    mongo_doc = col_clean.find_one({"scientific_name": row['scientific_name']})
    ai_data = mongo_doc.get("ai_data", {}) if mongo_doc else {}
    
    vn_name = ai_data.get('vietnamese_name', '')
    
    # Gộp tên Việt vào Common Names để tìm kiếm
    full_common_names = row['common_names']
    if vn_name and vn_name not in str(full_common_names):
        full_common_names = f"{vn_name}, {full_common_names}"

    distribution = ai_data.get('distribution', 'Unknown location')

    # Ưu tiên tên tiếng Việt trong vector bằng cách đặt lên đầu
    text = (
        f"Scientific Name: {row['scientific_name']}\n"
        f"Vietnamese Name: {vn_name}\n"
        f"Common Names: {full_common_names}\n"
        f"Family: {row['family']}\n"
        f"Danger Level: {row['danger_level']}\n"
        f"Max Length: {row.get('max_len')} cm\n"
        f"Distribution: {distribution}\n"
        f"--- BIOLOGY ---\n{ai_data.get('biology', '')}\n"
        f"--- VENOM ---\n{ai_data.get('venom', '')}\n"
        f"--- BEHAVIOR ---\n{ai_data.get('behavior', '')}"
    )
    return text, ai_data, distribution, vn_name

def run_etl():
    create_index()
    df = fetch_data_from_mysql()
    
    if df.empty:
        logging.warning("⚠️ No data found in MySQL. Exiting.")
        return

    logging.info("🚀 Starting ETL Process...")
    batch_size = 64
    
    for i in tqdm(range(0, len(df), batch_size)):
        batch = df.iloc[i : i+batch_size].copy()
        
        contexts = []
        mongo_data_list = []
        dist_list = []
        vn_names_list = []
        
        for _, row in batch.iterrows():
            txt, ai_data, dist, vn_name = construct_context(row)
            contexts.append(txt)
            mongo_data_list.append(ai_data)
            dist_list.append(dist)
            vn_names_list.append(vn_name)
            
        try:
            embeddings = model.encode(contexts, show_progress_bar=False)
        except Exception as e:
            logging.error(f"Embedding error: {e}")
            continue
        
        actions = []
        for idx, row in enumerate(batch.to_dict('records')):
            ai_data = mongo_data_list[idx]
            
            action = {
                "_index": "snakes",
                "_id": row['scientific_name'].replace(" ", "_"),
                "_source": {
                    "scientific_name": row['scientific_name'],
                    "vietnamese_name": vn_names_list[idx], # Lưu tên Việt
                    "common_names": row['common_names'],
                    "family": row['family'],
                    "danger_level": row['danger_level'],
                    "max_len": row.get('max_len'),
                    "countries": dist_list[idx],
                    "wiki_biology": ai_data.get("biology"),
                    "wiki_venom": ai_data.get("venom"),
                    "wiki_behavior": ai_data.get("behavior"),
                    "full_text_context": contexts[idx],
                    "vector_embedding": embeddings[idx].tolist()
                }
            }
            actions.append(action)
            
        if actions:
            helpers.bulk(es, actions)

    logging.info("🎉 ETL Process Completed Successfully!")

if __name__ == "__main__":
    if es.ping():
        run_etl()
    else:
        logging.error("❌ Cannot connect to Elasticsearch.")