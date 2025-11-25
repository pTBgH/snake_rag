"use client"

import { useState, useCallback, useRef, useEffect } from "react"
import { SearchBar } from "@/components/search-bar"
import { SearchResults } from "@/components/search-results"
import { SearchLoading } from "@/components/search-loading"
import { SearchError } from "@/components/search-error"
import { ThemeToggle } from "@/components/theme-toggle"
import { ChatSidebar } from "@/components/chat-sidebar"
import { logSearch } from "@/lib/search-logger"
import {
  createConversation,
  saveConversation,
  getConversation,
  getAllConversations,
  deleteConversation,
  setCurrentConversation,
  getCurrentConversation,
  type Conversation as ConversationType,
} from "@/lib/conversation-manager"

interface SearchResult {
  id: string
  title: string
  description: string
  url?: string
  category?: string
  date?: string
}

interface SearchEntry {
  id: string
  query: string
  results: SearchResult[]
  duration: number
  timestamp: Date
  state: "loading" | "success" | "error"
  error?: string
  answer?: string
}

type SearchState = "idle" | "loading" | "success" | "error"

export default function SearchPage() {
  const [searchHistory, setSearchHistory] = useState<SearchEntry[]>([])
  const [currentState, setCurrentState] = useState<SearchState>("idle")
  const [currentQuery, setCurrentQuery] = useState("")
  const [currentError, setCurrentError] = useState("")
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null)
  const [conversations, setConversations] = useState<ConversationType[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const saved = getAllConversations()
    setConversations(saved)

    const currentId = getCurrentConversation()
    if (currentId && saved.find((c) => c.id === currentId)) {
      setCurrentConversationId(currentId)
      const conv = getConversation(currentId)
      if (conv) {
        const entries: SearchEntry[] = conv.messages.map((msg) => ({
          ...msg,
          timestamp: new Date(msg.timestamp),
        }))
        setSearchHistory(entries)
      }
    } else {
      startNewConversation()
    }
  }, [])

  const startNewConversation = useCallback(() => {
    const newConv = createConversation()
    setCurrentConversationId(newConv.id)
    setCurrentConversation(newConv.id)
    setSearchHistory([])
    setCurrentState("idle")
    setCurrentError("")
    saveConversation(newConv)
    setConversations((prev) => [newConv, ...prev])
    setSidebarOpen(false)
  }, [])

  const handleSelectConversation = useCallback((id: string) => {
    const conv = getConversation(id)
    if (conv) {
      setCurrentConversationId(id)
      setCurrentConversation(id)
      const entries: SearchEntry[] = conv.messages.map((msg) => ({
        ...msg,
        timestamp: new Date(msg.timestamp),
      }))
      setSearchHistory(entries)
      setCurrentState("idle")
      setCurrentError("")
      setSidebarOpen(false)
    }
  }, [])

  const handleDeleteConversation = useCallback(
      (id: string) => {
        deleteConversation(id)
        setConversations((prev) => prev.filter((c) => c.id !== id))
        if (currentConversationId === id) {
          startNewConversation()
        }
      },
      [currentConversationId, startNewConversation],
  )

  const handleSearch = useCallback(
      async (searchQuery: string) => {
        setCurrentQuery(searchQuery)
        setCurrentState("loading")
        setCurrentError("")

        const entryId = Date.now().toString()
        const newEntry: SearchEntry = {
          id: entryId,
          query: searchQuery,
          results: [],
          duration: 0,
          timestamp: new Date(),
          state: "loading",
        }

        setSearchHistory((prev) => [...prev, newEntry])

        const startTime = performance.now()

        try {
          const response = await fetch("/api/search", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            // Gửi đúng key "question" để khớp với Backend
            body: JSON.stringify({ question: searchQuery }),
          })

          const endTime = performance.now()
          const duration = Math.round(endTime - startTime)

          if (!response.ok) {
            throw new Error(`Lỗi API: ${response.status}`)
          }

          const data = await response.json()
          const answerText = data.answer || ""
          const results: SearchResult[] = (data.sources || []).map((src: string, idx: number) => ({
            id: idx.toString(),
            title: `Nguồn ${idx + 1}`,
            description: src,
            date: new Date().toLocaleDateString()
          }))

          setSearchHistory((prev) =>
              prev.map((entry) =>
                  entry.id === entryId
                      ? { ...entry, results, answer: answerText, duration, state: "success" }
                      : entry,
              ),
          )

          setCurrentState("success")
          logSearch(searchQuery, duration, results.length, "success")

          if (currentConversationId) {
            const conv = getConversation(currentConversationId)
            if (conv) {
              conv.messages.push({
                id: entryId,
                query: searchQuery,
                results,
                answer: answerText,
                duration,
                timestamp: Date.now(),
                state: "success",
              } as any)

              if (conv.messages.length === 1) {
                conv.title = searchQuery.length > 30 ? searchQuery.slice(0, 30) + "..." : searchQuery
              }
              saveConversation(conv)
              setConversations((prev) =>
                  prev.map((c) => (c.id === currentConversationId ? conv : c)),
              )
            }
          }
        } catch (err) {
          const duration = Math.round(performance.now() - startTime)
          const errorMessage = err instanceof Error ? err.message : "Lỗi không xác định"
          setCurrentError(errorMessage)
          setCurrentState("error")
          setSearchHistory((prev) =>
              prev.map((entry) =>
                  entry.id === entryId ? { ...entry, duration, state: "error", error: errorMessage } : entry,
              ),
          )
          logSearch(searchQuery, duration, 0, "error", errorMessage)
        }
      },
      [currentConversationId],
  )

  const handleRetry = useCallback(() => {
    if (currentQuery) handleSearch(currentQuery)
  }, [currentQuery, handleSearch])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [searchHistory, currentState])

  return (
      <main className="h-screen flex flex-col bg-gradient-to-br from-background via-background to-secondary/5 dark:from-background dark:via-background dark:to-secondary/10">
        <ChatSidebar
            isOpen={sidebarOpen}
            onToggle={() => setSidebarOpen(!sidebarOpen)}
            // SỬA QUAN TRỌNG: Xóa ': Conversation' ở biến c và dùng 'as any' để bỏ qua lỗi timestamp
            conversations={conversations.map(c => ({
              id: c.id,
              title: c.title,
              date: new Date(c.timestamp).toLocaleDateString("vi-VN"),
              messageCount: c.messages.length
            })) as any}
            currentConversationId={currentConversationId}
            onSelectConversation={handleSelectConversation}
            onNewConversation={startNewConversation}
            onDeleteConversation={handleDeleteConversation}
        />

        <div className="pt-6 px-4 text-center border-b border-border/30 flex items-center justify-between md:ml-64">
          <div className="w-10 md:hidden" />
          <div>
            <div className="inline-block mb-2 text-5xl animate-bounce">🐍</div>
            <h1 className="text-2xl md:text-3xl font-bold text-foreground">Rắn AI Agent</h1>
            <p className="text-sm text-muted-foreground mt-1">Hỏi về loài rắn • Ask about snakes</p>
          </div>
          <ThemeToggle />
        </div>

        <div className="flex-1 overflow-y-auto md:ml-64">
          <div className="container mx-auto px-4 py-6">
            {searchHistory.length === 0 && currentState === "idle" && (
                <div className="h-full flex items-center justify-center min-h-[50vh]">
                  <div className="text-center max-w-md">
                    <div className="text-6xl mb-4 inline-block">🐍</div>
                    <h2 className="text-xl font-semibold text-foreground mb-2">Rắn AI Agent</h2>
                    <p className="text-muted-foreground text-sm">Hỏi tôi bất cứ điều gì về rắn!</p>
                  </div>
                </div>
            )}

            <div className="max-w-3xl mx-auto space-y-8 pb-20">
              {searchHistory.map((entry) => (
                  <div key={entry.id} className="space-y-6">
                    <div className="flex justify-end">
                      <div className="max-w-[85%] bg-primary text-primary-foreground rounded-2xl rounded-tr-none p-4 shadow-md">
                        <p>{entry.query}</p>
                      </div>
                    </div>

                    <div className="flex justify-start w-full">
                      <div className="max-w-full w-full bg-muted/50 rounded-2xl rounded-tl-none p-6 border border-border/50 shadow-sm">
                        {entry.state === "loading" && <SearchLoading />}

                        {entry.state === "success" && (
                            <div className="space-y-4">
                              <div className="prose dark:prose-invert whitespace-pre-wrap">
                                {entry.answer || "Đã tìm thấy thông tin:"}
                              </div>

                              {entry.results.length > 0 && (
                                  <div className="pt-4 border-t text-sm">
                                    <p className="font-bold text-muted-foreground mb-2">Nguồn tham khảo:</p>
                                    <SearchResults results={entry.results} query={entry.query} />
                                  </div>
                              )}
                            </div>
                        )}

                        {entry.state === "error" && (
                            <SearchError error={entry.error || currentError} onRetry={handleRetry} />
                        )}
                      </div>
                    </div>
                  </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          </div>
        </div>

        <div className="fixed bottom-0 left-0 right-0 bg-background/80 backdrop-blur-md border-t p-4 md:pl-72 z-20">
          <div className="container mx-auto max-w-3xl">
            <SearchBar onSearch={handleSearch} isLoading={currentState === "loading"} />
          </div>
        </div>
      </main>
  )
}