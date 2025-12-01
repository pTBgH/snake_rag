# Dùng bản python slim cực nhẹ
FROM python:3.12-slim

WORKDIR /app

# Chỉ cài FastAPI và Uvicorn (Không cài torch, langchain...)
RUN pip install --no-cache-dir fastapi uvicorn pydantic

# Copy code giả lập vào
COPY main.py .

# Mở port
EXPOSE 5000

# Chạy server
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]