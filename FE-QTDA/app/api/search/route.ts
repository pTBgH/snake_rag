import { NextResponse } from 'next/server';

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { question } = body;

    if (!question) {
      return NextResponse.json({ error: 'Question is required' }, { status: 400 });
    }

    // --- LOG QUAN TRỌNG ĐỂ DEBUG ---
    console.log("🚀 [API Route] Nhận câu hỏi từ Client:", question);

    // --- SỬA LỖI KẾT NỐI TẠI ĐÂY ---
    // Trong môi trường Docker, phải gọi tên service là "sn-java" thay vì "localhost"
    // Docker có hệ thống DNS nội bộ tự động trỏ "sn-java" sang IP của container backend
    const backendUrl = process.env.JAVA_BACKEND_URL || 'http://sn-java:9999/api/ask-snake';

    console.log("🔗 Đang gọi sang Java Backend tại:", backendUrl);

    const res = await fetch(backendUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ question: question }),
    });

    if (!res.ok) {
      const statusText = await res.text();
      console.error(`❌ Lỗi từ Java Backend (${res.status}):`, statusText);
      return NextResponse.json(
          { error: 'Lỗi kết nối Backend', details: statusText },
          { status: res.status }
      );
    }

    const data = await res.json();
    console.log("✅ Nhận phản hồi thành công từ Java:", data);

    return NextResponse.json(data);

  } catch (error) {
    console.error('🔥 Lỗi Proxy Server:', error);
    return NextResponse.json({ error: 'Lỗi Server Frontend' }, { status: 500 });
  }
}