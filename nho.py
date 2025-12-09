import pandas as pd
from pymongo import MongoClient
from bson.objectid import ObjectId
# --- 1. Thiết lập Cấu hình MongoDB ---
# Thay thế chuỗi kết nối của bạn tại đây
MONGO_URI = "mongodb://admin:MongconGaG000@192.168.100.231:17017"
DATABASE_NAME = "topjob" # Thay thế bằng tên DB thực tế, ví dụ: 'jobdata'
RAW_JOBS_COLLECTION = "raw_jobs"      # Tên collection raw_jobs
MAPPED_JOBS_COLLECTION = "mapped_jobs"  # Tên collection mapped_jobs
LIMIT = 200

def fetch_and_export_data():
    """
    Kết nối MongoDB, truy vấn, in dữ liệu mẫu, làm sạch, nối dữ liệu và xuất ra CSV.
    """
    try:
        # Kết nối tới MongoDB
        client = MongoClient(MONGO_URI)
        db = client[DATABASE_NAME]
        
        raw_jobs_col = db[RAW_JOBS_COLLECTION]
        mapped_jobs_col = db[MAPPED_JOBS_COLLECTION]

        print("✅ Kết nối MongoDB thành công.")

        # =======================================================
        ## 💡 BƯỚC MỚI: TRUY VẤN VÀ IN RA 200 DÒNG MAPPED_JOBS
        # =======================================================
        mapped_fields_projection = {
            "_id": 1, # Lấy _id để kiểm tra cấu trúc
            "job_id": 1,
            "job_ben": 1,
            "job_req": 1,
            "job_des": 1,
            "source": 1
        }
        mapped_data = list(mapped_jobs_col.find({}, mapped_fields_projection)
                                          .sort("created_at", -1) # <--- ĐÃ THÊM SẮP XẾP
                                          .limit(LIMIT))
        mapped_df = pd.DataFrame(mapped_data)

        print("\n--- 📝 200 DÒNG DỮ LIỆU MAPPED_JOBS TRUY VẤN ĐƯỢC ---")
        if not mapped_df.empty:
            # Chuyển đổi _id sang string để in
            mapped_df['_id'] = mapped_df['_id'].apply(lambda x: str(x) if isinstance(x, ObjectId) else x)
            # print(mapped_df.head(LIMIT).to_string())
        else:
            print("⚠️ mapped_jobs trống. Không có gì để in.")
            return # Dừng nếu mapped_jobs trống
        
        # Lọc các bản ghi thiếu 'job_id' để tránh lỗi KeyError khi xử lý tiếp
        mapped_df.dropna(subset=['job_id'], inplace=True)
        mapped_df['job_id'] = mapped_df['job_id'].astype(str)

        if mapped_df.empty:
            print("⚠️ Sau khi lọc, không còn bản ghi hợp lệ nào có 'job_id' trong mapped_jobs.")
            return
            
        print(f"\n✅ Đã truy vấn và làm sạch {len(mapped_df)} bản ghi từ mapped_jobs (Dùng cho join).")
        
        # =======================================================
        ## 💡 BƯỚC MỚI: TRUY VẤN VÀ IN RA 200 DÒNG RAW_JOBS
        # =======================================================
        
        # Lấy 200 job_id để kiểm tra (từ mapped_df đã sạch)
        job_ids_to_query = mapped_df['job_id'].tolist()
        
        # Projection cho raw_jobs (chỉ loại trừ các trường cờ)
        raw_fields_projection = {
            "job_id": 1,       # Thông tin job
            "job_link": 1,     # Original Link
            "title": 1,        # Thông tin job
            "source": 1,
            "due_date": 1,
            "up_date": 1,
            "company": 1,
            "company_link": 1,
            "avatar": 1,
            "raw_info": 1,
            "job_des": 1,
            "job_req": 1,
            "job_ben": 1,
            "keywords": 1,
            "created_at": 1,
        }
        
        # Truy vấn raw_jobs bằng các ID đã lọc
        raw_data = list(raw_jobs_col.find(
            {"job_id": {"$in": job_ids_to_query}},
            raw_fields_projection)
            .sort("created_at", -1)) # <--- ĐÃ THÊM SẮP XẾP

        raw_df = pd.DataFrame(raw_data)
        
        print("\n--- 📝 DỮ LIỆU RAW_JOBS TƯƠNG ỨNG TRUY VẤN ĐƯỢC ---")
        if not raw_df.empty:
            # Chuyển đổi _id sang string để in
            raw_df['_id'] = raw_df['_id'].apply(lambda x: str(x) if isinstance(x, ObjectId) else x)
            print(raw_df.head(LIMIT).to_string())
        else:
            print("⚠️ raw_jobs trống. Không có gì để in.")
            return # Dừng nếu raw_jobs trống

        # --- TIẾP TỤC BƯỚC NỐI (JOIN) ---

        # Chuẩn bị raw_df cho join
        raw_df.rename(columns={'job_link': 'original_link'}, inplace=True)
        raw_df['job_id'] = raw_df['job_id'].astype(str)

        print(f"\n✅ Đã truy vấn {len(raw_df)} bản ghi tương ứng từ raw_jobs (Dùng cho join).")

        # Nối mapped_df (chính) với raw_df (phụ)
        final_df = pd.merge(
            mapped_df, 
            raw_df,
            on='job_id',
            how='left', 
            suffixes=('_mapped', '_raw')
        )

        print("\n✅ Đã nối dữ liệu thành công.")

        # --- 4. Xuất ra CSV ---
        output_file = "job_data_export.csv"
        final_df.fillna('', inplace=True)
        final_df.to_csv(output_file, index=False, encoding='utf-8-sig')

        print(f"🎉 Hoàn tất! Đã xuất {len(final_df)} bản ghi ra file: **{output_file}**")

        client.close()

    except Exception as e:
        print(f"❌ Đã xảy ra lỗi: {e}")
# Chạy hàm
if __name__ == "__main__":
    fetch_and_export_data()