"use client"

import type React from "react"
import { useState } from "react"
import { Search, X, Send } from "lucide-react"

interface SearchBarProps {
  // Đã sửa query -> question
  onSearch: (question: string) => void
  isLoading?: boolean
}

export function SearchBar({ onSearch, isLoading = false }: SearchBarProps) {
  // Đã sửa state query -> question
  const [question, setQuestion] = useState("")

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    // Đã sửa kiểm tra question
    if (question.trim()) {
      onSearch(question)
    }
  }

  const handleClear = () => {
    setQuestion("")
  }

  return (
      <form onSubmit={handleSubmit} className="w-full">
        <div className="relative flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
            <input
                type="text"
                // Đã sửa value={question}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Hỏi về rắn... (Ví dụ: Con rắn nào dài nhất?)"
                disabled={isLoading}
                className="w-full pl-10 pr-10 py-3 border border-input bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed transition-all rounded-md"
            />
            {/* Đã sửa kiểm tra question */}
            {question && (
                <button
                    type="button"
                    onClick={handleClear}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                    aria-label="Clear search"
                >
                  <X className="w-5 h-5" />
                </button>
            )}
          </div>
          <button
              type="submit"
              // Đã sửa kiểm tra question
              disabled={isLoading || !question.trim()}
              className="bg-primary text-primary-foreground px-4 py-3 font-medium hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity flex items-center gap-2 rounded-md"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </form>
  )
}