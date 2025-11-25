"use client"

import { AlertCircle, RefreshCw } from "lucide-react"

interface SearchErrorProps {
  error: string
  onRetry: () => void
}

export function SearchError({ error, onRetry }: SearchErrorProps) {
  return (
    <div className="border border-destructive/50 bg-destructive/5 rounded-lg p-6">
      <div className="flex items-start gap-4">
        <AlertCircle className="w-5 h-5 text-destructive flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <h3 className="font-semibold text-destructive mb-1">Search Error</h3>
          <p className="text-sm text-muted-foreground mb-4">{error}</p>
          <button
            onClick={onRetry}
            className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium bg-destructive/10 text-destructive rounded hover:bg-destructive/20 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Try Again
          </button>
        </div>
      </div>
    </div>
  )
}
