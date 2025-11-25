"use client"
import { Menu, Plus, X, Trash2, Search } from "lucide-react"
import { useState } from "react"

interface Conversation {
  id: string
  title: string
  date: Date
  messageCount: number
}

interface ChatSidebarProps {
  isOpen: boolean
  onToggle: () => void
  conversations: Conversation[]
  currentConversationId: string | null
  onSelectConversation: (id: string) => void
  onNewConversation: () => void
  onDeleteConversation: (id: string) => void
}

export function ChatSidebar({
  isOpen,
  onToggle,
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
}: ChatSidebarProps) {
  const [searchQuery, setSearchQuery] = useState("")

  const filteredConversations = conversations.filter((conv) =>
    conv.title.toLowerCase().includes(searchQuery.toLowerCase()),
  )

  return (
    <>
      {/* Toggle Button */}
      <button
        onClick={onToggle}
        className="fixed left-4 top-4 z-40 p-2 rounded-lg hover:bg-primary/10 transition-colors text-foreground"
        aria-label="Toggle sidebar"
      >
        {isOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
      </button>

      {/* Overlay */}
      {isOpen && <div className="fixed inset-0 bg-black/50 z-30 md:hidden" onClick={onToggle} />}

      {/* Sidebar */}
      <aside
        className={`fixed left-0 top-0 h-screen w-64 bg-gradient-to-b from-background to-secondary/5 border-r border-border/20 flex flex-col z-40 transition-transform duration-300 ease-in-out ${
          isOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        } md:translate-x-0`}
      >
        {/* Top spacing for hamburger menu */}
        <div className="h-16" />

        {/* New Chat Button */}
        <div className="px-4 py-3">
          <button
            onClick={onNewConversation}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-gradient-to-r from-primary to-primary/80 text-primary-foreground hover:from-primary/90 hover:to-primary/70 transition-all duration-200 font-medium shadow-md hover:shadow-lg"
          >
            <Plus className="w-5 h-5" />
            Cuộc trò chuyện mới
          </button>
        </div>

        {/* Search Section */}
        <div className="px-4 py-3 border-b border-border/10">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Tìm kiếm..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-3 py-2 rounded-lg bg-muted text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all"
            />
          </div>
        </div>

        {/* Chat History */}
        <div className="flex-1 overflow-y-auto">
          <div className="p-4 space-y-1">
            <h3 className="text-xs font-semibold text-muted-foreground uppercase px-2 mb-3">Gần đây</h3>
            {filteredConversations.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                {searchQuery ? "Không tìm thấy" : "Không có cuộc trò chuyện"}
              </p>
            ) : (
              filteredConversations.map((conv) => (
                <div
                  key={conv.id}
                  className={`group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-all duration-200 ${
                    currentConversationId === conv.id
                      ? "bg-primary/15 text-primary shadow-sm"
                      : "hover:bg-muted text-foreground"
                  }`}
                  onClick={() => onSelectConversation(conv.id)}
                >
                  <span className="flex-1 truncate text-sm font-medium">{conv.title}</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      onDeleteConversation(conv.id)
                    }}
                    className="opacity-0 group-hover:opacity-100 p-1 hover:bg-destructive/10 rounded transition-all duration-150"
                    aria-label="Delete conversation"
                  >
                    <Trash2 className="w-4 h-4 text-destructive" />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Footer Settings */}
        <div className="px-4 py-3 border-t border-border/10">
          <button className="w-full flex items-center justify-start gap-3 px-3 py-2 rounded-lg hover:bg-muted transition-colors text-muted-foreground hover:text-foreground">
            <div className="w-5 h-5 flex items-center justify-center">⚙️</div>
            <span className="text-sm">Cài đặt và trợ giúp</span>
          </button>
        </div>
      </aside>
    </>
  )
}
