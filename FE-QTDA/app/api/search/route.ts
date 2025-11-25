import { NextResponse } from 'next/server';

export async function POST(req: Request) {
  try {
    const body = await req.json();

    // --- SỬA Ở ĐÂY: Nhận biến tên là "question" ---
    const { question } = body;

    if (!question) {
      return NextResponse.json({ error: 'Question is required' }, { status: 400 });
    }

    console.log("🔄 Đang gửi câu hỏi sang Java cổng 9999:", question);

    // --- SỬA Ở ĐÂY: Cập nhật Port 9999 ---
    const backendUrl = process.env.JAVA_BACKEND_URL || 'http://localhost:9999/api/ask-snake';

    const res = await fetch(backendUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      // Java đợi key "question", ta gửi đúng key "question"
      body: JSON.stringify({ question: question }),
    });

    if (!res.ok) {
      console.error("Lỗi từ Java Backend:", res.status);
      return NextResponse.json({ error: 'Lỗi kết nối Backend' }, { status: res.status });
    }

    const data = await res.json();
    return NextResponse.json(data);

  } catch (error) {
    console.error('Lỗi Proxy:', error);
    return NextResponse.json({ error: 'Lỗi Server Frontend' }, { status: 500 });
  }
}