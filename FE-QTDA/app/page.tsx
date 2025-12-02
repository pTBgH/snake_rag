'use client'

import { useEffect } from 'react'

export default function Home() {
    useEffect(() => {
        // Tự động chuyển người dùng sang trang /search bằng Client-side redirect
        // Cách này hoạt động ổn định và giải quyết vấn đề 404 ngay lập tức
        window.location.href = '/search'
    }, [])

    // Không hiển thị gì vì sẽ chuyển trang ngay
    return null
}