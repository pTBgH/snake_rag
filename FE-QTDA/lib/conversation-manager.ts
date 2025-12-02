/**
 * Conversation Manager - Manage chat conversations
 * Handles storing, retrieving, and managing conversation history
 */

export interface Message {
  id: string
  query: string
  results: any[]
  duration: number
  timestamp: Date
  state: "loading" | "success" | "error"
  error?: string
}

export interface Conversation {
  id: string
  title: string
  messages: Message[]
  createdAt: Date
  updatedAt: Date
}

const CONVERSATIONS_KEY = "conversations"
const CURRENT_CONVERSATION_KEY = "current_conversation_id"

export function createConversation(title = "Cuộc trò chuyện mới"): Conversation {
  const id = Date.now().toString()
  return {
    id,
    title,
    messages: [],
    createdAt: new Date(),
    updatedAt: new Date(),
  }
}

export function saveConversation(conversation: Conversation): void {
  try {
    const conversations = getAllConversations()
    const existingIndex = conversations.findIndex((c) => c.id === conversation.id)

    if (existingIndex >= 0) {
      conversations[existingIndex] = {
        ...conversation,
        updatedAt: new Date(),
      }
    } else {
      conversations.push(conversation)
    }

    localStorage.setItem(CONVERSATIONS_KEY, JSON.stringify(conversations))
  } catch (e) {
    console.error("[v0] Failed to save conversation:", e)
  }
}

export function getConversation(id: string): Conversation | null {
  try {
    const conversations = getAllConversations()
    return conversations.find((c) => c.id === id) || null
  } catch (e) {
    console.error("[v0] Failed to retrieve conversation:", e)
    return null
  }
}

export function getAllConversations(): Conversation[] {
  try {
    return JSON.parse(localStorage.getItem(CONVERSATIONS_KEY) || "[]") as Conversation[]
  } catch (e) {
    console.error("[v0] Failed to retrieve conversations:", e)
    return []
  }
}

export function deleteConversation(id: string): void {
  try {
    const conversations = getAllConversations().filter((c) => c.id !== id)
    localStorage.setItem(CONVERSATIONS_KEY, JSON.stringify(conversations))

    const currentId = localStorage.getItem(CURRENT_CONVERSATION_KEY)
    if (currentId === id) {
      localStorage.removeItem(CURRENT_CONVERSATION_KEY)
    }
  } catch (e) {
    console.error("[v0] Failed to delete conversation:", e)
  }
}

export function setCurrentConversation(id: string): void {
  try {
    localStorage.setItem(CURRENT_CONVERSATION_KEY, id)
  } catch (e) {
    console.error("[v0] Failed to set current conversation:", e)
  }
}

export function getCurrentConversation(): string | null {
  try {
    return localStorage.getItem(CURRENT_CONVERSATION_KEY)
  } catch (e) {
    console.error("[v0] Failed to get current conversation:", e)
    return null
  }
}

// Helper function
// Removed duplicate getAlleConversations function
