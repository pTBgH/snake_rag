# 1. Dùng Amazon Corretto 17 (Hỗ trợ cực tốt cho Mac M1/M2/M3 và rất nhẹ)
FROM amazoncorretto:17-alpine-jdk

# 2. Tạo thư mục làm việc
WORKDIR /app

# 3. Copy file cấu hình Gradle
COPY gradle gradle
COPY gradlew build.gradle settings.gradle ./

# 4. Cấp quyền thực thi (Quan trọng trên Mac/Linux)
RUN chmod +x gradlew

# 5. Copy code nguồn
COPY src ./src

# 6. Build file .jar
RUN ./gradlew bootJar -x test

# 7. Đổi tên file
RUN cp build/libs/*.jar app.jar

# 8. Mở cổng
EXPOSE 8080

# 9. Chạy
ENTRYPOINT ["java", "-jar", "app.jar"]