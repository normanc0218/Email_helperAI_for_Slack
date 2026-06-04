interface Group {
  group_id: string
  name: string
  email_count: number
  senders: string[]
  summary: string
  last_activity: string
}

interface Props {
  groups: Group[]
  loading: boolean
}

export function EmailGroupCard({ groups, loading }: Props) {
  if (loading) {
    return (
      <div className="space-y-2 p-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-16 rounded-lg bg-gray-100 animate-pulse" />
        ))}
      </div>
    )
  }

  if (groups.length === 0) {
    return (
      <p className="text-gray-400 text-sm text-center py-4">
        No email groups yet — run "organize my inbox" to start.
      </p>
    )
  }

  return (
    <div className="space-y-2 p-3">
      {groups.map((g) => (
        <div
          key={g.group_id}
          className="rounded-lg border border-gray-200 bg-white p-3 hover:border-blue-300 transition-colors">
          <div className="flex items-center justify-between mb-1">
            <span className="font-medium text-gray-800 text-sm">{g.name}</span>
            <span className="text-xs text-gray-400 bg-gray-100 rounded-full px-2 py-0.5">
              {g.email_count} emails
            </span>
          </div>
          {g.summary && (
            <p className="text-xs text-gray-500 line-clamp-2">{g.summary}</p>
          )}
          {g.senders?.length > 0 && (
            <p className="text-xs text-gray-400 mt-1">
              From: {g.senders.slice(0, 3).join(", ")}
              {g.senders.length > 3 ? ` +${g.senders.length - 3}` : ""}
            </p>
          )}
        </div>
      ))}
    </div>
  )
}
