/**
 * Search Logger - Utility for logging search activities
 * Logs queries, results, and errors to console and localStorage
 */

export interface SearchLog {
  id: string
  query: string
  timestamp: string
  duration: number
  resultCount: number
  status: "success" | "error"
  error?: string
}

const STORAGE_KEY = "search_logs"

export function logSearch(
  query: string,
  duration: number,
  resultCount: number,
  status: "success" | "error",
  error?: string,
): SearchLog {
  const log: SearchLog = {
    id: Math.random().toString(36).substring(2, 11),
    query,
    timestamp: new Date().toISOString(),
    duration,
    resultCount,
    status,
    error,
  }

  // Log to console
  console.log("[v0] Search Log:", {
    query: log.query,
    duration: `${log.duration}ms`,
    results: log.resultCount,
    status: log.status,
    error: log.error || "none",
    time: log.timestamp,
  })

  // Save to localStorage
  try {
    const existingLogs = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]") as SearchLog[]
    existingLogs.push(log)
    // Keep only last 50 searches
    const recentLogs = existingLogs.slice(-50)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(recentLogs))
  } catch (e) {
    console.error("[v0] Failed to save search log:", e)
  }

  return log
}

export function getSearchLogs(): SearchLog[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]") as SearchLog[]
  } catch (e) {
    console.error("[v0] Failed to retrieve search logs:", e)
    return []
  }
}

export function clearSearchLogs(): void {
  try {
    localStorage.removeItem(STORAGE_KEY)
    console.log("[v0] Search logs cleared")
  } catch (e) {
    console.error("[v0] Failed to clear search logs:", e)
  }
}
