# 1. Dùng Node.js bản nhẹ (Alpine)
FROM node:18-alpine

# 2. Tạo thư mục làm việc bên trong container
WORKDIR /app

# 3. Copy file khai báo thư viện trước (để tận dụng cache)
COPY package*.json ./

# 4. Cài đặt thư viện
# Dùng --legacy-peer-deps để tránh lỗi xung đột phiên bản thường gặp ở Next.js
RUN npm install --legacy-peer-deps

# 5. Copy toàn bộ code nguồn vào
COPY . .

# 6. Build ứng dụng Next.js
# Lệnh này sẽ tạo ra thư mục .next chứa code đã tối ưu
RUN npm run build

# 7. Mở cổng 3000 (Cổng mặc định của Next.js)
EXPOSE 3000

# 8. Lệnh chạy server
CMD ["npm", "start"]