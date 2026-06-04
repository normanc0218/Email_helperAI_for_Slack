import { apiFetch } from "~api/client"

export interface PendingAction {
  id: number
  action_type: string   // "archive" | "label"
  email_subject: string
  email_from: string
  label?: string
  created_at: string
}

interface Props {
  actions: PendingAction[]
  onUpdate: () => void
}

export function ActionConfirmCard({ actions, onUpdate }: Props) {
  if (actions.length === 0) return null

  const approve = async (id: number) => {
    await apiFetch(`/api/actions/${id}/approve`, { method: "POST" })
    onUpdate()
  }

  const reject = async (id: number) => {
    await apiFetch(`/api/actions/${id}/reject`, { method: "POST" })
    onUpdate()
  }

  return (
    <div className="border-t border-amber-200 bg-amber-50">
      <div className="px-3 py-2 flex items-center gap-2">
        <span className="text-amber-600 text-xs font-semibold uppercase tracking-wide">
          Pending Actions ({actions.length})
        </span>
      </div>
      <div className="space-y-1 px-3 pb-3">
        {actions.map((a) => (
          <div
            key={a.id}
            className="bg-white rounded-lg border border-amber-200 p-3">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <span className="inline-block text-xs font-medium uppercase tracking-wide text-amber-700 bg-amber-100 rounded px-1.5 py-0.5 mb-1">
                  {a.action_type}
                  {a.label ? ` → ${a.label}` : ""}
                </span>
                <p className="text-sm text-gray-800 truncate font-medium">
                  {a.email_subject}
                </p>
                <p className="text-xs text-gray-400 truncate">{a.email_from}</p>
              </div>
              <div className="flex gap-1 shrink-0">
                <button
                  onClick={() => approve(a.id)}
                  className="px-2 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700 transition-colors">
                  ✓
                </button>
                <button
                  onClick={() => reject(a.id)}
                  className="px-2 py-1 text-xs bg-gray-200 text-gray-600 rounded hover:bg-gray-300 transition-colors">
                  ✕
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
