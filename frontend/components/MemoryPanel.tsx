import { useState } from "react"
import { apiFetch } from "~api/client"

interface Memory {
  id: number
  type: "preference" | "summary" | "entity" | "conversation"
  key: string
  value: string
  updated_at: string
}

const TYPE_COLORS: Record<string, string> = {
  preference:   "bg-blue-100 text-blue-700",
  summary:      "bg-green-100 text-green-700",
  entity:       "bg-purple-100 text-purple-700",
  conversation: "bg-amber-100 text-amber-700",
}

interface Props {
  memories: Memory[]
  loading: boolean
  onDelete: (id: number) => void
}

export function MemoryPanel({ memories, loading, onDelete }: Props) {
  const [deleting, setDeleting] = useState<number | null>(null)

  const handleDelete = async (id: number) => {
    setDeleting(id)
    try {
      await apiFetch(`/api/memories/${id}`, { method: "DELETE" })
      onDelete(id)
    } finally {
      setDeleting(null)
    }
  }

  if (loading) {
    return (
      <div className="space-y-2 p-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-14 rounded-lg bg-gray-100 animate-pulse" />
        ))}
      </div>
    )
  }

  if (memories.length === 0) {
    return (
      <p className="text-gray-400 text-sm text-center py-8 px-4">
        No memories yet. Chat with the agent and it will start learning your preferences.
      </p>
    )
  }

  const grouped = memories.reduce<Record<string, Memory[]>>((acc, m) => {
    acc[m.type] = acc[m.type] || []
    acc[m.type].push(m)
    return acc
  }, {})

  const ORDER = ["preference", "summary", "entity", "conversation"]

  return (
    <div className="p-3 space-y-4 overflow-y-auto h-full">
      {ORDER.filter((t) => grouped[t]?.length).map((type) => (
        <div key={type}>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-1.5">
            {type}s
          </h3>
          <div className="space-y-1.5">
            {grouped[type].map((m) => (
              <div
                key={m.id}
                className="rounded-lg border border-gray-200 bg-white p-2.5 flex items-start gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <span className={`text-xs font-medium rounded px-1.5 py-0.5 ${TYPE_COLORS[m.type]}`}>
                      {m.type}
                    </span>
                    <span className="text-xs text-gray-500 truncate">{m.key}</span>
                  </div>
                  <p className="text-sm text-gray-700">{m.value}</p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {new Date(m.updated_at).toLocaleDateString()}
                  </p>
                </div>
                <button
                  onClick={() => handleDelete(m.id)}
                  disabled={deleting === m.id}
                  className="text-gray-300 hover:text-red-400 transition-colors shrink-0 text-sm mt-0.5">
                  {deleting === m.id ? "…" : "✕"}
                </button>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
