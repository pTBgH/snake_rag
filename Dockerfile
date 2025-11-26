FROM python:3.12-slim

# Thư mục làm việc trong container
WORKDIR /app

# Copy requirements và cài đặt (Cài torch CPU cho nhẹ)
COPY requirements.txt .
RUN pip install --no-cache-dir torch --extra-index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# Tạo sẵn thư mục logs trong container để tránh lỗi permission
RUN mkdir -p /app/logs

# Copy toàn bộ code hiện tại (bao gồm main.py, .env, v.v.) vào container
COPY . .

# Mở port
EXPOSE 5000

# Chạy server (Có reload để sửa code là nhận luôn)
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000", "--reload"]
