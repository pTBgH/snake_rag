"use client"

interface SearchResult {
  id: string
  title: string
  description: string
  url?: string
  category?: string
  date?: string
}

interface SearchResultsProps {
  results: SearchResult[]
  query: string
}

export function SearchResults({ results, query }: SearchResultsProps) {
  if (results.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground text-lg">
          No results found for "<span className="font-semibold text-foreground">{query}</span>"
        </p>
        <p className="text-muted-foreground text-sm mt-2">Try adjusting your search terms or filters</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="text-sm text-muted-foreground">
        Found <span className="font-semibold text-foreground">{results.length}</span> results
      </div>
      <div className="space-y-3">
        {results.map((result) => (
          <div
            key={result.id}
            className="p-4 border border-border rounded-lg hover:bg-muted/50 transition-colors group cursor-pointer"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                {result.category && (
                  <span className="inline-block px-2 py-1 text-xs font-medium bg-primary/10 text-primary rounded mb-2">
                    {result.category}
                  </span>
                )}
                <h3 className="text-base font-semibold text-foreground group-hover:text-primary transition-colors truncate">
                  {result.title}
                </h3>
                <p className="text-sm text-muted-foreground mt-1 line-clamp-2">{result.description}</p>
                {result.url && <p className="text-xs text-muted-foreground mt-2 truncate">{result.url}</p>}
              </div>
              {result.date && <span className="text-xs text-muted-foreground whitespace-nowrap">{result.date}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
