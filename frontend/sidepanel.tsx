import { useCallback, useEffect, useState } from "react"
import "./style.css"

import { apiFetch } from "~api/client"
import { ActionConfirmCard, type PendingAction } from "~components/ActionConfirmCard"
import { ChatStream, type Message } from "~components/ChatStream"
import { EmailGroupCard } from "~components/EmailGroupCard"
import { LoginButton } from "~components/LoginButton"
import { MemoryPanel } from "~components/MemoryPanel"

type Tab = "chat" | "groups" | "memory"

interface User {
  email: string
  name?: string
}

interface Group {
  group_id: string
  name: string
  email_count: number
  senders: string[]
  summary: string
  last_activity: string
}

interface Memory {
  id: number
  type: "preference" | "summary" | "entity" | "conversation"
  key: string
  value: string
  updated_at: string
}

export default function SidePanel() {
  const [user, setUser] = useState<User | null>(null)
  const [authChecked, setAuthChecked] = useState(false)
  const [tab, setTab] = useState<Tab>("chat")

  // Lifted state — persists across tab switches
  const [messages, setMessages] = useState<Message[]>([])
  const [groups, setGroups] = useState<Group[]>([])
  const [groupsLoading, setGroupsLoading] = useState(false)
  const [memories, setMemories] = useState<Memory[]>([])
  const [memoriesLoading, setMemoriesLoading] = useState(false)
  const [pendingActions, setPendingActions] = useState<PendingAction[]>([])

  const checkAuth = useCallback(() => {
    apiFetch<{ user: User } | { user: null }>("/api/me")
      .then((data) => setUser("user" in data ? data.user : null))
      .catch(() => setUser(null))
      .finally(() => setAuthChecked(true))
  }, [])

  // Initial auth check
  useEffect(() => { checkAuth() }, [checkAuth])

  // Re-check when background.ts stores the token after OAuth
  useEffect(() => {
    const listener = (changes: Record<string, chrome.storage.StorageChange>) => {
      if (changes.access_token?.newValue) checkAuth()
    }
    chrome.storage.onChanged.addListener(listener)
    return () => chrome.storage.onChanged.removeListener(listener)
  }, [checkAuth])

  const fetchGroups = useCallback(async () => {
    setGroupsLoading(true)
    try {
      const data = await apiFetch<Group[]>("/groups/detail")
      setGroups(data)
    } catch { /* ignore */ } finally {
      setGroupsLoading(false)
    }
  }, [])

  const fetchPending = useCallback(async () => {
    try {
      const data = await apiFetch<PendingAction[]>("/api/actions/pending")
      setPendingActions(data)
    } catch {
      setPendingActions([])
    }
  }, [])

  const fetchMemories = useCallback(async () => {
    setMemoriesLoading(true)
    try {
      const data = await apiFetch<Memory[]>("/api/memories")
      setMemories(data)
    } catch { /* ignore */ } finally {
      setMemoriesLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!user) return
    fetchGroups()
    fetchPending()
    fetchMemories()
    const id = setInterval(fetchPending, 10_000)
    return () => clearInterval(id)
  }, [user, fetchGroups, fetchPending, fetchMemories])

  // Refresh memories when switching to the memory tab
  useEffect(() => {
    if (tab === "memory" && user) fetchMemories()
  }, [tab, user, fetchMemories])

  if (!authChecked) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (!user) return <LoginButton />

  return (
    <div className="flex flex-col h-screen bg-white text-gray-900">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 shrink-0">
        <div>
          <h1 className="font-semibold text-gray-800 text-sm">Email Agent</h1>
          <p className="text-xs text-gray-400">{user.email}</p>
        </div>
        <div className="flex gap-1">
          <TabButton active={tab === "chat"} onClick={() => setTab("chat")}>
            Chat
          </TabButton>
          <TabButton active={tab === "groups"} onClick={() => setTab("groups")}>
            Groups{groups.length > 0 ? ` (${groups.length})` : ""}
          </TabButton>
          <TabButton active={tab === "memory"} onClick={() => setTab("memory")}>
            Memory{memories.length > 0 ? ` (${memories.length})` : ""}
          </TabButton>
        </div>
      </div>

      {/* Pending Actions banner */}
      <ActionConfirmCard
        actions={pendingActions}
        onUpdate={() => { fetchPending(); fetchGroups() }}
      />

      {/* Main content — all three panels mounted, only one visible */}
      <div className="flex-1 min-h-0 overflow-hidden">
        <div className={tab === "chat" ? "h-full" : "hidden"}>
          <ChatStream
            messages={messages}
            setMessages={setMessages}
            onOrganizeDone={() => {
              fetchGroups()
              fetchPending()
              fetchMemories()
            }}
          />
        </div>

        <div className={`h-full overflow-y-auto ${tab === "groups" ? "" : "hidden"}`}>
          <EmailGroupCard groups={groups} loading={groupsLoading} />
        </div>

        <div className={`h-full ${tab === "memory" ? "" : "hidden"}`}>
          <MemoryPanel
            memories={memories}
            loading={memoriesLoading}
            onDelete={(id) => setMemories((prev) => prev.filter((m) => m.id !== id))}
          />
        </div>
      </div>
    </div>
  )
}

function TabButton({
  active,
  onClick,
  children
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
        active
          ? "bg-blue-600 text-white"
          : "text-gray-500 hover:text-gray-700 hover:bg-gray-100"
      }`}>
      {children}
    </button>
  )
}
